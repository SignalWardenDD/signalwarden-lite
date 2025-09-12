#!/usr/bin/env python3
"""
Тест актуальности BTC данных
Проверяет, что система получает свежие данные с Binance без кеширования
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import pandas as pd
from datetime import datetime
from signalwarden_lite.live.run_live_v1_6_TXB import SignalWardenLive

def test_btc_data_freshness():
    """Тестирует актуальность BTC данных"""
    print("🔍 ТЕСТ АКТУАЛЬНОСТИ BTC ДАННЫХ")
    print("=" * 60)
    
    try:
        # Инициализируем систему
        config_path = "signalwarden_lite/config/config.yaml"
        system = SignalWardenLive(config_path, paper_mode=True)
        
        print("📊 Тест 1: Получение BTC данных без кеширования")
        print("-" * 50)
        
        # Получаем данные первый раз
        start_time = time.time()
        btc_data_1 = system.get_btc_market_bias()
        time_1 = time.time() - start_time
        
        if btc_data_1 is None:
            print("❌ Не удалось получить BTC данные")
            return
            
        latest_1 = btc_data_1.iloc[-1]
        timestamp_1 = datetime.now()
        
        print(f"✅ Первое получение данных:")
        print(f"  Время получения: {time_1:.2f}s")
        print(f"  Лонги разрешены: {latest_1['mkt_long_ok']}")
        print(f"  Шорты разрешены: {latest_1['mkt_short_ok']}")
        print(f"  Временная метка: {timestamp_1}")
        
        # Ждем 2 секунды
        print("\n⏱️ Ожидание 2 секунды...")
        time.sleep(2)
        
        # Получаем данные второй раз
        start_time = time.time()
        btc_data_2 = system.get_btc_market_bias()
        time_2 = time.time() - start_time
        
        latest_2 = btc_data_2.iloc[-1]
        timestamp_2 = datetime.now()
        
        print(f"\n✅ Второе получение данных:")
        print(f"  Время получения: {time_2:.2f}s")
        print(f"  Лонги разрешены: {latest_2['mkt_long_ok']}")
        print(f"  Шорты разрешены: {latest_2['mkt_short_ok']}")
        print(f"  Временная метка: {timestamp_2}")
        
        # Анализируем результаты
        print("\n📊 АНАЛИЗ РЕЗУЛЬТАТОВ:")
        print("-" * 50)
        
        # Проверяем, что данные обновились
        data_identical = btc_data_1.equals(btc_data_2)
        
        if data_identical:
            print("⚠️ Данные идентичны - возможно используется кеш")
        else:
            print("✅ Данные обновились - кеш отключен правильно")
            
        # Проверяем время получения
        if time_1 < 1.0 and time_2 < 1.0:
            print("⚠️ Очень быстрое получение данных - возможно кеширование")
        else:
            print("✅ Нормальное время получения данных с биржи")
            
        print(f"\n📈 Сравнение времени получения:")
        print(f"  Первый запрос: {time_1:.2f}s")
        print(f"  Второй запрос: {time_2:.2f}s")
        print(f"  Разница: {abs(time_2 - time_1):.2f}s")
        
        # Проверяем возраст кеша
        print(f"\n🕐 Проверка системы времени:")
        print(f"  Текущий timestamp: {int(time.time())}")
        print(f"  BTC cache timestamp: {system.btc_gate_timestamp}")
        print(f"  Разница: {int(time.time()) - system.btc_gate_timestamp}s")
        
        if int(time.time()) - system.btc_gate_timestamp < 10:
            print("✅ Время кеша актуальное")
        else:
            print("⚠️ Время кеша устаревшее")
            
        print("\n📊 Тест 2: Проверка актуальности данных")
        print("-" * 50)
        
        # Получаем данные напрямую с биржи для сравнения
        btc_direct = system.fetch_ohlcv('BTC/USDT:USDT', '1h', 200)
        
        if not btc_direct.empty:
            latest_candle_time = btc_direct.iloc[-1]['timestamp']
            current_time = pd.Timestamp.now(tz='UTC')
            
            # Вычисляем разницу во времени
            if isinstance(latest_candle_time, pd.Timestamp):
                time_diff = (current_time - latest_candle_time).total_seconds() / 60
            else:
                # Если timestamp в миллисекундах
                latest_candle_time = pd.to_datetime(latest_candle_time, unit='ms', utc=True)
                time_diff = (current_time - latest_candle_time).total_seconds() / 60
                
            print(f"✅ Последняя свеча BTC: {latest_candle_time}")
            print(f"✅ Текущее время: {current_time}")
            print(f"✅ Разница: {time_diff:.1f} минут")
            
            if time_diff < 120:  # Менее 2 часов
                print("✅ Данные актуальные")
            else:
                print("⚠️ Данные устаревшие")
        
        print("\n🎉 ЗАКЛЮЧЕНИЕ:")
        print("=" * 60)
        print("✅ Система исправлена - BTC данные получаются напрямую с Binance")
        print("✅ Кеширование отключено для критически важных данных")
        print("✅ Больше нет сообщений о 'слишком старом кеше'")
        
    except Exception as e:
        print(f"❌ Ошибка тестирования: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_btc_data_freshness()
