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
        
        # Risk parameters
        self.margin_usdt = self.cfg['risk']['margin_usdt']
        self.leverage = self.cfg['risk']['leverage']
        self.base_notional = self.margin_usdt * self.leverage  # 75 USDT
        
        logger.info(f"⚙️ Risk per trade: {self.margin_usdt} USDT margin × {self.leverage} = {self.base_notional} USDT notional")
        
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
            
            # Calculate position size
            qty = self.base_notional / entry
            
            # Calculate stop loss
            sl_atr_mult = self.cfg['risk']['sl_atr_mult']
            if side == 'LONG':
                sl_price = entry - (sl_atr_mult * atr)
            else:
                sl_price = entry + (sl_atr_mult * atr)
            
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
            
            # Place stop loss order  
            sl_side = 'sell' if side == 'LONG' else 'buy'
            sl_order = self.exchange.create_order(
                ccxt_sym,
                'stop_market',
                sl_side,
                qty,
                None,  # no limit price for stop market
                params={
                    'stopPrice': sl_price,
                    'reduceOnly': True
                }
            )
            
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
        logger.info(f"💰 Risk per trade: {self.base_notional} USDT notional")
        logger.info(f"⚙️ MTF Strategy: 1h breakout + 15m LTF setups")
        logger.info(f"🛡️ Adaptive shorts with BTC filter enabled")
        
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
