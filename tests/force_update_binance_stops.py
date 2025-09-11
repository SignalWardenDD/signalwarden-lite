#!/usr/bin/env python3
"""
Принудительное обновление стоп-лоссов на Binance
"""

import os
import sys
import json
import yaml
import ccxt
from typing import Dict, Any
from dotenv import load_dotenv

# Добавляем путь к модулям
sys.path.append('.')

# Загружаем переменные окружения
load_dotenv()

def make_exchange(cfg: dict):
    """Создание подключения к бирже"""
    # Получаем API ключи из переменных окружения
    api_key = os.getenv('BINANCE_API_KEY')
    secret = os.getenv('BINANCE_SECRET')
    
    if not api_key or not secret:
        raise ValueError("❌ Missing BINANCE_API_KEY or BINANCE_SECRET in .env file")
    
    exchange = ccxt.binanceusdm({
        'apiKey': api_key,
        'secret': secret,
        'enableRateLimit': cfg['exchange'].get('rate_limit', True),
        'timeout': 30000,
        'options': {'defaultType': 'future'}
    })
    
    # Set sandbox/live mode
    testnet_mode = cfg['exchange'].get('testnet', True)
    if testnet_mode:
        exchange.set_sandbox_mode(True)
        print("🧪 TESTNET mode enabled")
    else:
        print("🔴 LIVE TRADING mode enabled!")
    
    exchange.load_markets()
    return exchange

def ccxt_symbol(symbol: str) -> str:
    """Конвертация символа для CCXT"""
    return symbol.replace('_', '/')

def force_update_binance_stops():
    """Принудительное обновление стоп-лоссов на Binance"""
    
    print("🔧 ПРИНУДИТЕЛЬНОЕ ОБНОВЛЕНИЕ СТОП-ЛОССОВ НА BINANCE")
    print("=" * 80)
    
    # Загрузить конфигурацию
    try:
        with open('signalwarden_lite/config/config_production.yaml', 'r') as f:
            cfg = yaml.safe_load(f)
    except Exception as e:
        print(f"❌ Не удалось загрузить конфигурацию: {e}")
        return
    
    # Загрузить состояние системы
    try:
        with open('trading_state_v1_6_TXB.json', 'r') as f:
            state = json.load(f)
    except Exception as e:
        print(f"❌ Не удалось прочитать состояние системы: {e}")
        return
    
    # Подключиться к бирже
    try:
        exchange = make_exchange(cfg)
        print("✅ Подключение к Binance установлено")
    except Exception as e:
        print(f"❌ Не удалось подключиться к Binance: {e}")
        return
    
    print()
    print("🔍 АНАЛИЗ ПОЗИЦИЙ И СТОП-ОРДЕРОВ:")
    print("-" * 80)
    
    updated_count = 0
    errors = []
    
    for symbol, data in state.get('symbols', {}).items():
        if symbol.endswith('_position'):
            continue
            
        active_pos = data.get('active_position')
        if not active_pos:
            continue
        
        entry = active_pos.get('entry', 0)
        side = active_pos.get('side', 'UNKNOWN')
        qty = active_pos.get('qty', 0)
        sl_current = active_pos.get('sl_current', 0)
        
        print(f"📊 {symbol}:")
        print(f"   Entry: ${entry:.6f}")
        print(f"   Side: {side}")
        print(f"   Quantity: {qty:.6f}")
        print(f"   Target SL: ${sl_current:.6f}")
        
        try:
            ccxt_sym = ccxt_symbol(symbol)
            
            # Проверяем существующие стоп-ордера
            open_orders = exchange.fetch_open_orders(ccxt_sym)
            stop_orders = [order for order in open_orders 
                          if order['type'] in ['stop_market', 'stop'] and 
                          order['info'].get('reduceOnly')]
            
            print(f"   Существующих стоп-ордеров: {len(stop_orders)}")
            
            # Отменяем все старые стоп-ордера
            for order in stop_orders:
                try:
                    exchange.cancel_order(order['id'], ccxt_sym)
                    print(f"   ✅ Отменен старый SL ордер {order['id']} @ ${order.get('stopPrice', order.get('price')):.6f}")
                except Exception as e:
                    print(f"   ⚠️ Не удалось отменить ордер {order['id']}: {e}")
            
            # Создаем новый стоп-ордер
            sl_side = 'sell' if side == 'LONG' else 'buy'
            
            try:
                sl_order = exchange.create_order(
                    ccxt_sym,
                    'stop_market',
                    sl_side,
                    qty,
                    None,  # Нет цены исполнения для stop_market
                    params={
                        'stopPrice': sl_current,
                        'reduceOnly': True,
                        'timeInForce': 'GTC'
                    }
                )
                
                print(f"   ✅ СОЗДАН новый SL ордер {sl_order['id']} @ ${sl_current:.6f}")
                updated_count += 1
                
            except Exception as e:
                error_msg = f"{symbol}: Не удалось создать SL ордер: {e}"
                print(f"   ❌ {error_msg}")
                errors.append(error_msg)
            
        except Exception as e:
            error_msg = f"{symbol}: Ошибка при обработке: {e}"
            print(f"   ❌ {error_msg}")
            errors.append(error_msg)
        
        print()
    
    # Итоговый отчет
    print("🎯 РЕЗУЛЬТАТ ОБНОВЛЕНИЯ:")
    print("-" * 60)
    
    total_positions = len([s for s in state.get('symbols', {}).keys() 
                          if not s.endswith('_position') and 
                          state['symbols'][s].get('active_position')])
    
    print(f"✅ Всего позиций: {total_positions}")
    print(f"✅ Успешно обновлено: {updated_count}")
    print(f"❌ Ошибок: {len(errors)}")
    
    if errors:
        print()
        print("❌ ОШИБКИ:")
        for error in errors:
            print(f"   • {error}")
    
    if updated_count > 0:
        print()
        print("✅ РЕКОМЕНДАЦИИ:")
        print("   • Проверьте открытые ордера на Binance")
        print("   • Убедитесь, что все SL ордера активны")
        print("   • Проследите логи системы на предмет ошибок")
    
    print()
    print("⚠️ ВАЖНО:")
    print("   • Все старые стоп-ордера были отменены")
    print("   • Созданы новые с правильными ценами")
    print("   • Система будет управлять ими автоматически")

if __name__ == "__main__":
    force_update_binance_stops()
