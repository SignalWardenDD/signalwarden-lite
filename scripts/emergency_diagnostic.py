#!/usr/bin/env python3
"""
EMERGENCY DIAGNOSTIC - Полная диагностика критических проблем системы
"""

import sys
import os
sys.path.insert(0, os.path.abspath('.'))

import json
import ccxt
from datetime import datetime
import time

def check_exchange_connection():
    """Проверка подключения к бирже"""
    print("🔍 ДИАГНОСТИКА 1: Подключение к бирже")
    try:
        # Загружаем конфиг
        import yaml
        with open('signalwarden_lite/config/config_production.yaml', 'r') as f:
            config = yaml.safe_load(f)
        
        # Создаем подключение
        exchange = ccxt.binanceusdm({
            'apiKey': os.getenv('BINANCE_API_KEY'),
            'secret': os.getenv('BINANCE_SECRET'),
            'sandbox': False,
            'enableRateLimit': True,
        })
        
        # Проверяем подключение
        balance = exchange.fetch_balance()
        print(f"✅ Подключение OK. USDT баланс: {balance['USDT']['total']}")
        
        return exchange
        
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")
        return None

def check_open_positions(exchange):
    """Проверка открытых позиций на бирже"""
    print("\n🔍 ДИАГНОСТИКА 2: Открытые позиции на бирже")
    try:
        positions = exchange.fetch_positions()
        active_positions = [p for p in positions if float(p['contracts']) > 0]
        
        print(f"📊 Найдено {len(active_positions)} активных позиций на бирже:")
        for pos in active_positions:
            symbol = pos['symbol']
            size = pos['contracts']
            side = pos['side']
            entry_price = pos['entryPrice']
            unrealized_pnl = pos['unrealizedPnl']
            print(f"   {symbol}: {side} {size} @ {entry_price}, PnL: {unrealized_pnl}")
        
        return active_positions
        
    except Exception as e:
        print(f"❌ Ошибка получения позиций: {e}")
        return []

def check_open_orders(exchange):
    """Проверка открытых ордеров"""
    print("\n🔍 ДИАГНОСТИКА 3: Открытые ордера")
    try:
        # Включаем опцию для получения всех ордеров
        exchange.options["warnOnFetchOpenOrdersWithoutSymbol"] = False
        
        orders = exchange.fetch_open_orders()
        sl_orders = [o for o in orders if o['type'] in ['stop_market', 'stop'] and o['info'].get('reduceOnly')]
        
        print(f"📊 Найдено {len(orders)} открытых ордеров, из них {len(sl_orders)} SL ордеров:")
        
        # Группируем SL ордера по символам
        sl_by_symbol = {}
        for order in sl_orders:
            symbol = order['symbol']
            if symbol not in sl_by_symbol:
                sl_by_symbol[symbol] = []
            sl_by_symbol[symbol].append(order)
        
        for symbol, symbol_orders in sl_by_symbol.items():
            print(f"   {symbol}: {len(symbol_orders)} SL ордеров")
            for order in symbol_orders:
                print(f"      ID: {order['id']}, Stop: {order['stopPrice']}, Status: {order['status']}")
        
        return orders, sl_orders, sl_by_symbol
        
    except Exception as e:
        print(f"❌ Ошибка получения ордеров: {e}")
        return [], [], {}

def check_local_state():
    """Проверка локального состояния"""
    print("\n🔍 ДИАГНОСТИКА 4: Локальное состояние")
    try:
        state_file = 'data_files/trading_state_v1_6_TXB.json'
        if not os.path.exists(state_file):
            print("❌ Файл состояния не найден!")
            return None
            
        with open(state_file, 'r') as f:
            state = json.load(f)
        
        active_positions = state.get('active_positions', {})
        print(f"📊 В локальном состоянии {len(active_positions)} активных позиций:")
        
        for symbol, pos_data in active_positions.items():
            entry_price = pos_data.get('entry_price')
            quantity = pos_data.get('quantity')
            side = pos_data.get('side')
            sl_order_id = pos_data.get('sl_order_id')
            last_updated_sl = pos_data.get('last_updated_sl')
            
            print(f"   {symbol}: {side} {quantity} @ {entry_price}")
            print(f"      SL Order ID: {sl_order_id}, SL Price: {last_updated_sl}")
        
        return state
        
    except Exception as e:
        print(f"❌ Ошибка чтения состояния: {e}")
        return None

