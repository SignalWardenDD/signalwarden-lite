#!/usr/bin/env python3
"""
Проверка стоп-ордеров на Binance
"""

import os
import sys
import yaml
import json
from typing import Dict, List, Any

# Добавляем путь к модулям
sys.path.append('.')

def check_binance_stops():
    """Проверка стоп-ордеров на Binance"""
    
    print("🔍 ПРОВЕРКА СТОП-ОРДЕРОВ НА BINANCE")
    print("=" * 80)
    
    # Проверяем состояние системы
    try:
        with open('trading_state_v1_6_TXB.json', 'r') as f:
            state = json.load(f)
    except Exception as e:
        print(f"❌ Не удалось прочитать состояние системы: {e}")
        return
    
    print("📊 АКТИВНЫЕ ПОЗИЦИИ В СИСТЕМЕ:")
    print("-" * 60)
    
    symbols_with_positions = []
    
    for symbol, data in state.get('symbols', {}).items():
        if symbol.endswith('_position'):
            continue
            
        active_pos = data.get('active_position')
        if active_pos:
            symbols_with_positions.append(symbol)
            
            entry = active_pos.get('entry', 0)
            side = active_pos.get('side', 'UNKNOWN')
            qty = active_pos.get('qty', 0)
            sl_current = active_pos.get('sl_current', 0)
            sl_initial = active_pos.get('sl_initial', 0)
            peak_pnl = active_pos.get('peak_pnl_usdt', 0)
            
            print(f"📊 {symbol}:")
            print(f"   Side: {side}")
            print(f"   Entry: ${entry:.6f}")
            print(f"   Quantity: {qty}")
            print(f"   SL Current: ${sl_current:.6f}")
            print(f"   SL Initial: ${sl_initial:.6f}")
            print(f"   Peak PnL: {peak_pnl:.4f} USDT")
            
            # Рассчитываем расстояние SL
            if side == 'LONG':
                sl_distance = (entry - sl_current) / entry * 100
                sl_initial_distance = (entry - sl_initial) / entry * 100
            else:
                sl_distance = (sl_current - entry) / entry * 100
                sl_initial_distance = (sl_initial - entry) / entry * 100
            
            print(f"   SL Distance: {sl_distance:.2f}%")
            print(f"   SL Initial Distance: {sl_initial_distance:.2f}%")
            
            # Проверяем, обновлялся ли SL
            if abs(sl_current - sl_initial) > 1e-8:
                print(f"   ✅ SL был обновлен (трейлинг работал)")
            else:
                print(f"   ❌ SL не обновлялся (только начальный)")
            
            print()
    
    if not symbols_with_positions:
        print("❌ НЕТ АКТИВНЫХ ПОЗИЦИЙ В СИСТЕМЕ")
        return
    
    print("🎯 ЧТО НУЖНО ПРОВЕРИТЬ НА BINANCE:")
    print("-" * 60)
    
    print("1. ОТКРОЙТЕ BINANCE FUTURES:")
    print("   • Перейдите в раздел 'Позиции'")
    print("   • Проверьте наличие открытых позиций")
    
    print()
    print("2. ПРОВЕРЬТЕ ОТКРЫТЫЕ ОРДЕРА:")
    print("   • Перейдите в 'Открытые ордера'")
    print("   • Найдите стоп-ордера для каждой позиции")
    print("   • Тип должен быть 'Stop Market'")
    
    print()
    print("3. ПРОВЕРЬТЕ ЦЕНЫ СТОП-ОРДЕРОВ:")
    for symbol in symbols_with_positions:
        data = state['symbols'][symbol]
        active_pos = data['active_position']
        sl_current = active_pos.get('sl_current', 0)
        
        print(f"   • {symbol}: SL должен быть около ${sl_current:.6f}")
    
    print()
    print("4. ПРИЗНАКИ ПРОБЛЕМ:")
    print("   ❌ Нет стоп-ордеров для позиций")
    print("   ❌ Цены SL не соответствуют системе")
    print("   ❌ Тип ордера не 'Stop Market'")
    print("   ❌ Ордера в статусе 'Отклонен' или 'Отменен'")
    
    print()
    print("5. ЕСЛИ СТОП-ОРДЕРОВ НЕТ:")
    print("   • Система может не создавать их из-за ошибок")
    print("   • Проверьте логи на ошибки API")
    print("   • Убедитесь в правильности настроек API")
    print("   • Проверьте баланс и margin requirements")
    
    # Проверяем последние логи
    print()
    print("📋 РЕКОМЕНДУЕМЫЕ ДЕЙСТВИЯ:")
    print("-" * 60)
    
    print("1. НЕМЕДЛЕННО:")
    print("   • Проверить наличие стоп-ордеров на Binance")
    print("   • Если их нет - СРОЧНО установить вручную")
    print("   • Проверить логи системы на ошибки")
    
    print()
    print("2. АНАЛИЗ ЛОГОВ:")
    print("   • Найти сообщения 'SL order created'")
    print("   • Найти ошибки 'Failed to create SL'")
    print("   • Проверить обновления 'SL improvement'")
    
    print()
    print("3. ТЕСТИРОВАНИЕ:")
    print("   • Перезапустить систему")
    print("   • Проследить создание новых SL")
    print("   • Убедиться в синхронизации с биржей")

if __name__ == "__main__":
    check_binance_stops()
