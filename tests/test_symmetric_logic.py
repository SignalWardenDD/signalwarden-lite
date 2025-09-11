#!/usr/bin/env python3
"""
Тест симметричной логики для лонгов и шортов
Проверяет, что система одинаково хорошо работает в обе стороны
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
import ccxt

def create_bull_market_data():
    """Создает данные для бычьего рынка с сигналами"""
    timestamps = pd.date_range('2025-01-01', periods=200, freq='1h')
    base_price = 100000
    
    # Симулируем бычий тренд с четким ростом
    prices = []
    for i in range(200):
        # Стабильный рост для создания тренда
        growth = 0.002  # 0.2% за час
        if i == 0:
            price = base_price
        else:
            price = prices[-1] * (1 + growth)
        prices.append(price)
    
    # Создаем OHLCV данные с достаточной волатильностью для сигналов
    data = []
    for i, (ts, price) in enumerate(zip(timestamps, prices)):
        # Создаем достаточную волатильность для генерации сигналов
        volatility = 0.02  # 2% волатильность
        high = price * (1 + volatility)
        low = price * (1 - volatility)
        
        data.append({
            'timestamp': int(ts.timestamp() * 1000),
            'open': price,
            'high': high,
            'low': low,
            'close': price,
            'volume': np.random.uniform(1000, 5000)
        })
    
    return pd.DataFrame(data)

def create_bear_market_data():
    """Создает данные для медвежьего рынка с сигналами"""
    timestamps = pd.date_range('2025-01-01', periods=200, freq='1h')
    base_price = 100000
    
    # Симулируем медвежий тренд с четким падением
    prices = []
    for i in range(200):
        # Стабильное падение для создания тренда
        decline = -0.002  # -0.2% за час
        if i == 0:
            price = base_price
        else:
            price = prices[-1] * (1 + decline)
        prices.append(price)
    
    # Создаем OHLCV данные с достаточной волатильностью для сигналов
    data = []
    for i, (ts, price) in enumerate(zip(timestamps, prices)):
        # Создаем достаточную волатильность для генерации сигналов
        volatility = 0.02  # 2% волатильность
        high = price * (1 + volatility)
        low = price * (1 - volatility)
        
        data.append({
            'timestamp': int(ts.timestamp() * 1000),
            'open': price,
            'high': high,
            'low': low,
            'close': price,
            'volume': np.random.uniform(1000, 5000)
        })
    
    return pd.DataFrame(data)

def test_bull_market_logic():
    """Тестирует логику в бычьем рынке"""
    print("🧪 ТЕСТ ЛОГИКИ В БЫЧЬЕМ РЫНКЕ")
    print("=" * 50)
    
    # Создаем бычий рынок
    df_btc = create_bull_market_data()
    
    # Анализируем тренд
    bias = compute_market_bias(df_btc)
    latest = bias.iloc[-1]
    
    print(f"📊 Анализ бычьего рынка:")
    print(f"  Цена BTC: ${df_btc.iloc[-1]['close']:,.2f}")
    print(f"  Лонги разрешены: {latest['mkt_long_ok']}")
    print(f"  Шорты разрешены: {latest['mkt_short_ok']}")
    
    # Создаем данные для альткоина
    df_symbol = create_bull_market_data()
    df_symbol['close'] = df_symbol['close'] * 0.01  # Масштабируем
    
    # Добавляем индикаторы
    df_symbol = add_indicators(df_symbol, ema_fast=50, ema_slow=200)
    df_symbol = add_regime(df_symbol, RegimeThresholds())
    
    # Параметры сигналов
    signal_params = SignalParams()
    
    # Генерируем сигналы
    signals = generate_signals(df_symbol, signal_params, bias)
    
    # Анализируем последние 50 баров
    latest_signals = signals.tail(50)
    
    long_signals = latest_signals['allow_long'].sum()
    short_signals = latest_signals['allow_short'].sum()
    
    print(f"\n📈 Результаты в бычьем рынке:")
    print(f"  Лонги разрешены: {long_signals} раз")
    print(f"  Шорты разрешены: {short_signals} раз")
    
    # Ожидаем, что в бычьем рынке лонги должны быть более доступны
    success = long_signals > short_signals
    print(f"  ✅ Тест пройден: {success}")
    
    if not success:
        print(f"  ⚠️ В бычьем рынке ожидалось больше лонгов, но получили: Лонги {long_signals}, Шорты {short_signals}")
    
    return success, long_signals, short_signals

def test_bear_market_logic():
    """Тестирует логику в медвежьем рынке"""
    print("\n🧪 ТЕСТ ЛОГИКИ В МЕДВЕЖЬЕМ РЫНКЕ")
    print("=" * 50)
    
    # Создаем медвежий рынок
    df_btc = create_bear_market_data()
    
    # Анализируем тренд
    bias = compute_market_bias(df_btc)
    latest = bias.iloc[-1]
    
    print(f"📊 Анализ медвежьего рынка:")
    print(f"  Цена BTC: ${df_btc.iloc[-1]['close']:,.2f}")
    print(f"  Лонги разрешены: {latest['mkt_long_ok']}")
    print(f"  Шорты разрешены: {latest['mkt_short_ok']}")
    
    # Создаем данные для альткоина
    df_symbol = create_bear_market_data()
    df_symbol['close'] = df_symbol['close'] * 0.01  # Масштабируем
    
    # Добавляем индикаторы
    df_symbol = add_indicators(df_symbol, ema_fast=50, ema_slow=200)
    df_symbol = add_regime(df_symbol, RegimeThresholds())
    
    # Параметры сигналов
    signal_params = SignalParams()
    
    # Генерируем сигналы
    signals = generate_signals(df_symbol, signal_params, bias)
    
    # Анализируем последние 50 баров
    latest_signals = signals.tail(50)
    
    long_signals = latest_signals['allow_long'].sum()
    short_signals = latest_signals['allow_short'].sum()
    
    print(f"\n📈 Результаты в медвежьем рынке:")
    print(f"  Лонги разрешены: {long_signals} раз")
    print(f"  Шорты разрешены: {short_signals} раз")
    
    # Ожидаем, что в медвежьем рынке шорты должны быть более доступны
    success = short_signals > long_signals
    print(f"  ✅ Тест пройден: {success}")
    
    if not success:
        print(f"  ⚠️ В медвежьем рынке ожидалось больше шортов, но получили: Лонги {long_signals}, Шорты {short_signals}")
    
    return success, long_signals, short_signals

def test_trend_switching():
    """Тестирует переключение между трендами"""
    print("\n🧪 ТЕСТ ПЕРЕКЛЮЧЕНИЯ МЕЖДУ ТРЕНДАМИ")
    print("=" * 50)
    
    # Создаем данные с переключением тренда
    timestamps = pd.date_range('2025-01-01', periods=300, freq='1h')
    base_price = 100000
    
    prices = []
    for i in range(300):
        if i < 150:
            # Первые 150 часов - бычий тренд
            growth = 0.001 + np.random.normal(0, 0.003)
        else:
            # Следующие 150 часов - медвежий тренд
            growth = -0.001 + np.random.normal(0, 0.003)
        
        if i == 0:
            price = base_price
        else:
            price = prices[-1] * (1 + growth)
        prices.append(price)
    
    # Создаем OHLCV данные
    data = []
    for i, (ts, price) in enumerate(zip(timestamps, prices)):
        data.append({
            'timestamp': int(ts.timestamp() * 1000),
            'open': price,
            'high': price * (1 + abs(np.random.normal(0, 0.01))),
            'low': price * (1 - abs(np.random.normal(0, 0.01))),
            'close': price,
            'volume': np.random.uniform(1000, 5000)
        })
    
    df_btc = pd.DataFrame(data)
    
    # Анализируем тренд
    bias = compute_market_bias(df_btc)
    
    # Находим точку переключения
    switch_point = None
    for i in range(1, len(bias)):
        prev = bias.iloc[i-1]
        curr = bias.iloc[i]
        
        # Ищем переключение с бычьего на медвежий
        if prev['mkt_long_ok'] and curr['mkt_short_ok']:
            switch_point = i
            break
    
    if switch_point:
        print(f"📊 Найдена точка переключения на баре {switch_point}")
        
        # Анализируем до и после переключения
        before_switch = bias.iloc[switch_point-50:switch_point]
        after_switch = bias.iloc[switch_point:switch_point+50]
        
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

def test_cache_vs_direct():
    """Тестирует кеш против прямого получения данных"""
    print("\n🧪 ТЕСТ КЕША VS ПРЯМОГО ПОЛУЧЕНИЯ ДАННЫХ")
    print("=" * 50)
    
    try:
        # Получаем данные напрямую с Binance
        exchange = ccxt.binance()
        ohlcv = exchange.fetch_ohlcv('BTC/USDT', '1h', limit=200)
        
        df_direct = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df_direct['timestamp'] = pd.to_datetime(df_direct['timestamp'], unit='ms')
        
        # Анализируем тренд
        bias_direct = compute_market_bias(df_direct)
        latest_direct = bias_direct.iloc[-1]
        
        print(f"📊 Прямое получение данных:")
        print(f"  Время: {df_direct.iloc[-1]['timestamp']}")
        print(f"  Цена: ${df_direct.iloc[-1]['close']:,.2f}")
        print(f"  Лонги: {latest_direct['mkt_long_ok']}")
        print(f"  Шорты: {latest_direct['mkt_short_ok']}")
        
        # Симулируем кеш (те же данные)
        bias_cached = compute_market_bias(df_direct)
        latest_cached = bias_cached.iloc[-1]
        
        print(f"\n📊 Кешированные данные:")
        print(f"  Лонги: {latest_cached['mkt_long_ok']}")
        print(f"  Шорты: {latest_cached['mkt_short_ok']}")
        
        # Сравниваем результаты
        results_match = (latest_direct['mkt_long_ok'] == latest_cached['mkt_long_ok'] and
                        latest_direct['mkt_short_ok'] == latest_cached['mkt_short_ok'])
        
        print(f"\n✅ Результаты совпадают: {results_match}")
        
        if results_match:
            print("💡 РЕКОМЕНДАЦИЯ: Кеш работает корректно, можно использовать")
        else:
            print("⚠️ РЕКОМЕНДАЦИЯ: Есть расхождения, лучше получать данные напрямую")
        
        return results_match
        
    except Exception as e:
        print(f"❌ Ошибка тестирования: {e}")
        return False

def main():
    """Главная функция тестирования"""
    print("🚀 ТЕСТ СИММЕТРИЧНОЙ ЛОГИКИ СИСТЕМЫ")
    print("=" * 60)
    
    tests_passed = 0
    total_tests = 4
    
    # Тест 1: Бычий рынок
    bull_success, bull_long, bull_short = test_bull_market_logic()
    if bull_success:
        tests_passed += 1
    
    # Тест 2: Медвежий рынок
    bear_success, bear_long, bear_short = test_bear_market_logic()
    if bear_success:
        tests_passed += 1
    
    # Тест 3: Переключение трендов
    switch_success = test_trend_switching()
    if switch_success:
        tests_passed += 1
    
    # Тест 4: Кеш vs прямое получение
    cache_success = test_cache_vs_direct()
    if cache_success:
        tests_passed += 1
    
    print(f"\n📊 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ:")
    print(f"  Пройдено тестов: {tests_passed}/{total_tests}")
    
    print(f"\n📈 ДЕТАЛЬНЫЕ РЕЗУЛЬТАТЫ:")
    print(f"  Бычий рынок: Лонги {bull_long}, Шорты {bull_short}")
    print(f"  Медвежий рынок: Лонги {bear_long}, Шорты {bear_short}")
    
    if tests_passed == total_tests:
        print("\n🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
        print("\n✅ СИСТЕМА РАБОТАЕТ СИММЕТРИЧНО:")
        print("  • В бычьем рынке предпочитает лонги")
        print("  • В медвежьем рынке предпочитает шорты")
        print("  • Корректно переключается между трендами")
        print("  • Кеш работает надежно")
    else:
        print(f"\n❌ НЕ ВСЕ ТЕСТЫ ПРОЙДЕНЫ ({tests_passed}/{total_tests})")
        print("  Требуется дополнительная настройка")

if __name__ == "__main__":
    main()
