#!/usr/bin/env python3
"""
Диагностика проблем с трейлингом LTC
"""

import os
import sys
import json
import yaml
from dotenv import load_dotenv

# Добавляем путь к модулям
sys.path.append('.')
load_dotenv()

def debug_ltc_trailing():
    """Диагностика трейлинга LTC"""
    
    print("🔍 ДИАГНОСТИКА ТРЕЙЛИНГА LTC")
    print("=" * 80)
    
    # Загрузить состояние системы
    try:
        with open('trading_state_v1_6_TXB.json', 'r') as f:
            state = json.load(f)
    except Exception as e:
        print(f"❌ Не удалось прочитать состояние системы: {e}")
        return
    
    # Загрузить конфигурацию
    with open('signalwarden_lite/config/config_production.yaml', 'r') as f:
        cfg = yaml.safe_load(f)
    
    trailing_config = cfg['trailing']
    
    print("📊 КОНФИГУРАЦИЯ ТРЕЙЛИНГА:")
    print(f"   activate_pnl_usdt: {trailing_config['activate_pnl_usdt']}")
    print(f"   level_1_pnl: {trailing_config['level_1_pnl']} (keep {trailing_config['level_1_keep_pct']*100}%)")
    print(f"   level_2_pnl: {trailing_config['level_2_pnl']} (keep {trailing_config['level_2_keep_pct']*100}%)")
    print(f"   level_3_pnl: {trailing_config['level_3_pnl']} (keep {trailing_config['level_3_keep_pct']*100}%)")
    print(f"   level_4_pnl: {trailing_config['level_4_pnl']} (keep {trailing_config['level_4_keep_pct']*100}%)")
    print()
    
    # Найти позицию LTC
    ltc_data = state.get('symbols', {}).get('LTC_USDT', {})
    active_pos = ltc_data.get('active_position')
    
    if not active_pos:
        print("❌ Позиция LTC не найдена!")
        return
    
    entry = active_pos.get('entry', 0)
    side = active_pos.get('side', 'UNKNOWN')
    qty = active_pos.get('qty', 0)
    sl_current = active_pos.get('sl_current', 0)
    sl_initial = active_pos.get('sl_initial', 0)
    peak_pnl = active_pos.get('peak_pnl_usdt', 0)
    
    print("📊 ТЕКУЩАЯ ПОЗИЦИЯ LTC:")
    print(f"   Entry: ${entry:.6f}")
    print(f"   Side: {side}")
    print(f"   Quantity: {qty:.6f}")
    print(f"   SL Initial: ${sl_initial:.6f}")
    print(f"   SL Current: ${sl_current:.6f}")
    print(f"   Peak PnL: {peak_pnl:.4f} USDT")
    print()
    
    # Получим текущую цену (симуляция)
    # Для диагностики используем несколько сценариев
    
    test_prices = [
        114.0,   # Ниже entry (убыток)
        114.5,   # Около entry
        115.0,   # Небольшая прибыль
        116.0,   # Средняя прибыль
        117.0,   # Хорошая прибыль
        118.0,   # Большая прибыль
    ]
    
    print("🧮 ТЕСТИРОВАНИЕ ТРЕЙЛИНГА НА РАЗНЫХ ЦЕНАХ:")
    print("-" * 80)
    
    for current_price in test_prices:
        print(f"💰 ЦЕНА: ${current_price:.2f}")
        
        # Рассчитываем текущий PnL
        if side == 'LONG':
            current_pnl = (current_price - entry) * qty
        else:
            current_pnl = (entry - current_price) * qty
        
        print(f"   Current PnL: {current_pnl:.4f} USDT")
        
        # Проверяем активацию трейлинга
        if current_pnl >= trailing_config['activate_pnl_usdt']:
            print(f"   ✅ Трейлинг АКТИВЕН (PnL >= {trailing_config['activate_pnl_usdt']})")
            
            # Определяем уровень трейлинга
            level_info = None
            if current_pnl >= trailing_config['level_4_pnl']:
                level_info = {
                    'level': 4,
                    'pnl_threshold': trailing_config['level_4_pnl'],
                    'keep_pct': trailing_config['level_4_keep_pct']
                }
            elif current_pnl >= trailing_config['level_3_pnl']:
                level_info = {
                    'level': 3,
                    'pnl_threshold': trailing_config['level_3_pnl'],
                    'keep_pct': trailing_config['level_3_keep_pct']
                }
            elif current_pnl >= trailing_config['level_2_pnl']:
                level_info = {
                    'level': 2,
                    'pnl_threshold': trailing_config['level_2_pnl'],
                    'keep_pct': trailing_config['level_2_keep_pct']
                }
            elif current_pnl >= trailing_config['level_1_pnl']:
                level_info = {
                    'level': 1,
                    'pnl_threshold': trailing_config['level_1_pnl'],
                    'keep_pct': trailing_config['level_1_keep_pct']
                }
            
            if level_info:
                print(f"   📊 Уровень {level_info['level']}: Сохранить {level_info['keep_pct']*100}% от {level_info['pnl_threshold']} USDT")
                
                # Рассчитываем целевую прибыль
                target_profit = level_info['pnl_threshold'] * level_info['keep_pct']
                print(f"   🎯 Целевая прибыль: {target_profit:.4f} USDT")
                
                # Рассчитываем новый SL
                if side == 'LONG':
                    new_sl = entry + (target_profit / qty)
                else:
                    new_sl = entry - (target_profit / qty)
                
                print(f"   🛡️ Новый SL: ${new_sl:.6f}")
                
                # Сравниваем с текущим SL
                if side == 'LONG':
                    if new_sl > sl_current:
                        print(f"   ✅ SL УЛУЧШАЕТСЯ: ${sl_current:.6f} → ${new_sl:.6f}")
                    elif new_sl < sl_current:
                        print(f"   ❌ SL УХУДШАЕТСЯ: ${sl_current:.6f} → ${new_sl:.6f}")
                    else:
                        print(f"   ➡️ SL НЕ ИЗМЕНЯЕТСЯ: ${sl_current:.6f}")
                else:
                    if new_sl < sl_current:
                        print(f"   ✅ SL УЛУЧШАЕТСЯ: ${sl_current:.6f} → ${new_sl:.6f}")
                    elif new_sl > sl_current:
                        print(f"   ❌ SL УХУДШАЕТСЯ: ${sl_current:.6f} → ${new_sl:.6f}")
                    else:
                        print(f"   ➡️ SL НЕ ИЗМЕНЯЕТСЯ: ${sl_current:.6f}")
            else:
                print(f"   ⚠️ Трейлинг активен, но уровень не определен")
        else:
            print(f"   ❌ Трейлинг НЕ АКТИВЕН (PnL < {trailing_config['activate_pnl_usdt']})")
        
        print()
    
    print("🔍 ВОЗМОЖНЫЕ ПРОБЛЕМЫ:")
    print("-" * 60)
    
    print("1. НЕПРАВИЛЬНЫЙ PEAK PNL:")
    print(f"   • Текущий Peak PnL: {peak_pnl:.4f} USDT")
    print("   • Если Peak PnL не обновляется, трейлинг работает неправильно")
    print("   • Peak PnL должен сохранять максимальную прибыль")
    
    print()
    print("2. ЛОГИКА РАСЧЕТА SL:")
    print("   • SL должен рассчитываться от entry + target_profit")
    print("   • Для лонгов: new_sl = entry + (target_profit / qty)")
    print("   • SL должен только улучшаться, никогда не ухудшаться")
    
    print()
    print("3. ОБНОВЛЕНИЕ НА БИРЖЕ:")
    print("   • SL должен обновляться на Binance")
    print("   • Старые ордера должны отменяться")
    print("   • Новые ордера должны создаваться")
    
    print()
    print("🎯 ЧТО ПРОВЕРИТЬ:")
    print("-" * 60)
    
    print("1. ЛОГИ СИСТЕМЫ:")
    print("   • Найти сообщения 'SL improvement' для LTC")
    print("   • Проверить обновления Peak PnL")
    print("   • Найти ошибки трейлинга")
    
    print()
    print("2. ТЕКУЩАЯ ЦЕНА LTC:")
    print("   • Получить реальную цену с биржи")
    print("   • Рассчитать текущий PnL")
    print("   • Определить, должен ли трейлинг быть активен")
    
    print()
    print("3. СОСТОЯНИЕ НА BINANCE:")
    print("   • Проверить актуальный SL ордер")
    print("   • Сравнить с системным SL")
    print("   • Убедиться в синхронизации")

if __name__ == "__main__":
    debug_ltc_trailing()
