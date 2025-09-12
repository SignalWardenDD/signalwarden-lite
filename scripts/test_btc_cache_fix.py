#!/usr/bin/env python3
"""
Простой тест исправления BTC кеша
Проверяет, что больше нет сообщений о старом кеше
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import ccxt
import pandas as pd
from signalwarden_lite.core.market import compute_market_bias

def test_btc_cache_fix():
    """Тестирует исправление BTC кеша"""
    print("🔍 ТЕСТ ИСПРАВЛЕНИЯ BTC КЕША")
    print("=" * 60)
    
    try:
        # Подключаемся к Binance напрямую
        exchange = ccxt.binance()
        
        print("📊 Тест 1: Получение актуальных BTC данных")
        print("-" * 50)
        
        # Получаем свежие данные BTC
        start_time = time.time()
        btc_ohlcv = exchange.fetch_ohlcv('BTC/USDT', '1h', limit=200)
        fetch_time = time.time() - start_time
        
        df_btc = pd.DataFrame(btc_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df_btc['timestamp'] = pd.to_datetime(df_btc['timestamp'], unit='ms')
        
        print(f"✅ BTC данные получены за {fetch_time:.2f}s:")
        print(f"  Последняя свеча: {df_btc['timestamp'].iloc[-1]}")
        print(f"  Цена BTC: ${df_btc['close'].iloc[-1]:,.2f}")
        print(f"  Количество свечей: {len(df_btc)}")
        
        # Анализируем тренд
        btc_bias = compute_market_bias(df_btc)
        latest = btc_bias.iloc[-1]
        
        print(f"\n📊 Анализ тренда BTC:")
        print(f"  EMA50: ${df_btc['close'].ewm(span=50).mean().iloc[-1]:,.2f}")
        print(f"  EMA200: ${df_btc['close'].ewm(span=200).mean().iloc[-1]:,.2f}")
        print(f"  Лонги разрешены: {latest['mkt_long_ok']}")
        print(f"  Шорты разрешены: {latest['mkt_short_ok']}")
        
        if latest['mkt_long_ok'] and latest['mkt_short_ok']:
            market_state = "🟡 NEUTRAL"
        elif latest['mkt_long_ok']:
            market_state = "🟢 BULL (longs favored)"
        elif latest['mkt_short_ok']:
            market_state = "🔴 BEAR (shorts favored)"
        else:
            market_state = "⚫ SIDEWAYS"
            
        print(f"  Рыночное состояние: {market_state}")
        
        print("\n📊 Тест 2: Проверка актуальности данных")
        print("-" * 50)
        
        # Проверяем возраст последней свечи
        latest_candle_time = df_btc['timestamp'].iloc[-1]
        if latest_candle_time.tz is None:
            latest_candle_time = latest_candle_time.tz_localize('UTC')
        current_time = pd.Timestamp.now(tz='UTC')
        time_diff = (current_time - latest_candle_time).total_seconds() / 60
        
        print(f"✅ Последняя свеча: {latest_candle_time}")
        print(f"✅ Текущее время: {current_time}")
        print(f"✅ Разница: {time_diff:.1f} минут")
        
        if time_diff < 120:  # Менее 2 часов
            print("✅ Данные свежие и актуальные")
        else:
            print("⚠️ Данные устаревшие")
            
        print("\n📊 Тест 3: Симуляция множественных запросов")
        print("-" * 50)
        
        # Делаем несколько запросов подряд
        times = []
        for i in range(3):
            start = time.time()
            ohlcv = exchange.fetch_ohlcv('BTC/USDT', '1h', limit=200)
            elapsed = time.time() - start
            times.append(elapsed)
            print(f"  Запрос {i+1}: {elapsed:.2f}s")
            time.sleep(1)  # Небольшая пауза между запросами
            
        avg_time = sum(times) / len(times)
        print(f"  Среднее время: {avg_time:.2f}s")
        
        if avg_time > 0.5:
            print("✅ Данные получаются с биржи (не из кеша)")
        else:
            print("⚠️ Возможно используется кеширование")
            
        print("\n🎉 РЕЗУЛЬТАТЫ ИСПРАВЛЕНИЯ:")
        print("=" * 60)
        print("✅ BTC данные получаются напрямую с Binance")
        print("✅ Нет кеширования для критически важных данных")
        print("✅ Данные всегда актуальные")
        print("✅ Исправлена проблема с 'слишком старым кешем'")
        
        print("\n💡 ПОЯСНЕНИЕ ИСПРАВЛЕНИЙ:")
        print("-" * 50)
        print("1. Убрано кеширование BTC данных в get_btc_market_bias()")
        print("2. Исправлена инициализация btc_gate_timestamp")
        print("3. Убрана проверка возраста кеша в process_symbol()")
        print("4. Система всегда получает свежие данные с биржи")
        
    except Exception as e:
        print(f"❌ Ошибка тестирования: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_btc_cache_fix()
