#!/usr/bin/env python3
"""
Отладка генерации сигналов
Проверяет, почему система не генерирует сигналы
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import numpy as np
from signalwarden_lite.core.market import compute_market_bias
from signalwarden_lite.core.signals import generate_signals, SignalParams
from signalwarden_lite.core.features import add_indicators
from signalwarden_lite.core.regimes import add_regime, RegimeThresholds

def debug_signal_generation():
    """Отлаживает генерацию сигналов"""
    print("🔍 ОТЛАДКА ГЕНЕРАЦИИ СИГНАЛОВ")
    print("=" * 50)
    
    # Создаем простые тестовые данные
    timestamps = pd.date_range('2025-01-01', periods=100, freq='1h')
    base_price = 1.0
    
    # Создаем данные с трендом
    prices = []
    for i in range(100):
        if i < 50:
            # Первые 50 часов - рост
            price = base_price * (1 + i * 0.01)
        else:
            # Следующие 50 часов - падение
            price = prices[49] * (1 - (i-49) * 0.01)
        prices.append(price)
    
    # Создаем OHLCV данные
    data = []
    for i, (ts, price) in enumerate(zip(timestamps, prices)):
        data.append({
            'timestamp': int(ts.timestamp() * 1000),
            'open': price,
            'high': price * 1.02,
            'low': price * 0.98,
            'close': price,
            'volume': 1000
        })
    
    df_symbol = pd.DataFrame(data)
    
    print(f"📊 Созданы тестовые данные:")
    print(f"  Период: {len(df_symbol)} часов")
    print(f"  Цена: ${df_symbol['close'].iloc[0]:.4f} - ${df_symbol['close'].iloc[-1]:.4f}")
    
    # Добавляем индикаторы
    df_symbol = add_indicators(df_symbol, ema_fast=50, ema_slow=200)
    df_symbol = add_regime(df_symbol, RegimeThresholds())
    
    print(f"\n📈 Индикаторы добавлены:")
    print(f"  EMA50: {df_symbol['ema_fast'].iloc[-1]:.4f}")
    print(f"  EMA200: {df_symbol['ema_slow'].iloc[-1]:.4f}")
    print(f"  RSI: {df_symbol['rsi'].iloc[-1]:.2f}")
    print(f"  NATR: {df_symbol['natr'].iloc[-1]:.4f}")
    print(f"  Режим: {df_symbol['regime'].iloc[-1]}")
    
    # Создаем BTC фильтр (бычий тренд)
    df_btc = df_symbol.copy()
    df_btc['close'] = df_btc['close'] * 100000  # Масштабируем для BTC
    
    btc_bias = compute_market_bias(df_btc)
    latest_btc = btc_bias.iloc[-1]
    
    print(f"\n📊 BTC фильтр:")
    print(f"  Лонги разрешены: {latest_btc['mkt_long_ok']}")
    print(f"  Шорты разрешены: {latest_btc['mkt_short_ok']}")
    
    # Параметры сигналов
    signal_params = SignalParams()
    
    print(f"\n⚙️ Параметры сигналов:")
    print(f"  Breakout: {signal_params.setup_breakout}")
    print(f"  Inside: {signal_params.setup_inside}")
    print(f"  Trend continuation: {signal_params.setup_trend_cont}")
    print(f"  Squeeze: {signal_params.setup_squeeze}")
    
    # Генерируем сигналы
    signals = generate_signals(df_symbol, signal_params, btc_bias)
    
    print(f"\n🔍 Анализ последнего бара:")
    latest = signals.iloc[-1]
    
    print(f"  Цена: ${latest['close']:.4f}")
    print(f"  EMA50: {latest['ema_fast']:.4f}")
    print(f"  EMA200: {latest['ema_slow']:.4f}")
    print(f"  RSI: {latest['rsi']:.2f}")
    print(f"  NATR: {latest['natr']:.4f}")
    print(f"  Режим: {latest['regime']}")
    
    print(f"\n📊 Тренды:")
    print(f"  Trend long: {latest['trend_long']}")
    print(f"  Trend short: {latest['trend_short']}")
    
    print(f"\n🎯 Сырые сигналы:")
    print(f"  Long breakout: {latest.get('sig_long_breakout', False)}")
    print(f"  Long inside: {latest.get('sig_long_inside', False)}")
    print(f"  Long trend cont: {latest.get('sig_long_tc', False)}")
    print(f"  Long squeeze: {latest.get('sig_long_sq', False)}")
    print(f"  Short breakout: {latest.get('sig_short_breakout', False)}")
    print(f"  Short inside: {latest.get('sig_short_inside', False)}")
    print(f"  Short trend cont: {latest.get('sig_short_tc', False)}")
    print(f"  Short squeeze: {latest.get('sig_short_sq', False)}")
    
    print(f"\n🔒 Сырые разрешения:")
    print(f"  Allow long raw: {latest.get('allow_long_raw', False)}")
    print(f"  Allow short raw: {latest.get('allow_short_raw', False)}")
    
    print(f"\n🛡️ Фильтры:")
    print(f"  BTC long ok: {latest.get('mkt_long_ok', False)}")
    print(f"  BTC short ok: {latest.get('mkt_short_ok', False)}")
    
    print(f"\n✅ Финальные разрешения:")
    print(f"  Allow long: {latest.get('allow_long', False)}")
    print(f"  Allow short: {latest.get('allow_short', False)}")
    
    # Анализируем последние 10 баров
    print(f"\n📊 Анализ последних 10 баров:")
    recent = signals.tail(10)
    
    long_count = recent['allow_long'].sum()
    short_count = recent['allow_short'].sum()
    long_raw_count = recent['allow_long_raw'].sum()
    short_raw_count = recent['allow_short_raw'].sum()
    
    print(f"  Лонги (сырые): {long_raw_count}/10")
    print(f"  Шорты (сырые): {short_raw_count}/10")
    print(f"  Лонги (финальные): {long_count}/10")
    print(f"  Шорты (финальные): {short_count}/10")
    
    # Проверяем, где теряются сигналы
    if long_raw_count > 0 and long_count == 0:
        print(f"\n❌ ПРОБЛЕМА: Сырые лонги есть, но финальные лонги отсутствуют")
        print(f"   Проверьте BTC фильтр и другие фильтры")
    
    if short_raw_count > 0 and short_count == 0:
        print(f"\n❌ ПРОБЛЕМА: Сырые шорты есть, но финальные шорты отсутствуют")
        print(f"   Проверьте BTC фильтр и другие фильтры")
    
    if long_raw_count == 0 and short_raw_count == 0:
        print(f"\n❌ ПРОБЛЕМА: Нет сырых сигналов вообще")
        print(f"   Проверьте настройки сигналов и условия входа")

def main():
    """Главная функция"""
    debug_signal_generation()

if __name__ == "__main__":
    main()
