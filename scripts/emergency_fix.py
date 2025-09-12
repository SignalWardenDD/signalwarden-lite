#!/usr/bin/env python3
"""
EMERGENCY FIX - Исправление критических проблем системы
"""

import sys
import os
sys.path.insert(0, os.path.abspath('.'))

import json
import ccxt
from datetime import datetime
import time

def connect_exchange():
    """Подключение к бирже"""
    exchange = ccxt.binanceusdm({
        'apiKey': os.getenv('BINANCE_API_KEY'),
        'secret': os.getenv('BINANCE_SECRET'),
        'sandbox': False,
        'enableRateLimit': True,
    })
    exchange.options["warnOnFetchOpenOrdersWithoutSymbol"] = False
    return exchange

def fix_local_state(exchange):
    """Исправление локального состояния"""
    print("🔧 ИСПРАВЛЕНИЕ 1: Синхронизация локального состояния")
    
    state_file = 'data_files/trading_state_v1_6_TXB.json'
    
    # Создаем бэкап
    backup_file = f"{state_file}.emergency_backup.{int(time.time())}"
    if os.path.exists(state_file):
        import shutil
        shutil.copy2(state_file, backup_file)
        print(f"✅ Создан бэкап: {backup_file}")
    
    # Получаем актуальные данные с биржи
    positions = exchange.fetch_positions()
    active_positions = [p for p in positions if float(p['contracts']) > 0]
    
    orders = exchange.fetch_open_orders()
    sl_orders = [o for o in orders if o['type'] in ['stop_market', 'stop'] and o['info'].get('reduceOnly')]
    
    # Группируем SL ордера по символам
    sl_by_symbol = {}
    for order in sl_orders:
        symbol = order['symbol']
        if symbol not in sl_by_symbol:
            sl_by_symbol[symbol] = []
        sl_by_symbol[symbol].append(order)
    
    # Создаем новое состояние
    new_state = {
        "active_positions": {},
        "metadata": {
            "last_updated": datetime.now().isoformat(),
            "emergency_fix": True,
            "version": "v1_6_TXB"
        }
    }
    
    print("🔧 Восстанавливаем позиции из биржи:")
    
    for pos in active_positions:
        symbol = pos['symbol'].replace('/', '_').replace(':USDT', '')
        side = pos['side']
        size = float(pos['contracts'])
        entry_price = float(pos['entryPrice'])
        unrealized_pnl = float(pos['unrealizedPnl']) if pos['unrealizedPnl'] else 0.0
        
        print(f"   {symbol}: {side.upper()} {size} @ {entry_price}, PnL: {unrealized_pnl}")
        
        # Ищем SL ордер для этой позиции
        sl_order_id = None
        last_updated_sl = None
        
        ccxt_symbol = pos['symbol']
        if ccxt_symbol in sl_by_symbol:
            sl_order = sl_by_symbol[ccxt_symbol][0]  # Берем первый (должен быть только один)
            sl_order_id = str(sl_order['id'])
            last_updated_sl = float(sl_order['stopPrice'])
            print(f"      SL: {last_updated_sl} (Order: {sl_order_id})")
        else:
            print(f"      ❌ НЕТ SL ОРДЕРА!")
        
        # Добавляем позицию в состояние
        new_state["active_positions"][symbol] = {
            "symbol": symbol,
            "side": side,
            "quantity": size,
            "entry_price": entry_price,
            "sl_order_id": sl_order_id,
            "last_updated_sl": last_updated_sl,
            "unrealized_pnl": unrealized_pnl,
            "peak_pnl": max(0.0, unrealized_pnl),  # Начинаем с текущего PnL если положительный
            "trailing_active": False,
            "created_at": datetime.now().isoformat(),
            "last_sync": datetime.now().isoformat()
        }
    
    # Сохраняем новое состояние
    with open(state_file, 'w') as f:
        json.dump(new_state, f, indent=2)
    
    print(f"✅ Состояние восстановлено: {len(new_state['active_positions'])} позиций")
    return new_state

def clean_duplicate_sl_orders(exchange):
    """Очистка дублированных SL ордеров"""
    print("\n🔧 ИСПРАВЛЕНИЕ 2: Очистка дублированных SL ордеров")
    
    orders = exchange.fetch_open_orders()
    sl_orders = [o for o in orders if o['type'] in ['stop_market', 'stop'] and o['info'].get('reduceOnly')]
    
    # Группируем по символам
    sl_by_symbol = {}
    for order in sl_orders:
        symbol = order['symbol']
        if symbol not in sl_by_symbol:
            sl_by_symbol[symbol] = []
        sl_by_symbol[symbol].append(order)
    
    cleaned_count = 0
    
    for symbol, symbol_orders in sl_by_symbol.items():
        if len(symbol_orders) > 1:
            print(f"🧹 {symbol}: Найдено {len(symbol_orders)} SL ордеров, оставляем новейший")
            
            # Сортируем по времени создания (новейший первый)
            symbol_orders.sort(key=lambda x: x['timestamp'], reverse=True)
            
            newest_order = symbol_orders[0]
            orders_to_cancel = symbol_orders[1:]
            
            print(f"   Оставляем: ID {newest_order['id']} @ {newest_order['stopPrice']}")
            
            # Отменяем старые ордера
            for old_order in orders_to_cancel:
                try:
                    exchange.cancel_order(old_order['id'], symbol)
                    print(f"   ✅ Отменен: ID {old_order['id']} @ {old_order['stopPrice']}")
                    cleaned_count += 1
                    time.sleep(0.1)  # Небольшая задержка
                except Exception as e:
                    print(f"   ❌ Ошибка отмены {old_order['id']}: {e}")
    
    print(f"✅ Очищено {cleaned_count} дублированных SL ордеров")
    return cleaned_count

