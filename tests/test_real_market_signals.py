#!/usr/bin/env python3
"""
Тест генерации сигналов на реальных рыночных данных
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

def test_real_market_signals():
    """Тестирует генерацию сигналов на реальных данных"""
    print("🧪 ТЕСТ ГЕНЕРАЦИИ СИГНАЛОВ НА РЕАЛЬНЫХ ДАННЫХ")
    print("=" * 60)
    
    try:
        exchange = ccxt.binance()
        
        # Получаем данные BTC
        print("📊 Получение данных BTC...")
        btc_ohlcv = exchange.fetch_ohlcv('BTC/USDT', '1h', limit=200)
        df_btc = pd.DataFrame(btc_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df_btc['timestamp'] = pd.to_datetime(df_btc['timestamp'], unit='ms')
        
        # Получаем данные ADA (как пример альткоина)
        print("📊 Получение данных ADA...")
        ada_ohlcv = exchange.fetch_ohlcv('ADA/USDT', '1h', limit=200)
        df_ada = pd.DataFrame(ada_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df_ada['timestamp'] = pd.to_datetime(df_ada['timestamp'], unit='ms')
        
        print(f"✅ Данные получены:")
        print(f"  BTC: {len(df_btc)} часов, цена: ${df_btc['close'].iloc[-1]:,.2f}")
        print(f"  ADA: {len(df_ada)} часов, цена: ${df_ada['close'].iloc[-1]:,.4f}")
        
        # Анализируем тренд BTC
        btc_bias = compute_market_bias(df_btc)
        latest_btc = btc_bias.iloc[-1]
        
        print(f"\n📊 Тренд BTC:")
        print(f"  Лонги разрешены: {latest_btc['mkt_long_ok']}")
        print(f"  Шорты разрешены: {latest_btc['mkt_short_ok']}")
        
        # Добавляем индикаторы для ADA
        df_ada = add_indicators(df_ada, ema_fast=50, ema_slow=200)
        df_ada = add_regime(df_ada, RegimeThresholds())
        
        print(f"\n📈 Индикаторы ADA:")
        latest_ada = df_ada.iloc[-1]
        print(f"  EMA50: {latest_ada['ema_fast']:.4f}")
        print(f"  EMA200: {latest_ada['ema_slow']:.4f}")
        print(f"  RSI: {latest_ada['rsi']:.2f}")
        print(f"  NATR: {latest_ada['natr']:.4f}")
        print(f"  Режим: {latest_ada['regime']}")
        
        # Параметры сигналов
        signal_params = SignalParams()
        
        # Генерируем сигналы
        signals = generate_signals(df_ada, signal_params, btc_bias)
        
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
        if latest_btc['mkt_long_ok']:
            expected = "лонги"
            actual_long = long_signals
            actual_short = short_signals
        else:
            expected = "шорты"
            actual_long = long_signals
            actual_short = short_signals
        
        print(f"\n📊 Анализ симметричности:")
        print(f"  BTC тренд: {'бычий' if latest_btc['mkt_long_ok'] else 'медвежий'}")
        print(f"  Ожидается: {expected}")
        print(f"  Получено: Лонги {actual_long}, Шорты {actual_short}")
        
        # Проверяем, работает ли система
        if latest_btc['mkt_long_ok'] and long_signals > short_signals:
            success = True
            print(f"  ✅ Система работает правильно в бычьем рынке")
        elif latest_btc['mkt_short_ok'] and short_signals > long_signals:
            success = True
            print(f"  ✅ Система работает правильно в медвежьем рынке")
        else:
            success = False
            print(f"  ❌ Система не адаптируется к тренду BTC")
        
        return success
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_multiple_symbols():
    """Тестирует несколько символов"""
    print("\n🧪 ТЕСТ НЕСКОЛЬКИХ СИМВОЛОВ")
    print("=" * 50)
    
    symbols = ['ADA/USDT', 'LTC/USDT', 'DOGE/USDT']
    results = {}
    
    try:
        exchange = ccxt.binance()
        
        # Получаем данные BTC
        btc_ohlcv = exchange.fetch_ohlcv('BTC/USDT', '1h', limit=200)
        df_btc = pd.DataFrame(btc_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df_btc['timestamp'] = pd.to_datetime(df_btc['timestamp'], unit='ms')
        btc_bias = compute_market_bias(df_btc)
        
        for symbol in symbols:
            print(f"\n📊 Тестирование {symbol}...")
            
            try:
                ohlcv = exchange.fetch_ohlcv(symbol, '1h', limit=200)
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                
                # Добавляем индикаторы
                df = add_indicators(df, ema_fast=50, ema_slow=200)
                df = add_regime(df, RegimeThresholds())
                
                # Генерируем сигналы
                signal_params = SignalParams()
                signals = generate_signals(df, signal_params, btc_bias)
                
                # Анализируем последние 50 баров
                recent = signals.tail(50)
                long_signals = recent['allow_long'].sum()
                short_signals = recent['allow_short'].sum()
                
                results[symbol] = {
                    'long': long_signals,
                    'short': short_signals,
                    'price': df['close'].iloc[-1]
                }
                
                print(f"  Цена: ${df['close'].iloc[-1]:.4f}")
                print(f"  Лонги: {long_signals}/50")
                print(f"  Шорты: {short_signals}/50")
                
            except Exception as e:
                print(f"  ❌ Ошибка для {symbol}: {e}")
                results[symbol] = {'long': 0, 'short': 0, 'price': 0}
        
        # Анализируем результаты
        print(f"\n📊 Сводка по всем символам:")
        total_long = sum(r['long'] for r in results.values())
        total_short = sum(r['short'] for r in results.values())
        
        print(f"  Всего лонгов: {total_long}")
        print(f"  Всего шортов: {total_short}")
        
        # Проверяем симметричность
        latest_btc = btc_bias.iloc[-1]
        if latest_btc['mkt_long_ok']:
            expected = "лонги"
            success = total_long > total_short
        else:
            expected = "шорты"
            success = total_short > total_long
        
        print(f"  BTC тренд: {'бычий' if latest_btc['mkt_long_ok'] else 'медвежий'}")
        print(f"  Ожидается: {expected}")
        print(f"  ✅ Симметричность: {success}")
        
        return success
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

def main():
    """Главная функция"""
    print("🚀 ТЕСТ РЕАЛЬНЫХ РЫНОЧНЫХ СИГНАЛОВ")
    print("=" * 60)
    
    # Тест 1: Один символ
    success1 = test_real_market_signals()
    
    # Тест 2: Несколько символов
    success2 = test_multiple_symbols()
    
    print(f"\n📊 РЕЗУЛЬТАТЫ:")
    print(f"  Тест одного символа: {'✅' if success1 else '❌'}")
    print(f"  Тест нескольких символов: {'✅' if success2 else '❌'}")
    
    if success1 and success2:
        print(f"\n🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
        print(f"✅ Система правильно адаптируется к тренду BTC")
        print(f"✅ Логика работает симметрично для лонгов и шортов")
    else:
        print(f"\n❌ НЕ ВСЕ ТЕСТЫ ПРОЙДЕНЫ")
        print(f"⚠️ Требуется дополнительная настройка")

if __name__ == "__main__":
    main()
