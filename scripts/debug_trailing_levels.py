#!/usr/bin/env python3
"""
ОТЛАДКА УРОВНЕЙ ТРЕЙЛИНГА
Проверяем правильность определения уровней
"""

import sys
import os
sys.path.append('.')

from signalwarden_lite.core.trailing_pnl_only import TrailingConfigPnLOnly, update_trailing_pnl_only
from signalwarden_lite.core.types import Position, Side

def debug_trailing_levels():
    """Отладка уровней трейлинга"""
    print("🔍 ОТЛАДКА УРОВНЕЙ ТРЕЙЛИНГА")
    print("=" * 60)
    
    trailing_cfg = TrailingConfigPnLOnly(
        level_1_pnl=0.06,
        level_1_keep_pct=0.50,
        level_2_pnl=0.15,
        level_2_keep_pct=0.60,
        level_3_pnl=0.25,
        level_3_keep_pct=0.70,
        level_4_pnl=0.35,
        level_4_keep_pct=0.80
    )
    
    print(f"📊 КОНФИГУРАЦИЯ ТРЕЙЛИНГА:")
    print(f"   L1: ${trailing_cfg.level_1_pnl:.2f} → {trailing_cfg.level_1_keep_pct*100:.0f}%")
    print(f"   L2: ${trailing_cfg.level_2_pnl:.2f} → {trailing_cfg.level_2_keep_pct*100:.0f}%")
    print(f"   L3: ${trailing_cfg.level_3_pnl:.2f} → {trailing_cfg.level_3_keep_pct*100:.0f}%")
    print(f"   L4: ${trailing_cfg.level_4_pnl:.2f} → {trailing_cfg.level_4_keep_pct*100:.0f}%")
    print()
    
    # Тестовые сценарии из логов
    test_cases = [
        {'symbol': 'LTC_USDT', 'entry': 120.222857, 'qty': 0.1747, 'peak_pnl': 0.0833, 'current_price': 120.70},
        {'symbol': 'DOGE_USDT', 'entry': 0.300204, 'qty': 69.95, 'peak_pnl': 0.27, 'current_price': 0.304},
        {'symbol': 'PNUT_USDT', 'entry': 0.2736, 'qty': 76.0, 'peak_pnl': 0.11, 'current_price': 0.275},
    ]
    
    for i, case in enumerate(test_cases, 1):
        print(f"{i}️⃣ ТЕСТ: {case['symbol']}")
        print(f"   Entry: ${case['entry']:.6f}")
        print(f"   Qty: {case['qty']:.2f}")
        print(f"   Peak PnL: ${case['peak_pnl']:.4f}")
        print(f"   Current Price: ${case['current_price']:.6f}")
        
        # Создаем позицию
        position = Position(
            side=Side.LONG,
            entry=case['entry'],
            qty=case['qty'],
            remaining_qty=case['qty'],
            r_per_unit=0.05,
            sl=case['entry'] - 0.01,  # Dummy SL
            peak_pnl_usdt=case['peak_pnl']
        )
        
        # Применяем трейлинг
        updated_pos = update_trailing_pnl_only(
            position, 
            case['current_price'], 
            case['current_price'], 
            0.01,  # Dummy ATR
            trailing_cfg
        )
        
        # Анализируем результат
        debug = getattr(updated_pos, 'trailing_debug', {})
        level = debug.get('level', 'NONE')
        keep_pct = debug.get('keep_pct', 0)
        target_profit = debug.get('target_profit', 0)
        
        current_pnl = (case['current_price'] - case['entry']) * case['qty']
        
        print(f"   Current PnL: ${current_pnl:.4f}")
        print(f"   Peak PnL (updated): ${updated_pos.peak_pnl_usdt:.4f}")
        print(f"   Уровень: {level}")
        print(f"   Keep %: {keep_pct*100:.0f}%")
        print(f"   Target Profit: ${target_profit:.4f}")
        print(f"   SL: ${updated_pos.sl:.6f}")
        
        # Проверяем логику
        expected_level = "INACTIVE"
        if updated_pos.peak_pnl_usdt >= trailing_cfg.level_4_pnl:
            expected_level = "L4"
        elif updated_pos.peak_pnl_usdt >= trailing_cfg.level_3_pnl:
            expected_level = "L3"
        elif updated_pos.peak_pnl_usdt >= trailing_cfg.level_2_pnl:
            expected_level = "L2"
        elif updated_pos.peak_pnl_usdt >= trailing_cfg.level_1_pnl:
            expected_level = "L1"
        
        if level == expected_level:
            print(f"   ✅ Уровень правильный: {level}")
        else:
            print(f"   ❌ Уровень неправильный! Ожидали: {expected_level}, получили: {level}")
        
        # Проверяем минимальную защиту
        if level != "INACTIVE":
            protected_profit = (updated_pos.sl - case['entry']) * case['qty']
            if protected_profit >= 0.03:
                print(f"   ✅ Минимальная защита $0.03: ${protected_profit:.4f}")
            else:
                print(f"   ⚠️ Минимальная защита НЕ обеспечена: ${protected_profit:.4f}")
        
        print()
    
    # СПЕЦИАЛЬНЫЙ ТЕСТ: Проверяем граничные случаи
    print("🎯 ГРАНИЧНЫЕ СЛУЧАИ:")
    print("-" * 40)
    
    boundary_tests = [
        {'pnl': 0.059, 'expected': 'INACTIVE'},
        {'pnl': 0.060, 'expected': 'L1'},
        {'pnl': 0.149, 'expected': 'L1'},
        {'pnl': 0.150, 'expected': 'L2'},
        {'pnl': 0.249, 'expected': 'L2'},
        {'pnl': 0.250, 'expected': 'L3'},
        {'pnl': 0.349, 'expected': 'L3'},
        {'pnl': 0.350, 'expected': 'L4'},
    ]
    
    for test in boundary_tests:
        position = Position(
            side=Side.LONG,
            entry=1.0,
            qty=1.0,
            remaining_qty=1.0,
            r_per_unit=0.05,
            sl=0.95,
            peak_pnl_usdt=test['pnl']
        )
        
        updated_pos = update_trailing_pnl_only(position, 1.0 + test['pnl'], 1.0 + test['pnl'], 0.01, trailing_cfg)
        debug = getattr(updated_pos, 'trailing_debug', {})
        level = debug.get('level', 'NONE')
        
        if level == test['expected']:
            print(f"   PnL ${test['pnl']:.3f} → {level} ✅")
        else:
            print(f"   PnL ${test['pnl']:.3f} → {level} ❌ (ожидали {test['expected']})")

if __name__ == "__main__":
    debug_trailing_levels()
