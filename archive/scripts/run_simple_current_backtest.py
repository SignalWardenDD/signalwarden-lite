#!/usr/bin/env python3
"""
Упрощенный но точный бэктест текущей системы с новым PnL-трейлингом
Использует данные из @data/ и проверяет результаты
"""

import sys
import os
import pandas as pd
import numpy as np
import pickle
from datetime import datetime, timedelta
import yaml
import warnings
warnings.filterwarnings('ignore')

# Add project root to path
sys.path.append('.')

from signalwarden_lite.core.types import Position, Side
from signalwarden_lite.core.trailing import TrailingConfig, update_trailing_pnl_based


def load_data(symbol: str, timeframe: str) -> pd.DataFrame:
    """Загрузка данных из historical_candles/"""
    pkl_file = f"data/historical_candles/{symbol}_{timeframe}.pkl"
    
    if not os.path.exists(pkl_file):
        return pd.DataFrame()
    
    try:
        with open(pkl_file, 'rb') as f:
            df = pickle.load(f)
        
        # Ensure timestamp column
        if 'timestamp' not in df.columns:
            if df.index.name == 'timestamp':
                df = df.reset_index()
            else:
                return pd.DataFrame()
        
        # Convert timestamp to datetime if needed
        if df['timestamp'].dtype in ['int64', 'float64']:
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
        elif df['timestamp'].dtype == 'object':
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Filter 2022-2024
        start_dt = pd.to_datetime('2022-01-01')
        end_dt = pd.to_datetime('2024-01-01')
        df = df[(df['timestamp'] >= start_dt) & (df['timestamp'] < end_dt)]
        
        # Add simple indicators
        df['returns'] = df['close'].pct_change()
        df['volatility'] = df['returns'].rolling(20).std()
        df['atr'] = (df['high'] - df['low']).rolling(14).mean()
        df['rsi'] = calculate_rsi(df['close'], 14)
        
        df = df.sort_values('timestamp').reset_index(drop=True)
        return df
        
    except Exception as e:
        print(f"❌ Ошибка загрузки {pkl_file}: {e}")
        return pd.DataFrame()


def calculate_rsi(prices, period=14):
    """Calculate RSI"""
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def generate_simple_signals(df):
    """Генерация простых сигналов на основе волатильности и momentum"""
    signals = pd.DataFrame(index=df.index)
    signals['timestamp'] = df['timestamp']
    
    # Простые условия входа (аналог оригинальной стратегии)
    # Breakout условие: цена пробивает максимум последних 20 баров
    signals['high_20'] = df['high'].rolling(20).max().shift(1)
    signals['low_20'] = df['low'].rolling(20).min().shift(1)
    
    # Long signal: пробой вверх + RSI не перекуплен + достаточная волатильность
    signals['long_breakout'] = (
        (df['close'] > signals['high_20']) & 
        (df['rsi'] < 70) & 
        (df['atr'] > df['close'] * 0.005)  # Минимальная волатильность
    )
    
    # Short signal: пробой вниз + RSI не перепродан + достаточная волатильность  
    signals['short_breakout'] = (
        (df['close'] < signals['low_20']) & 
        (df['rsi'] > 30) & 
        (df['atr'] > df['close'] * 0.005)
    )
    
    return signals


