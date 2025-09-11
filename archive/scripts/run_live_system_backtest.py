#!/usr/bin/env python3
"""
ПОЛНАЯ КОПИЯ LIVE СИСТЕМЫ ДЛЯ БЭКТЕСТА
Точно воспроизводит логику SignalWardenLive v1.6-TXB
"""

import os
import sys
import yaml
import pandas as pd
import numpy as np
import pickle
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

# Добавляем путь к модулям
sys.path.append('.')

from signalwarden_lite.core.features import add_indicators
from signalwarden_lite.core.regimes import add_regime, RegimeThresholds
from signalwarden_lite.core.market import compute_market_bias
from signalwarden_lite.core.signals import generate_signals, SignalParams
from signalwarden_lite.core.trailing import TrailingConfig, update_trailing_pnl_based
from signalwarden_lite.core.types import Side, Position

class BacktestSignalWardenLive:
    """
    Точная копия SignalWardenLive для бэктеста
    Использует ту же логику, что и реальная система
    """
    
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.load_config()
        self.setup_parameters()
        self.active_positions = {}  # symbol -> position_data
        self.trades_log = []
        self.current_time = None
        
        print(f"🚀 BacktestSignalWarden v1.6-TXB initialized")
        
    def load_config(self):
        """Load configuration (same as live system)"""
        with open(self.config_path, 'r') as f:
            self.cfg = yaml.safe_load(f)
        
        print(f"✅ Config loaded: {self.cfg['profile']}")
        
    def setup_parameters(self):
        """Setup trading parameters (same as live system)"""
        # Risk parameters
        self.margin_usdt = self.cfg['risk']['margin_usdt']  # 21 USDT
        self.leverage = self.cfg['risk']['leverage']  # 5
        self.sl_atr_mult = self.cfg['risk']['sl_atr_mult']  # 2.5
        
        # Trailing configuration
        self.trailing_config = TrailingConfig(
            activate_pnl_usdt=self.cfg['trailing']['activate_pnl_usdt'],
            level_1_pnl=self.cfg['trailing']['level_1_pnl'],
            level_1_keep_pct=self.cfg['trailing']['level_1_keep_pct'],
            level_2_pnl=self.cfg['trailing']['level_2_pnl'],
            level_2_keep_pct=self.cfg['trailing']['level_2_keep_pct'],
            level_3_pnl=self.cfg['trailing']['level_3_pnl'],
            level_3_keep_pct=self.cfg['trailing']['level_3_keep_pct'],
            level_4_pnl=self.cfg['trailing']['level_4_pnl'],
            level_4_keep_pct=self.cfg['trailing']['level_4_keep_pct']
        )
        
        # Signal parameters (same as live system)
        self.signal_params = SignalParams(
            lookback_calm=self.cfg['signals']['dynamic_lookback']['calm'],
            lookback_normal=self.cfg['signals']['dynamic_lookback']['normal'],
            lookback_high=self.cfg['signals']['dynamic_lookback']['high'],
            long_cushion_calm=self.cfg['signals']['atr_cushion_long']['calm'],
            long_cushion_normal=self.cfg['signals']['atr_cushion_long']['normal'],
            long_cushion_high=self.cfg['signals']['atr_cushion_long']['high'],
            short_cushion_calm=self.cfg['signals']['atr_cushion_short']['calm'],
            short_cushion_normal=self.cfg['signals']['atr_cushion_short']['normal'],
            short_cushion_high=self.cfg['signals']['atr_cushion_short']['high'],
            setup_breakout=self.cfg['signals']['setups']['breakout']['enabled'],
            setup_inside=self.cfg['signals']['setups']['inside_bar']['enabled'],
            setup_trend_cont=self.cfg['signals']['setups']['trend_continuation']['enabled'],
            setup_squeeze=self.cfg['signals']['setups']['squeeze_breakout']['enabled'],
            ib_min_prev_range_k_atr=self.cfg['signals']['setups']['inside_bar']['min_prev_range_k_atr'],
            tc_min_body_k_range=self.cfg['signals']['setups']['trend_continuation']['min_body_k_range'],
            tc_confirm_close_k_body=self.cfg['signals']['setups']['trend_continuation']['confirm_close_k_body'],
            bb_period=self.cfg['signals']['setups']['squeeze_breakout']['bb_period'],
            bb_k=self.cfg['signals']['setups']['squeeze_breakout']['bb_k'],
            width_k_perc=self.cfg['signals']['setups']['squeeze_breakout']['width_k_perc'],
            ltf_thinbar_k=self.cfg['signals']['ltf_thinbar_k'],
            sg_rsi_bear_max=self.cfg['short_guard']['rsi_bear_max'],
            sg_rsi_bullcorr_max=self.cfg['short_guard']['rsi_bullcorr_max'],
            sg_min_natr_bear=self.cfg['short_guard']['min_natr_bear'],
            sg_min_natr_bullcorr=self.cfg['short_guard']['min_natr_bullcorr'],
            sg_require_close_below_ema20_bullcorr=self.cfg['short_guard']['require_close_below_ema20_bullcorr'],
            sg_slope_lookback=self.cfg['short_guard']['slope_lookback']
        )
        
        # Regime thresholds
        self.regime_thresholds = RegimeThresholds(
            ultra_calm=self.cfg['regime']['calm_thresholds']['ultra_calm'],
            calm=self.cfg['regime']['calm_thresholds']['calm'],
            high=self.cfg['regime']['calm_thresholds']['high']
        )
        
    def load_historical_data(self, symbol: str, timeframe: str) -> pd.DataFrame:
        """Load historical data (same format as live system expects)"""
        
        # Try pickle format first
        pickle_file = f"data/historical_candles/{symbol}_{timeframe}.pkl"
        if os.path.exists(pickle_file):
            try:
                with open(pickle_file, 'rb') as f:
                    df = pickle.load(f)
                
                # Convert timestamp to datetime index
                if 'timestamp' in df.columns:
                    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
                    df.set_index('timestamp', inplace=True)
                elif not isinstance(df.index, pd.DatetimeIndex):
                    df.index = pd.to_datetime(df.index, unit='s')
                
                # Filter to 2022-2024 data
                df = df[(df.index >= '2022-01-01') & (df.index < '2024-01-01')]
                
                if len(df) > 0:
                    print(f"    ✅ Loaded {len(df)} candles for {symbol} {timeframe}")
                    return df
                    
            except Exception as e:
                print(f"    ⚠️ Error loading {pickle_file}: {e}")
        
        print(f"    ❌ No data found for {symbol} {timeframe}")
        return None
        
    def process_symbol_mtf(self, symbol: str, btc_bias: pd.DataFrame) -> Dict[str, Any]:
        """
        Process symbol with MTF strategy (EXACT copy of live system logic)
        """
        result = {
            'symbol': symbol,
            'signals_1h': [],
            'signals_15m': [],
            'data_1h': None,
            'data_15m': None,
            'errors': []
        }
        
        try:
            print(f"📈 Processing {symbol} with MTF strategy...")
            
            # Load 1h data for breakout signals
            df_1h = self.load_historical_data(symbol, '1h')
            if df_1h is None or len(df_1h) < 200:
                result['errors'].append(f"Insufficient 1h data")
                return result
            
            # Load 15m data for LTF signals  
            df_15m = self.load_historical_data(symbol, '15m')
            if df_15m is None or len(df_15m) < 200:
                result['errors'].append(f"Insufficient 15m data")
                return result
            
            # Add indicators (same as live system)
            df_1h = add_indicators(df_1h)
            df_15m = add_indicators(df_15m)
            
            # Add regime classification
            df_1h = add_regime(df_1h, self.regime_thresholds)
            df_15m = add_regime(df_15m, self.regime_thresholds)
            
            # Generate signals with BTC market filter
            df_1h_signals = generate_signals(df_1h, self.signal_params, btc_bias)
            df_15m_signals = generate_signals(df_15m, self.signal_params, btc_bias)
            
            # Extract signals from 1h (breakout only)
            for timestamp, row in df_1h_signals.iterrows():
                if row.get('signal_long', False) or row.get('signal_short', False):
                    signal = {
                        'timestamp': timestamp,
                        'symbol': symbol,
                        'timeframe': '1h',
                        'side': 'LONG' if row.get('signal_long', False) else 'SHORT',
                        'setup': 'breakout',
                        'entry': float(df_1h.loc[timestamp, 'close']),
                        'atr': float(df_1h.loc[timestamp, 'atr']),
                        'high': float(df_1h.loc[timestamp, 'high']),
                        'low': float(df_1h.loc[timestamp, 'low']),
                        'allow_long': row.get('allow_long', False),
                        'allow_short': row.get('allow_short', False)
                    }
                    result['signals_1h'].append(signal)
            
            # Extract signals from 15m (LTF setups)
            for timestamp, row in df_15m_signals.iterrows():
                if row.get('signal_long', False) or row.get('signal_short', False):
                    signal = {
                        'timestamp': timestamp,
                        'symbol': symbol,
                        'timeframe': '15m',
                        'side': 'LONG' if row.get('signal_long', False) else 'SHORT',
                        'setup': row.get('setup_name', 'ltf'),
                        'entry': float(df_15m.loc[timestamp, 'close']),
                        'atr': float(df_15m.loc[timestamp, 'atr']),
                        'high': float(df_15m.loc[timestamp, 'high']),
                        'low': float(df_15m.loc[timestamp, 'low']),
                        'allow_long': row.get('allow_long', False),
                        'allow_short': row.get('allow_short', False)
                    }
                    result['signals_15m'].append(signal)
            
            result['data_1h'] = df_1h
            result['data_15m'] = df_15m
            
            total_signals = len(result['signals_1h']) + len(result['signals_15m'])
            print(f"    ✅ Generated {total_signals} signals ({len(result['signals_1h'])} from 1h, {len(result['signals_15m'])} from 15m)")
            
        except Exception as e:
            result['errors'].append(str(e))
            print(f"    ❌ Error processing {symbol}: {e}")
        
        return result
        
    def has_open_position(self, symbol: str) -> bool:
        """Check if position exists (same as live system)"""
        return symbol in self.active_positions
        
    def can_open_new_position(self) -> bool:
        """Check if we can open new position (same as live system)"""
        # Simple check - max 4 positions (same as live system logic)
        return len(self.active_positions) < 4
        
    def execute_signal(self, signal: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Execute trading signal (EXACT copy of live system logic)
        """
        symbol = signal['symbol']
        side = signal['side']
        entry = signal['entry']
        atr = signal['atr']
        
        # Check if position already exists
        if self.has_open_position(symbol):
            print(f"    ⚠️ Position already open for {symbol} - skipping")
            return None
            
        # Check if we can open new position
        if not self.can_open_new_position():
            print(f"    ⚠️ Max positions reached - skipping {symbol}")
            return None
        
        # Calculate position size: EXACTLY as live system
        position_value_usdt = self.margin_usdt  # 21 USDT notional
        qty = position_value_usdt / entry
        
        # Calculate stop loss with MINIMUM ATR protection (CRITICAL!)
        # This is the KEY difference that causes losses!
        min_atr_pct = 0.02  # Minimum 2% from price (SAME AS LIVE SYSTEM!)
        min_atr = entry * min_atr_pct
        effective_atr = max(atr, min_atr)  # Use larger ATR
        
        if side == 'LONG':
            sl_price = entry - (self.sl_atr_mult * effective_atr)
        else:
            sl_price = entry + (self.sl_atr_mult * effective_atr)
        
        # Calculate fees (EXACTLY as live system)
        maker_bps = self.cfg['fees']['maker_bps']  # 2.0
        taker_bps = self.cfg['fees']['taker_bps']  # 5.0
        
        # Entry fees (taker for market orders in backtest)
        entry_fees_usdt = position_value_usdt * (taker_bps / 10000.0)
        
        # Create position
        position = {
            'symbol': symbol,
            'side': side,
            'entry': entry,
            'qty': qty,
            'sl_initial': sl_price,
            'sl_current': sl_price,
            'atr': effective_atr,
            'original_atr': atr,
            'entry_fees_usdt': entry_fees_usdt,
            'timestamp': signal['timestamp'],
            'setup': signal['setup'],
            'timeframe': signal['timeframe'],
            'peak_pnl_usdt': 0.0,
            'trailing_active': False
        }
        
        # Store position
        self.active_positions[symbol] = position
        
        print(f"    ✅ Opened {side} position: {symbol} @ {entry:.6f}, SL: {sl_price:.6f}")
        print(f"        ATR protection: {atr:.6f} → {effective_atr:.6f} ({effective_atr/entry*100:.1f}% of price)")
        
        return position
        
    def update_trailing_stops(self, current_data: Dict[str, pd.DataFrame]):
        """
        Update trailing stops (EXACT copy of live system logic)
        """
        for symbol, pos in list(self.active_positions.items()):
            try:
                # Get current price data
                if pos['timeframe'] == '1h':
                    df = current_data[symbol]['data_1h']
                else:
                    df = current_data[symbol]['data_15m']
                
                if df is None or len(df) == 0:
                    continue
                
                # Get current price at this timestamp
                try:
                    current_row = df.loc[self.current_time]
                    current_price = float(current_row['close'])
                except:
                    # If exact timestamp not found, use nearest
                    nearest_idx = df.index.get_indexer([self.current_time], method='nearest')[0]
                    current_row = df.iloc[nearest_idx]
                    current_price = float(current_row['close'])
                
                # Calculate current PnL (EXACTLY as live system)
                if pos['side'] == 'LONG':
                    current_pnl_usdt = (current_price - pos['entry']) * pos['qty']
                else:
                    current_pnl_usdt = (pos['entry'] - current_price) * pos['qty']
                
                # Update peak PnL
                pos['peak_pnl_usdt'] = max(pos['peak_pnl_usdt'], current_pnl_usdt)
                
                # Create Position object for trailing function
                position_obj = Position(
                    side=Side.LONG if pos['side'] == 'LONG' else Side.SHORT,
                    entry=pos['entry'],
                    sl=pos['sl_current'],
                    qty=pos['qty'],
                    remaining_qty=pos['qty'],
                    r_per_unit=0.0,
                    sl_initial=pos['sl_initial'],
                    peak_pnl_usdt=pos['peak_pnl_usdt'],
                    bars_open=0,
                    entry_fees_usdt=pos['entry_fees_usdt']
                )
                
                # Update trailing stop (EXACTLY as live system)
                old_sl = position_obj.sl
                position_obj = update_trailing_pnl_based(position_obj, current_price, current_pnl_usdt, self.trailing_config)
                
                # Update position if SL changed
                if position_obj.sl != old_sl:
                    pos['sl_current'] = position_obj.sl
                    pos['trailing_active'] = True
                    print(f"    📊 {symbol}: Trailing SL updated {old_sl:.6f} → {position_obj.sl:.6f} (PnL: {current_pnl_usdt:.4f})")
                
                # Update position data
                pos['peak_pnl_usdt'] = position_obj.peak_pnl_usdt
                
            except Exception as e:
                print(f"    ⚠️ Error updating trailing for {symbol}: {e}")
                
    def check_stop_loss_hits(self, current_data: Dict[str, pd.DataFrame]) -> List[Dict[str, Any]]:
        """
        Check for stop loss hits (EXACT copy of live system logic)
        """
        closed_trades = []
        
        for symbol, pos in list(self.active_positions.items()):
            try:
                # Get current price data
                if pos['timeframe'] == '1h':
                    df = current_data[symbol]['data_1h']
                else:
                    df = current_data[symbol]['data_15m']
                
                if df is None or len(df) == 0:
                    continue
                
                # Get current bar data
                try:
                    current_row = df.loc[self.current_time]
                except:
                    nearest_idx = df.index.get_indexer([self.current_time], method='nearest')[0]
                    current_row = df.iloc[nearest_idx]
                
                high = float(current_row['high'])
                low = float(current_row['low'])
                close = float(current_row['close'])
                
                # Check stop loss hit
                sl_hit = False
                exit_price = pos['sl_current']
                
                if pos['side'] == 'LONG':
                    if low <= pos['sl_current']:
                        sl_hit = True
                        exit_price = pos['sl_current']
                else:  # SHORT
                    if high >= pos['sl_current']:
                        sl_hit = True
                        exit_price = pos['sl_current']
                
                if sl_hit:
                    # Calculate final PnL
                    if pos['side'] == 'LONG':
                        pnl_usdt = (exit_price - pos['entry']) * pos['qty']
                    else:
                        pnl_usdt = (pos['entry'] - exit_price) * pos['qty']
                    
                    # Calculate exit fees (always taker for SL)
                    exit_notional = exit_price * pos['qty']
                    exit_fees_usdt = exit_notional * (self.cfg['fees']['taker_bps'] / 10000.0)
                    
                    # Net PnL after fees
                    net_pnl_usdt = pnl_usdt - pos['entry_fees_usdt'] - exit_fees_usdt
                    
                    # Create trade log
                    trade = {
                        'symbol': symbol,
                        'entry_timestamp': pos['timestamp'],
                        'exit_timestamp': self.current_time,
                        'side': pos['side'],
                        'setup': pos['setup'],
                        'timeframe': pos['timeframe'],
                        'entry': pos['entry'],
                        'exit': exit_price,
                        'qty': pos['qty'],
                        'pnl_usdt': pnl_usdt,
                        'entry_fees_usdt': pos['entry_fees_usdt'],
                        'exit_fees_usdt': exit_fees_usdt,
                        'net_pnl_usdt': net_pnl_usdt,
                        'sl_initial': pos['sl_initial'],
                        'sl_final': pos['sl_current'],
                        'peak_pnl_usdt': pos['peak_pnl_usdt'],
                        'exit_reason': 'stop_loss',
                        'atr_used': pos['atr'],
                        'atr_original': pos['original_atr'],
                        'trailing_was_active': pos['trailing_active']
                    }
                    
                    closed_trades.append(trade)
                    
                    # Remove from active positions
                    del self.active_positions[symbol]
                    
                    print(f"    🔴 SL Hit: {symbol} {pos['side']} @ {exit_price:.6f}, PnL: {net_pnl_usdt:.4f} USDT")
                    
            except Exception as e:
                print(f"    ⚠️ Error checking SL for {symbol}: {e}")
        
        return closed_trades
        
    def run_backtest(self, start_date: str = '2022-06-01', end_date: str = '2023-12-31'):
        """
        Run complete backtest (EXACT copy of live system flow)
        """
        print("🚀 ЗАПУСК ПОЛНОГО БЭКТЕСТА LIVE СИСТЕМЫ")
        print("=" * 80)
        print(f"📅 Period: {start_date} to {end_date}")
        print(f"💰 Position Size: {self.margin_usdt} USDT")
        print(f"🛡️ SL Multiplier: {self.sl_atr_mult}")
        print(f"⚠️ ATR Protection: 2% minimum (SAME AS LIVE!)")
        print()
        
        # Load BTC market bias
        print("🔧 Loading BTC market bias...")
        btc_data = self.load_historical_data('BTC_USDT', '1h')
        if btc_data is not None:
            btc_data = add_indicators(btc_data)
            btc_data_for_bias = btc_data.reset_index()
            btc_bias = compute_market_bias(
                btc_data_for_bias,
                self.cfg['market_filter']['ema_fast'],
                self.cfg['market_filter']['ema_slow']
            )
            btc_bias.set_index('timestamp', inplace=True)
            print(f"✅ BTC bias loaded: {len(btc_bias)} bars")
        else:
            btc_bias = None
            print("⚠️ BTC bias not loaded")
        
        # Process symbols
        available_symbols = ['ADA_USDT', 'LTC_USDT', 'DOGE_USDT', 'HBAR_USDT']
        symbol_data = {}
        all_signals = []
        
        print(f"\n📊 Processing {len(available_symbols)} symbols...")
        for symbol in available_symbols:
            result = self.process_symbol_mtf(symbol, btc_bias)
            if not result['errors']:
                symbol_data[symbol] = result
                
                # Collect all signals with timestamps
                for signal in result['signals_1h'] + result['signals_15m']:
                    all_signals.append(signal)
        
        if not all_signals:
            print("❌ No signals generated!")
            return
        
        # Sort signals by timestamp
        all_signals.sort(key=lambda x: x['timestamp'])
        
        print(f"✅ Total signals to process: {len(all_signals)}")
        print()
        
        # Process signals chronologically (EXACT copy of live system)
        print("🔄 Processing signals chronologically...")
        processed_signals = 0
        
        for signal in all_signals:
            self.current_time = signal['timestamp']
            processed_signals += 1
            
            if processed_signals % 100 == 0:
                print(f"    📊 Processed {processed_signals}/{len(all_signals)} signals...")
            
            # Try to execute signal
            position = self.execute_signal(signal)
            
            # Update trailing stops for all active positions
            self.update_trailing_stops(symbol_data)
            
            # Check for stop loss hits
            closed_trades = self.check_stop_loss_hits(symbol_data)
            self.trades_log.extend(closed_trades)
        
        print(f"✅ Processed all {len(all_signals)} signals")
        print()
        
        # Close any remaining positions at end of backtest
        print("🔚 Closing remaining positions...")
        for symbol, pos in list(self.active_positions.items()):
            try:
                # Get final price
                if pos['timeframe'] == '1h':
                    df = symbol_data[symbol]['data_1h']
                else:
                    df = symbol_data[symbol]['data_15m']
                
                final_price = float(df.iloc[-1]['close'])
                
                # Calculate final PnL
                if pos['side'] == 'LONG':
                    pnl_usdt = (final_price - pos['entry']) * pos['qty']
                else:
                    pnl_usdt = (pos['entry'] - final_price) * pos['qty']
                
                # Calculate fees
                exit_notional = final_price * pos['qty']
                exit_fees_usdt = exit_notional * (self.cfg['fees']['taker_bps'] / 10000.0)
                net_pnl_usdt = pnl_usdt - pos['entry_fees_usdt'] - exit_fees_usdt
                
                # Create final trade
                trade = {
                    'symbol': symbol,
                    'entry_timestamp': pos['timestamp'],
                    'exit_timestamp': df.index[-1],
                    'side': pos['side'],
                    'setup': pos['setup'],
                    'timeframe': pos['timeframe'],
                    'entry': pos['entry'],
                    'exit': final_price,
                    'qty': pos['qty'],
                    'pnl_usdt': pnl_usdt,
                    'entry_fees_usdt': pos['entry_fees_usdt'],
                    'exit_fees_usdt': exit_fees_usdt,
                    'net_pnl_usdt': net_pnl_usdt,
                    'sl_initial': pos['sl_initial'],
                    'sl_final': pos['sl_current'],
                    'peak_pnl_usdt': pos['peak_pnl_usdt'],
                    'exit_reason': 'backtest_end',
                    'atr_used': pos['atr'],
                    'atr_original': pos['original_atr'],
                    'trailing_was_active': pos['trailing_active']
                }
                
                self.trades_log.append(trade)
                print(f"    🔚 Closed {symbol} {pos['side']} @ {final_price:.6f}, PnL: {net_pnl_usdt:.4f} USDT")
                
            except Exception as e:
                print(f"    ⚠️ Error closing {symbol}: {e}")
        
        # Clear active positions
        self.active_positions.clear()
        
        # Analyze results
        self.analyze_results()
        
    def analyze_results(self):
        """Analyze backtest results"""
        if not self.trades_log:
            print("❌ No trades executed!")
            return
        
        print("\n📊 РЕЗУЛЬТАТЫ ТОЧНОГО БЭКТЕСТА LIVE СИСТЕМЫ:")
        print("=" * 80)
        
        df_trades = pd.DataFrame(self.trades_log)
        
        # Overall statistics
        total_trades = len(df_trades)
        total_pnl = df_trades['net_pnl_usdt'].sum()
        gross_pnl = df_trades['pnl_usdt'].sum()
        total_fees = (df_trades['entry_fees_usdt'] + df_trades['exit_fees_usdt']).sum()
        
        winning_trades = len(df_trades[df_trades['net_pnl_usdt'] > 0])
        losing_trades = len(df_trades[df_trades['net_pnl_usdt'] < 0])
        win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0
        
        avg_win = df_trades[df_trades['net_pnl_usdt'] > 0]['net_pnl_usdt'].mean() if winning_trades > 0 else 0
        avg_loss = df_trades[df_trades['net_pnl_usdt'] < 0]['net_pnl_usdt'].mean() if losing_trades > 0 else 0
        profit_factor = abs(avg_win * winning_trades / (avg_loss * losing_trades)) if losing_trades > 0 and avg_loss != 0 else float('inf')
        
        print(f"📊 ОСНОВНЫЕ РЕЗУЛЬТАТЫ:")
        print(f"   💰 Net PnL: ${total_pnl:.2f}")
        print(f"   💰 Gross PnL: ${gross_pnl:.2f}")
        print(f"   📈 Total Trades: {total_trades}")
        print(f"   ✅ Win Rate: {win_rate:.1f}%")
        print(f"   📊 Profit Factor: {profit_factor:.2f}")
        print(f"   💸 Total Fees: ${total_fees:.2f}")
        print(f"   📊 Avg Win: ${avg_win:.4f}")
        print(f"   📊 Avg Loss: ${avg_loss:.4f}")
        print()
        
        # ATR Protection Analysis
        atr_protected = df_trades[df_trades['atr_used'] > df_trades['atr_original']]
        print(f"🛡️ ATR PROTECTION ANALYSIS:")
        print(f"   🛡️ Trades with ATR protection: {len(atr_protected)} ({len(atr_protected)/total_trades*100:.1f}%)")
        if len(atr_protected) > 0:
            avg_protection = ((atr_protected['atr_used'] - atr_protected['atr_original']) / atr_protected['atr_original'] * 100).mean()
            protection_pnl = atr_protected['net_pnl_usdt'].sum()
            print(f"   📊 Avg ATR increase: {avg_protection:.1f}%")
            print(f"   💰 Protected trades PnL: ${protection_pnl:.2f}")
            print(f"   ⚠️ ATR protection impact: {protection_pnl/total_pnl*100:.1f}% of total PnL")
        print()
        
        # Trailing Analysis
        trailing_active = df_trades[df_trades['trailing_was_active'] == True]
        print(f"📈 TRAILING ANALYSIS:")
        print(f"   🎯 Trades with trailing: {len(trailing_active)} ({len(trailing_active)/total_trades*100:.1f}%)")
        if len(trailing_active) > 0:
            trailing_pnl = trailing_active['net_pnl_usdt'].sum()
            avg_peak = trailing_active['peak_pnl_usdt'].mean()
            print(f"   💰 Trailing trades PnL: ${trailing_pnl:.2f}")
            print(f"   📊 Avg peak PnL: ${avg_peak:.4f}")
        print()
        
        # Symbol breakdown
        print(f"📊 BREAKDOWN BY SYMBOLS:")
        symbol_stats = df_trades.groupby('symbol').agg({
            'net_pnl_usdt': ['count', 'sum', 'mean'],
            'entry_fees_usdt': 'sum',
            'exit_fees_usdt': 'sum'
        }).round(4)
        
        for symbol in symbol_stats.index:
            trades_count = int(symbol_stats.loc[symbol, ('net_pnl_usdt', 'count')])
            pnl_sum = symbol_stats.loc[symbol, ('net_pnl_usdt', 'sum')]
            pnl_avg = symbol_stats.loc[symbol, ('net_pnl_usdt', 'mean')]
            fees_sum = symbol_stats.loc[symbol, ('entry_fees_usdt', 'sum')] + symbol_stats.loc[symbol, ('exit_fees_usdt', 'sum')]
            
            print(f"   📈 {symbol}: {trades_count} trades, Net PnL: ${pnl_sum:.2f}, Avg: ${pnl_avg:.4f}, Fees: ${fees_sum:.2f}")
        print()
        
        # Side breakdown
        long_trades = df_trades[df_trades['side'] == 'LONG']
        short_trades = df_trades[df_trades['side'] == 'SHORT']
        
        print(f"📊 BREAKDOWN BY SIDE:")
        print(f"   📈 Long: {len(long_trades)} trades ({len(long_trades)/total_trades*100:.1f}%), PnL: ${long_trades['net_pnl_usdt'].sum():.2f}")
        print(f"   📉 Short: {len(short_trades)} trades ({len(short_trades)/total_trades*100:.1f}%), PnL: ${short_trades['net_pnl_usdt'].sum():.2f}")
        print()
        
        # Final conclusion
        print("🎯 ЗАКЛЮЧЕНИЕ:")
        print("-" * 60)
        if total_pnl > 0:
            print("✅ LIVE СИСТЕМА В БЭКТЕСТЕ ПРИБЫЛЬНА!")
            print(f"✅ Net PnL: ${total_pnl:.2f}")
        else:
            print("❌ LIVE СИСТЕМА В БЭКТЕСТЕ УБЫТОЧНА!")
            print(f"❌ Net PnL: ${total_pnl:.2f}")
            print()
            print("🔍 ПРИЧИНЫ УБЫТКОВ:")
            print("   1. Минимальная защита ATR 2% делает SL слишком далеко")
            print("   2. Высокие комиссии 0.07% на каждую сделку")
            print("   3. PnL трейлинг активируется слишком поздно")
            print("   4. Мелкие позиции $21 vs большие комиссии")
        
        # Save results
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        results_file = f"live_system_backtest_results_{timestamp}.csv"
        df_trades.to_csv(results_file, index=False)
        print(f"\n💾 Results saved to: {results_file}")
        
        # Save summary
        summary = {
            'timestamp': timestamp,
            'total_trades': total_trades,
            'net_pnl_usdt': float(total_pnl),
            'gross_pnl_usdt': float(gross_pnl),
            'total_fees_usdt': float(total_fees),
            'win_rate_pct': float(win_rate),
            'profit_factor': float(profit_factor),
            'avg_win_usdt': float(avg_win),
            'avg_loss_usdt': float(avg_loss),
            'atr_protected_trades': len(atr_protected),
            'trailing_active_trades': len(trailing_active),
            'config_used': self.cfg['profile']
        }
        
        summary_file = f"live_system_backtest_summary_{timestamp}.json"
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2, default=str)
        print(f"💾 Summary saved to: {summary_file}")

def main():
    """Run the live system backtest"""
    
    # Use production config (same as live system)
    config_path = 'signalwarden_lite/config/config_production.yaml'
    
    # Create and run backtest
    backtest = BacktestSignalWardenLive(config_path)
    backtest.run_backtest(start_date='2022-06-01', end_date='2023-12-31')

if __name__ == "__main__":
    main()
