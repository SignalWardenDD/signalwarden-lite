#!/usr/bin/env python3
"""
ПРОВЕРКА РЕАЛЬНОГО СТАТУСА PNUT_USDT
Проверяем данные PNUT на Binance и в системе
"""

import ccxt
import os
import json
import sys
from datetime import datetime
from dotenv import load_dotenv

def check_pnut_real_status():
    """Проверяем реальный статус PNUT"""
    print("🔍 ПРОВЕРКА РЕАЛЬНОГО СТАТУСА PNUT_USDT")
    print("=" * 70)
    
    # 1. Подключение к Binance
    try:
        load_dotenv()
        
        api_key = os.getenv('BINANCE_API_KEY')
        secret = os.getenv('BINANCE_SECRET')
        
        if not api_key or not secret:
            print(f"❌ Отсутствуют API ключи")
            return False
        
        exchange = ccxt.binanceusdm({
            'apiKey': api_key,
            'secret': secret,
            'sandbox': False,
            'options': {'defaultType': 'future'}
        })
        
        exchange.load_markets()
        print("✅ Подключение к Binance успешно")
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")
        return False
    
    symbol = 'PNUT/USDT'
    ccxt_symbol = 'PNUTUSDT'
    
    # 2. ТЕКУЩАЯ ЦЕНА
    try:
        ticker = exchange.fetch_ticker(symbol)
        current_price = ticker['last']
        print(f"\n💰 ТЕКУЩАЯ ЦЕНА PNUT: ${current_price:.6f}")
    except Exception as e:
        print(f"❌ Ошибка получения цены: {e}")
        return False
    
    # 3. ПОЗИЦИЯ НА BINANCE
    try:
        positions = exchange.fetch_positions([ccxt_symbol])
        pnut_position = None
        
        for pos in positions:
            if pos['symbol'] == symbol and abs(pos['size']) > 0:
                pnut_position = pos
                break
        
        if pnut_position:
            entry = pnut_position['entryPrice']
            qty = pnut_position['size']
            mark_price = pnut_position['markPrice']
            pnl_usdt = pnut_position['unrealizedPnl']
            
            print(f"\n📊 ПОЗИЦИЯ PNUT НА BINANCE:")
            print(f"   Сторона: {pnut_position['side']}")
            print(f"   Размер: {qty:.2f}")
            print(f"   Entry Price: ${entry:.6f}")
            print(f"   Mark Price: ${mark_price:.6f}")
            print(f"   PnL: ${pnl_usdt:.6f}")
            print(f"   PnL %: {pnut_position['percentage']:.4f}%")
            
            # Рассчитываем точный PnL
            if pnut_position['side'] == 'long':
                calculated_pnl = (mark_price - entry) * qty
                print(f"   Расчетный PnL: ${calculated_pnl:.6f}")
                
                # АНАЛИЗ ТРЕЙЛИНГА
                print(f"\n🎯 АНАЛИЗ ТРЕЙЛИНГА:")
                if pnl_usdt >= 0.06:
                    print(f"   ✅ PnL ${pnl_usdt:.4f} >= $0.06 - ТРЕЙЛИНГ ДОЛЖЕН БЫТЬ АКТИВЕН!")
                    print(f"   🛡️ Минимальная защита должна быть: $0.03")
                    expected_sl = entry + (0.03 / qty)
                    print(f"   📈 Ожидаемый минимальный SL: ${expected_sl:.6f}")
                elif pnl_usdt > 0:
                    print(f"   ⚠️ PnL ${pnl_usdt:.4f} > 0 но < $0.06 - трейлинг НЕ должен быть активен")
                else:
                    print(f"   📉 PnL ${pnl_usdt:.4f} отрицательный - трейлинг НЕ должен быть активен")
        else:
            print(f"\n❌ ПОЗИЦИЯ PNUT НЕ НАЙДЕНА НА BINANCE")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка получения позиций: {e}")
        return False
    
    # 4. ОТКРЫТЫЕ ОРДЕРА
    try:
        orders = exchange.fetch_open_orders(symbol)
        print(f"\n📋 ОТКРЫТЫЕ ОРДЕРА PNUT ({len(orders)}):")
        
        sl_orders = []
        for order in orders:
            if order['type'] in ['stop_market', 'stop']:
                sl_orders.append(order)
                print(f"   🛑 SL Ордер ID: {order['id']}")
                print(f"      Тип: {order['type']}")
                print(f"      Сторона: {order['side']}")
                print(f"      Размер: {order['amount']:.2f}")
                print(f"      Stop Price: ${order.get('stopPrice', 'N/A'):.6f}")
                print(f"      Статус: {order['status']}")
        
        if not sl_orders:
            print(f"   ⚠️ STOP-LOSS ОРДЕРОВ НЕ НАЙДЕНО!")
        
        # АНАЛИЗ SL ОРДЕРОВ
        if sl_orders and pnut_position:
            sl_order = sl_orders[0]
            stop_price = sl_order.get('stopPrice')
            entry = pnut_position['entryPrice']
            
            if stop_price and entry:
                if pnut_position['side'] == 'long':
                    if stop_price > entry:
                        protected_profit = (stop_price - entry) * qty
                        print(f"\n🔍 АНАЛИЗ ТРЕЙЛИНГ SL:")
                        print(f"   Entry: ${entry:.6f}")
                        print(f"   SL: ${stop_price:.6f}")
                        print(f"   ✅ SL ВЫШЕ ENTRY - ТРЕЙЛИНГ АКТИВЕН!")
                        print(f"   🛡️ Защищенная прибыль: ${protected_profit:.6f}")
                        
                        if protected_profit >= 0.03:
                            print(f"   ✅ Минимальная защита $0.03 обеспечена")
                        else:
                            print(f"   ❌ Минимальная защита НЕ обеспечена!")
                    else:
                        sl_distance = abs(stop_price - entry)
                        sl_distance_pct = (sl_distance / entry) * 100
                        print(f"\n🔍 АНАЛИЗ ОБЫЧНОГО SL:")
                        print(f"   Entry: ${entry:.6f}")
                        print(f"   SL: ${stop_price:.6f}")
                        print(f"   Дистанция: ${sl_distance:.6f} ({sl_distance_pct:.2f}%)")
                        print(f"   📉 SL НИЖЕ ENTRY - обычный стоп-лосс")
                        
    except Exception as e:
        print(f"❌ Ошибка получения ордеров: {e}")
        return False
    
    # 5. ДАННЫЕ ИЗ JSON
    try:
        with open('trading_state_v1_6_TXB.json', 'r', encoding='utf-8') as f:
            state = json.load(f)
        
        print(f"\n📄 ДАННЫЕ ИЗ JSON:")
        
        # Проверяем symbols секцию
        if 'PNUT_USDT' in state.get('symbols', {}):
            pnut_symbols = state['symbols']['PNUT_USDT']
            active_pos = pnut_symbols.get('active_position')
            
            if active_pos:
                print(f"   symbols.PNUT_USDT.active_position:")
                print(f"      Entry: ${active_pos.get('entry', 0):.6f}")
                print(f"      Qty: {active_pos.get('qty', 0):.2f}")
                print(f"      SL Current: ${active_pos.get('sl_current', 0):.6f}")
                print(f"      Peak PnL: ${active_pos.get('peak_pnl_usdt', 0):.6f}")
                print(f"      Trailing Active: {active_pos.get('trailing_active', False)}")
            else:
                print(f"   symbols.PNUT_USDT.active_position: None")
        
        # Проверяем active_positions секцию
        active_positions = state.get('active_positions', {})
        pnut_keys = [key for key in active_positions.keys() if 'PNUT' in key]
        
        if pnut_keys:
            for key in pnut_keys:
                pnut_active = active_positions[key]
                print(f"   active_positions.{key}:")
                print(f"      Entry: ${pnut_active.get('entry', 0):.6f}")
                print(f"      Qty: {pnut_active.get('qty', 0):.2f}")
                print(f"      SL Current: ${pnut_active.get('sl_current', 0):.6f}")
                print(f"      Peak PnL: ${pnut_active.get('peak_pnl_usdt', 0):.6f}")
                print(f"      Trailing Active: {pnut_active.get('trailing_active', False)}")
        else:
            print(f"   active_positions: Нет PNUT позиций")
            
    except Exception as e:
        print(f"⚠️ Ошибка чтения JSON: {e}")
    
    # 6. ДИАГНОЗ
    print(f"\n🎯 ДИАГНОЗ:")
    if pnut_position and pnl_usdt >= 0.06:
        print(f"   🚨 КРИТИЧНО: PNUT PnL ${pnl_usdt:.4f} >= $0.06")
        print(f"   🛡️ ТРЕЙЛИНГ ДОЛЖЕН БЫТЬ АКТИВЕН!")
        print(f"   💰 Минимальная защита: $0.03")
        
        if sl_orders:
            sl_order = sl_orders[0]
            stop_price = sl_order.get('stopPrice')
            if stop_price and stop_price > entry:
                print(f"   ✅ SL выше entry - трейлинг работает")
            else:
                print(f"   ❌ SL не защищает прибыль - ПРОБЛЕМА!")
        else:
            print(f"   ❌ НЕТ SL ОРДЕРОВ - КРИТИЧЕСКАЯ ПРОБЛЕМА!")
    
    return True

if __name__ == "__main__":
    success = check_pnut_real_status()
    exit(0 if success else 1)