def run_simple_backtest():
    """Простой но точный бэктест"""
    
    print("🚀 УПРОЩЕННЫЙ БЭКТЕСТ ТЕКУЩЕЙ СИСТЕМЫ")
    print("=" * 60)
    
    # Load configuration
    with open('signalwarden_lite/config/config_production.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    # Parameters
    symbols = config['symbols']
    margin_usdt = config['risk']['margin_usdt']  # 21 USDT
    sl_atr_mult = config['risk']['sl_atr_mult']  # 1.5
    
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
    
    print(f"📊 Размер позиции: ${margin_usdt} USDT")
    print(f"📊 SL множитель: {sl_atr_mult}x ATR")
    print(f"📊 Трейлинг активация: ${trailing_config.activate_pnl_usdt}")
    print(f"📊 Минимальная защита: ${trailing_config.min_keep_usdt}")
    print()
    
    # Load data
    print("📊 ЗАГРУЗКА ДАННЫХ...")
    symbol_data = {}
    
    for symbol in symbols:
        df_1h = load_data(symbol, '1h')
        if df_1h.empty or len(df_1h) < 100:
            print(f"❌ Пропуск {symbol} - недостаточно данных")
            continue
        
        symbol_data[symbol] = df_1h
        print(f"✅ {symbol}: {len(df_1h)} свечей")
    
    if not symbol_data:
        print("❌ Нет данных для бэктеста")
        return
    
    print(f"✅ Загружено {len(symbol_data)} символов")
    print()
    
    # Backtest
    trades = []
    positions = {}
    total_pnl = 0.0
    
    # Get common time range
    all_timestamps = set()
    for df in symbol_data.values():
        all_timestamps.update(df['timestamp'].values)
    
    timestamps = sorted(all_timestamps)
    print(f"🔄 Период: {timestamps[0]} - {timestamps[-1]}")
    print(f"🔄 Всего временных точек: {len(timestamps)}")
    print()
    
    print("🔄 ЗАПУСК БЭКТЕСТА...")
    
    for i, current_time in enumerate(timestamps):
        if i % 1000 == 0:
            progress = (i / len(timestamps)) * 100
            print(f"   Прогресс: {progress:.1f}%")
        
        # Check existing positions for exits
        positions_to_close = []
        
        for symbol, pos in positions.items():
            if symbol not in symbol_data:
                continue
                
            df = symbol_data[symbol]
            current_bars = df[df['timestamp'] == current_time]
            
            if current_bars.empty:
                continue
                
            current_bar = current_bars.iloc[0]
            current_price = current_bar['close']
            atr = current_bar['atr']
            
            # Calculate current PnL
            if pos.side == Side.LONG:
                current_pnl = (current_price - pos.entry) * pos.qty
            else:
                current_pnl = (pos.entry - current_price) * pos.qty
            
            # Apply trailing if profitable
            if current_pnl > 0:
                updated_pos = update_trailing_pnl_based(pos, current_price, current_pnl, trailing_config, atr)
                if updated_pos.sl != pos.sl:
                    pos.sl = updated_pos.sl
                    pos.peak_pnl_usdt = updated_pos.peak_pnl_usdt
            
            # Check SL hit
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
                
                # Account for fees (0.07% total)
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
                positions_to_close.append(symbol)
        
        # Remove closed positions
        for symbol in positions_to_close:
            del positions[symbol]
        
        # Look for new entries
        for symbol in symbols:
            if symbol in positions:  # Already have position
                continue
                
            if symbol not in symbol_data:
                continue
            
            df = symbol_data[symbol]
            current_bars = df[df['timestamp'] == current_time]
            
            if current_bars.empty:
                continue
            
            current_bar = current_bars.iloc[0]
            
            # Need enough history
            historical_bars = df[df['timestamp'] <= current_time].tail(50)
            if len(historical_bars) < 50:
                continue
            
            # Generate signals
            signals = generate_simple_signals(historical_bars)
            current_signal = signals.iloc[-1]
            
            # Check for entry signals
            entry_signal = None
            if current_signal['long_breakout']:
                entry_signal = {'side': Side.LONG, 'price': current_bar['close']}
            elif current_signal['short_breakout']:
                entry_signal = {'side': Side.SHORT, 'price': current_bar['close']}
            
            if entry_signal:
                # Create position
                entry_price = entry_signal['price']
                side = entry_signal['side']
                qty = margin_usdt / entry_price
                atr = current_bar['atr']
                
                # Calculate stop loss
                if side == Side.LONG:
                    sl_price = entry_price - (sl_atr_mult * atr)
                else:
                    sl_price = entry_price + (sl_atr_mult * atr)
                
                position = Position(
                    side=side,
                    entry=entry_price,
                    sl=sl_price,
                    qty=qty,
                    remaining_qty=qty,
                    r_per_unit=abs(entry_price - sl_price),
                    atr=atr,
                    sl_initial=sl_price,
                    peak_pnl_usdt=0.0,
                    bars_open=current_time
                )
                
                positions[symbol] = position
    
    # Close remaining positions
    final_time = timestamps[-1]
    for symbol, pos in positions.items():
        df = symbol_data[symbol]
        final_bars = df[df['timestamp'] == final_time]
        
        if not final_bars.empty:
            final_price = final_bars.iloc[0]['close']
            
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
                'exit_time': final_time,
                'reason': 'FINAL_CLOSE'
            })
            
            total_pnl += net_pnl
    
    print()
    print("📊 РЕЗУЛЬТАТЫ БЭКТЕСТА")
    print("=" * 50)
    
    if not trades:
        print("❌ Нет сделок")
        return
    
    total_trades = len(trades)
    winning_trades = len([t for t in trades if t['pnl_net'] > 0])
    losing_trades = total_trades - winning_trades
    win_rate = (winning_trades / total_trades) * 100
    
    avg_trade = total_pnl / total_trades
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
    
    # Show some example trades
    print()
    print("📋 ПРИМЕРЫ СДЕЛОК:")
    for i, trade in enumerate(trades[:10]):
        pnl_color = "🟢" if trade['pnl_net'] > 0 else "🔴"
        print(f"   {i+1}. {trade['symbol']} {trade['side']} @ ${trade['entry']:.4f} → ${trade['exit']:.4f} {pnl_color} ${trade['pnl_net']:.3f}")
    
    # Save results
    trades_df = pd.DataFrame(trades)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"current_system_backtest_{timestamp}.csv"
    trades_df.to_csv(filename, index=False)
    
    print(f"💾 Результаты сохранены: {filename}")
    
    return {
        'total_pnl': total_pnl,
        'total_trades': total_trades,
        'win_rate': win_rate,
        'profit_factor': profit_factor,
        'avg_trade': avg_trade
    }


if __name__ == "__main__":
    results = run_simple_backtest()
