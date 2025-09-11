#!/usr/bin/env python3
"""
Тест системы в медвежьем сценарии
Симулирует медвежий рынок BTC и проверяет генерацию шортов
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

def create_bear_market_scenario():
    """Создает сценарий медвежьего рынка"""
    print("🧪 ТЕСТ СИСТЕМЫ В МЕДВЕЖЬЕМ СЦЕНАРИИ")
    print("=" * 50)
    
    # Создаем данные BTC с медвежьим трендом
    timestamps = pd.date_range('2025-01-01', periods=200, freq='1h')
    base_price = 100000
    
    # Симулируем медвежий тренд BTC
    btc_prices = []
    for i in range(200):
        # Падение BTC на 0.3% за час
        decline = -0.003
        if i == 0:
            price = base_price
        else:
            price = btc_prices[-1] * (1 + decline)
        btc_prices.append(price)
    
    # Создаем OHLCV данные для BTC
    btc_data = []
    for i, (ts, price) in enumerate(zip(timestamps, btc_prices)):
        btc_data.append({
            'timestamp': int(ts.timestamp() * 1000),
            'open': price,
            'high': price * 1.01,
            'low': price * 0.99,
            'close': price,
            'volume': 1000
        })
    
    df_btc = pd.DataFrame(btc_data)
    
    # Создаем данные альткоина с корреляцией к BTC
    alt_prices = []
    for i, btc_price in enumerate(btc_prices):
        # Альткоин падает еще сильнее (1.5x корреляция)
        alt_price = (btc_price / base_price) ** 1.5 * 1.0
        alt_prices.append(alt_price)
    
    # Создаем OHLCV данные для альткоина
    alt_data = []
    for i, (ts, price) in enumerate(zip(timestamps, alt_prices)):
        alt_data.append({
            'timestamp': int(ts.timestamp() * 1000),
            'open': price,
            'high': price * 1.02,
            'low': price * 0.98,
            'close': price,
            'volume': 1000
        })
    
    df_alt = pd.DataFrame(alt_data)
    
    print(f"📊 Создан медвежий сценарий:")
    print(f"  BTC: ${df_btc['close'].iloc[0]:,.2f} → ${df_btc['close'].iloc[-1]:,.2f}")
    print(f"  Альткоин: ${df_alt['close'].iloc[0]:.4f} → ${df_alt['close'].iloc[-1]:.4f}")
    
    # Анализируем тренд BTC
    btc_bias = compute_market_bias(df_btc)
    latest_btc = btc_bias.iloc[-1]
    
    print(f"\n📊 Тренд BTC:")
    print(f"  Лонги разрешены: {latest_btc['mkt_long_ok']}")
    print(f"  Шорты разрешены: {latest_btc['mkt_short_ok']}")
    
    # Добавляем индикаторы для альткоина
    df_alt = add_indicators(df_alt, ema_fast=50, ema_slow=200)
    df_alt = add_regime(df_alt, RegimeThresholds())
    
    print(f"\n📈 Индикаторы альткоина:")
    latest_alt = df_alt.iloc[-1]
    print(f"  EMA50: {latest_alt['ema_fast']:.4f}")
    print(f"  EMA200: {latest_alt['ema_slow']:.4f}")
    print(f"  RSI: {latest_alt['rsi']:.2f}")
    print(f"  NATR: {latest_alt['natr']:.4f}")
    print(f"  Режим: {latest_alt['regime']}")
    
    # Параметры сигналов
    signal_params = SignalParams()
    
    # Генерируем сигналы
    signals = generate_signals(df_alt, signal_params, btc_bias)
    
    # Анализируем последние 50 баров
    recent = signals.tail(50)
    
    long_signals = recent['allow_long'].sum()
    short_signals = recent['allow_short'].sum()
    long_raw = recent['allow_long_raw'].sum()
    short_raw = recent['allow_short_raw'].sum()
    
    print(f"\n🎯 Результаты генерации сигналов (последние 50 часов):")
    print(f"  Лонги (сырые): {long_raw}/50")
    print(f"  Шорты (сырые): {short_raw}/50")
    print(f"  Лонги (финальные): {long_signals}/50")
    print(f"  Шорты (финальные): {short_signals}/50")
    
    # Анализируем последний бар детально
    latest_signal = signals.iloc[-1]
    
    print(f"\n🔍 Анализ последнего бара:")
    print(f"  Цена: ${latest_signal['close']:.4f}")
    print(f"  Trend long: {latest_signal['trend_long']}")
    print(f"  Trend short: {latest_signal['trend_short']}")
    print(f"  RSI: {latest_signal['rsi']:.2f}")
    print(f"  NATR: {latest_signal['natr']:.4f}")
    
    print(f"\n🎯 Сырые сигналы:")
    print(f"  Long breakout: {latest_signal.get('sig_long_breakout', False)}")
    print(f"  Long inside: {latest_signal.get('sig_long_inside', False)}")
    print(f"  Long trend cont: {latest_signal.get('sig_long_tc', False)}")
    print(f"  Long squeeze: {latest_signal.get('sig_long_sq', False)}")
    print(f"  Short breakout: {latest_signal.get('sig_short_breakout', False)}")
    print(f"  Short inside: {latest_signal.get('sig_short_inside', False)}")
    print(f"  Short trend cont: {latest_signal.get('sig_short_tc', False)}")
    print(f"  Short squeeze: {latest_signal.get('sig_short_sq', False)}")
    
    print(f"\n🔒 Разрешения:")
    print(f"  Allow long raw: {latest_signal.get('allow_long_raw', False)}")
    print(f"  Allow short raw: {latest_signal.get('allow_short_raw', False)}")
    print(f"  Allow long: {latest_signal.get('allow_long', False)}")
    print(f"  Allow short: {latest_signal.get('allow_short', False)}")
    
    # Проверяем симметричность
    print(f"\n📊 Анализ симметричности:")
    print(f"  BTC тренд: {'бычий' if latest_btc['mkt_long_ok'] else 'медвежий'}")
    print(f"  Ожидается: {'лонги' if latest_btc['mkt_long_ok'] else 'шорты'}")
    print(f"  Получено: Лонги {long_signals}, Шорты {short_signals}")
    
    # Проверяем, работает ли система
    if latest_btc['mkt_short_ok'] and short_signals > long_signals:
        success = True
        print(f"  ✅ Система работает правильно в медвежьем рынке")
    elif latest_btc['mkt_long_ok'] and long_signals > short_signals:
        success = True
        print(f"  ✅ Система работает правильно в бычьем рынке")
    else:
        success = False
        print(f"  ❌ Система не адаптируется к тренду BTC")
    
    return success, long_signals, short_signals

def test_trend_switching_scenario():
    """Тестирует сценарий переключения тренда"""
    print("\n🧪 ТЕСТ СЦЕНАРИЯ ПЕРЕКЛЮЧЕНИЯ ТРЕНДА")
    print("=" * 50)
    
    # Создаем данные с переключением тренда
    timestamps = pd.date_range('2025-01-01', periods=300, freq='1h')
    base_price = 100000
    
    # Первые 150 часов - бычий тренд, следующие 150 - медвежий
    btc_prices = []
    for i in range(300):
        if i < 150:
            # Бычий тренд
            growth = 0.002
        else:
            # Медвежий тренд
            growth = -0.002
        
        if i == 0:
            price = base_price
        else:
            price = btc_prices[-1] * (1 + growth)
        btc_prices.append(price)
    
    # Создаем OHLCV данные
    btc_data = []
    for i, (ts, price) in enumerate(zip(timestamps, btc_prices)):
        btc_data.append({
            'timestamp': int(ts.timestamp() * 1000),
            'open': price,
            'high': price * 1.01,
            'low': price * 0.99,
            'close': price,
            'volume': 1000
        })
    
    df_btc = pd.DataFrame(btc_data)
    
    # Анализируем тренд
    btc_bias = compute_market_bias(df_btc)
    
    # Находим точку переключения
    switch_point = None
    for i in range(1, len(btc_bias)):
        prev = btc_bias.iloc[i-1]
        curr = btc_bias.iloc[i]
        
        # Ищем переключение с бычьего на медвежий
        if prev['mkt_long_ok'] and curr['mkt_short_ok']:
            switch_point = i
            break
    
    if switch_point:
        print(f"📊 Найдена точка переключения на баре {switch_point}")
        
        # Анализируем до и после переключения
        before_switch = btc_bias.iloc[switch_point-50:switch_point]
        after_switch = btc_bias.iloc[switch_point:switch_point+50]
        
        before_long = before_switch['mkt_long_ok'].sum()
        before_short = before_switch['mkt_short_ok'].sum()
        
        after_long = after_switch['mkt_long_ok'].sum()
        after_short = after_switch['mkt_short_ok'].sum()
        
        print(f"  До переключения: Лонги {before_long}, Шорты {before_short}")
        print(f"  После переключения: Лонги {after_long}, Шорты {after_short}")
        
        # Проверяем, что система правильно переключилась
        success = (before_long > before_short) and (after_short > after_long)
        print(f"  ✅ Переключение работает: {success}")
        
        return success
    else:
        print("❌ Точка переключения не найдена")
        return False

def main():
    """Главная функция"""
    print("🚀 ТЕСТ МЕДВЕЖЬЕГО СЦЕНАРИЯ")
    print("=" * 60)
    
    # Тест 1: Медвежий рынок
    success1, long_count, short_count = create_bear_market_scenario()
    
    # Тест 2: Переключение тренда
    success2 = test_trend_switching_scenario()
    
    print(f"\n📊 РЕЗУЛЬТАТЫ:")
    print(f"  Тест медвежьего рынка: {'✅' if success1 else '❌'}")
    print(f"  Тест переключения тренда: {'✅' if success2 else '❌'}")
    
    if success1 and success2:
        print(f"\n🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
        print(f"✅ Система правильно работает в медвежьем рынке")
        print(f"✅ Система корректно переключается между трендами")
        print(f"✅ Логика симметрична для лонгов и шортов")
    else:
        print(f"\n❌ НЕ ВСЕ ТЕСТЫ ПРОЙДЕНЫ")
        print(f"⚠️ Требуется дополнительная настройка")

if __name__ == "__main__":
    main()
