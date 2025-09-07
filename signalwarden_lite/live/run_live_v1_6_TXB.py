# signalwarden_lite/live/run_live_v1_6_TXB.py
"""
SignalWarden Lite v1.6-TXB Live Trading
- Adaptive Shorts with BTC market filter
- MTF strategy (1h + 15m)  
- Production-ready architecture
- Real maker/taker fees
"""

import os
import time
import yaml
import argparse
import threading
from datetime import datetime, timedelta
from dotenv import load_dotenv
import ccxt
import pandas as pd
import numpy as np
from typing import Optional, Dict, Any

from ..core.features import add_indicators
from ..core.regimes import add_regime, RegimeThresholds
from ..core.market import compute_market_bias
from ..core.signals import generate_signals, SignalParams
from ..core.trailing import TrailingConfig
from ..core.storage import JSONStore
from ..core.types import Side
from ..utils.logger import get_logger

logger = get_logger(__name__)

class SignalWardenLive:
    """Production-ready live trading system v1.6-TXB"""
    
    def __init__(self, config_path: str, paper_mode: bool = False):
        self.config_path = config_path
        self.paper_mode = paper_mode
        self.load_config()
        self.setup_exchange()
        self.setup_components()
        
        # State tracking
        self.last_1h_fetch = {}  # symbol -> timestamp
        self.last_15m_fetch = {}  # symbol -> timestamp  
        self.btc_gate_cache = None
        self.btc_gate_timestamp = 0
        
        logger.info(f"🚀 SignalWarden v1.6-TXB initialized ({'Paper' if paper_mode else 'LIVE'} mode)")
        
    def load_config(self):
        """Load and validate configuration"""
        with open(self.config_path, 'r') as f:
            self.cfg = yaml.safe_load(f)
            
        # Validate v1.6-TXB config structure
        required_sections = ['signals', 'short_guard', 'market_filter', 'timeframes']
        for section in required_sections:
            if section not in self.cfg:
                raise ValueError(f"Missing required config section: {section}")
                
        logger.info(f"✅ Config loaded: {self.cfg['profile']}")
        logger.info(f"📊 Symbols: {self.cfg['symbols']}")
        logger.info(f"⏰ Timeframes: {self.cfg['timeframes']}")
        
    def setup_exchange(self):
        """Setup CCXT exchange connection"""
        if self.paper_mode:
            self.exchange = None
            logger.info("📝 Paper trading mode - no exchange connection")
            return
            
        load_dotenv()
        
        api_key = os.getenv('BINANCE_API_KEY')
        secret = os.getenv('BINANCE_SECRET')
        
        if not api_key or not secret:
            raise ValueError("❌ Missing BINANCE_API_KEY or BINANCE_SECRET in .env file")
        
        self.exchange = ccxt.binanceusdm({
            'apiKey': api_key,
            'secret': secret,
            'enableRateLimit': self.cfg['exchange'].get('rate_limit', True),
            'timeout': 30000,
            'options': {'defaultType': 'future'}
        })
        
        # Set sandbox/live mode
        testnet_mode = self.cfg['exchange'].get('testnet', True)
        if testnet_mode:
            self.exchange.set_sandbox_mode(True)
            logger.info("🧪 TESTNET mode enabled")
        else:
            logger.warning("🔴 LIVE TRADING mode enabled!")
            
        try:
            self.exchange.load_markets()
            balance = self.exchange.fetch_balance()
            logger.info(f"💰 Connected to Binance USDM. USDT balance: {balance.get('USDT', {}).get('total', 0):.2f}")
        except Exception as e:
            logger.error(f"❌ Exchange connection failed: {e}")
            raise
            
    def setup_components(self):
        """Setup trading components"""
        # Signal parameters for v1.6-TXB
        s, st = self.cfg['signals'], self.cfg['signals']['setups']
        self.signal_params = SignalParams(
            lookback_calm=s['dynamic_lookback']['calm'],
            lookback_normal=s['dynamic_lookback']['normal'], 
            lookback_high=s['dynamic_lookback']['high'],
            ltf_thinbar_k=s['ltf_thinbar_k'],
            long_cushion_calm=s['atr_cushion_long']['calm'],
            long_cushion_normal=s['atr_cushion_long']['normal'],
            long_cushion_high=s['atr_cushion_long']['high'],
            short_cushion_calm=s['atr_cushion_short']['calm'],
            short_cushion_normal=s['atr_cushion_short']['normal'],
            short_cushion_high=s['atr_cushion_short']['high'],
            setup_breakout=st['breakout']['enabled'],
            setup_inside=st['inside_bar']['enabled'],
            setup_trend_cont=st['trend_continuation']['enabled'],
            setup_squeeze=st['squeeze_breakout']['enabled'],
            ib_min_prev_range_k_atr=st['inside_bar']['min_prev_range_k_atr'],
            tc_min_body_k_range=st['trend_continuation']['min_body_k_range'],
            tc_confirm_close_k_body=st['trend_continuation']['confirm_close_k_body'],
            bb_period=st['squeeze_breakout']['bb_period'],
            bb_k=st['squeeze_breakout']['bb_k'],
            width_k_perc=st['squeeze_breakout']['width_k_perc'],
            sg_rsi_bear_max=self.cfg['short_guard']['rsi_bear_max'],
            sg_rsi_bullcorr_max=self.cfg['short_guard']['rsi_bullcorr_max'],
            sg_min_natr_bear=self.cfg['short_guard']['min_natr_bear'],
            sg_min_natr_bullcorr=self.cfg['short_guard']['min_natr_bullcorr'],
            sg_require_close_below_ema20_bullcorr=self.cfg['short_guard']['require_close_below_ema20_bullcorr'],
            sg_slope_lookback=self.cfg['short_guard']['slope_lookback'],
            lg_rsi_long_min=52.0
        )
        
        # Regime thresholds
        self.regime_thresholds = RegimeThresholds(**self.cfg['regime']['calm_thresholds'])
        
        # Trailing config
        self.trailing = TrailingConfig(**self.cfg['trailing'])
        
        # Storage
        self.storage = JSONStore('trading_state_v1_6_TXB.json')
        
        # Risk parameters - FIXED: margin_usdt is NOTIONAL size, not actual margin
        self.margin_usdt = self.cfg['risk']['margin_usdt']  # 21 USDT notional per trade
        self.leverage = self.cfg['risk']['leverage']  # 5x leverage
        self.sl_atr_mult = self.cfg['risk']['sl_atr_mult']  # 1.5x ATR for SL
        
        # Active positions tracking (1 position per symbol max)
        self.active_positions = {}  # symbol -> position_info
        
        # Sync positions from exchange on startup
        self.sync_positions_from_exchange()
        
        # Trailing thread control
        self.trailing_thread = None
        self.trailing_stop_event = threading.Event()
        
        logger.info(f"⚙️ Risk per trade: {self.margin_usdt} USDT notional ({self.margin_usdt/self.leverage:.1f} USDT actual margin)")
        
    def sync_positions_from_exchange(self):
        """Sync positions from Binance exchange"""
        if self.paper_mode:
            return
            
        try:
            positions = self.exchange.fetch_positions()
            logger.info(f"📊 Syncing positions from exchange...")
            
            synced_count = 0
            for pos in positions:
                if float(pos['contracts']) == 0:  # No position
                    continue
                    
                symbol_ccxt = pos['symbol']  # ADA/USDT:USDT format
                if ':USDT' not in symbol_ccxt:
                    continue
                    
                # Convert to our format: ADA/USDT:USDT -> ADA_USDT
                base_quote = symbol_ccxt.split(':')[0]  # ADA/USDT
                symbol = base_quote.replace('/', '_')   # ADA_USDT
                
                if symbol not in self.cfg['symbols']:
                    continue
                    
                # Calculate stop loss levels for synced position
                try:
                    # Get recent data to calculate ATR
                    ccxt_sym = self.ccxt_symbol(symbol)
                    df = self.fetch_recent_data(ccxt_sym, '1h', 100)
                    
                    if df is not None and len(df) > 0:
                        # Calculate ATR
                        df['hl'] = df['high'] - df['low']
                        df['hc'] = abs(df['high'] - df['close'].shift())
                        df['lc'] = abs(df['low'] - df['close'].shift())
                        df['tr'] = df[['hl', 'hc', 'lc']].max(axis=1)
                        atr = df['tr'].rolling(window=14).mean().iloc[-1]
                        
                        # Calculate stop loss
                        entry_price = float(pos['entryPrice'])
                        side = 'LONG' if pos['side'] == 'long' else 'SHORT'
                        
                        if side == 'LONG':
                            sl_price = entry_price - (self.sl_atr_mult * atr)
                        else:
                            sl_price = entry_price + (self.sl_atr_mult * atr)
                    else:
                        # Fallback: use 2% stop loss if no data
                        entry_price = float(pos['entryPrice'])
                        side = 'LONG' if pos['side'] == 'long' else 'SHORT'
                        
                        if side == 'LONG':
                            sl_price = entry_price * 0.98
                        else:
                            sl_price = entry_price * 1.02
                        atr = entry_price * 0.02  # 2% fallback
                        
                except Exception as e:
                    logger.warning(f"⚠️ Could not calculate SL for {symbol}: {e}, using 2% fallback")
                    entry_price = float(pos['entryPrice'])
                    side = 'LONG' if pos['side'] == 'long' else 'SHORT'
                    
                    if side == 'LONG':
                        sl_price = entry_price * 0.98
                    else:
                        sl_price = entry_price * 1.02
                    atr = entry_price * 0.02
                
                # Create position info from exchange data
                position_info = {
                    'symbol': symbol,
                    'side': 'LONG' if pos['side'] == 'long' else 'SHORT',
                    'entry': float(pos['entryPrice']),
                    'qty': abs(float(pos['contracts'])),
                    'sl_initial': sl_price,
                    'sl_current': sl_price,
                    'atr': atr,
                    'timestamp': time.time(),
                    'order_id': None,
                    'trailing_active': False,
                    'unrealized_pnl': float(pos['unrealizedPnl']),
                    'peak_pnl_usdt': 0.0,  # Track maximum PnL for trailing
                    'synced_from_exchange': True
                }
                
                self.active_positions[symbol] = position_info
                synced_count += 1
                
                # Place stop loss order for synced position
                try:
                    self.update_sliding_stop_loss(symbol, position_info)
                    logger.info(f"📍 Synced {symbol}: {position_info['side']} @ {position_info['entry']:.6f}, "
                              f"Qty: {position_info['qty']:.6f}, SL: {sl_price:.6f}, PnL: {position_info['unrealized_pnl']:.2f} USDT")
                except Exception as sl_error:
                    logger.warning(f"⚠️ Could not place SL order for synced position {symbol}: {sl_error}")
                    logger.info(f"📍 Synced {symbol}: {position_info['side']} @ {position_info['entry']:.6f}, "
                              f"Qty: {position_info['qty']:.6f}, SL: {sl_price:.6f} (NO SL ORDER), PnL: {position_info['unrealized_pnl']:.2f} USDT")
                          
            logger.info(f"✅ Synced {synced_count} positions from exchange")
            
        except Exception as e:
            logger.error(f"❌ Failed to sync positions from exchange: {e}")
    
    def has_open_position(self, symbol: str) -> bool:
        """Check if symbol has an open position"""
        return symbol in self.active_positions
    
    def can_open_new_position(self) -> bool:
        """Check if we have enough balance for a new position"""
        if self.paper_mode:
            return len(self.active_positions) < len(self.cfg['symbols'])
            
        try:
            # Get current balance
            balance = self.exchange.fetch_balance()
            free_usdt = balance.get('USDT', {}).get('free', 0)
            
            # With 5x leverage, margin_usdt is NOTIONAL, actual margin = notional/leverage
            # Small buffer for fees (~0.1% entry + 0.1% exit = 0.2% total)  
            actual_margin_per_position = self.margin_usdt / self.leverage  # Real margin needed
            required_margin = actual_margin_per_position * 1.05  # 5% buffer for fees
            
            if free_usdt < required_margin:
                logger.debug(f"Insufficient balance: {free_usdt:.2f} USDT free, need {required_margin:.2f} USDT")
                return False
                
            # Also check we don't exceed max positions per symbol limit
            current_positions = len(self.active_positions)  # Use tracked positions
            max_total_positions = len(self.cfg['symbols'])  # 1 position per symbol
            
            if current_positions >= max_total_positions:
                logger.debug(f"Max positions reached: {current_positions}/{max_total_positions}")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Error checking balance for new position: {e}")
            return False  # Conservative: don't open on error
        
    def get_position_pnl_from_exchange(self, symbol: str) -> float:
        """Get real-time PnL from exchange"""
        if self.paper_mode:
            return 0.0
            
        try:
            ccxt_sym = self.ccxt_symbol(symbol)
            positions = self.exchange.fetch_positions([ccxt_sym])
            
            for pos in positions:
                if float(pos['contracts']) != 0:
                    return float(pos['unrealizedPnl'])
                    
            return 0.0
            
        except Exception as e:
            logger.error(f"❌ Failed to get PnL for {symbol}: {e}")
            return 0.0
        
    def start_trailing_thread(self):
        """Start fast trailing updates in separate thread"""
        if self.trailing_thread and self.trailing_thread.is_alive():
            return
            
        self.trailing_stop_event.clear()
        self.trailing_thread = threading.Thread(target=self._fast_trailing_loop, daemon=True)
        self.trailing_thread.start()
        logger.info("🔄 Fast trailing thread started (3-second updates)")
        
    def stop_trailing_thread(self):
        """Stop trailing thread"""
        if self.trailing_thread and self.trailing_thread.is_alive():
            self.trailing_stop_event.set()
            self.trailing_thread.join(timeout=5)
            logger.info("⏹️ Fast trailing thread stopped")
            
    def _fast_trailing_loop(self):
        """Fast trailing updates every 3 seconds"""
        while not self.trailing_stop_event.is_set():
            try:
                self.update_trailing_stops()
                self.trailing_stop_event.wait(3)  # 3-second updates
            except Exception as e:
                logger.error(f"❌ Fast trailing error: {e}")
                self.trailing_stop_event.wait(3)
    
    def update_trailing_stops(self):
        """Update trailing stops for all open positions with real PnL from Binance"""
        if not self.active_positions:
            return
            
        for symbol, pos in list(self.active_positions.items()):
            try:
                # Get current price and PnL from exchange
                df = self.fetch_ohlcv(symbol, '1m', 5)
                if df.empty:
                    continue
                    
                current_price = float(df.iloc[-1]['close'])
                real_pnl = self.get_position_pnl_from_exchange(symbol)
                
                # Update position with real PnL
                pos['unrealized_pnl'] = real_pnl
                
                # Calculate ATR if missing (for synced positions)
                if pos['atr'] is None:
                    df_atr = self.fetch_ohlcv(symbol, '1h', 50)
                    if not df_atr.empty:
                        df_atr = add_indicators(df_atr, atr_p=14)
                        pos['atr'] = float(df_atr.iloc[-1]['atr'])
                        pos['sl_initial'] = pos['entry'] - (self.sl_atr_mult * pos['atr']) if pos['side'] == 'LONG' else pos['entry'] + (self.sl_atr_mult * pos['atr'])
                        pos['sl_current'] = pos['sl_initial']
                
                if pos['atr'] is None:  # Still None, skip
                    continue
                
                # Update trailing logic using new PnL-based system
                from ..core.trailing import update_trailing_pnl_based
                from ..core.types import Position, Side
                
                # Convert to Position object
                position = Position(
                    side=Side.LONG if pos['side'] == 'LONG' else Side.SHORT,
                    entry=pos['entry'],
                    sl=pos['sl_current'] if pos['sl_current'] else pos['sl_initial'],
                    sl_initial=pos['sl_initial'],
                    qty=pos['qty'],
                    remaining_qty=pos['qty'],
                    r_per_unit=pos['atr'] * self.sl_atr_mult
                )
                
                # Add peak_pnl_usdt tracking to Position object
                position.peak_pnl_usdt = pos.get('peak_pnl_usdt', 0.0)
                
                # Use new PnL-based trailing system
                updated_pos = update_trailing_pnl_based(
                    position, 
                    current_price,
                    real_pnl,  # Current PnL in USDT from Binance
                    self.trailing
                )
                
                # Check if SL hit
                sl_hit = False
                if pos['side'] == 'LONG' and current_price <= updated_pos.sl:
                    sl_hit = True
                elif pos['side'] == 'SHORT' and current_price >= updated_pos.sl:
                    sl_hit = True
                    
                if sl_hit:
                    self.close_position(symbol, current_price, "Trailing SL Hit")
                else:
                    # CRITICAL: Only improve SL, never degrade it
                    should_update = False
                    if pos['side'] == 'LONG' and updated_pos.sl > pos['sl_current']:
                        should_update = True  # SL moves up for longs
                    elif pos['side'] == 'SHORT' and updated_pos.sl < pos['sl_current']:
                        should_update = True  # SL moves down for shorts
                        
                    if should_update:
                        old_sl = pos['sl_current']
                        pos['sl_current'] = updated_pos.sl
                        pos['trailing_active'] = True
                        
                        # Save updated peak PnL
                        pos['peak_pnl_usdt'] = updated_pos.peak_pnl_usdt
                        
                        # Update sliding market stop loss on exchange
                        self.update_sliding_stop_loss(symbol, pos)
                        
                        # Log trailing update with detailed debug info
                        direction = "🟢" if pos['side'] == 'LONG' else "🔴"
                        
                        # Get debug info from trailing function
                        debug_info = getattr(updated_pos, 'trailing_debug', {})
                        level_info = f" ({debug_info.get('level', 'L?')}: {debug_info.get('keep_pct', 0)*100:.0f}%)"
                        
                        logger.info(f"{direction} {symbol}: Trailing SL {old_sl:.6f} → {updated_pos.sl:.6f}, PnL: {real_pnl:.2f} USDT{level_info}")
                        
                        # Additional debug logging
                        if debug_info:
                            logger.debug(f"📊 {symbol} Trailing Debug: Peak={debug_info.get('peak_pnl', 0):.2f}, Target={debug_info.get('target_profit', 0):.2f}, Updated={debug_info.get('sl_updated', False)}")
                        
            except Exception as e:
                logger.error(f"❌ Trailing update failed for {symbol}: {e}")
                
    def close_position(self, symbol: str, exit_price: float, reason: str):
        """Close position and clean up"""
        if symbol not in self.active_positions:
            return
            
        try:
            pos = self.active_positions[symbol]
            
            # Check if position still exists on exchange first
            ccxt_sym = self.ccxt_symbol(symbol)
            
            if not self.paper_mode:
                try:
                    exchange_positions = self.exchange.fetch_positions([ccxt_sym])
                    position_exists = False
                    
                    for exchange_pos in exchange_positions:
                        if float(exchange_pos['contracts']) != 0:
                            position_exists = True
                            break
                    
                    if not position_exists:
                        logger.info(f"📊 {symbol}: Position already closed on exchange")
                        # Remove from tracking
                        del self.active_positions[symbol]
                        self.storage.update_symbol(symbol, {'active_position': None})
                        return
                except Exception as pos_check_error:
                    logger.warning(f"⚠️ Could not check position status for {symbol}: {pos_check_error}")
            
            # Place market order to close
            close_side = 'sell' if pos['side'] == 'LONG' else 'buy'
            
            close_order = self.exchange.create_market_order(
                ccxt_sym,
                close_side,
                pos['qty'],
                exit_price,
                params={'reduceOnly': True}
            )
            
            # Calculate PnL
            if pos['side'] == 'LONG':
                pnl_usdt = (exit_price - pos['entry']) * pos['qty']
            else:
                pnl_usdt = (pos['entry'] - exit_price) * pos['qty']
                
            logger.info(f"🔚 {symbol}: Position closed @ {exit_price:.6f} ({reason}), PnL: {pnl_usdt:.2f} USDT")
            
            # Remove from tracking
            del self.active_positions[symbol]
            
            # Update storage
            self.storage.update_symbol(symbol, {
                'active_position': None,
                'last_close_time': time.time(),
                'last_pnl': pnl_usdt
            })
            
        except Exception as e:
            logger.error(f"❌ Failed to close position {symbol}: {e}")
    
    def check_active_positions(self):
        """Check all active positions for stop loss triggers and sync with exchange"""
        if not self.active_positions:
            return
            
        logger.debug(f"🔍 Checking {len(self.active_positions)} active positions...")
        
        positions_to_close = []
        
        for symbol, pos in list(self.active_positions.items()):
            try:
                # Get current market price
                ccxt_sym = self.ccxt_symbol(symbol)
                
                if not self.paper_mode:
                    # Verify position still exists on exchange
                    try:
                        exchange_positions = self.exchange.fetch_positions([ccxt_sym])
                        position_exists = False
                        
                        for exchange_pos in exchange_positions:
                            if float(exchange_pos['contracts']) != 0:
                                position_exists = True
                                break
                        
                        if not position_exists:
                            logger.info(f"📊 {symbol}: Position no longer exists on exchange, removing from tracking")
                            positions_to_close.append(symbol)
                            continue
                            
                    except Exception as e:
                        logger.warning(f"⚠️ Could not verify {symbol} position on exchange: {e}")
                        continue
                
                # Get current price
                ticker = self.exchange.fetch_ticker(ccxt_sym)
                current_price = ticker['last']
                
                # Check stop loss trigger
                sl_price = pos.get('sl_current') or pos.get('sl_initial')
                if not sl_price:
                    logger.warning(f"⚠️ {symbol}: No stop loss price set!")
                    continue
                
                should_close = False
                
                if pos['side'] == 'LONG':
                    # For longs: close if current price <= stop loss
                    if current_price <= sl_price:
                        should_close = True
                        logger.warning(f"🚨 {symbol} LONG SL HIT: Price ${current_price:.6f} <= SL ${sl_price:.6f}")
                else:
                    # For shorts: close if current price >= stop loss
                    if current_price >= sl_price:
                        should_close = True
                        logger.warning(f"🚨 {symbol} SHORT SL HIT: Price ${current_price:.6f} >= SL ${sl_price:.6f}")
                
                if should_close:
                    logger.error(f"💥 {symbol}: STOP LOSS TRIGGERED! Closing position immediately...")
                    self.close_position(symbol, current_price, "STOP_LOSS_HIT")
                    positions_to_close.append(symbol)
                else:
                    # Log position status
                    pnl = pos.get('unrealized_pnl', 0)
                    direction = "🟢" if pos['side'] == 'LONG' else "🔴"
                    logger.debug(f"{direction} {symbol}: Price ${current_price:.6f}, SL ${sl_price:.6f}, PnL: {pnl:.2f} USDT")
                    
            except Exception as e:
                logger.error(f"❌ Failed to check position {symbol}: {e}")
        
        # Clean up closed positions
        for symbol in positions_to_close:
            if symbol in self.active_positions:
                del self.active_positions[symbol]
                self.storage.update_symbol(symbol, {'active_position': None})
    
    def update_sliding_stop_loss(self, symbol: str, pos: Dict[str, Any]):
        """Update sliding market stop loss order on exchange"""
        if self.paper_mode:
            return
            
        try:
            ccxt_sym = self.ccxt_symbol(symbol)
            
            # First, check if position still exists
            try:
                exchange_positions = self.exchange.fetch_positions([ccxt_sym])
                position_exists = False
                
                for exchange_pos in exchange_positions:
                    if float(exchange_pos['contracts']) != 0:
                        position_exists = True
                        break
                
                if not position_exists:
                    logger.debug(f"📊 {symbol}: No position on exchange, skipping SL update")
                    return
            except Exception as pos_check_error:
                logger.warning(f"⚠️ Could not verify position for SL update {symbol}: {pos_check_error}")
                return
            
            # Get existing stop loss orders first
            old_sl_orders = []
            try:
                open_orders = self.exchange.fetch_open_orders(ccxt_sym)
                for order in open_orders:
                    if order['type'] == 'stop_market' and order['info'].get('reduceOnly'):
                        old_sl_orders.append(order)
                        logger.debug(f"📊 {symbol}: Found existing SL order {order['id']} @ {order['stopPrice']}")
            except Exception as orders_error:
                logger.warning(f"⚠️ Could not fetch open orders for {symbol}: {orders_error}")
            
            # Small delay to avoid rate limits
            import time
            time.sleep(0.1)
            
            # First, try to create NEW stop loss order
            sl_side = 'sell' if pos['side'] == 'LONG' else 'buy'
            new_sl_created = False
            new_sl_order = None
            
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    new_sl_order = self.exchange.create_order(
                        ccxt_sym,
                        'stop_market',
                        sl_side,
                        pos['qty'],
                        None,
                        params={
                            'stopPrice': pos['sl_current'],
                            'reduceOnly': True,
                            'timeInForce': 'GTC'
                        }
                    )
                    new_sl_created = True
                    logger.info(f"✅ {symbol}: New SL order created @ {pos['sl_current']:.6f} (ID: {new_sl_order['id']})")
                    break
                except Exception as e:
                    logger.warning(f"⚠️ {symbol}: SL creation attempt {attempt+1} failed: {e}")
                    if attempt < max_retries - 1:
                        time.sleep(1)  # Wait before retry
            
            # Only cancel old orders if new one was created successfully
            if new_sl_created and old_sl_orders:
                time.sleep(0.2)  # Small delay
                for old_order in old_sl_orders:
                    try:
                        self.exchange.cancel_order(old_order['id'], ccxt_sym)
                        logger.debug(f"🚫 {symbol}: Cancelled old SL order {old_order['id']}")
                    except Exception as cancel_error:
                        logger.warning(f"⚠️ {symbol}: Could not cancel old SL order {old_order['id']}: {cancel_error}")
            elif not new_sl_created:
                logger.error(f"❌ {symbol}: CRITICAL - Could not create new SL order! Position may be unprotected!")
                if old_sl_orders:
                    logger.warning(f"🛡️ {symbol}: Keeping {len(old_sl_orders)} existing SL orders as fallback")
                return  # Don't proceed if we couldn't create new SL
            
            # Update position with new SL order ID
            if new_sl_created and new_sl_order:
                pos['sl_order_id'] = new_sl_order['id']
            
        except Exception as e:
            logger.error(f"❌ Failed to update sliding SL for {symbol}: {e}")
        
    def ccxt_symbol(self, symbol: str) -> str:
        """Convert symbol format: ADA_USDT -> ADA/USDT:USDT"""
        base, quote = symbol.split('_')
        return f"{base}/{quote}:{quote}"
        
    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 500) -> pd.DataFrame:
        """Fetch OHLCV data from exchange"""
        if self.paper_mode:
            # In paper mode, return empty DataFrame
            return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
        try:
            ccxt_sym = self.ccxt_symbol(symbol)
            ohlcv = self.exchange.fetch_ohlcv(ccxt_sym, timeframe=timeframe, limit=limit)
            
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = (df['timestamp'] // 1000).astype(int)  # Convert to seconds
            
            return df.sort_values('timestamp').reset_index(drop=True)
            
        except Exception as e:
            logger.error(f"❌ Failed to fetch {symbol} {timeframe}: {e}")
            return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
    def get_btc_market_bias(self) -> Optional[pd.DataFrame]:
        """Get BTC market filter with caching"""
        current_time = int(time.time())
        
        # Cache for 5 minutes
        if (self.btc_gate_cache is not None and 
            current_time - self.btc_gate_timestamp < 300):
            return self.btc_gate_cache
            
        try:
            btc_1h = self.fetch_ohlcv('BTC_USDT', '1h', 200)
            if btc_1h.empty:
                logger.warning("⚠️ No BTC data - market filter disabled")
                return None
                
            btc_bias = compute_market_bias(
                btc_1h, 
                self.cfg['market_filter']['ema_fast'], 
                self.cfg['market_filter']['ema_slow']
            )
            
            self.btc_gate_cache = btc_bias
            self.btc_gate_timestamp = current_time
            
            # Log current market state
            latest = btc_bias.iloc[-1]
            long_ok = latest['mkt_long_ok']
            short_ok = latest['mkt_short_ok']
            
            if long_ok and short_ok:
                market_state = "🟡 NEUTRAL"
            elif long_ok:
                market_state = "🟢 BULL (longs favored)"
            elif short_ok:
                market_state = "🔴 BEAR (shorts favored)"
            else:
                market_state = "⚫ SIDEWAYS"
                
            logger.info(f"📊 BTC Market Filter: {market_state}")
            
            return btc_bias
            
        except Exception as e:
            logger.error(f"❌ BTC market filter failed: {e}")
            return None
            
    def prepare_data(self, df: pd.DataFrame, gate: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """Prepare data with indicators and signals"""
        if df.empty:
            return df
            
        # Add indicators
        df = add_indicators(
            df, 
            ema_fast=50, 
            ema_slow=200, 
            atr_p=self.cfg['regime']['natr_period'],
            rsi_p=self.cfg['short_guard'].get('rsi_period', 14)
        )
        
        # Add regime
        df = add_regime(df, self.regime_thresholds)
        
        # Generate signals
        df = generate_signals(df, self.signal_params, market_gate=gate)
        
        return df
        
    def process_symbol_mtf(self, symbol: str) -> Dict[str, Any]:
        """Process symbol with MTF logic (1h + 15m)"""
        result = {
            'symbol': symbol,
            'signals': [],
            'current_state': {},
            'errors': []
        }
        
        try:
            # Get BTC market filter
            btc_gate = self.get_btc_market_bias()
            
            # Fetch 1h data for breakout signals
            df_1h = self.fetch_ohlcv(symbol, '1h', 200)
            if df_1h.empty:
                result['errors'].append("No 1h data")
                return result
                
            sig_1h = self.prepare_data(df_1h, btc_gate)
            latest_1h = sig_1h.iloc[-1]
            
            # Check 1h breakout signals
            if latest_1h.get('sig_long_breakout', False) and latest_1h.get('allow_long', False):
                result['signals'].append({
                    'timeframe': '1h',
                    'side': 'LONG',
                    'setup': 'breakout',
                    'entry': float(latest_1h['long_entry_final']),
                    'reason': latest_1h.get('long_reason', 'breakout'),
                    'atr': float(latest_1h['atr']),
                    'regime': latest_1h.get('regime', 'unknown'),
                    'confidence': 'HIGH'
                })
                
            if latest_1h.get('sig_short_breakout', False) and latest_1h.get('allow_short', False):
                result['signals'].append({
                    'timeframe': '1h',
                    'side': 'SHORT', 
                    'setup': 'breakout',
                    'entry': float(latest_1h['short_entry_final']),
                    'reason': latest_1h.get('short_reason', 'breakout'),
                    'atr': float(latest_1h['atr']),
                    'regime': latest_1h.get('regime', 'unknown'),
                    'confidence': 'HIGH'
                })
            
            # Fetch 15m data for LTF signals
            df_15m = self.fetch_ohlcv(symbol, '15m', 400)
            if not df_15m.empty:
                # Forward fill BTC gate to 15m
                gate_15m = None
                if btc_gate is not None:
                    gate_15m_data = []
                    for ts in df_15m['timestamp'].values:
                        mask = btc_gate['timestamp'] <= ts
                        if mask.any():
                            idx = mask.idxmax()
                            gate_15m_data.append({
                                'timestamp': ts,
                                'mkt_long_ok': btc_gate.iloc[idx]['mkt_long_ok'],
                                'mkt_short_ok': btc_gate.iloc[idx]['mkt_short_ok']
                            })
                        else:
                            gate_15m_data.append({'timestamp': ts, 'mkt_long_ok': False, 'mkt_short_ok': False})
                    gate_15m = pd.DataFrame(gate_15m_data)
                
                sig_15m = self.prepare_data(df_15m, gate_15m)
                latest_15m = sig_15m.iloc[-1]
                
                # Check 15m LTF signals (inside/trend/squeeze)
                ltf_setups = ['inside', 'tc', 'sq']
                for setup in ltf_setups:
                    # Long signals
                    if (latest_15m.get(f'sig_long_{setup}', False) and 
                        latest_15m.get('allow_long', False)):
                        result['signals'].append({
                            'timeframe': '15m',
                            'side': 'LONG',
                            'setup': setup,
                            'entry': float(latest_15m['long_entry_final']),
                            'reason': latest_15m.get('long_reason', setup),
                            'atr': float(latest_15m['atr']),
                            'regime': latest_15m.get('regime', 'unknown'),
                            'confidence': 'MEDIUM'
                        })
                        break  # Only one signal per side
                    
                    # Short signals  
                    if (latest_15m.get(f'sig_short_{setup}', False) and 
                        latest_15m.get('allow_short', False)):
                        result['signals'].append({
                            'timeframe': '15m',
                            'side': 'SHORT',
                            'setup': setup,
                            'entry': float(latest_15m['short_entry_final']),
                            'reason': latest_15m.get('short_reason', setup),
                            'atr': float(latest_15m['atr']),
                            'regime': latest_15m.get('regime', 'unknown'),
                            'confidence': 'MEDIUM'
                        })
                        break  # Only one signal per side
                        
            # Current state for monitoring
            result['current_state'] = {
                'regime_1h': latest_1h.get('regime', 'unknown'),
                'trend_long_1h': bool(latest_1h.get('trend_long', False)),
                'trend_short_1h': bool(latest_1h.get('trend_short', False)),
                'natr_1h': float(latest_1h.get('natr', 0)),
                'rsi_1h': float(latest_1h.get('rsi', 50)),
                'btc_long_ok': bool(latest_1h.get('mkt_long_ok', True)),
                'btc_short_ok': bool(latest_1h.get('mkt_short_ok', True)),
                'price': float(latest_1h['close'])
            }
            
        except Exception as e:
            logger.error(f"❌ Error processing {symbol}: {e}")
            result['errors'].append(str(e))
            
        return result
        
    def execute_signal(self, signal: Dict[str, Any]) -> str:
        """Execute trading signal"""
        if self.paper_mode:
            return f"PAPER: {signal['side']} {signal['setup']} @ {signal['entry']:.6f}"
            
        try:
            symbol = signal['symbol']
            side = signal['side']
            entry = signal['entry']
            atr = signal['atr']
            
            # Check if position already exists for this symbol
            if self.has_open_position(symbol):
                error_msg = f"❌ Position already open for {symbol} - skipping"
                logger.warning(f"⚠️ {symbol}: {error_msg}")
                return error_msg
            
            # Check if we have enough balance for new position (considering 5x leverage)
            if not self.can_open_new_position():
                error_msg = f"❌ Insufficient balance for new position - need {self.margin_usdt/self.leverage:.1f} USDT margin"
                logger.warning(f"⚠️ {symbol}: {error_msg}")
                return error_msg
            
            # Calculate position size: FIXED margin_usdt positions (21 USDT notional with 5x leverage)
            # This ensures we trade with exactly margin_usdt notional value
            position_value_usdt = self.margin_usdt  # 21 USDT notional exactly
            qty = position_value_usdt / entry
            
            # Calculate stop loss
            if side == 'LONG':
                sl_price = entry - (self.sl_atr_mult * atr)
            else:
                sl_price = entry + (self.sl_atr_mult * atr)
            
            ccxt_sym = self.ccxt_symbol(symbol)
            
            # Place market order
            order_side = 'buy' if side == 'LONG' else 'sell'
            order = self.exchange.create_market_order(
                ccxt_sym, 
                order_side, 
                qty,
                entry,  # price for logging
                params={'reduceOnly': False}
            )
            
            # Create initial stop loss order immediately
            sl_side = 'sell' if side == 'LONG' else 'buy'
            try:
                sl_order = self.exchange.create_order(
                    ccxt_sym,
                    'stop_market',
                    sl_side,
                    qty,
                    None,
                    params={
                        'stopPrice': sl_price,
                        'reduceOnly': True,
                        'timeInForce': 'GTC'
                    }
                )
                sl_order_id = sl_order['id']
                logger.info(f"🛡️ {symbol}: Stop-loss created @ {sl_price:.6f} (Order ID: {sl_order_id})")
            except Exception as e:
                logger.error(f"❌ {symbol}: Failed to create stop-loss: {e}")
                sl_order_id = None
            
            # Track position
            position_info = {
                'symbol': symbol,
                'side': side,
                'entry': entry,
                'qty': qty,
                'sl_initial': sl_price,
                'sl_current': sl_price,
                'atr': atr,
                'timestamp': time.time(),
                'order_id': order['id'],
                'sl_order_id': sl_order_id,
                'trailing_active': False,
                'peak_pnl_usdt': 0.0  # Initialize peak PnL tracking
            }
            
            self.active_positions[symbol] = position_info
            
            # Save state
            self.storage.update_symbol(symbol, {
                'active_position': position_info,
                'last_signal_time': time.time()
            })
            
            result = f"✅ {side} {signal['setup']} @ {entry:.6f}, SL @ {sl_price:.6f}, Qty: {qty:.6f}"
            logger.info(f"🎯 {symbol}: {result}")
            
            return result
            
        except Exception as e:
            error_msg = f"❌ Execution failed: {e}"
            logger.error(f"💥 {symbol}: {error_msg}")
            return error_msg
            
    def run_trading_cycle(self):
        """Run one complete trading cycle"""
        cycle_start = time.time()
        logger.info("=" * 80)
        logger.info(f"🔄 TRADING CYCLE START: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
        
        total_signals = 0
        executed_trades = 0
        
        # CRITICAL: First check and manage active positions
        self.check_active_positions()
        
        # Trailing is now handled by separate thread, no need to update here
        
        for symbol in self.cfg['symbols']:
            try:
                logger.info(f"📊 Processing {symbol}...")
                
                # Process with MTF logic
                result = self.process_symbol_mtf(symbol)
                
                # Log current state
                state = result['current_state']
                if state:
                    logger.info(f"   State: {state['regime_1h']} regime, "
                              f"Price: ${state['price']:.6f}, "
                              f"NATR: {state['natr_1h']:.1f}%, "
                              f"RSI: {state['rsi_1h']:.0f}, "
                              f"BTC: {'🟢L' if state['btc_long_ok'] else '❌L'}"
                              f"{'🔴S' if state['btc_short_ok'] else '❌S'}")
                
                # Process signals
                if result['signals']:
                    for signal in result['signals']:
                        total_signals += 1
                        signal['symbol'] = symbol
                        
                        logger.info(f"🎯 {symbol}: {signal['confidence']} {signal['timeframe']} "
                                  f"{signal['side']} {signal['setup']} @ {signal['entry']:.6f}")
                        
                        # Execute signal
                        exec_result = self.execute_signal(signal)
                        
                        if "✅" in exec_result:
                            executed_trades += 1
                            
                        # Store signal in history
                        self.storage.add_signal(symbol, {
                            'timestamp': int(time.time()),
                            'signal': signal,
                            'result': exec_result
                        })
                        
                else:
                    logger.info(f"   No signals detected")
                    
                # Log errors
                if result['errors']:
                    for error in result['errors']:
                        logger.warning(f"   ⚠️ {error}")
                        
            except Exception as e:
                logger.error(f"💥 Failed to process {symbol}: {e}")
                continue
                
        # Cycle summary
        cycle_time = time.time() - cycle_start
        logger.info(f"📈 CYCLE COMPLETE: {total_signals} signals, {executed_trades} trades executed in {cycle_time:.1f}s")
        logger.info("=" * 80)
        
        return total_signals, executed_trades
        
    def run(self):
        """Main trading loop"""
        logger.info("🚀 Starting SignalWarden v1.6-TXB live trading...")
        logger.info(f"📊 Monitoring {len(self.cfg['symbols'])} symbols")
        logger.info(f"💰 Risk per trade: {self.margin_usdt} USDT notional ({self.margin_usdt/self.leverage:.1f} USDT margin)")
        logger.info(f"⚙️ MTF Strategy: 1h breakout + 15m LTF setups")
        logger.info(f"🛡️ Adaptive shorts with BTC filter enabled")
        logger.info(f"🔄 PnL-based trailing: 0.10 USDT activation, 50%/60%/70%/80% levels")
        
        # Start fast trailing thread
        self.start_trailing_thread()
        
        cycle_count = 0
        
        try:
            while True:
                cycle_count += 1
                
                try:
                    signals, trades = self.run_trading_cycle()
                    
                    # Sleep for 2 minutes between cycles
                    logger.info(f"😴 Cycle {cycle_count} complete. Sleeping 120 seconds...")
                    time.sleep(120)
                    
                except KeyboardInterrupt:
                    logger.info("🛑 Received interrupt signal, shutting down...")
                    self.stop_trailing_thread()
                    break
                    
                except Exception as e:
                    logger.error(f"💥 Cycle error: {e}")
                    logger.info("⏰ Sleeping 60 seconds before retry...")
                    time.sleep(60)
                    
        except KeyboardInterrupt:
            logger.info("🛑 Shutdown complete")
            
        logger.info(f"📊 Total cycles completed: {cycle_count}")

def main():
    parser = argparse.ArgumentParser(description='SignalWarden Lite v1.6-TXB Live Trading')
    parser.add_argument('--config', required=True, help='Config YAML file path')
    parser.add_argument('--paper', action='store_true', help='Run in paper trading mode')
    
    args = parser.parse_args()
    
    # Create and run trading system
    trader = SignalWardenLive(args.config, paper_mode=args.paper)
    trader.run()

if __name__ == '__main__':
    main()
