#!/usr/bin/env python3
"""
Точный бэктест текущей системы с новым PnL-трейлингом
Использует данные из @data/ и полностью соответствует live логике
"""

import sys
import os
import pandas as pd
import numpy as np
import pickle
from datetime import datetime, timedelta
import yaml
from typing import Dict, List, Optional, Tuple
import warnings
warnings.filterwarnings('ignore')

# Add project root to path
sys.path.append('.')

from signalwarden_lite.core.types import Position, Side
from signalwarden_lite.core.signals import SignalParams, generate_signals
from signalwarden_lite.core.regimes import RegimeThresholds, add_regime
from signalwarden_lite.core.market import compute_market_bias
from signalwarden_lite.core.trailing import TrailingConfig, update_trailing_pnl_based
from signalwarden_lite.core.features import add_indicators


def load_local_data(symbol: str, timeframe: str, start_date: str = "2022-01-01", end_date: str = "2024-01-01") -> pd.DataFrame:
    """Загрузка локальных данных из historical_candles/"""
    pkl_file = f"data/historical_candles/{symbol}_{timeframe}.pkl"
    
    if not os.path.exists(pkl_file):
        print(f"❌ Файл не найден: {pkl_file}")
        return pd.DataFrame()
    
    try:
        with open(pkl_file, 'rb') as f:
            df = pickle.load(f)
        
        # Ensure timestamp column
        if 'timestamp' not in df.columns:
            if df.index.name == 'timestamp':
                df = df.reset_index()
            else:
                print(f"❌ Нет колонки timestamp в {pkl_file}")
                return pd.DataFrame()
        
        # Convert timestamp to datetime if needed
        if df['timestamp'].dtype in ['int64', 'float64']:
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
        elif df['timestamp'].dtype == 'object':
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Filter by date range
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)
        df = df[(df['timestamp'] >= start_dt) & (df['timestamp'] < end_dt)]
        
        # Sort and reset index
        df = df.sort_values('timestamp').reset_index(drop=True)
        
        print(f"✅ {symbol} {timeframe}: {len(df)} свечей ({df['timestamp'].min()} - {df['timestamp'].max()})")
        return df
        
    except Exception as e:
        print(f"❌ Ошибка загрузки {pkl_file}: {e}")
        return pd.DataFrame()


