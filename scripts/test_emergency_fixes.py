#!/usr/bin/env python3
"""
Тестирование всех экстренных исправлений
"""

import sys
import os
sys.path.insert(0, os.path.abspath('.'))

import json
import ccxt
from datetime import datetime
import time

def test_state_consistency():
    """Тест 1: Консистентность состояния"""
    print("🧪 ТЕСТ 1: Проверка консистентности состояния")
    
    state_file = 'data_files/trading_state_v1_6_TXB.json'
    
    if not os.path.exists(state_file):
        print("❌ Файл состояния не найден!")
        return False
    
    try:
        with open(state_file, 'r') as f:
            state = json.load(f)
        
        active_positions = state.get('active_positions', {})
        
        print(f"📊 Проверяем {len(active_positions)} позиций в состоянии:")
        
        all_valid = True
        
        for symbol, pos_data in active_positions.items():
            # Проверяем обязательные поля
            required_fields = ['symbol', 'side', 'quantity', 'entry_price']
            missing_fields = []
            
            for field in required_fields:
                if field not in pos_data or pos_data[field] is None:
                    missing_fields.append(field)
            
            if missing_fields:
                print(f"   ❌ {symbol}: Отсутствуют поля: {missing_fields}")
                all_valid = False
            else:
                sl_order_id = pos_data.get('sl_order_id')
                last_updated_sl = pos_data.get('last_updated_sl')
                
                if sl_order_id and last_updated_sl:
                    print(f"   ✅ {symbol}: Все поля корректны, SL: {last_updated_sl} (ID: {sl_order_id})")
                else:
                    print(f"   ⚠️ {symbol}: Поля корректны, но нет SL данных")
        
        return all_valid
        
    except Exception as e:
        print(f"❌ Ошибка проверки состояния: {e}")
        return False

def test_exchange_sync():
    """Тест 2: Синхронизация с биржей"""
    print("\n🧪 ТЕСТ 2: Синхронизация с биржей")
    
    try:
        # Подключение к бирже
        exchange = ccxt.binanceusdm({
            'apiKey': os.getenv('BINANCE_API_KEY'),
            'secret': os.getenv('BINANCE_SECRET'),
            'sandbox': False,
            'enableRateLimit': True,
        })
        exchange.options["warnOnFetchOpenOrdersWithoutSymbol"] = False
        
        # Получаем позиции с биржи
        positions = exchange.fetch_positions()
        active_positions = [p for p in positions if float(p['contracts']) > 0]
        
        # Получаем SL ордера
        orders = exchange.fetch_open_orders()
        sl_orders = [o for o in orders if o['type'] in ['stop_market', 'stop'] and o['info'].get('reduceOnly')]
        
        print(f"📊 Позиций на бирже: {len(active_positions)}")
        print(f"📊 SL ордеров на бирже: {len(sl_orders)}")
        
        # Проверяем соответствие
        position_symbols = set()
        for pos in active_positions:
            symbol = pos['symbol']
            position_symbols.add(symbol)
        
        sl_symbols = set()
        for order in sl_orders:
            symbol = order['symbol']
            sl_symbols.add(symbol)
        
        missing_sl = position_symbols - sl_symbols
        orphaned_sl = sl_symbols - position_symbols
        
        all_good = True
        
        if missing_sl:
            print(f"❌ Позиции без SL: {missing_sl}")
            all_good = False
        
        if orphaned_sl:
            print(f"⚠️ Orphaned SL ордера: {orphaned_sl}")
        
        # Проверяем дубликаты
        sl_counts = {}
        for order in sl_orders:
            symbol = order['symbol']
            sl_counts[symbol] = sl_counts.get(symbol, 0) + 1
        
        duplicates = {k: v for k, v in sl_counts.items() if v > 1}
        if duplicates:
            print(f"❌ Дублированные SL: {duplicates}")
            all_good = False
        
        if all_good:
            print("✅ Синхронизация с биржей корректна")
        
        return all_good
        
    except Exception as e:
        print(f"❌ Ошибка синхронизации с биржей: {e}")
        return False

def test_code_syntax():
    """Тест 3: Синтаксис кода"""
    print("\n🧪 ТЕСТ 3: Проверка синтаксиса кода")
    
    try:
        # Пытаемся импортировать основной модуль
        from signalwarden_lite.live.run_live_v1_6_TXB import SignalWardenLive
        
        print("✅ Импорт SignalWardenLive успешен")
        
        # Проверяем наличие ключевых методов
        required_methods = [
            'cleanup_orphaned_orders',
            'verify_all_positions_have_sl_protection',
            'get_position_pnl_from_exchange',
            'update_trailing_stops'
        ]
        
        for method_name in required_methods:
            if hasattr(SignalWardenLive, method_name):
                print(f"✅ Метод {method_name} найден")
            else:
                print(f"❌ Метод {method_name} отсутствует")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка импорта: {e}")
        return False

def test_position_data_access():
    """Тест 4: Доступ к данным позиций"""
    print("\n🧪 ТЕСТ 4: Проверка доступа к данным позиций")
    
    try:
        state_file = 'data_files/trading_state_v1_6_TXB.json'
        
        with open(state_file, 'r') as f:
            state = json.load(f)
        
        active_positions = state.get('active_positions', {})
        
        if not active_positions:
            print("⚠️ Нет активных позиций для тестирования")
            return True
        
        # Тестируем доступ к данным как в коде
        for symbol, pos in active_positions.items():
            # Тестируем все варианты доступа к данным
            entry_price = pos.get('entry_price', pos.get('entry', 0))
            side = pos.get('side', 'long').lower()
            quantity = pos.get('quantity', pos.get('qty', 0))
            current_sl = pos.get('last_updated_sl', pos.get('sl_current', 'N/A'))
            
            if entry_price and side and quantity:
                print(f"✅ {symbol}: Доступ к данным корректен - {side.upper()} {quantity} @ {entry_price}")
            else:
                print(f"❌ {symbol}: Проблемы с доступом к данным")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка доступа к данным позиций: {e}")
        return False

def main():
    print("🚨 ТЕСТИРОВАНИЕ ЭКСТРЕННЫХ ИСПРАВЛЕНИЙ")
    print("=" * 60)
    
    tests = [
        ("Консистентность состояния", test_state_consistency),
        ("Синхронизация с биржей", test_exchange_sync),
        ("Синтаксис кода", test_code_syntax),
        ("Доступ к данным позиций", test_position_data_access),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            if result:
                passed += 1
            print(f"{'✅' if result else '❌'} {test_name}: {'ПРОШЕЛ' if result else 'ПРОВАЛЕН'}")
        except Exception as e:
            print(f"❌ {test_name}: ОШИБКА - {e}")
    
    print("\n" + "=" * 60)
    print(f"📊 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ: {passed}/{total} тестов прошли")
    
    if passed == total:
        print("🎉 ВСЕ ТЕСТЫ ПРОШЛИ УСПЕШНО!")
        print("✅ Система готова к безопасной работе")
        return True
    else:
        print("⚠️ НЕ ВСЕ ТЕСТЫ ПРОШЛИ")
        print("🔧 Требуется дополнительное исправление")
        return False

if __name__ == "__main__":
    main()
