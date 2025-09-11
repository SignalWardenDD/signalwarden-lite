#!/usr/bin/env python3
"""
Детальная отладка генерации сигналов
Проверяет все типы сигналов и их условия
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import numpy as np
import ccxt
from signalwarden_lite.core.market import compute_market_bias
from signalwarden_lite.core.signals import generate_signals, SignalParams
from signalwarden_lite.core.features import add_indicators
from signalwarden_lite.core.regimes import add_regime, RegimeThresholds
from datetime import datetime

def debug_signal_generation_detailed():
    """Детальная отладка генерации сигналов"""
    print("🔍 ДЕТАЛЬНАЯ ОТЛАДКА ГЕНЕРАЦИИ СИГНАЛОВ")
    print("=" * 80)
    
    try:
        exchange = ccxt.binance()
        
        # Получаем данные BTC
        btc_ohlcv = exchange.fetch_ohlcv('BTC/USDT', '1h', limit=200)
        df_btc = pd.DataFrame(btc_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df_btc['timestamp'] = pd.to_datetime(df_btc['timestamp'], unit='ms')
        
        # Анализируем тренд BTC
        btc_bias = compute_market_bias(df_btc)
        latest_btc = btc_bias.iloc[-1]
        
        print(f"📊 BTC MARKET FILTER:")
        print(f"  Лонги разрешены: {latest_btc['mkt_long_ok']}")
        print(f"  Шорты разрешены: {latest_btc['mkt_short_ok']}")
        print()
        
        # Тестируем на паре DOGE (должна быть разрешена)
        symbol = "DOGE/USDT"
        print(f"🔍 ДЕТАЛЬНЫЙ АНАЛИЗ СИГНАЛОВ ДЛЯ {symbol}:")
        
        # Получаем данные 1h
        doge_1h = exchange.fetch_ohlcv(symbol, '1h', limit=200)
        df_1h = pd.DataFrame(doge_1h, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df_1h['timestamp'] = pd.to_datetime(df_1h['timestamp'], unit='ms')
        
        # Добавляем индикаторы
        df_1h = add_indicators(df_1h, ema_fast=50, ema_slow=200)
        df_1h = add_regime(df_1h, RegimeThresholds())
        
        # Параметры сигналов
        signal_params = SignalParams()
        
        # Генерируем сигналы
        signals = generate_signals(df_1h, signal_params, btc_bias)
        latest = signals.iloc[-1]
        
        print(f"  📊 ОСНОВНЫЕ ДАННЫЕ:")
        print(f"    Цена: ${latest['close']:.6f}")
        print(f"    RSI: {latest['rsi']:.1f}")
        print(f"    NATR: {latest['natr']:.2f}%")
        print(f"    Режим: {latest['regime']}")
        print(f"    Allow long: {latest.get('allow_long', False)}")
        print(f"    Allow short: {latest.get('allow_short', False)}")
        
        print(f"\n  🔍 ПРОВЕРКА ВСЕХ ТИПОВ СИГНАЛОВ:")
        
        # Проверяем все колонки с сигналами
        signal_columns = [col for col in signals.columns if 'sig_' in col]
        print(f"    Найдено {len(signal_columns)} типов сигналов:")
        
        for col in signal_columns:
            value = latest.get(col, False)
            if value:
                print(f"      ✅ {col}: {value}")
            else:
                print(f"      ❌ {col}: {value}")
        
        # Проверяем entry точки
        entry_columns = [col for col in signals.columns if 'entry' in col]
        print(f"\n    Entry точки:")
        for col in entry_columns:
            value = latest.get(col, None)
            if value is not None and not pd.isna(value):
                print(f"      {col}: {value:.6f}")
        
        # Проверяем reason колонки
        reason_columns = [col for col in signals.columns if 'reason' in col]
        print(f"\n    Причины сигналов:")
        for col in reason_columns:
            value = latest.get(col, None)
            if value is not None:
                print(f"      {col}: {value}")
        
        # Проверяем 15m данные
        print(f"\n🔍 АНАЛИЗ 15M ДАННЫХ:")
        
        doge_15m = exchange.fetch_ohlcv(symbol, '15m', limit=400)
        df_15m = pd.DataFrame(doge_15m, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df_15m['timestamp'] = pd.to_datetime(df_15m['timestamp'], unit='ms')
        
        # Добавляем индикаторы
        df_15m = add_indicators(df_15m, ema_fast=50, ema_slow=200)
        df_15m = add_regime(df_15m, RegimeThresholds())
        
        # Forward fill BTC gate to 15m
        gate_15m_data = []
        for ts in df_15m['timestamp'].values:
            mask = btc_bias['timestamp'] <= ts
            if mask.any():
                idx = mask.idxmax()
                gate_15m_data.append({
                    'timestamp': ts,
                    'mkt_long_ok': btc_bias.iloc[idx]['mkt_long_ok'],
                    'mkt_short_ok': btc_bias.iloc[idx]['mkt_short_ok']
                })
            else:
                gate_15m_data.append({'timestamp': ts, 'mkt_long_ok': False, 'mkt_short_ok': False})
        gate_15m = pd.DataFrame(gate_15m_data)
        
        # Генерируем сигналы для 15m
        signals_15m = generate_signals(df_15m, signal_params, gate_15m)
        latest_15m = signals_15m.iloc[-1]
        
        print(f"  📊 ОСНОВНЫЕ ДАННЫЕ 15M:")
        print(f"    Цена: ${latest_15m['close']:.6f}")
        print(f"    RSI: {latest_15m['rsi']:.1f}")
        print(f"    NATR: {latest_15m['natr']:.2f}%")
        print(f"    Режим: {latest_15m['regime']}")
        print(f"    Allow long: {latest_15m.get('allow_long', False)}")
        print(f"    Allow short: {latest_15m.get('allow_short', False)}")
        
        # Проверяем все типы сигналов на 15m
        print(f"\n  🔍 ПРОВЕРКА 15M СИГНАЛОВ:")
        
        signal_columns_15m = [col for col in signals_15m.columns if 'sig_' in col]
        for col in signal_columns_15m:
            value = latest_15m.get(col, False)
            if value:
                print(f"      ✅ {col}: {value}")
            else:
                print(f"      ❌ {col}: {value}")
        
        # Проверяем внутренние бары на 15m
        print(f"\n  🔍 ПРОВЕРКА ВНУТРЕННИХ БАРОВ (15M):")
        recent_15m = df_15m.tail(5)
        inside_bars_15m = 0
        for i in range(1, len(recent_15m)):
            if (recent_15m.iloc[i]['high'] <= recent_15m.iloc[i-1]['high'] and 
                recent_15m.iloc[i]['low'] >= recent_15m.iloc[i-1]['low']):
                inside_bars_15m += 1
                print(f"      Бар {i}: Внутренний ✅ (H:{recent_15m.iloc[i]['high']:.6f} <= {recent_15m.iloc[i-1]['high']:.6f}, L:{recent_15m.iloc[i]['low']:.6f} >= {recent_15m.iloc[i-1]['low']:.6f})")
            else:
                print(f"      Бар {i}: Обычный ❌")
        
        print(f"      Всего внутренних баров на 15m: {inside_bars_15m}/4")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Главная функция"""
    print("🚀 ДЕТАЛЬНАЯ ОТЛАДКА ГЕНЕРАЦИИ СИГНАЛОВ")
    print("=" * 80)
    
    # Отладка генерации сигналов
    debug_signal_generation_detailed()
    
    print(f"\n🎯 ИТОГОВЫЙ ВЫВОД:")
    print(f"  Система проверяет множество типов сигналов")
    print(f"  Для генерации сигнала нужны специфические условия")
    print(f"  'No signals detected' означает отсутствие всех типов сигналов")

if __name__ == "__main__":
    main()