def analyze_sync_problems(exchange_positions, local_state, sl_by_symbol):
    """Анализ проблем синхронизации"""
    print("\n🔍 ДИАГНОСТИКА 5: Анализ проблем синхронизации")
    
    # Конвертируем биржевые позиции в удобный формат
    exchange_symbols = set()
    for pos in exchange_positions:
        symbol = pos['symbol'].replace('/', '_').replace(':USDT', '')
        exchange_symbols.add(symbol)
    
    # Локальные позиции
    local_positions = local_state.get('active_positions', {}) if local_state else {}
    local_symbols = set(local_positions.keys())
    
    print("🔍 Сравнение позиций:")
    print(f"   Биржа: {exchange_symbols}")
    print(f"   Локально: {local_symbols}")
    
    # Находим несоответствия
    missing_local = exchange_symbols - local_symbols  # Есть на бирже, нет локально
    missing_exchange = local_symbols - exchange_symbols  # Есть локально, нет на бирже
    
    if missing_local:
        print(f"❌ Отсутствуют в локальном состоянии: {missing_local}")
    
    if missing_exchange:
        print(f"❌ Призрачные позиции (есть локально, нет на бирже): {missing_exchange}")
    
    # Проверяем SL ордера для каждой позиции
    print("\n🔍 Проверка SL ордеров:")
    for symbol in local_symbols:
        pos_data = local_positions[symbol]
        sl_order_id = pos_data.get('sl_order_id')
        
        # Ищем соответствующий символ в SL ордерах
        ccxt_symbol = None
        for ccxt_sym in sl_by_symbol.keys():
            if symbol in ccxt_sym.replace('/', '_').replace(':USDT', ''):
                ccxt_symbol = ccxt_sym
                break
        
        if ccxt_symbol and ccxt_symbol in sl_by_symbol:
            sl_orders = sl_by_symbol[ccxt_symbol]
            print(f"   {symbol}: {len(sl_orders)} SL ордеров на бирже")
            
            # Проверяем, есть ли наш ордер
            our_order_found = False
            for order in sl_orders:
                if str(order['id']) == str(sl_order_id):
                    our_order_found = True
                    break
            
            if not our_order_found and sl_order_id:
                print(f"      ❌ SL ордер {sl_order_id} НЕ НАЙДЕН на бирже!")
            elif len(sl_orders) > 1:
                print(f"      ⚠️ Найдено {len(sl_orders)} SL ордеров (должен быть 1)")
            elif len(sl_orders) == 0:
                print(f"      ❌ НЕТ SL ордеров на бирже!")
            else:
                print(f"      ✅ SL ордер найден")
        else:
            print(f"   {symbol}: ❌ НЕТ SL ордеров на бирже!")
    
    return {
        'missing_local': missing_local,
        'missing_exchange': missing_exchange,
        'sl_problems': True  # Упрощенно, детали выше
    }

def main():
    print("🚨 EMERGENCY DIAGNOSTIC - Полная диагностика системы")
    print("=" * 60)
    
    # 1. Проверка подключения
    exchange = check_exchange_connection()
    if not exchange:
        print("❌ Не удалось подключиться к бирже. Диагностика прервана.")
        return
    
    # 2. Проверка позиций на бирже
    exchange_positions = check_open_positions(exchange)
    
    # 3. Проверка ордеров
    all_orders, sl_orders, sl_by_symbol = check_open_orders(exchange)
    
    # 4. Проверка локального состояния
    local_state = check_local_state()
    
    # 5. Анализ проблем
    problems = analyze_sync_problems(exchange_positions, local_state, sl_by_symbol)
    
    print("\n" + "=" * 60)
    print("📋 РЕЗЮМЕ ДИАГНОСТИКИ:")
    print(f"   Позиций на бирже: {len(exchange_positions)}")
    print(f"   SL ордеров на бирже: {len(sl_orders)}")
    print(f"   Локальных позиций: {len(local_state.get('active_positions', {})) if local_state else 0}")
    
    if problems['missing_local']:
        print(f"   ❌ Отсутствуют локально: {problems['missing_local']}")
    
    if problems['missing_exchange']:
        print(f"   ❌ Призрачные позиции: {problems['missing_exchange']}")
    
    print("\n🔧 Готов к исправлению проблем...")

if __name__ == "__main__":
    main()
