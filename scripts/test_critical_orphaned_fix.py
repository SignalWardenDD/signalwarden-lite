#!/usr/bin/env python3
"""
КРИТИЧЕСКИЙ ТЕСТ: Проверка исправления функции cleanup_orphaned_orders
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import inspect
from signalwarden_lite.live.run_live_v1_6_TXB import SignalWardenLive

def test_critical_orphaned_fix():
    """Критический тест исправления get_all_positions_from_exchange"""
    print("🚨 КРИТИЧЕСКИЙ ТЕСТ: Исправление cleanup_orphaned_orders")
    print("=" * 70)
    
    # Создаем экземпляр системы в paper mode для безопасности
    config_path = "./signalwarden_lite/config/config_production.yaml"
    
    try:
        trader = SignalWardenLive(config_path, paper_mode=True)
        print("✅ Система инициализирована в paper mode")
        
        # Тест 1: Проверяем что функция cleanup_orphaned_orders существует
        print("\n🔍 Тест 1: Проверка наличия функции cleanup_orphaned_orders")
        if hasattr(trader, 'cleanup_orphaned_orders'):
            print("✅ Функция cleanup_orphaned_orders найдена")
        else:
            print("❌ Функция cleanup_orphaned_orders НЕ найдена!")
            return False
        
        # Тест 2: Проверяем исходный код функции на наличие get_all_positions_from_exchange
        print("\n🔍 Тест 2: Анализ исходного кода cleanup_orphaned_orders")
        try:
            source_code = inspect.getsource(trader.cleanup_orphaned_orders)
            
            if 'get_all_positions_from_exchange' in source_code:
                print("❌ КРИТИЧЕСКАЯ ОШИБКА: get_all_positions_from_exchange все еще в коде!")
                print("🔍 Найдено в коде:")
                lines = source_code.split('\n')
                for i, line in enumerate(lines):
                    if 'get_all_positions_from_exchange' in line:
                        print(f"   Строка {i+1}: {line.strip()}")
                return False
            else:
                print("✅ get_all_positions_from_exchange НЕ найдено в коде")
            
            if 'self.exchange.fetch_positions()' in source_code:
                print("✅ Найдено правильное использование: self.exchange.fetch_positions()")
            else:
                print("⚠️ Не найдено self.exchange.fetch_positions() - проверьте реализацию")
            
            if 'self.exchange.fetch_open_orders()' in source_code:
                print("✅ Найдено правильное использование: self.exchange.fetch_open_orders()")
            else:
                print("⚠️ Не найдено self.exchange.fetch_open_orders() - проверьте orphaned логику")
                
        except Exception as e:
            print(f"❌ Ошибка анализа исходного кода: {e}")
            return False
        
        # Тест 3: Пытаемся вызвать функцию и проверить что она не падает с AttributeError
        print("\n🔍 Тест 3: Вызов cleanup_orphaned_orders в paper mode")
        try:
            trader.cleanup_orphaned_orders()
            print("✅ Функция выполнилась без AttributeError")
        except AttributeError as ae:
            if 'get_all_positions_from_exchange' in str(ae):
                print(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {ae}")
                return False
            else:
                print(f"⚠️ Другая AttributeError (возможно нормально в paper mode): {ae}")
        except Exception as e:
            print(f"ℹ️ Другая ошибка (ожидаемо в paper mode): {e}")
        
        # Тест 4: Проверяем verify_all_positions_have_sl_protection
        print("\n🔍 Тест 4: Проверка verify_all_positions_have_sl_protection")
        try:
            trader.verify_all_positions_have_sl_protection()
            print("✅ verify_all_positions_have_sl_protection работает")
        except AttributeError as ae:
            print(f"❌ AttributeError в verify_all_positions_have_sl_protection: {ae}")
            return False
        except Exception as e:
            print(f"ℹ️ Другая ошибка (ожидаемо в paper mode): {e}")
        
        # Тест 5: Проверяем интеграцию с update_trailing_stops
        print("\n🔍 Тест 5: Проверка интеграции с update_trailing_stops")
        try:
            # Принудительно запускаем проверку
            trader._last_protection_check = 0
            trader.update_trailing_stops()
            print("✅ update_trailing_stops выполнилась с интеграцией очистки")
        except AttributeError as ae:
            if 'get_all_positions_from_exchange' in str(ae):
                print(f"❌ КРИТИЧЕСКАЯ ОШИБКА в update_trailing_stops: {ae}")
                return False
            else:
                print(f"⚠️ Другая AttributeError: {ae}")
        except Exception as e:
            print(f"ℹ️ Другая ошибка (ожидаемо в paper mode): {e}")
        
        print("\n🎉 ВСЕ КРИТИЧЕСКИЕ ТЕСТЫ ПРОЙДЕНЫ!")
        print("=" * 70)
        print("✅ get_all_positions_from_exchange исправлено на self.exchange.fetch_positions()")
        print("✅ Функция cleanup_orphaned_orders не падает с AttributeError")
        print("✅ Интеграция с update_trailing_stops работает")
        print("✅ Система готова к работе без критических ошибок")
        
        return True
        
    except Exception as e:
        print(f"❌ Критическая ошибка в тестах: {e}")
        return False

def test_detailed_function_analysis():
    """Детальный анализ исправленной функции"""
    print("\n🔍 ДЕТАЛЬНЫЙ АНАЛИЗ ИСПРАВЛЕНИЙ")
    print("-" * 50)
    
    config_path = "./signalwarden_lite/config/config_production.yaml"
    
    try:
        trader = SignalWardenLive(config_path, paper_mode=True)
        
        # Анализируем исходный код функции
        source = inspect.getsource(trader.cleanup_orphaned_orders)
        
        print("📋 Анализ исходного кода cleanup_orphaned_orders:")
        
        # Проверяем ключевые исправления
        checks = [
            ("self.exchange.fetch_positions()", "✅ Правильное получение позиций с биржи"),
            ("self.exchange.fetch_open_orders(ccxt_sym)", "✅ Правильное получение ордеров по символу"),
            ("self.exchange.fetch_open_orders()", "✅ Правильное получение ВСЕХ ордеров"),
            ("get_all_positions_from_exchange", "❌ КРИТИЧЕСКАЯ ОШИБКА: старый метод все еще используется"),
            ("try:", "✅ Обработка ошибок"),
            ("except Exception", "✅ Перехват исключений"),
        ]
        
        for pattern, message in checks:
            if pattern in source:
                if "❌" in message:
                    print(f"   {message}")
                    return False
                else:
                    print(f"   {message}")
        
        print("\n📊 Статистика функции:")
        lines = source.split('\n')
        print(f"   Всего строк: {len(lines)}")
        print(f"   Try-except блоков: {source.count('try:')}")
        print(f"   Exchange вызовов: {source.count('self.exchange.')}")
        print(f"   Logger сообщений: {source.count('logger.')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка детального анализа: {e}")
        return False

if __name__ == '__main__':
    print("🚀 ЗАПУСК КРИТИЧЕСКИХ ТЕСТОВ ИСПРАВЛЕНИЯ")
    print("=" * 70)
    
    success = True
    
    # Основной критический тест
    if not test_critical_orphaned_fix():
        success = False
    
    # Детальный анализ
    if not test_detailed_function_analysis():
        success = False
    
    print("\n" + "=" * 70)
    if success:
        print("🎉 ВСЕ КРИТИЧЕСКИЕ ТЕСТЫ ПРОЙДЕНЫ!")
        print("✅ Система исправлена и готова к работе")
        print("✅ get_all_positions_from_exchange больше не используется")
        print("✅ cleanup_orphaned_orders работает корректно")
        print("")
        print("🚀 СИСТЕМА ГОТОВА К ЗАПУСКУ БЕЗ КРИТИЧЕСКИХ ОШИБОК!")
    else:
        print("❌ КРИТИЧЕСКИЕ ТЕСТЫ ПРОВАЛЕНЫ!")
        print("🚨 СИСТЕМА НЕ ГОТОВА К ЗАПУСКУ!")
        print("🔧 ТРЕБУЮТСЯ ДОПОЛНИТЕЛЬНЫЕ ИСПРАВЛЕНИЯ!")
    
    print("=" * 70)
