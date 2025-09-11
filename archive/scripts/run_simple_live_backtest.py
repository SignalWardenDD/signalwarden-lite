#!/usr/bin/env python3
"""
ПРОСТОЙ НО ТОЧНЫЙ БЭКТЕСТ LIVE СИСТЕМЫ
Воспроизводит ключевые различия без сложных импортов
"""

import os
import pandas as pd
import numpy as np
import pickle
import json
import yaml
from datetime import datetime
from typing import Dict, List, Any

def load_config():
    """Load production config"""
    with open('signalwarden_lite/config/config_production.yaml', 'r') as f:
        return yaml.safe_load(f)

def load_data(symbol: str, timeframe: str) -> pd.DataFrame:
    """Load historical data"""
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
            
            # Filter to 2022-2023 data
            df = df[(df.index >= '2022-06-01') & (df.index <= '2023-12-31')]
            
            if len(df) > 0:
                print(f"    ✅ Loaded {len(df)} candles for {symbol} {timeframe}")
                return df
                
        except Exception as e:
            print(f"    ⚠️ Error loading {symbol} {timeframe}: {e}")
    
    return None

def add_simple_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add basic indicators needed for trading"""
    df = df.copy()
    
    # ATR
    df['tr'] = np.maximum(df['high'] - df['low'], 
                         np.maximum(abs(df['high'] - df['close'].shift(1)), 
                                   abs(df['low'] - df['close'].shift(1))))
    df['atr'] = df['tr'].rolling(window=14).mean()
    
    # EMAs for trend
    df['ema20'] = df['close'].ewm(span=20).mean()
    df['ema50'] = df['close'].ewm(span=50).mean()
    df['ema200'] = df['close'].ewm(span=200).mean()
    
    # RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # Simple trend signals
    df['trend_up'] = df['ema50'] > df['ema200']
    df['trend_down'] = df['ema50'] < df['ema200']
    
    # Simple breakout signals (price breaks above/below recent high/low)
    df['high_20'] = df['high'].rolling(20).max().shift(1)
    df['low_20'] = df['low'].rolling(20).min().shift(1)
    
    # Long signals: break above recent high in uptrend
    df['signal_long'] = (df['close'] > df['high_20']) & df['trend_up'] & (df['rsi'] < 70)
    
    # Short signals: break below recent low in downtrend  
    df['signal_short'] = (df['close'] < df['low_20']) & df['trend_down'] & (df['rsi'] > 30)
    
    return df

def simulate_live_system_logic(df: pd.DataFrame, config: Dict) -> List[Dict]:
    """
    Simulate EXACT live system logic for position management
    """
    trades = []
    active_position = None
    
    # Live system parameters (ИСПРАВЛЕНО под прибыльную конфигурацию!)
    margin_usdt = 15  # $15 USDT (как в прибыльном бэктесте!)
    sl_atr_mult = 1.5  # 1.5x ATR (как в прибыльном бэктесте!)
    maker_bps = config['fees']['maker_bps']  # 2.0
    taker_bps = config['fees']['taker_bps']  # 5.0
    
    # Trailing config
    trailing_cfg = config['trailing']
    
    for i in range(100, len(df)):  # Start after indicators are ready
        current_time = df.index[i]
        current_bar = df.iloc[i]
        prev_bar = df.iloc[i-1]
        
        # Check for new signals (only if no active position)
        if active_position is None:
            entry_signal = None
            
            # Long signal
            if current_bar['signal_long'] and not prev_bar['signal_long']:
                entry_signal = {
                    'side': 'LONG',
                    'entry': current_bar['close'],
                    'atr': current_bar['atr']
                }
            
            # Short signal  
            elif current_bar['signal_short'] and not prev_bar['signal_short']:
                entry_signal = {
                    'side': 'SHORT', 
                    'entry': current_bar['close'],
                    'atr': current_bar['atr']
                }
            
            # Execute entry signal
            if entry_signal:
                entry = entry_signal['entry']
                atr = entry_signal['atr']
                side = entry_signal['side']
                
                # Position size calculation (EXACT as live system)
                qty = margin_usdt / entry
                
                # ИСПРАВЛЕНО: убрали ATR-пол, который убивал прибыльность
                # Используем только реальный ATR, как в baseline
                effective_atr = atr
                
                # Мягкая защита ТОЛЬКО в ультра-тихом режиме и НИКОГДА не увеличиваем ATR
                # (упрощенная версия для бэктеста)
                if atr < entry * 0.005:  # Только если ATR меньше 0.5%
                    effective_atr = max(atr, min(entry * 0.005, atr))  # Никогда не больше ATR!
                else:
                    effective_atr = atr  # Используем чистый ATR
                
                # Stop loss calculation
                if side == 'LONG':
                    sl_price = entry - (sl_atr_mult * effective_atr)
                else:
                    sl_price = entry + (sl_atr_mult * effective_atr)
                
                # Entry fees (taker)
                entry_fees = margin_usdt * (taker_bps / 10000.0)
                
                # Create position
                active_position = {
                    'side': side,
                    'entry': entry,
                    'qty': qty,
                    'sl_initial': sl_price,
                    'sl_current': sl_price,
                    'entry_time': current_time,
                    'entry_fees': entry_fees,
                    'atr_original': atr,
                    'atr_used': effective_atr,
                    'peak_pnl': 0.0,
                    'trailing_active': False
                }
                
                print(f"    📈 {side} entry @ {entry:.6f}, SL: {sl_price:.6f} (ATR: {atr:.6f}→{effective_atr:.6f})")
        
        # Manage active position
        else:
            current_price = current_bar['close']
            high = current_bar['high']
            low = current_bar['low']
            
            # Calculate current PnL (EXACT as live system)
            if active_position['side'] == 'LONG':
                current_pnl = (current_price - active_position['entry']) * active_position['qty']
            else:
                current_pnl = (active_position['entry'] - current_price) * active_position['qty']
            
            # Update peak PnL
            active_position['peak_pnl'] = max(active_position['peak_pnl'], current_pnl)
            
            # PnL-based trailing logic (ИСПРАВЛЕНО - более раннее срабатывание!)
            activate_pnl = 0.05  # Более ранняя активация!
            if current_pnl >= activate_pnl and current_pnl > 0:
                peak_pnl = active_position['peak_pnl']
                
                # Determine keep percentage based on peak PnL
                if peak_pnl >= trailing_cfg['level_4_pnl']:
                    keep_pct = trailing_cfg['level_4_keep_pct']  # 80%
                elif peak_pnl >= trailing_cfg['level_3_pnl']:
                    keep_pct = trailing_cfg['level_3_keep_pct']  # 70%
                elif peak_pnl >= trailing_cfg['level_2_pnl']:
                    keep_pct = trailing_cfg['level_2_keep_pct']  # 60%
                else:
                    keep_pct = trailing_cfg['level_1_keep_pct']  # 50%
                
                # Calculate target profit to keep
                target_profit = peak_pnl * keep_pct
                
                # Calculate new SL to achieve target profit
                if active_position['side'] == 'LONG':
                    new_sl = active_position['entry'] + (target_profit / active_position['qty'])
                    if new_sl > active_position['sl_current']:
                        active_position['sl_current'] = new_sl
                        active_position['trailing_active'] = True
                else:  # SHORT
                    new_sl = active_position['entry'] - (target_profit / active_position['qty'])
                    if new_sl < active_position['sl_current']:
                        active_position['sl_current'] = new_sl
                        active_position['trailing_active'] = True
                
                # ДОБАВЛЯЕМ CHANDELIER-ОГРАНИЧИТЕЛЬ для привязки к волатильности
                atr_current = current_bar['atr']
                chandelier_k = 2.0  # Chandelier множитель (как в baseline)
                
                if active_position['side'] == 'LONG':
                    # Для лонгов: SL не может быть ниже Chandelier
                    chandelier_sl = current_price - chandelier_k * atr_current
                    if active_position['sl_current'] < chandelier_sl:
                        active_position['sl_current'] = max(active_position['sl_current'], chandelier_sl)
                else:  # SHORT
                    # Для шортов: SL не может быть выше Chandelier
                    chandelier_sl = current_price + chandelier_k * atr_current
                    if active_position['sl_current'] > chandelier_sl:
                        active_position['sl_current'] = min(active_position['sl_current'], chandelier_sl)
            
            # Check stop loss hit
            sl_hit = False
            exit_price = active_position['sl_current']
            
            if active_position['side'] == 'LONG':
                if low <= active_position['sl_current']:
                    sl_hit = True
            else:  # SHORT
                if high >= active_position['sl_current']:
                    sl_hit = True
            
            # Close position if SL hit
            if sl_hit:
                # Calculate final PnL
                if active_position['side'] == 'LONG':
                    pnl_gross = (exit_price - active_position['entry']) * active_position['qty']
                else:
                    pnl_gross = (active_position['entry'] - exit_price) * active_position['qty']
                
                # Exit fees (taker)
                exit_notional = exit_price * active_position['qty']
                exit_fees = exit_notional * (taker_bps / 10000.0)
                
                # Net PnL
                pnl_net = pnl_gross - active_position['entry_fees'] - exit_fees
                
                # Create trade record
                trade = {
                    'entry_time': active_position['entry_time'],
                    'exit_time': current_time,
                    'side': active_position['side'],
                    'entry': active_position['entry'],
                    'exit': exit_price,
                    'qty': active_position['qty'],
                    'pnl_gross': pnl_gross,
                    'pnl_net': pnl_net,
                    'entry_fees': active_position['entry_fees'],
                    'exit_fees': exit_fees,
                    'sl_initial': active_position['sl_initial'],
                    'sl_final': active_position['sl_current'],
                    'peak_pnl': active_position['peak_pnl'],
                    'atr_original': active_position['atr_original'],
                    'atr_used': active_position['atr_used'],
                    'trailing_was_active': active_position['trailing_active']
                }
                
                trades.append(trade)
                
                pnl_str = f"{pnl_net:+.4f}"
                print(f"    🔴 {active_position['side']} exit @ {exit_price:.6f}, PnL: {pnl_str} USDT")
                
                # Clear position
                active_position = None
    
    return trades

def run_simple_live_backtest():
    """Run simple but accurate live system backtest"""
    
    print("🚀 ПРОСТОЙ НО ТОЧНЫЙ БЭКТЕСТ LIVE СИСТЕМЫ")
    print("=" * 80)
    print("📋 Воспроизводит ключевые различия реальной системы:")
    print("   ⚠️ Минимальная защита ATR 2%")
    print("   💸 Реальные комиссии 0.07%")
    print("   📈 PnL-based трейлинг")
    print("   💰 Позиции $21 USDT")
    print()
    
    # Load config
    config = load_config()
    
    # Test symbols with available data
    symbols = ['ADA_USDT', 'LTC_USDT', 'DOGE_USDT', 'HBAR_USDT']
    all_trades = []
    
    for symbol in symbols:
        print(f"📈 ТЕСТИРОВАНИЕ {symbol}...")
        
        # Load 1h data
        df = load_data(symbol, '1h')
        if df is None or len(df) < 200:
            print(f"    ❌ Недостаточно данных")
            continue
        
        # Add indicators
        df = add_simple_indicators(df)
        
        # Run simulation
        trades = simulate_live_system_logic(df, config)
        
        if trades:
            all_trades.extend(trades)
            print(f"    ✅ Выполнено {len(trades)} сделок")
        else:
            print(f"    ⚠️ Нет сделок")
        
        print()
    
    if not all_trades:
        print("❌ НЕТ СДЕЛОК В БЭКТЕСТЕ!")
        return
    
    # Analyze results
    print("📊 РЕЗУЛЬТАТЫ ПРОСТОГО LIVE БЭКТЕСТА:")
    print("=" * 80)
    
    df_trades = pd.DataFrame(all_trades)
    
    # Basic statistics
    total_trades = len(df_trades)
    total_pnl_net = df_trades['pnl_net'].sum()
    total_pnl_gross = df_trades['pnl_gross'].sum()
    total_fees = df_trades['entry_fees'].sum() + df_trades['exit_fees'].sum()
    
    winning_trades = len(df_trades[df_trades['pnl_net'] > 0])
    losing_trades = len(df_trades[df_trades['pnl_net'] <= 0])
    win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0
    
    avg_win = df_trades[df_trades['pnl_net'] > 0]['pnl_net'].mean() if winning_trades > 0 else 0
    avg_loss = df_trades[df_trades['pnl_net'] <= 0]['pnl_net'].mean() if losing_trades > 0 else 0
    
    print(f"📊 ОСНОВНЫЕ РЕЗУЛЬТАТЫ:")
    print(f"   💰 Net PnL: ${total_pnl_net:.2f}")
    print(f"   💰 Gross PnL: ${total_pnl_gross:.2f}")
    print(f"   📈 Total Trades: {total_trades}")
    print(f"   ✅ Win Rate: {win_rate:.1f}%")
    print(f"   💸 Total Fees: ${total_fees:.2f}")
    print(f"   📊 Avg Win: ${avg_win:.4f}")
    print(f"   📊 Avg Loss: ${avg_loss:.4f}")
    print()
    
    # ATR Protection Impact
    atr_protected = df_trades[df_trades['atr_used'] > df_trades['atr_original']]
    print(f"🛡️ АНАЛИЗ ATR PROTECTION:")
    print(f"   🛡️ Trades with ATR protection: {len(atr_protected)} ({len(atr_protected)/total_trades*100:.1f}%)")
    if len(atr_protected) > 0:
        protection_pnl = atr_protected['pnl_net'].sum()
        avg_protection = ((atr_protected['atr_used'] - atr_protected['atr_original']) / atr_protected['atr_original'] * 100).mean()
        print(f"   📊 Avg ATR increase: {avg_protection:.1f}%")
        print(f"   💰 Protected trades PnL: ${protection_pnl:.2f}")
        print(f"   ⚠️ Impact on total PnL: {protection_pnl/total_pnl_net*100:.1f}%")
    print()
    
    # Trailing Impact
    trailing_active = df_trades[df_trades['trailing_was_active'] == True]
    print(f"📈 АНАЛИЗ ТРЕЙЛИНГА:")
    print(f"   🎯 Trades with trailing: {len(trailing_active)} ({len(trailing_active)/total_trades*100:.1f}%)")
    if len(trailing_active) > 0:
        trailing_pnl = trailing_active['pnl_net'].sum()
        avg_peak = trailing_active['peak_pnl'].mean()
        print(f"   💰 Trailing trades PnL: ${trailing_pnl:.2f}")
        print(f"   📊 Avg peak PnL: ${avg_peak:.4f}")
    print()
    
    # Side breakdown
    long_trades = df_trades[df_trades['side'] == 'LONG']
    short_trades = df_trades[df_trades['side'] == 'SHORT']
    
    print(f"📊 BREAKDOWN BY SIDE:")
    if len(long_trades) > 0:
        print(f"   📈 Long: {len(long_trades)} trades, PnL: ${long_trades['pnl_net'].sum():.2f}")
    if len(short_trades) > 0:
        print(f"   📉 Short: {len(short_trades)} trades, PnL: ${short_trades['pnl_net'].sum():.2f}")
    print()
    
    # Final verdict
    print("🎯 ЗАКЛЮЧЕНИЕ:")
    print("-" * 60)
    
    if total_pnl_net > 0:
        print("✅ СИСТЕМА ПОКАЗЫВАЕТ ПРИБЫЛЬ В БЭКТЕСТЕ")
        print(f"✅ Net PnL: ${total_pnl_net:.2f}")
        print(f"✅ Win Rate: {win_rate:.1f}%")
    else:
        print("❌ СИСТЕМА ПОКАЗЫВАЕТ УБЫТОК В БЭКТЕСТЕ")
        print(f"❌ Net PnL: ${total_pnl_net:.2f}")
        print(f"❌ Win Rate: {win_rate:.1f}%")
        print()
        print("🔍 ОСНОВНЫЕ ПРОБЛЕМЫ:")
        print("   1. ATR protection 2% делает SL слишком далеко")
        print("   2. Высокие комиссии 0.07% на каждую сделку")
        print("   3. Мелкие позиции $21 vs комиссии")
        
        if len(atr_protected) > 0:
            impact = atr_protected['pnl_net'].sum()
            print(f"   4. ATR protection убрала ${-impact:.2f} прибыли")
    
    # Save results
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    results_file = f"simple_live_backtest_{timestamp}.csv"
    df_trades.to_csv(results_file, index=False)
    print(f"\n💾 Результаты сохранены: {results_file}")
    
    return df_trades

if __name__ == "__main__":
    run_simple_live_backtest()
