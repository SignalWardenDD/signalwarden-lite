#!/usr/bin/env python3
"""
Тест сценария DOGE: PnL достигает $0.06, должен активироваться трейлинг
"""

import sys
import os
sys.path.append('.')

from signalwarden_lite.core.trailing_pnl_only import TrailingConfigPnLOnly, update_trailing_pnl_only
from signalwarden_lite.core.types import Position, Side

def test_doge_scenario():
    """Тест сценария DOGE с достижением $0.06"""
    print("🐕 ТЕСТ СЦЕНАРИЯ DOGE")
    print("=" * 50)
    
    trailing_cfg = TrailingConfigPnLOnly(
        level_1_pnl=0.06,   # Порог активации $0.06
        level_1_keep_pct=0.50,
        level_2_pnl=0.15,
        level_2_keep_pct=0.60,
        level_3_pnl=0.25,
        level_3_keep_pct=0.70,
        level_4_pnl=0.35,
        level_4_keep_pct=0.80
    )
    
    # Параметры DOGE из логов
    entry = 0.300557
    qty = 69.8703
    atr = 0.005189
    
    print(f"📊 DOGE_USDT:")
    print(f"   Entry: ${entry:.6f}")
    print(f"   Qty: {qty:.4f}")
    print(f"   ATR: {atr:.6f}")
    print()
    
    # Создаем начальную позицию
    position = Position(
        side=Side.LONG,
        entry=entry,
        qty=qty,
        remaining_qty=qty,
        r_per_unit=0.05,
        sl=entry - (2.5 * atr),  # Начальный SL
        peak_pnl_usdt=0.0
    )
    
    print(f"   Начальный SL: ${position.sl:.6f}")
    print()
    
    # Тестируем сценарии роста цены
    scenarios = [
        {'price': 0.301, 'desc': 'Небольшой рост'},
        {'price': 0.302, 'desc': 'Рост продолжается'},
        {'price': 0.3014, 'desc': 'Приближаемся к $0.06 PnL'},
        {'price': 0.3015, 'desc': 'ДОСТИГАЕМ $0.06 PnL'},
        {'price': 0.3020, 'desc': 'Превышаем $0.06 PnL'},
    ]
    
    current_pos = position
    
    for i, scenario in enumerate(scenarios, 1):
        price = scenario['price']
        desc = scenario['desc']
        
        # Применяем трейлинг
        updated_pos = update_trailing_pnl_only(current_pos, price, 0, atr, trailing_cfg)
        current_pnl = (price - entry) * qty
        
        print(f"{i}. {desc}: ${price:.6f}")
        print(f"   PnL: ${current_pnl:.4f}")
        print(f"   Peak PnL: ${updated_pos.peak_pnl_usdt:.4f}")
        
        if hasattr(updated_pos, 'trailing_debug'):
            debug = updated_pos.trailing_debug
            level = debug.get('level', 'INACTIVE')
            keep_pct = debug.get('keep_pct', 0)
            
            print(f"   Уровень: {level}")
            print(f"   Keep %: {keep_pct * 100:.0f}%")
            
            # Проверяем активацию трейлинга
            if current_pnl >= 0.06 and level != 'INACTIVE':
                print(f"   ✅ ТРЕЙЛИНГ АКТИВИРОВАН при PnL >= $0.06!")
                protected_profit = (updated_pos.sl - entry) * qty
                print(f"   🛡️ Защищенная прибыль: ${protected_profit:.4f}")
            elif current_pnl < 0.06 and level == 'INACTIVE':
                print(f"   ✅ Трейлинг неактивен (PnL < $0.06)")
            else:
                print(f"   ❌ ПРОБЛЕМА С АКТИВАЦИЕЙ ТРЕЙЛИНГА!")
        
        print(f"   SL: ${updated_pos.sl:.6f}")
        print()
        
        current_pos = updated_pos
    
    # Тест падения цены после активации
    print("📉 ТЕСТ ПАДЕНИЯ ЦЕНЫ ПОСЛЕ АКТИВАЦИИ:")
    print("-" * 40)
    
    # Сохраняем состояние после активации
    activated_pos = current_pos
    
    falling_scenarios = [
        {'price': 0.3010, 'desc': 'Небольшое падение'},
        {'price': 0.3005, 'desc': 'Падение продолжается'},
        {'price': 0.3000, 'desc': 'Возврат к entry'},
    ]
    
    for i, scenario in enumerate(falling_scenarios, 1):
        price = scenario['price']
        desc = scenario['desc']
        
        # Применяем трейлинг с сохраненным Peak PnL
        test_pos = Position(
            side=Side.LONG,
            entry=entry,
            qty=qty,
            remaining_qty=qty,
            r_per_unit=0.05,
            sl=activated_pos.sl,
            peak_pnl_usdt=activated_pos.peak_pnl_usdt
        )
        
        updated_pos = update_trailing_pnl_only(test_pos, price, 0, atr, trailing_cfg)
        current_pnl = (price - entry) * qty
        protected_profit = (updated_pos.sl - entry) * qty
        
        print(f"{i}. {desc}: ${price:.6f}")
        print(f"   Текущий PnL: ${current_pnl:.4f}")
        print(f"   Peak PnL: ${updated_pos.peak_pnl_usdt:.4f} (сохраняется)")
        print(f"   SL: ${updated_pos.sl:.6f}")
        print(f"   Защищенная прибыль: ${protected_profit:.4f}")
        
        if protected_profit >= 0.029:  # ~$0.03
            print(f"   ✅ Минимальная защита $0.03 СОХРАНЕНА!")
        else:
            print(f"   ❌ Минимальная защита потеряна!")
        
        print()

if __name__ == "__main__":
    test_doge_scenario()