def run_backtest():
    """Запуск точного бэктеста с текущими настройками"""
    
    print("🚀 ТОЧНЫЙ БЭКТЕСТ ТЕКУЩЕЙ СИСТЕМЫ")
    print("=" * 70)
    
    # Load configuration
    with open('signalwarden_lite/config/config_production.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    print("📋 НАСТРОЙКИ:")
    print(f"   Размер позиции: ${config['risk']['margin_usdt']} USDT")
    print(f"   SL множитель: {config['risk']['sl_atr_mult']}x ATR")
    print(f"   Трейлинг активация: ${config['trailing']['activate_pnl_usdt']}")
    print(f"   Минимальная защита: ${config['trailing']['min_keep_usdt']}")
    print()
    
    # Setup parameters
    symbols = config['symbols']
    margin_usdt = config['risk']['margin_usdt']  # 21 USDT
    sl_atr_mult = config['risk']['sl_atr_mult']  # 1.5
    
    # Create objects from config
    regime_thresholds = RegimeThresholds(
        ultra_calm=config['regime']['calm_thresholds']['ultra_calm'],
        calm=config['regime']['calm_thresholds']['calm'], 
        high=config['regime']['calm_thresholds']['high']
    )
    
    signal_params = SignalParams(
        setup_breakout=config['signals']['setups']['breakout']['enabled'],
        setup_inside=config['signals']['setups']['inside_bar']['enabled'],
        setup_trend_cont=config['signals']['setups']['trend_continuation']['enabled'],
        setup_squeeze=config['signals']['setups']['squeeze_breakout']['enabled']
    )
    
    trailing_config = TrailingConfig(
        activate_pnl_usdt=config['trailing']['activate_pnl_usdt'],
        level_1_pnl=config['trailing']['level_1_pnl'],
        level_1_keep_pct=config['trailing']['level_1_keep_pct'],
        level_2_pnl=config['trailing']['level_2_pnl'],
        level_2_keep_pct=config['trailing']['level_2_keep_pct'],
        level_3_pnl=config['trailing']['level_3_pnl'],
        level_3_keep_pct=config['trailing']['level_3_keep_pct'],
        level_4_pnl=config['trailing']['level_4_pnl'],
        level_4_keep_pct=config['trailing']['level_4_keep_pct'],
        chandelier_k_atr=config['trailing']['chandelier_k_atr'],
        min_keep_usdt=config['trailing']['min_keep_usdt']
    )
    
    print("📊 ЗАГРУЗКА ДАННЫХ...")
    
    # Load BTC data for market filter
    btc_1h = load_local_data('BTC_USDT', '1h')
    if btc_1h.empty:
        print("❌ Не удалось загрузить BTC данные")
        return
    
    btc_1h = add_indicators(btc_1h, ema_fast=50, ema_slow=200)
    btc_1h = btc_1h.reset_index(drop=True)
    btc_1h['timestamp'] = (btc_1h['timestamp'].astype('int64') // 10**9).astype('int64')
    btc_bias = compute_market_bias(btc_1h)
    btc_bias = btc_bias.set_index('timestamp')
    
    # Load symbol data
    symbol_data = {}
    for symbol in symbols:
        # Load both timeframes
        df_1h = load_local_data(symbol, '1h')
        df_15m = load_local_data(symbol, '15m')
        
        if df_1h.empty or df_15m.empty:
            print(f"❌ Пропуск {symbol} - нет данных")
            continue
        
        # Add indicators
        df_1h = add_indicators(df_1h, atr_p=14, rsi_p=14)
        df_15m = add_indicators(df_15m, atr_p=14, rsi_p=14)
        
        # Convert timestamps to int for compatibility
        df_1h = df_1h.reset_index(drop=True)
        df_15m = df_15m.reset_index(drop=True)
        df_1h['timestamp'] = (df_1h['timestamp'].astype('int64') // 10**9).astype('int64')
        df_15m['timestamp'] = (df_15m['timestamp'].astype('int64') // 10**9).astype('int64')
        
        symbol_data[symbol] = {
            '1h': df_1h,
            '15m': df_15m
        }
    
    print(f"✅ Загружено {len(symbol_data)} символов")
    print()
    
    # Backtest parameters
    trades = []
    positions = {}  # symbol -> Position
    total_pnl = 0.0
    total_trades = 0
    winning_trades = 0
    losing_trades = 0
    
    # Get common timeframe for iteration (1h)
    if not symbol_data:
        print("❌ Нет данных для бэктеста")
        return
    
    first_symbol = list(symbol_data.keys())[0]
    time_index = symbol_data[first_symbol]['1h']['timestamp'].values
    
    print("🔄 ЗАПУСК БЭКТЕСТА...")
    
    for i, current_time in enumerate(time_index):
        if i < 200:  # Skip first 200 bars for indicators
            continue
            
        if i % 1000 == 0:
            progress = (i / len(time_index)) * 100
            print(f"   Прогресс: {progress:.1f}% ({i}/{len(time_index)})")
        
        # Check existing positions for exits first
        positions_to_close = []
        
        for symbol, pos in positions.items():
            if symbol not in symbol_data:
                continue
                
            try:
                # Get current price data
                df_1h = symbol_data[symbol]['1h']
                current_bar_idx = np.where(df_1h['timestamp'] == current_time)[0]
                
                if len(current_bar_idx) == 0:
                    continue
                    
                current_bar_idx = current_bar_idx[0]
                current_bar = df_1h.iloc[current_bar_idx]
                current_price = current_bar['close']
                atr = current_bar['atr']
                
                # Update trailing if PnL is positive
                current_pnl = 0.0
                if pos.side == Side.LONG:
                    current_pnl = (current_price - pos.entry) * pos.qty
                else:
                    current_pnl = (pos.entry - current_price) * pos.qty
                
                # Apply trailing if profitable
                if current_pnl > 0:
                    updated_pos = update_trailing_pnl_based(pos, current_price, current_pnl, trailing_config, atr)
                    if updated_pos.sl != pos.sl:
                        # Update position with new SL
                        pos.sl = updated_pos.sl
                        pos.peak_pnl_usdt = updated_pos.peak_pnl_usdt
                
                # Check for SL hit
                sl_hit = False
                if pos.side == Side.LONG and current_price <= pos.sl:
                    sl_hit = True
                elif pos.side == Side.SHORT and current_price >= pos.sl:
                    sl_hit = True
                
                if sl_hit:
                    # Close position
                    exit_price = pos.sl
                    if pos.side == Side.LONG:
                        pnl = (exit_price - pos.entry) * pos.qty
                    else:
                        pnl = (pos.entry - exit_price) * pos.qty
                    
                    # Account for fees (maker entry + taker exit = 0.07%)
                    fees = pos.qty * pos.entry * 0.0007
                    net_pnl = pnl - fees
                    
                    trades.append({
                        'symbol': symbol,
                        'side': pos.side.value,
                        'entry': pos.entry,
                        'exit': exit_price,
                        'qty': pos.qty,
                        'pnl_gross': pnl,
                        'fees': fees,
                        'pnl_net': net_pnl,
                        'entry_time': pos.bars_open,
                        'exit_time': current_time,
                        'reason': 'SL_HIT'
                    })
                    
                    total_pnl += net_pnl
                    total_trades += 1
                    if net_pnl > 0:
                        winning_trades += 1
                    else:
                        losing_trades += 1
                    
                    positions_to_close.append(symbol)
                    
            except Exception as e:
                print(f"❌ Ошибка проверки позиции {symbol}: {e}")
                continue
        
        # Remove closed positions
        for symbol in positions_to_close:
            del positions[symbol]
        
        # Look for new entries
        for symbol in symbols:
            if symbol in positions:  # Already have position
                continue
                
            if symbol not in symbol_data:
                continue
            
            try:
                # Get data
                df_1h = symbol_data[symbol]['1h']
                df_15m = symbol_data[symbol]['15m']
                
                # Find current bar
                current_bar_idx_1h = np.where(df_1h['timestamp'] == current_time)[0]
                if len(current_bar_idx_1h) == 0:
                    continue
                current_bar_idx_1h = current_bar_idx_1h[0]
                
                if current_bar_idx_1h < 50:  # Need history
                    continue
                
                # Get current bar data
                current_bar_1h = df_1h.iloc[current_bar_idx_1h]
                current_price = current_bar_1h['close']
                atr = current_bar_1h['atr']
                
                # Regime classification
                natr = current_bar_1h['natr']
                regime = classify_regime(natr, regime_thresholds)
                
                # Market bias (BTC filter)
                try:
                    market_bias = btc_bias.loc[current_time, 'bias'] if current_time in btc_bias.index else 'NEUTRAL'
                except:
                    market_bias = 'NEUTRAL'
                
                # Prepare 1h data with signals (same as live system)
                htf_data = df_1h.iloc[max(0, current_bar_idx_1h-49):current_bar_idx_1h+1].copy()
                
                # Create BTC gate for this timestamp
                btc_gate_data = []
                for ts in htf_data['timestamp'].values:
                    if ts in btc_bias.index:
                        bias = btc_bias.loc[ts, 'bias']
                        btc_gate_data.append({
                            'timestamp': ts,
                            'mkt_long_ok': bias in ['BULL', 'NEUTRAL'],
                            'mkt_short_ok': bias in ['BEAR', 'NEUTRAL']
                        })
                    else:
                        btc_gate_data.append({'timestamp': ts, 'mkt_long_ok': True, 'mkt_short_ok': True})
                
                btc_gate = pd.DataFrame(btc_gate_data)
                
                # Add regime and generate 1h signals
                htf_data = add_regime(htf_data, regime_thresholds)
                htf_signals = generate_signals(htf_data, signal_params, market_gate=btc_gate)
                
                current_1h = htf_signals.iloc[-1]
                signals_found = []
                
                # Check 1h breakout signals (HIGH confidence)
                if current_1h.get('sig_long_breakout', False) and current_1h.get('allow_long', False):
                    signals_found.append({
                        'timeframe': '1h',
                        'side': 'LONG',
                        'setup': 'breakout',
                        'entry': float(current_1h['long_entry_final']),
                        'confidence': 'HIGH'
                    })
                    
                if current_1h.get('sig_short_breakout', False) and current_1h.get('allow_short', False):
                    signals_found.append({
                        'timeframe': '1h',
                        'side': 'SHORT',
                        'setup': 'breakout',
                        'entry': float(current_1h['short_entry_final']),
                        'confidence': 'HIGH'
                    })
                
                # Check 15m LTF signals (MEDIUM confidence)
                current_15m_bars = df_15m[df_15m['timestamp'] <= current_time].tail(200)
                if len(current_15m_bars) >= 50:
                    # Create 15m BTC gate
                    btc_gate_15m_data = []
                    for ts in current_15m_bars['timestamp'].values:
                        if ts in btc_bias.index:
                            bias = btc_bias.loc[ts, 'bias']
                            btc_gate_15m_data.append({
                                'timestamp': ts,
                                'mkt_long_ok': bias in ['BULL', 'NEUTRAL'],
                                'mkt_short_ok': bias in ['BEAR', 'NEUTRAL']
                            })
                        else:
                            btc_gate_15m_data.append({'timestamp': ts, 'mkt_long_ok': True, 'mkt_short_ok': True})
                    
                    btc_gate_15m = pd.DataFrame(btc_gate_15m_data)
                    
                    # Add regime and generate 15m signals
                    ltf_data = add_regime(current_15m_bars, regime_thresholds)
                    ltf_signals = generate_signals(ltf_data, signal_params, market_gate=btc_gate_15m)
                    
                    current_15m = ltf_signals.iloc[-1]
                    
                    # Check 15m LTF signals (inside/trend_continuation/squeeze)
                    ltf_setups = [('inside', 'sig_long_inside', 'sig_short_inside'),
                                  ('tc', 'sig_long_tc', 'sig_short_tc'),
                                  ('sq', 'sig_long_sq', 'sig_short_sq')]
                    
                    for setup_name, long_col, short_col in ltf_setups:
                        if current_15m.get(long_col, False) and current_15m.get('allow_long', False):
                            signals_found.append({
                                'timeframe': '15m',
                                'side': 'LONG',
                                'setup': setup_name,
                                'entry': float(current_15m['long_entry_final']),
                                'confidence': 'MEDIUM'
                            })
                            break
                        
                        if current_15m.get(short_col, False) and current_15m.get('allow_short', False):
                            signals_found.append({
                                'timeframe': '15m',
                                'side': 'SHORT',
                                'setup': setup_name,
                                'entry': float(current_15m['short_entry_final']),
                                'confidence': 'MEDIUM'
                            })
                            break
                
                if not signals_found:
                    continue
                
                # Take first signal (prioritize HIGH confidence)
                signals_found.sort(key=lambda x: 0 if x['confidence'] == 'HIGH' else 1)
                signal = signals_found[0]
                side = Side.LONG if signal['side'] == 'LONG' else Side.SHORT
                entry_price = signal['entry']
                
                # Calculate position size
                qty = margin_usdt / entry_price
                
                # Calculate stop loss
                if side == Side.LONG:
                    sl_price = entry_price - (sl_atr_mult * atr)
                else:
                    sl_price = entry_price + (sl_atr_mult * atr)
                
                # Create position
                r_per_unit = abs(entry_price - sl_price)
                position = Position(
                    side=side,
                    entry=entry_price,
                    sl=sl_price,
                    qty=qty,
                    remaining_qty=qty,
                    r_per_unit=r_per_unit,
                    atr=atr,
                    sl_initial=sl_price,
                    peak_pnl_usdt=0.0,
                    bars_open=current_time
                )
                
                positions[symbol] = position
                
            except Exception as e:
                print(f"❌ Ошибка обработки {symbol}: {e}")
                continue
    
    # Close remaining positions
    for symbol, pos in positions.items():
        try:
            df_1h = symbol_data[symbol]['1h']
            final_price = df_1h.iloc[-1]['close']
            
            if pos.side == Side.LONG:
                pnl = (final_price - pos.entry) * pos.qty
            else:
                pnl = (pos.entry - final_price) * pos.qty
            
            fees = pos.qty * pos.entry * 0.0007
            net_pnl = pnl - fees
            
            trades.append({
                'symbol': symbol,
                'side': pos.side.value,
                'entry': pos.entry,
                'exit': final_price,
                'qty': pos.qty,
                'pnl_gross': pnl,
                'fees': fees,
                'pnl_net': net_pnl,
                'entry_time': pos.bars_open,
                'exit_time': time_index[-1],
                'reason': 'FINAL_CLOSE'
            })
            
            total_pnl += net_pnl
            total_trades += 1
            if net_pnl > 0:
                winning_trades += 1
            else:
                losing_trades += 1
        except:
            continue
    
    print()
    print("📊 РЕЗУЛЬТАТЫ БЭКТЕСТА")
    print("=" * 50)
    
    if total_trades == 0:
        print("❌ Нет сделок")
        return
    
    win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0
    avg_trade = total_pnl / total_trades if total_trades > 0 else 0
    
    winning_pnl = sum([t['pnl_net'] for t in trades if t['pnl_net'] > 0])
    losing_pnl = sum([t['pnl_net'] for t in trades if t['pnl_net'] < 0])
    avg_win = winning_pnl / winning_trades if winning_trades > 0 else 0
    avg_loss = losing_pnl / losing_trades if losing_trades > 0 else 0
    profit_factor = abs(winning_pnl / losing_pnl) if losing_pnl != 0 else float('inf')
    
    print(f"💰 Общая прибыль: ${total_pnl:.2f}")
    print(f"📈 Всего сделок: {total_trades}")
    print(f"✅ Прибыльных: {winning_trades} ({win_rate:.1f}%)")
    print(f"❌ Убыточных: {losing_trades} ({100-win_rate:.1f}%)")
    print(f"📊 Средняя сделка: ${avg_trade:.3f}")
    print(f"🟢 Средняя прибыль: ${avg_win:.3f}")
    print(f"🔴 Средний убыток: ${avg_loss:.3f}")
    print(f"⚖️ Profit Factor: {profit_factor:.2f}")
    
    # Save detailed results
    trades_df = pd.DataFrame(trades)
    
    # Create summary
    summary = {
        'total_pnl': total_pnl,
        'total_trades': total_trades,
        'winning_trades': winning_trades,
        'losing_trades': losing_trades,
        'win_rate': win_rate,
        'avg_trade': avg_trade,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'profit_factor': profit_factor,
        'settings': {
            'margin_usdt': margin_usdt,
            'sl_atr_mult': sl_atr_mult,
            'trailing_activation': trailing_config.activate_pnl_usdt,
            'min_keep_usdt': trailing_config.min_keep_usdt
        }
    }
    
    # Save files
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    trades_file = f"backtest_trades_current_system_{timestamp}.csv"
    summary_file = f"backtest_summary_current_system_{timestamp}.yaml"
    
    trades_df.to_csv(trades_file, index=False)
    
    with open(summary_file, 'w') as f:
        yaml.dump(summary, f, default_flow_style=False)
    
    print()
    print(f"💾 Результаты сохранены:")
    print(f"   Сделки: {trades_file}")
    print(f"   Сводка: {summary_file}")
    
    return summary


if __name__ == "__main__":
    summary = run_backtest()
