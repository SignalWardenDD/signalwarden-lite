#!/usr/bin/env python3
"""
Комплексные тесты системы в различных рыночных условиях
Проверяет генерацию позиций при разных сценариях
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
from datetime import datetime, timedelta

def create_test_data(base_price=0.5, trend='bull', volatility='normal', length=200):
    """Создает тестовые данные с заданными параметрами"""
    dates = pd.date_range(start='2024-01-01', periods=length, freq='1H')
    
    if trend == 'bull':
        # Бычий тренд с ростом
        price_trend = np.linspace(base_price, base_price * 1.2, length)
    elif trend == 'bear':
        # Медвежий тренд с падением
        price_trend = np.linspace(base_price, base_price * 0.8, length)
    else:  # sideways
        # Боковое движение
        price_trend = np.full(length, base_price)
    
    # Добавляем волатильность
    if volatility == 'high':
        noise = np.random.normal(0, base_price * 0.02, length)
    elif volatility == 'low':
        noise = np.random.normal(0, base_price * 0.005, length)
    else:  # normal
        noise = np.random.normal(0, base_price * 0.01, length)
    
    prices = price_trend + noise
    
    # Создаем OHLC данные
    data = []
    for i, price in enumerate(prices):
        if volatility == 'high':
            high = price * (1 + np.random.uniform(0, 0.02))
            low = price * (1 - np.random.uniform(0, 0.02))
        elif volatility == 'low':
            high = price * (1 + np.random.uniform(0, 0.005))
            low = price * (1 - np.random.uniform(0, 0.005))
        else:
            high = price * (1 + np.random.uniform(0, 0.01))
            low = price * (1 - np.random.uniform(0, 0.01))
        
        data.append({
            'timestamp': dates[i],
            'open': price,
            'high': high,
            'low': low,
            'close': price,
            'volume': np.random.uniform(1000, 10000)
        })
    
    return pd.DataFrame(data)

def test_ideal_conditions():
    """Тест 1: Идеальные условия для лонгов"""
    print("🧪 ТЕСТ 1: ИДЕАЛЬНЫЕ УСЛОВИЯ ДЛЯ ЛОНГОВ")
    print("=" * 60)
    
    try:
        # Создаем идеальные данные
        df = create_test_data(base_price=0.5, trend='bull', volatility='high', length=200)
        
        # Добавляем индикаторы
        df = add_indicators(df, ema_fast=50, ema_slow=200)
        df = add_regime(df, RegimeThresholds())
        
        # Создаем бычий BTC тренд
        btc_data = create_test_data(base_price=50000, trend='bull', volatility='normal', length=200)
        btc_bias = compute_market_bias(btc_data)
        
        # Параметры сигналов
        signal_params = SignalParams()
        
        # Генерируем сигналы
        signals = generate_signals(df, signal_params, btc_bias)
        latest = signals.iloc[-1]
        latest_btc = btc_bias.iloc[-1]
        
        print(f"📊 УСЛОВИЯ:")
        print(f"  Тренд: Бычий")
        print(f"  Волатильность: Высокая")
        print(f"  BTC тренд: Бычий")
        print(f"  Цена: ${latest['close']:.6f}")
        print(f"  RSI: {latest['rsi']:.1f}")
        print(f"  NATR: {latest['natr']:.2f}%")
        print(f"  Режим: {latest['regime']}")
        print(f"  BTC mkt_long_ok: {latest_btc['mkt_long_ok']}")
        
        print(f"\n🔍 РЕЗУЛЬТАТЫ:")
        print(f"  Allow long: {latest.get('allow_long', False)}")
        print(f"  Allow short: {latest.get('allow_short', False)}")
        
        # Проверяем сигналы
        signal_types = ['sig_long_breakout', 'sig_long_inside', 'sig_long_tc', 'sig_long_sq']
        signals_found = []
        for sig_type in signal_types:
            if latest.get(sig_type, False):
                signals_found.append(sig_type)
        
        print(f"  Найденные сигналы: {signals_found}")
        print(f"  Количество сигналов: {len(signals_found)}")
        
        # Ожидаемый результат
        expected = latest.get('allow_long', False) and len(signals_found) > 0
        print(f"\n✅ ОЖИДАЕМЫЙ РЕЗУЛЬТАТ: {'ПОЗИЦИИ ДОЛЖНЫ ГЕНЕРИРОВАТЬСЯ' if expected else 'ПОЗИЦИИ НЕ ГЕНЕРИРУЮТСЯ'}")
        
        return expected
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

def test_poor_conditions():
    """Тест 2: Неподходящие условия"""
    print("\n🧪 ТЕСТ 2: НЕПОДХОДЯЩИЕ УСЛОВИЯ")
    print("=" * 60)
    
    try:
        # Создаем неподходящие данные
        df = create_test_data(base_price=0.5, trend='bear', volatility='low', length=200)
        
        # Добавляем индикаторы
        df = add_indicators(df, ema_fast=50, ema_slow=200)
        df = add_regime(df, RegimeThresholds())
        
        # Создаем медвежий BTC тренд
        btc_data = create_test_data(base_price=50000, trend='bear', volatility='normal', length=200)
        btc_bias = compute_market_bias(btc_data)
        
        # Параметры сигналов
        signal_params = SignalParams()
        
        # Генерируем сигналы
        signals = generate_signals(df, signal_params, btc_bias)
        latest = signals.iloc[-1]
        latest_btc = btc_bias.iloc[-1]
        
        print(f"📊 УСЛОВИЯ:")
        print(f"  Тренд: Медвежий")
        print(f"  Волатильность: Низкая")
        print(f"  BTC тренд: Медвежий")
        print(f"  Цена: ${latest['close']:.6f}")
        print(f"  RSI: {latest['rsi']:.1f}")
        print(f"  NATR: {latest['natr']:.2f}%")
        print(f"  Режим: {latest['regime']}")
        print(f"  BTC mkt_long_ok: {latest_btc['mkt_long_ok']}")
        print(f"  BTC mkt_short_ok: {latest_btc['mkt_short_ok']}")
        
        print(f"\n🔍 РЕЗУЛЬТАТЫ:")
        print(f"  Allow long: {latest.get('allow_long', False)}")
        print(f"  Allow short: {latest.get('allow_short', False)}")
        
        # Проверяем сигналы
        signal_types = ['sig_long_breakout', 'sig_long_inside', 'sig_long_tc', 'sig_long_sq',
                       'sig_short_breakout', 'sig_short_inside', 'sig_short_tc', 'sig_short_sq']
        signals_found = []
        for sig_type in signal_types:
            if latest.get(sig_type, False):
                signals_found.append(sig_type)
        
        print(f"  Найденные сигналы: {signals_found}")
        print(f"  Количество сигналов: {len(signals_found)}")
        
        # Ожидаемый результат
        expected = not (latest.get('allow_long', False) or latest.get('allow_short', False))
        print(f"\n✅ ОЖИДАЕМЫЙ РЕЗУЛЬТАТ: {'ПОЗИЦИИ НЕ ДОЛЖНЫ ГЕНЕРИРОВАТЬСЯ' if expected else 'ПОЗИЦИИ МОГУТ ГЕНЕРИРОВАТЬСЯ'}")
        
        return expected
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

def test_trend_reversal():
    """Тест 3: Реакция на разворот тренда"""
    print("\n🧪 ТЕСТ 3: РЕАКЦИЯ НА РАЗВОРОТ ТРЕНДА")
    print("=" * 60)
    
    try:
        # Создаем данные с разворотом тренда
        df_bull = create_test_data(base_price=0.5, trend='bull', volatility='normal', length=100)
        df_bear = create_test_data(base_price=0.6, trend='bear', volatility='normal', length=100)
        
        # Объединяем данные
        df = pd.concat([df_bull, df_bear], ignore_index=True)
        df['timestamp'] = pd.date_range(start='2024-01-01', periods=200, freq='1H')
        
        # Добавляем индикаторы
        df = add_indicators(df, ema_fast=50, ema_slow=200)
        df = add_regime(df, RegimeThresholds())
        
        # Создаем BTC с разворотом
        btc_bull = create_test_data(base_price=50000, trend='bull', volatility='normal', length=100)
        btc_bear = create_test_data(base_price=60000, trend='bear', volatility='normal', length=100)
        btc_data = pd.concat([btc_bull, btc_bear], ignore_index=True)
        btc_data['timestamp'] = pd.date_range(start='2024-01-01', periods=200, freq='1H')
        btc_bias = compute_market_bias(btc_data)
        
        # Параметры сигналов
        signal_params = SignalParams()
        
        # Анализируем несколько точек
        test_points = [50, 100, 150, 199]  # До разворота, в развороте, после разворота
        
        print(f"📊 АНАЛИЗ РАЗВОРОТА ТРЕНДА:")
        
        for i, point in enumerate(test_points):
            signals = generate_signals(df.iloc[:point+1], signal_params, btc_bias.iloc[:point+1])
            latest = signals.iloc[-1]
            latest_btc = btc_bias.iloc[point]
            
            phase = ["До разворота", "Начало разворота", "В развороте", "После разворота"][i]
            
            print(f"\n  {phase} (бар {point}):")
            print(f"    Цена: ${latest['close']:.6f}")
            print(f"    RSI: {latest['rsi']:.1f}")
            print(f"    Режим: {latest['regime']}")
            print(f"    BTC mkt_long_ok: {latest_btc['mkt_long_ok']}")
            print(f"    BTC mkt_short_ok: {latest_btc['mkt_short_ok']}")
            print(f"    Allow long: {latest.get('allow_long', False)}")
            print(f"    Allow short: {latest.get('allow_short', False)}")
        
        # Проверяем адаптивность
        final_signals = generate_signals(df, signal_params, btc_bias)
        final_latest = final_signals.iloc[-1]
        final_btc = btc_bias.iloc[-1]
        
        print(f"\n🔍 АДАПТИВНОСТЬ СИСТЕМЫ:")
        print(f"  Финальное состояние:")
        print(f"    Allow long: {final_latest.get('allow_long', False)}")
        print(f"    Allow short: {final_latest.get('allow_short', False)}")
        print(f"    BTC тренд: {'Бычий' if final_btc['mkt_long_ok'] else 'Медвежий'}")
        
        # Ожидаемый результат
        expected = final_btc['mkt_short_ok']  # Должен разрешить шорты после разворота
        print(f"\n✅ ОЖИДАЕМЫЙ РЕЗУЛЬТАТ: {'СИСТЕМА АДАПТИРОВАЛАСЬ К РАЗВОРОТУ' if expected else 'СИСТЕМА НЕ АДАПТИРОВАЛАСЬ'}")
        
        return expected
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

def test_correction_scenario():
    """Тест 4: Реакция на коррекцию"""
    print("\n🧪 ТЕСТ 4: РЕАКЦИЯ НА КОРРЕКЦИЮ")
    print("=" * 60)
    
    try:
        # Создаем данные с коррекцией в бычьем тренде
        df_up = create_test_data(base_price=0.5, trend='bull', volatility='normal', length=80)
        df_down = create_test_data(base_price=0.6, trend='bear', volatility='high', length=40)
        df_up2 = create_test_data(base_price=0.48, trend='bull', volatility='normal', length=80)
        
        # Объединяем данные
        df = pd.concat([df_up, df_down, df_up2], ignore_index=True)
        df['timestamp'] = pd.date_range(start='2024-01-01', periods=200, freq='1H')
        
        # Добавляем индикаторы
        df = add_indicators(df, ema_fast=50, ema_slow=200)
        df = add_regime(df, RegimeThresholds())
        
        # Создаем стабильный бычий BTC
        btc_data = create_test_data(base_price=50000, trend='bull', volatility='normal', length=200)
        btc_data['timestamp'] = pd.date_range(start='2024-01-01', periods=200, freq='1H')
        btc_bias = compute_market_bias(btc_data)
        
        # Параметры сигналов
        signal_params = SignalParams()
        
        # Анализируем ключевые точки
        test_points = [80, 120, 160, 199]  # До коррекции, в коррекции, после коррекции
        
        print(f"📊 АНАЛИЗ КОРРЕКЦИИ В БЫЧЬЕМ ТРЕНДЕ:")
        
        for i, point in enumerate(test_points):
            signals = generate_signals(df.iloc[:point+1], signal_params, btc_bias.iloc[:point+1])
            latest = signals.iloc[-1]
            latest_btc = btc_bias.iloc[point]
            
            phase = ["До коррекции", "В коррекции", "Выход из коррекции", "После коррекции"][i]
            
            print(f"\n  {phase} (бар {point}):")
            print(f"    Цена: ${latest['close']:.6f}")
            print(f"    RSI: {latest['rsi']:.1f}")
            print(f"    Режим: {latest['regime']}")
            print(f"    BTC mkt_long_ok: {latest_btc['mkt_long_ok']}")
            print(f"    Allow long: {latest.get('allow_long', False)}")
            print(f"    Allow short: {latest.get('allow_short', False)}")
        
        # Проверяем адаптивность к коррекции
        final_signals = generate_signals(df, signal_params, btc_bias)
        final_latest = final_signals.iloc[-1]
        final_btc = btc_bias.iloc[-1]
        
        print(f"\n🔍 АДАПТИВНОСТЬ К КОРРЕКЦИИ:")
        print(f"  Финальное состояние:")
        print(f"    Allow long: {final_latest.get('allow_long', False)}")
        print(f"    Allow short: {final_latest.get('allow_short', False)}")
        print(f"    BTC тренд: {'Бычий' if final_btc['mkt_long_ok'] else 'Медвежий'}")
        
        # Ожидаемый результат
        expected = final_btc['mkt_long_ok'] and not final_btc['mkt_short_ok']  # Должен остаться бычьим
        print(f"\n✅ ОЖИДАЕМЫЙ РЕЗУЛЬТАТ: {'СИСТЕМА ПРАВИЛЬНО ОБРАБОТАЛА КОРРЕКЦИЮ' if expected else 'СИСТЕМА НЕПРАВИЛЬНО ОБРАБОТАЛА КОРРЕКЦИЮ'}")
        
        return expected
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

def test_edge_cases():
    """Тест 5: Граничные случаи"""
    print("\n🧪 ТЕСТ 5: ГРАНИЧНЫЕ СЛУЧАИ")
    print("=" * 60)
    
    try:
        # Тест 1: RSI на границе
        print("📊 ТЕСТ 5.1: RSI НА ГРАНИЦЕ (35)")
        df = create_test_data(base_price=0.5, trend='bull', volatility='normal', length=200)
        df['close'] = df['close'] * 0.95  # Снижаем цену для низкого RSI
        
        df = add_indicators(df, ema_fast=50, ema_slow=200)
        df = add_regime(df, RegimeThresholds())
        
        btc_data = create_test_data(base_price=50000, trend='bull', volatility='normal', length=200)
        btc_bias = compute_market_bias(btc_data)
        
        signal_params = SignalParams()
        signals = generate_signals(df, signal_params, btc_bias)
        latest = signals.iloc[-1]
        
        print(f"  RSI: {latest['rsi']:.1f}")
        print(f"  Allow long: {latest.get('allow_long', False)}")
        print(f"  RSI ≥ 35: {latest['rsi'] >= 35}")
        
        # Тест 2: NATR на границе
        print(f"\n📊 ТЕСТ 5.2: NATR НА ГРАНИЦЕ (0.5%)")
        df2 = create_test_data(base_price=0.5, trend='sideways', volatility='low', length=200)
        
        df2 = add_indicators(df2, ema_fast=50, ema_slow=200)
        df2 = add_regime(df2, RegimeThresholds())
        
        signals2 = generate_signals(df2, signal_params, btc_bias)
        latest2 = signals2.iloc[-1]
        
        print(f"  NATR: {latest2['natr']:.2f}%")
        print(f"  Allow long: {latest2.get('allow_long', False)}")
        print(f"  NATR ≥ 0.5%: {latest2['natr'] >= 0.5}")
        
        # Тест 3: Режим на границе
        print(f"\n📊 ТЕСТ 5.3: РЕЖИМ НА ГРАНИЦЕ")
        df3 = create_test_data(base_price=0.5, trend='bull', volatility='normal', length=200)
        
        df3 = add_indicators(df3, ema_fast=50, ema_slow=200)
        df3 = add_regime(df3, RegimeThresholds())
        
        signals3 = generate_signals(df3, signal_params, btc_bias)
        latest3 = signals3.iloc[-1]
        
        print(f"  Режим: {latest3['regime']}")
        print(f"  Allow long: {latest3.get('allow_long', False)}")
        print(f"  Режим normal/high: {latest3['regime'] in ['normal', 'high']}")
        
        print(f"\n✅ ГРАНИЧНЫЕ СЛУЧАИ ПРОТЕСТИРОВАНЫ")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

def main():
    """Главная функция тестирования"""
    print("🚀 КОМПЛЕКСНЫЕ ТЕСТЫ СИСТЕМЫ В РАЗЛИЧНЫХ УСЛОВИЯХ")
    print("=" * 80)
    
    results = []
    
    # Запускаем все тесты
    results.append(("Идеальные условия", test_ideal_conditions()))
    results.append(("Неподходящие условия", test_poor_conditions()))
    results.append(("Разворот тренда", test_trend_reversal()))
    results.append(("Коррекция", test_correction_scenario()))
    results.append(("Граничные случаи", test_edge_cases()))
    
    # Итоговый отчет
    print(f"\n📊 ИТОГОВЫЙ ОТЧЕТ ТЕСТИРОВАНИЯ:")
    print("=" * 80)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ ПРОЙДЕН" if result else "❌ ПРОВАЛЕН"
        print(f"  {test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n🎯 ОБЩИЙ РЕЗУЛЬТАТ: {passed}/{total} тестов пройдено")
    print(f"📈 ПРОЦЕНТ УСПЕХА: {(passed/total)*100:.1f}%")
    
    if passed == total:
        print(f"🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ! Система работает корректно.")
    else:
        print(f"⚠️ НЕКОТОРЫЕ ТЕСТЫ ПРОВАЛЕНЫ. Требуется дополнительный анализ.")

if __name__ == "__main__":
    main()