def create_missing_sl_orders(exchange, state):
    """Создание отсутствующих SL ордеров"""
    print("\n🔧 ИСПРАВЛЕНИЕ 3: Создание отсутствующих SL ордеров")
    
    positions_without_sl = []
    
    for symbol, pos_data in state["active_positions"].items():
        if not pos_data.get("sl_order_id"):
            positions_without_sl.append(symbol)
    
    if not positions_without_sl:
        print("✅ Все позиции имеют SL ордера")
        return 0
    
    print(f"🔧 Создаем SL ордера для {len(positions_without_sl)} позиций:")
    
    created_count = 0
    
    for symbol in positions_without_sl:
        pos_data = state["active_positions"][symbol]
        
        try:
            # Получаем текущую цену
            ccxt_symbol = f"{symbol.replace('_', '/')}/USDT:USDT"
            ticker = exchange.fetch_ticker(ccxt_symbol)
            current_price = float(ticker['last'])
            
            # Рассчитываем SL цену (2% от входа для безопасности)
            entry_price = pos_data['entry_price']
            side = pos_data['side']
            quantity = pos_data['quantity']
            
            if side == 'long':
                sl_price = entry_price * 0.98  # 2% ниже входа
            else:
                sl_price = entry_price * 1.02  # 2% выше входа
            
            # Проверяем, что SL не слишком близко к текущей цене
            distance_pct = abs(current_price - sl_price) / current_price * 100
            if distance_pct < 0.5:  # Минимум 0.5%
                if side == 'long':
                    sl_price = current_price * 0.995  # 0.5% ниже
                else:
                    sl_price = current_price * 1.005  # 0.5% выше
            
            print(f"   {symbol}: Создаем SL @ {sl_price:.6f} (текущая: {current_price:.6f})")
            
            # Создаем SL ордер
            order = exchange.create_order(
                symbol=ccxt_symbol,
                type='stop_market',
                side='sell' if side == 'long' else 'buy',
                amount=quantity,
                price=None,
                params={
                    'stopPrice': sl_price,
                    'reduceOnly': True
                }
            )
            
            # Обновляем состояние
            pos_data['sl_order_id'] = str(order['id'])
            pos_data['last_updated_sl'] = sl_price
            
            print(f"   ✅ SL создан: ID {order['id']}")
            created_count += 1
            time.sleep(0.2)  # Задержка между ордерами
            
        except Exception as e:
            print(f"   ❌ Ошибка создания SL для {symbol}: {e}")
    
    # Сохраняем обновленное состояние
    state_file = 'data_files/trading_state_v1_6_TXB.json'
    with open(state_file, 'w') as f:
        json.dump(state, f, indent=2)
    
    print(f"✅ Создано {created_count} SL ордеров")
    return created_count

def validate_final_state(exchange):
    """Финальная валидация состояния"""
    print("\n🔍 ФИНАЛЬНАЯ ВАЛИДАЦИЯ:")
    
    # Проверяем позиции на бирже
    positions = exchange.fetch_positions()
    active_positions = [p for p in positions if float(p['contracts']) > 0]
    
    # Проверяем SL ордера
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
    
    if missing_sl:
        print(f"❌ Позиции без SL: {missing_sl}")
        return False
    
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
        return False
    
    print("✅ Все проверки пройдены успешно!")
    return True

def main():
    print("🚨 EMERGENCY FIX - Исправление критических проблем")
    print("=" * 60)
    
    # Подключение к бирже
    exchange = connect_exchange()
    
    # 1. Исправление локального состояния
    state = fix_local_state(exchange)
    
    # 2. Очистка дублированных SL ордеров
    clean_duplicate_sl_orders(exchange)
    
    # 3. Создание отсутствующих SL ордеров
    create_missing_sl_orders(exchange, state)
    
    # 4. Финальная валидация
    success = validate_final_state(exchange)
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 ИСПРАВЛЕНИЕ ЗАВЕРШЕНО УСПЕШНО!")
        print("✅ Все критические проблемы исправлены")
        print("✅ Система готова к безопасной работе")
    else:
        print("⚠️ ИСПРАВЛЕНИЕ ЗАВЕРШЕНО С ПРЕДУПРЕЖДЕНИЯМИ")
        print("🔧 Рекомендуется дополнительная проверка")
    
    return success

if __name__ == "__main__":
    main()
