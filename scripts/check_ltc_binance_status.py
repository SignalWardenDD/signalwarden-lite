#!/usr/bin/env python3
"""
ПРОВЕРКА СТАТУСА LTC_USDT НА BINANCE
Проверяем реальные данные позиции и ордеров
"""

import ccxt
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

def check_ltc_binance_status():
    """Проверяем статус LTC на Binance"""
    print("🔍 ПРОВЕРКА LTC_USDT НА BINANCE")
    print("=" * 60)
    
    # Подключение к Binance
    try:
        load_dotenv()
        
        api_key = os.getenv('BINANCE_API_KEY')
        secret = os.getenv('BINANCE_SECRET')
        
        if not api_key or not secret:
            print(f"❌ Отсутствуют API ключи в .env файле")
            print(f"   API Key: {'✅' if api_key else '❌'}")
            print(f"   Secret: {'✅' if secret else '❌'}")
            return False
        
        exchange = ccxt.binanceusdm({
            'apiKey': api_key,
            'secret': secret,
            'sandbox': False,
            'options': {
                'defaultType': 'future'
            }
        })
        
        exchange.load_markets()
        print("✅ Подключение к Binance USDM успешно")
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")
        return False
    
    symbol = 'LTC/USDT'
    ccxt_symbol = 'LTCUSDT'
    
    # 1. ТЕКУЩАЯ ЦЕНА
    try:
        ticker = exchange.fetch_ticker(symbol)
        current_price = ticker['last']
        print(f"\n💰 ТЕКУЩАЯ ЦЕНА LTC: ${current_price:.6f}")
    except Exception as e:
        print(f"❌ Ошибка получения цены: {e}")
        return False
    
    # 2. ПОЗИЦИИ
    try:
        positions = exchange.fetch_positions([ccxt_symbol])
        ltc_position = None
        
        for pos in positions:
            if pos['symbol'] == symbol and abs(pos['size']) > 0:
                ltc_position = pos
                break
        
        if ltc_position:
            print(f"\n📊 ПОЗИЦИЯ LTC_USDT:")
            print(f"   Сторона: {ltc_position['side']}")
            print(f"   Размер: {ltc_position['size']:.6f}")
            print(f"   Entry Price: ${ltc_position['entryPrice']:.6f}")
            print(f"   Mark Price: ${ltc_position['markPrice']:.6f}")
            print(f"   PnL: ${ltc_position['unrealizedPnl']:.6f}")
            print(f"   PnL %: {ltc_position['percentage']:.4f}%")
            
            # Рассчитываем точный PnL в USDT
            entry = ltc_position['entryPrice']
            qty = ltc_position['size']
            mark_price = ltc_position['markPrice']
            
            if ltc_position['side'] == 'long':
                pnl_usdt = (mark_price - entry) * qty
                print(f"   Расчетный PnL: ${pnl_usdt:.6f}")
                
                # АНАЛИЗ ТРЕЙЛИНГА
                print(f"\n🎯 АНАЛИЗ ТРЕЙЛИНГА:")
                if pnl_usdt >= 0.06:
                    print(f"   ✅ PnL ${pnl_usdt:.4f} >= $0.06 - ТРЕЙЛИНГ ДОЛЖЕН БЫТЬ АКТИВЕН")
                    min_protection = 0.03  # 50% от $0.06
                    print(f"   🛡️ Минимальная защита: ${min_protection:.3f}")
                    expected_sl = entry + (min_protection / qty)
                    print(f"   📈 Ожидаемый минимальный SL: ${expected_sl:.6f}")
                else:
                    print(f"   ❌ PnL ${pnl_usdt:.4f} < $0.06 - ТРЕЙЛИНГ НЕ ДОЛЖЕН БЫТЬ АКТИВЕН")
                    print(f"   📉 Должен действовать обычный SL -2.5×ATR")
        else:
            print(f"\n❌ ПОЗИЦИЯ LTC_USDT НЕ НАЙДЕНА")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка получения позиций: {e}")
        return False
    
    # 3. ОТКРЫТЫЕ ОРДЕРА
    try:
        orders = exchange.fetch_open_orders(symbol)
        print(f"\n📋 ОТКРЫТЫЕ ОРДЕРА ({len(orders)}):")
        
        sl_orders = []
        for order in orders:
            if order['type'] in ['stop_market', 'stop']:
                sl_orders.append(order)
                print(f"   🛑 SL Ордер ID: {order['id']}")
                print(f"      Тип: {order['type']}")
                print(f"      Сторона: {order['side']}")
                print(f"      Размер: {order['amount']:.6f}")
                print(f"      Stop Price: ${order.get('stopPrice', 'N/A'):.6f}")
                print(f"      Статус: {order['status']}")
        
        if not sl_orders:
            print(f"   ⚠️ STOP-LOSS ОРДЕРОВ НЕ НАЙДЕНО!")
        
        # АНАЛИЗ SL ОРДЕРОВ
        if sl_orders and ltc_position:
            sl_order = sl_orders[0]  # Берем первый SL ордер
            stop_price = sl_order.get('stopPrice')
            entry = ltc_position['entryPrice']
            
            if stop_price and entry:
                sl_distance = abs(stop_price - entry)
                sl_distance_pct = (sl_distance / entry) * 100
                
                print(f"\n🔍 АНАЛИЗ СТОП-ЛОССА:")
                print(f"   Entry: ${entry:.6f}")
                print(f"   SL: ${stop_price:.6f}")
                print(f"   Дистанция: ${sl_distance:.6f} ({sl_distance_pct:.2f}%)")
                
                # Проверяем соответствие 2.5×ATR
                expected_atr_distance_pct = 2.5 * 2.0  # Примерно 5% для 2% ATR
                
                if sl_distance_pct < 3.0:  # Менее 3% - подозрительно близко
                    print(f"   ⚠️ SL СЛИШКОМ БЛИЗКО! Возможно трейлинг активен неправильно")
                elif sl_distance_pct > 8.0:  # Более 8% - слишком далеко
                    print(f"   ⚠️ SL СЛИШКОМ ДАЛЕКО!")
                else:
                    print(f"   ✅ SL на разумной дистанции")
                    
    except Exception as e:
        print(f"❌ Ошибка получения ордеров: {e}")
        return False
    
    # 4. ИТОГОВЫЙ ДИАГНОЗ
    print(f"\n🎯 ДИАГНОЗ:")
    if ltc_position:
        pnl = ltc_position['unrealizedPnl']
        if pnl < 0:
            print(f"   📉 PnL отрицательный (${pnl:.4f}) - трейлинг НЕ должен быть активен")
            print(f"   🛡️ Должен действовать обычный SL -2.5×ATR от entry")
        elif pnl >= 0.06:
            print(f"   📈 PnL >= $0.06 (${pnl:.4f}) - трейлинг ДОЛЖЕН быть активен")
            print(f"   🛡️ Должна быть защищена минимум $0.03 прибыли")
        else:
            print(f"   📊 PnL < $0.06 (${pnl:.4f}) - трейлинг НЕ должен быть активен")
            print(f"   🛡️ Должен действовать обычный SL -2.5×ATR от entry")
    
    return True

if __name__ == "__main__":
    success = check_ltc_binance_status()
    exit(0 if success else 1)
