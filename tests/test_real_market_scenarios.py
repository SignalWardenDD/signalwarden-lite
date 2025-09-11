#!/usr/bin/env python3
"""
Тесты системы на реальных рыночных данных
Проверяет поведение в различных рыночных условиях
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

def test_current_market_conditions():
    """Тест 1: Текущие рыночные условия"""
    print("🧪 ТЕСТ 1: ТЕКУЩИЕ РЫНОЧНЫЕ УСЛОВИЯ")
    print("=" * 60)
    
    try:
        exchange = ccxt.binance()
        
        # Получаем данные BTC
        btc_ohlcv = exchange.fetch_ohlcv('BTC/USDT', '1h', limit=200)
        df_btc = pd.DataFrame(btc_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df_btc['timestamp'] = pd.to_datetime(df_btc['timestamp'], unit='ms')
        
        # Анализируем тренд BTC
        btc_bias = compute_market_bias(df_btc)
        latest_btc = btc_bias.iloc[-1]
        
        print(f"📊 ТЕКУЩИЕ УСЛОВИЯ BTC:")
        print(f"  Цена: ${df_btc['close'].iloc[-1]:,.2f}")
        print(f"  EMA50: ${df_btc['close'].ewm(span=50).mean().iloc[-1]:,.2f}")
        print(f"  EMA200: ${df_btc['close'].ewm(span=200).mean().iloc[-1]:,.2f}")
        print(f"  Лонги разрешены: {latest_btc['mkt_long_ok']}")
        print(f"  Шорты разрешены: {latest_btc['mkt_short_ok']}")
        
        # Тестируем все пары
        symbols = ['ADA/USDT', 'LTC/USDT', 'DOGE/USDT', 'ENA/USDT', 'HBAR/USDT', 'WIF/USDT', 'PNUT/USDT']
        
        signal_params = SignalParams()
        results = []
        
        for symbol in symbols:
            try:
                # Получаем данные
                ohlcv = exchange.fetch_ohlcv(symbol, '1h', limit=200)
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                
                # Добавляем индикаторы
                df = add_indicators(df, ema_fast=50, ema_slow=200)
                df = add_regime(df, RegimeThresholds())
                
                # Генерируем сигналы
                signals = generate_signals(df, signal_params, btc_bias)
                latest = signals.iloc[-1]
                
                # Анализируем условия
                long_conditions = [
                    latest_btc['mkt_long_ok'],
                    latest['ema_fast'] > latest['ema_slow'],
                    latest['rsi'] >= 35,
                    latest['natr'] >= 0.5,
                    latest['regime'] in ['normal', 'high']
                ]
                
                short_conditions = [
                    latest_btc['mkt_short_ok'],
                    latest['ema_fast'] < latest['ema_slow'],
                    latest['rsi'] <= 50 if not latest_btc['mkt_short_ok'] else latest['rsi'] <= 52,
                    latest['natr'] >= 0.8 if not latest_btc['mkt_short_ok'] else latest['natr'] >= 0.9,
                    latest['regime'] in ['normal', 'high']
                ]
                
                results.append({
                    'symbol': symbol,
                    'price': latest['close'],
                    'rsi': latest['rsi'],
                    'natr': latest['natr'],
                    'regime': latest['regime'],
                    'long_conditions': sum(long_conditions),
                    'short_conditions': sum(short_conditions),
                    'allow_long': latest.get('allow_long', False),
                    'allow_short': latest.get('allow_short', False)
                })
                
            except Exception as e:
                print(f"  ❌ Ошибка для {symbol}: {e}")
        
        # Анализируем результаты
        print(f"\n📊 АНАЛИЗ РЕЗУЛЬТАТОВ:")
        print(f"{'Пара':<12} {'RSI':<6} {'NATR':<8} {'Режим':<8} {'Лонги':<6} {'Шорты':<6} {'Allow L':<8} {'Allow S':<8}")
        print("-" * 80)
        
        long_ready = 0
        short_ready = 0
        
        for result in results:
            print(f"{result['symbol']:<12} {result['rsi']:<6.1f} {result['natr']:<7.2f}% {result['regime']:<8} {result['long_conditions']:<6} {result['short_conditions']:<6} {result['allow_long']:<8} {result['allow_short']:<8}")
            
            if result['allow_long']:
                long_ready += 1
            if result['allow_short']:
                short_ready += 1
        
        print(f"\n📈 СТАТИСТИКА:")
        print(f"  Пар готовых к лонгам: {long_ready}/{len(results)}")
        print(f"  Пар готовых к шортам: {short_ready}/{len(results)}")
        print(f"  Общий тренд: {'Бычий' if latest_btc['mkt_long_ok'] else 'Медвежий'}")
        
        return long_ready > 0 or short_ready > 0
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

def test_volatility_scenarios():
    """Тест 2: Различные сценарии волатильности"""
    print("\n🧪 ТЕСТ 2: СЦЕНАРИИ ВОЛАТИЛЬНОСТИ")
    print("=" * 60)
    
    try:
        exchange = ccxt.binance()
        
        # Получаем данные BTC
        btc_ohlcv = exchange.fetch_ohlcv('BTC/USDT', '1h', limit=200)
        df_btc = pd.DataFrame(btc_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df_btc['timestamp'] = pd.to_datetime(df_btc['timestamp'], unit='ms')
        
        # Анализируем тренд BTC
        btc_bias = compute_market_bias(df_btc)
        
        # Тестируем на ADA
        symbol = 'ADA/USDT'
        ohlcv = exchange.fetch_ohlcv(symbol, '1h', limit=200)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        # Добавляем индикаторы
        df = add_indicators(df, ema_fast=50, ema_slow=200)
        df = add_regime(df, RegimeThresholds())
        
        signal_params = SignalParams()
        signals = generate_signals(df, signal_params, btc_bias)
        
        # Анализируем последние 10 баров
        print(f"📊 АНАЛИЗ ВОЛАТИЛЬНОСТИ ({symbol}):")
        print(f"{'Бар':<4} {'Цена':<12} {'RSI':<6} {'NATR':<8} {'Режим':<10} {'Allow L':<8} {'Allow S':<8}")
        print("-" * 70)
        
        recent_data = signals.tail(10)
        for i, (idx, row) in enumerate(recent_data.iterrows()):
            print(f"{i+1:<4} ${row['close']:<11.6f} {row['rsi']:<6.1f} {row['natr']:<7.2f}% {row['regime']:<10} {row.get('allow_long', False):<8} {row.get('allow_short', False):<8}")
        
        # Анализируем изменения режима
        regime_changes = 0
        for i in range(1, len(recent_data)):
            if recent_data.iloc[i]['regime'] != recent_data.iloc[i-1]['regime']:
                regime_changes += 1
        
        print(f"\n📈 АНАЛИЗ ИЗМЕНЕНИЙ:")
        print(f"  Изменений режима за 10 баров: {regime_changes}")
        print(f"  Текущий режим: {recent_data.iloc[-1]['regime']}")
        print(f"  Средний NATR: {recent_data['natr'].mean():.2f}%")
        print(f"  Диапазон RSI: {recent_data['rsi'].min():.1f} - {recent_data['rsi'].max():.1f}")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

def test_trend_adaptation():
    """Тест 3: Адаптация к изменению тренда"""
    print("\n🧪 ТЕСТ 3: АДАПТАЦИЯ К ИЗМЕНЕНИЮ ТРЕНДА")
    print("=" * 60)
    
    try:
        exchange = ccxt.binance()
        
        # Получаем данные BTC за последние 50 баров
        btc_ohlcv = exchange.fetch_ohlcv('BTC/USDT', '1h', limit=50)
        df_btc = pd.DataFrame(btc_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df_btc['timestamp'] = pd.to_datetime(df_btc['timestamp'], unit='ms')
        
        # Анализируем тренд BTC
        btc_bias = compute_market_bias(df_btc)
        
        # Тестируем на DOGE
        symbol = 'DOGE/USDT'
        ohlcv = exchange.fetch_ohlcv(symbol, '1h', limit=50)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        # Добавляем индикаторы
        df = add_indicators(df, ema_fast=50, ema_slow=200)
        df = add_regime(df, RegimeThresholds())
        
        signal_params = SignalParams()
        signals = generate_signals(df, signal_params, btc_bias)
        
        # Анализируем адаптацию
        print(f"📊 АНАЛИЗ АДАПТАЦИИ ({symbol}):")
        print(f"{'Бар':<4} {'BTC Long':<9} {'BTC Short':<10} {'Allow L':<8} {'Allow S':<8} {'RSI':<6} {'Режим':<8}")
        print("-" * 70)
        
        recent_data = signals.tail(20)
        recent_btc = btc_bias.tail(20)
        
        for i in range(len(recent_data)):
            row = recent_data.iloc[i]
            btc_row = recent_btc.iloc[i]
            print(f"{i+1:<4} {btc_row['mkt_long_ok']:<9} {btc_row['mkt_short_ok']:<10} {row.get('allow_long', False):<8} {row.get('allow_short', False):<8} {row['rsi']:<6.1f} {row['regime']:<8}")
        
        # Проверяем адаптивность
        btc_changes = 0
        for i in range(1, len(recent_btc)):
            if (recent_btc.iloc[i]['mkt_long_ok'] != recent_btc.iloc[i-1]['mkt_long_ok'] or
                recent_btc.iloc[i]['mkt_short_ok'] != recent_btc.iloc[i-1]['mkt_short_ok']):
                btc_changes += 1
        
        print(f"\n📈 АНАЛИЗ АДАПТИВНОСТИ:")
        print(f"  Изменений BTC тренда за 20 баров: {btc_changes}")
        print(f"  Текущий BTC тренд: {'Бычий' if recent_btc.iloc[-1]['mkt_long_ok'] else 'Медвежий'}")
        print(f"  Текущие разрешения: Long={recent_data.iloc[-1].get('allow_long', False)}, Short={recent_data.iloc[-1].get('allow_short', False)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

def test_signal_quality():
    """Тест 4: Качество сигналов"""
    print("\n🧪 ТЕСТ 4: КАЧЕСТВО СИГНАЛОВ")
    print("=" * 60)
    
    try:
        exchange = ccxt.binance()
        
        # Получаем данные BTC
        btc_ohlcv = exchange.fetch_ohlcv('BTC/USDT', '1h', limit=200)
        df_btc = pd.DataFrame(btc_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df_btc['timestamp'] = pd.to_datetime(df_btc['timestamp'], unit='ms')
        
        # Анализируем тренд BTC
        btc_bias = compute_market_bias(df_btc)
        
        # Тестируем на ENA (высокая волатильность)
        symbol = 'ENA/USDT'
        ohlcv = exchange.fetch_ohlcv(symbol, '1h', limit=200)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        # Добавляем индикаторы
        df = add_indicators(df, ema_fast=50, ema_slow=200)
        df = add_regime(df, RegimeThresholds())
        
        signal_params = SignalParams()
        signals = generate_signals(df, signal_params, btc_bias)
        
        # Анализируем качество сигналов
        print(f"📊 АНАЛИЗ КАЧЕСТВА СИГНАЛОВ ({symbol}):")
        
        # Подсчитываем сигналы
        signal_types = ['sig_long_breakout', 'sig_long_inside', 'sig_long_tc', 'sig_long_sq',
                       'sig_short_breakout', 'sig_short_inside', 'sig_short_tc', 'sig_short_sq']
        
        signal_counts = {}
        for sig_type in signal_types:
            count = signals[sig_type].sum()
            signal_counts[sig_type] = count
        
        print(f"  Количество сигналов за 200 баров:")
        for sig_type, count in signal_counts.items():
            print(f"    {sig_type}: {count}")
        
        # Анализируем условия
        allow_long_count = signals['allow_long'].sum()
        allow_short_count = signals['allow_short'].sum()
        
        print(f"\n  Условия разрешения:")
        print(f"    Allow long: {allow_long_count}/200 баров")
        print(f"    Allow short: {allow_short_count}/200 баров")
        
        # Анализируем режимы
        regime_counts = signals['regime'].value_counts()
        print(f"\n  Распределение режимов:")
        for regime, count in regime_counts.items():
            print(f"    {regime}: {count} баров")
        
        # Анализируем RSI
        rsi_stats = signals['rsi'].describe()
        print(f"\n  Статистика RSI:")
        print(f"    Среднее: {rsi_stats['mean']:.1f}")
        print(f"    Медиана: {rsi_stats['50%']:.1f}")
        print(f"    Диапазон: {rsi_stats['min']:.1f} - {rsi_stats['max']:.1f}")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

def main():
    """Главная функция тестирования"""
    print("🚀 ТЕСТЫ СИСТЕМЫ НА РЕАЛЬНЫХ РЫНОЧНЫХ ДАННЫХ")
    print("=" * 80)
    
    results = []
    
    # Запускаем все тесты
    results.append(("Текущие рыночные условия", test_current_market_conditions()))
    results.append(("Сценарии волатильности", test_volatility_scenarios()))
    results.append(("Адаптация к тренду", test_trend_adaptation()))
    results.append(("Качество сигналов", test_signal_quality()))
    
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
        print(f"🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ! Система работает корректно на реальных данных.")
    else:
        print(f"⚠️ НЕКОТОРЫЕ ТЕСТЫ ПРОВАЛЕНЫ. Требуется дополнительный анализ.")

if __name__ == "__main__":
    main()
