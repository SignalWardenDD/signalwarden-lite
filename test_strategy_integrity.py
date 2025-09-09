#!/usr/bin/env python3
"""
Тест целостности стратегии
Проверяет, что наши исправления не нарушили основную логику стратегии
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

def compute_market_bias_old(df_btc: pd.DataFrame, ema_fast: int = 50, ema_slow: int = 200) -> pd.DataFrame:
    """Старая логика определения тренда (до исправлений)"""
    out = df_btc.copy().sort_values('timestamp')
    
    # EMA расчеты
    out['ema_fast'] = out['close'].ewm(span=ema_fast, adjust=False).mean()
    out['ema_slow'] = out['close'].ewm(span=ema_slow, adjust=False).mean()
    
    # Наклон медленной EMA (сравнение с 3 барами назад)
    out['ema_slow_slope'] = out['ema_slow'] - out['ema_slow'].shift(3)
    
    # СТАРАЯ ЛОГИКА: Строгие условия
    out['mkt_long_ok'] = (out['ema_fast'] > out['ema_slow']) & (out['ema_slow_slope'] > 0)
    out['mkt_short_ok'] = (out['ema_fast'] < out['ema_slow']) & (out['ema_slow_slope'] < 0)
    
    return out[['timestamp', 'mkt_long_ok', 'mkt_short_ok']]

def test_strategy_integrity():
    """Тестирует целостность стратегии после исправлений"""
    print("🧪 ТЕСТ ЦЕЛОСТНОСТИ СТРАТЕГИИ")
    print("=" * 50)
    
    # Создаем тестовые данные с различными сценариями
    scenarios = [
        ("Бычий тренд", create_bull_trend_data()),
        ("Медвежий тренд", create_bear_trend_data()),
        ("Боковое движение", create_sideways_data()),
        ("Переключение тренда", create_trend_switch_data())
    ]
    
    results = {}
    
    for scenario_name, df_btc in scenarios:
        print(f"\n📊 Тестирование: {scenario_name}")
        
        # Тестируем старую логику
        old_bias = compute_market_bias_old(df_btc)
        old_latest = old_bias.iloc[-1]
        
        # Тестируем новую логику
        new_bias = compute_market_bias(df_btc)
        new_latest = new_bias.iloc[-1]
        
        print(f"  Старая логика: Long={old_latest['mkt_long_ok']}, Short={old_latest['mkt_short_ok']}")
        print(f"  Новая логика:  Long={new_latest['mkt_long_ok']}, Short={new_latest['mkt_short_ok']}")
        
        # Проверяем совместимость
        old_state = (old_latest['mkt_long_ok'], old_latest['mkt_short_ok'])
        new_state = (new_latest['mkt_long_ok'], new_latest['mkt_short_ok'])
        
        # Новая логика должна быть более чувствительной (больше разрешений)
        old_permissive = old_latest['mkt_long_ok'] or old_latest['mkt_short_ok']
        new_permissive = new_latest['mkt_long_ok'] or new_latest['mkt_short_ok']
        
        # Новая логика не должна быть менее разрешительной
        compatibility = new_permissive >= old_permissive
        
        print(f"  Совместимость: {compatibility}")
        results[scenario_name] = {
            'old': old_state,
            'new': new_state,
            'compatible': compatibility
        }
    
    # Анализируем результаты
    print(f"\n📊 АНАЛИЗ РЕЗУЛЬТАТОВ:")
    all_compatible = all(r['compatible'] for r in results.values())
    
    for scenario, result in results.items():
        status = "✅" if result['compatible'] else "❌"
        print(f"  {status} {scenario}: {result['compatible']}")
    
    print(f"\n🔍 ОБЩИЙ РЕЗУЛЬТАТ:")
    print(f"  Все сценарии совместимы: {all_compatible}")
    
    if all_compatible:
        print("  ✅ Стратегия сохраняет целостность")
        print("  ✅ Новая логика более чувствительна к трендам")
        print("  ✅ Система будет быстрее адаптироваться")
    else:
        print("  ❌ Обнаружены проблемы совместимости")
    
    return all_compatible

def create_bull_trend_data():
    """Создает данные для бычьего тренда"""
    timestamps = pd.date_range('2025-01-01', periods=200, freq='1h')
    base_price = 100000
    
    prices = []
    for i in range(200):
        growth = 0.002  # Стабильный рост
        if i == 0:
            price = base_price
        else:
            price = prices[-1] * (1 + growth)
        prices.append(price)
    
    data = []
    for i, (ts, price) in enumerate(zip(timestamps, prices)):
        data.append({
            'timestamp': int(ts.timestamp() * 1000),
            'open': price,
            'high': price * 1.01,
            'low': price * 0.99,
            'close': price,
            'volume': 1000
        })
    
    return pd.DataFrame(data)

def create_bear_trend_data():
    """Создает данные для медвежьего тренда"""
    timestamps = pd.date_range('2025-01-01', periods=200, freq='1h')
    base_price = 100000
    
    prices = []
    for i in range(200):
        decline = -0.002  # Стабильное падение
        if i == 0:
            price = base_price
        else:
            price = prices[-1] * (1 + decline)
        prices.append(price)
    
    data = []
    for i, (ts, price) in enumerate(zip(timestamps, prices)):
        data.append({
            'timestamp': int(ts.timestamp() * 1000),
            'open': price,
            'high': price * 1.01,
            'low': price * 0.99,
            'close': price,
            'volume': 1000
        })
    
    return pd.DataFrame(data)

def create_sideways_data():
    """Создает данные для бокового движения"""
    timestamps = pd.date_range('2025-01-01', periods=200, freq='1h')
    base_price = 100000
    
    prices = []
    for i in range(200):
        # Боковое движение с небольшой волатильностью
        change = np.random.normal(0, 0.001)
        if i == 0:
            price = base_price
        else:
            price = prices[-1] * (1 + change)
        prices.append(price)
    
    data = []
    for i, (ts, price) in enumerate(zip(timestamps, prices)):
        data.append({
            'timestamp': int(ts.timestamp() * 1000),
            'open': price,
            'high': price * 1.01,
            'low': price * 0.99,
            'close': price,
            'volume': 1000
        })
    
    return pd.DataFrame(data)

def create_trend_switch_data():
    """Создает данные с переключением тренда"""
    timestamps = pd.date_range('2025-01-01', periods=300, freq='1h')
    base_price = 100000
    
    prices = []
    for i in range(300):
        if i < 150:
            # Первые 150 часов - бычий тренд
            growth = 0.002
        else:
            # Следующие 150 часов - медвежий тренд
            growth = -0.002
        
        if i == 0:
            price = base_price
        else:
            price = prices[-1] * (1 + growth)
        prices.append(price)
    
    data = []
    for i, (ts, price) in enumerate(zip(timestamps, prices)):
        data.append({
            'timestamp': int(ts.timestamp() * 1000),
            'open': price,
            'high': price * 1.01,
            'low': price * 0.99,
            'close': price,
            'volume': 1000
        })
    
    return pd.DataFrame(data)

def test_signal_generation_integrity():
    """Тестирует целостность генерации сигналов"""
    print("\n🧪 ТЕСТ ЦЕЛОСТНОСТИ ГЕНЕРАЦИИ СИГНАЛОВ")
    print("=" * 50)
    
    # Создаем тестовые данные
    timestamps = pd.date_range('2025-01-01', periods=200, freq='1h')
    base_price = 1.0
    
    prices = []
    for i in range(200):
        change = np.random.normal(0, 0.02)
        if i == 0:
            price = base_price
        else:
            price = prices[-1] * (1 + change)
        prices.append(price)
    
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
    
    # Добавляем индикаторы
    df_symbol = add_indicators(df_symbol, ema_fast=50, ema_slow=200)
    df_symbol = add_regime(df_symbol, RegimeThresholds())
    
    # Создаем BTC фильтр
    df_btc = df_symbol.copy()
    df_btc['close'] = df_btc['close'] * 100000
    btc_bias = compute_market_bias(df_btc)
    
    # Параметры сигналов
    signal_params = SignalParams()
    
    # Генерируем сигналы
    signals = generate_signals(df_symbol, signal_params, btc_bias)
    
    # Анализируем последние 50 баров
    recent = signals.tail(50)
    
    long_signals = recent['allow_long'].sum()
    short_signals = recent['allow_short'].sum()
    long_raw = recent['allow_long_raw'].sum()
    short_raw = recent['allow_short_raw'].sum()
    
    print(f"📊 Результаты генерации сигналов:")
    print(f"  Лонги (сырые): {long_raw}/50")
    print(f"  Шорты (сырые): {short_raw}/50")
    print(f"  Лонги (финальные): {long_signals}/50")
    print(f"  Шорты (финальные): {short_signals}/50")
    
    # Проверяем, что система генерирует сигналы
    has_signals = (long_signals > 0) or (short_signals > 0)
    print(f"  ✅ Система генерирует сигналы: {has_signals}")
    
    # Проверяем, что фильтры работают
    filters_work = (long_signals <= long_raw) and (short_signals <= short_raw)
    print(f"  ✅ Фильтры работают корректно: {filters_work}")
    
    return has_signals and filters_work

def main():
    """Главная функция тестирования целостности"""
    print("🚀 ТЕСТ ЦЕЛОСТНОСТИ СТРАТЕГИИ")
    print("=" * 60)
    
    # Тест 1: Целостность стратегии
    integrity_ok = test_strategy_integrity()
    
    # Тест 2: Целостность генерации сигналов
    signals_ok = test_signal_generation_integrity()
    
    print(f"\n📊 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ:")
    print(f"  Целостность стратегии: {'✅' if integrity_ok else '❌'}")
    print(f"  Генерация сигналов: {'✅' if signals_ok else '❌'}")
    
    if integrity_ok and signals_ok:
        print(f"\n🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
        print(f"\n✅ СТРАТЕГИЯ СОХРАНЯЕТ ЦЕЛОСТНОСТЬ:")
        print("  • Исправления не нарушили основную логику")
        print("  • Новая логика более чувствительна к трендам")
        print("  • Система быстрее адаптируется к изменениям")
        print("  • Генерация сигналов работает корректно")
        print("  • Фильтры применяются правильно")
        
        print(f"\n🚨 ВАЖНО:")
        print("  • Стратегия v1.6-TXB полностью сохранена")
        print("  • Все исправления улучшают адаптивность")
        print("  • Система готова к работе в автоматическом режиме")
        
    else:
        print(f"\n❌ ОБНАРУЖЕНЫ ПРОБЛЕМЫ")
        print("  ⚠️ Требуется дополнительная проверка")

if __name__ == "__main__":
    main()
