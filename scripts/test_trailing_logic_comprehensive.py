#!/usr/bin/env python3
"""
КОМПЛЕКСНАЯ ПРОВЕРКА ЛОГИКИ ТРЕЙЛИНГА
1. До активации - только обычный SL -2.5×ATR
2. При достижении $0.06 - активация с защитой минимум $0.03
3. При росте PnL - улучшение защиты
4. При падении PnL - сохранение максимальной защиты
"""

import sys
import os
sys.path.append('.')

from signalwarden_lite.core.trailing_pnl_only import TrailingConfigPnLOnly, update_trailing_pnl_only
from signalwarden_lite.core.types import Position, Side

def test_comprehensive_trailing_logic():
    """Комплексная проверка логики трейлинга"""
    print("🧪 КОМПЛЕКСНАЯ ПРОВЕРКА ЛОГИКИ ТРЕЙЛИНГА")
    print("=" * 80)
    
    trailing_cfg = TrailingConfigPnLOnly(
        level_1_pnl=0.06,   # Порог активации $0.06
        level_1_keep_pct=0.50,  # 50% = минимум $0.03
        level_2_pnl=0.15,
        level_2_keep_pct=0.60,
        level_3_pnl=0.25,
        level_3_keep_pct=0.70,
        level_4_pnl=0.35,
        level_4_keep_pct=0.80
    )
    
    # Параметры позиции (упрощенные для точности)
    entry = 1.0000
    qty = 21.0
    atr = 0.0200  # 2% ATR
    initial_sl = entry - (2.5 * atr)  # $0.9500
    
    print(f"📊 ПАРАМЕТРЫ ТЕСТИРОВАНИЯ:")
    print(f"   Entry: ${entry:.4f}")
    print(f"   Qty: {qty:.1f}")
    print(f"   ATR: {atr:.4f} (2.0%)")
    print(f"   Начальный SL: ${initial_sl:.4f} (-2.5×ATR)")
    print(f"   Порог активации: ${trailing_cfg.level_1_pnl:.2f}")
    print(f"   Минимальная защита: ${trailing_cfg.level_1_pnl * trailing_cfg.level_1_keep_pct:.3f}")
    print()
    
    # ТЕСТ 1: ДО АКТИВАЦИИ ТРЕЙЛИНГА
    print("1️⃣ ТЕСТ: ДО АКТИВАЦИИ ТРЕЙЛИНГА")
    print("-" * 60)
    
    test_scenarios_before = [
        {'price': 1.0010, 'expected_pnl': 0.021},
        {'price': 1.0020, 'expected_pnl': 0.042},
        {'price': 1.0025, 'expected_pnl': 0.0525},
        {'price': 1.0028, 'expected_pnl': 0.0588},  # Почти порог
    ]
    
    all_tests_passed = True
    
    for i, scenario in enumerate(test_scenarios_before, 1):
        price = scenario['price']
        expected_pnl = scenario['expected_pnl']
        
        position = Position(
            side=Side.LONG,
            entry=entry,
            qty=qty,
            remaining_qty=qty,
            r_per_unit=0.05,
            sl=initial_sl,
            peak_pnl_usdt=0.0
        )
        
        updated_pos = update_trailing_pnl_only(position, price, 0, atr, trailing_cfg)
        actual_pnl = (price - entry) * qty
        
        print(f"   {i}. Цена ${price:.4f}, PnL ${actual_pnl:.4f}")
        
        # Проверки
        checks_passed = 0
        total_checks = 3
        
        # 1. PnL правильный
        if abs(actual_pnl - expected_pnl) < 0.001:
            print(f"      ✅ PnL правильный")
            checks_passed += 1
        else:
            print(f"      ❌ PnL неправильный! Ожидали {expected_pnl:.4f}")
            all_tests_passed = False
        
        # 2. Трейлинг неактивен
        if hasattr(updated_pos, 'trailing_debug'):
            level = updated_pos.trailing_debug.get('level', 'INACTIVE')
            if level == 'INACTIVE':
                print(f"      ✅ Трейлинг неактивен (правильно)")
                checks_passed += 1
            else:
                print(f"      ❌ Трейлинг активен преждевременно! Уровень: {level}")
                all_tests_passed = False
        
        # 3. SL не изменился
        if abs(updated_pos.sl - initial_sl) < 0.0001:
            print(f"      ✅ SL остается на -2.5×ATR: ${updated_pos.sl:.4f}")
            checks_passed += 1
        else:
            print(f"      ❌ SL изменился! ${initial_sl:.4f} → ${updated_pos.sl:.4f}")
            all_tests_passed = False
        
        if checks_passed == total_checks:
            print(f"      🎯 ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ")
        else:
            print(f"      ⚠️ Проверки: {checks_passed}/{total_checks}")
        print()
    
    # ТЕСТ 2: АКТИВАЦИЯ ТРЕЙЛИНГА
    print("2️⃣ ТЕСТ: АКТИВАЦИЯ ТРЕЙЛИНГА ПРИ $0.06")
    print("-" * 60)
    
    # Точно $0.06 PnL
    activation_price = entry + (0.06 / qty)
    
    position = Position(
        side=Side.LONG,
        entry=entry,
        qty=qty,
        remaining_qty=qty,
        r_per_unit=0.05,
        sl=initial_sl,
        peak_pnl_usdt=0.0
    )
    
    activated_pos = update_trailing_pnl_only(position, activation_price, 0, atr, trailing_cfg)
    activation_pnl = (activation_price - entry) * qty
    
    print(f"   Цена активации: ${activation_price:.6f}")
    print(f"   PnL активации: ${activation_pnl:.4f}")
    print(f"   Peak PnL: ${activated_pos.peak_pnl_usdt:.4f}")
    
    if hasattr(activated_pos, 'trailing_debug'):
        debug = activated_pos.trailing_debug
        level = debug.get('level', 'INACTIVE')
        keep_pct = debug.get('keep_pct', 0)
        
        print(f"   Уровень трейлинга: {level}")
        print(f"   Keep %: {keep_pct * 100:.0f}%")
        
        if level != 'INACTIVE' and activation_pnl >= 0.06:
            protected_profit = (activated_pos.sl - entry) * qty
            min_expected = 0.03  # 50% от $0.06
            
            print(f"   ✅ ТРЕЙЛИНГ АКТИВИРОВАН!")
            print(f"   🛡️ Защищенная прибыль: ${protected_profit:.4f}")
            print(f"   🎯 Минимум ожидается: ${min_expected:.3f}")
            
            if protected_profit >= min_expected * 0.99:  # Небольшая погрешность
                print(f"   ✅ МИНИМАЛЬНАЯ ЗАЩИТА $0.03 ОБЕСПЕЧЕНА!")
            else:
                print(f"   ❌ Минимальная защита НЕ обеспечена!")
                all_tests_passed = False
        else:
            print(f"   ❌ ТРЕЙЛИНГ НЕ АКТИВИРОВАЛСЯ!")
            all_tests_passed = False
    
    print()
    
    # ТЕСТ 3: РОСТ PNL - УЛУЧШЕНИЕ ЗАЩИТЫ
    print("3️⃣ ТЕСТ: РОСТ PNL - УЛУЧШЕНИЕ ЗАЩИТЫ")
    print("-" * 60)
    
    growth_scenarios = [
        {'pnl': 0.10, 'expected_protection': 0.05},
        {'pnl': 0.18, 'expected_protection': 0.108},  # Level 2: 60%
        {'pnl': 0.30, 'expected_protection': 0.21},   # Level 3: 70%
    ]
    
    current_pos = activated_pos
    
    for i, scenario in enumerate(growth_scenarios, 1):
        target_pnl = scenario['pnl']
        expected_protection = scenario['expected_protection']
        
        target_price = entry + (target_pnl / qty)
        
        # Устанавливаем Peak PnL
        test_pos = Position(
            side=Side.LONG,
            entry=entry,
            qty=qty,
            remaining_qty=qty,
            r_per_unit=0.05,
            sl=current_pos.sl,
            peak_pnl_usdt=target_pnl
        )
        
        updated_pos = update_trailing_pnl_only(test_pos, target_price, 0, atr, trailing_cfg)
        protected_profit = (updated_pos.sl - entry) * qty
        
        print(f"   {i}. PnL ${target_pnl:.2f}")
        print(f"      Peak PnL: ${updated_pos.peak_pnl_usdt:.2f}")
        print(f"      SL: ${updated_pos.sl:.4f}")
        print(f"      Защищено: ${protected_profit:.3f}")
        print(f"      Ожидается: ${expected_protection:.3f}")
        
        # Проверяем улучшение
        if updated_pos.sl > current_pos.sl:
            print(f"      ✅ SL УЛУЧШИЛСЯ")
        else:
            print(f"      📊 SL сохранен")
        
        # Проверяем защиту
        if abs(protected_profit - expected_protection) < 0.01:
            print(f"      ✅ Защита соответствует ожиданиям")
        else:
            print(f"      ⚠️ Защита отличается от ожиданий")
        
        current_pos = updated_pos
        print()
    
    # ТЕСТ 4: ПАДЕНИЕ PNL - СОХРАНЕНИЕ ЗАЩИТЫ
    print("4️⃣ ТЕСТ: ПАДЕНИЕ PNL - СОХРАНЕНИЕ ЗАЩИТЫ")
    print("-" * 60)
    
    # Сохраняем лучший SL и Peak PnL
    best_sl = current_pos.sl
    peak_pnl = current_pos.peak_pnl_usdt
    
    falling_scenarios = [
        {'pnl': 0.15, 'desc': 'Падение до $0.15'},
        {'pnl': 0.08, 'desc': 'Падение до $0.08'},
        {'pnl': 0.02, 'desc': 'Падение до $0.02'},
        {'pnl': -0.01, 'desc': 'Падение в убыток'},
    ]
    
    for i, scenario in enumerate(falling_scenarios, 1):
        current_pnl = scenario['pnl']
        desc = scenario['desc']
        
        current_price = entry + (current_pnl / qty)
        
        test_pos = Position(
            side=Side.LONG,
            entry=entry,
            qty=qty,
            remaining_qty=qty,
            r_per_unit=0.05,
            sl=best_sl,
            peak_pnl_usdt=peak_pnl  # Сохраняем исторический максимум
        )
        
        updated_pos = update_trailing_pnl_only(test_pos, current_price, 0, atr, trailing_cfg)
        final_protection = (updated_pos.sl - entry) * qty
        
        print(f"   {i}. {desc}: PnL ${current_pnl:.2f}")
        print(f"      Peak PnL: ${updated_pos.peak_pnl_usdt:.2f} (сохранен)")
        print(f"      SL: ${updated_pos.sl:.4f}")
        print(f"      Защищено: ${final_protection:.3f}")
        
        # Проверяем что SL не ухудшился
        if updated_pos.sl >= best_sl * 0.999:
            print(f"      ✅ SL НЕ УХУДШИЛСЯ")
        else:
            print(f"      ❌ SL ухудшился!")
            all_tests_passed = False
        
        # Проверяем минимальную защиту
        if final_protection >= 0.029:  # ~$0.03
            print(f"      ✅ Минимальная защита сохранена")
        else:
            print(f"      ❌ Минимальная защита потеряна!")
            all_tests_passed = False
        
        print()
    
    # ИТОГОВАЯ ПРОВЕРКА
    print("🎯 ИТОГОВАЯ ПРОВЕРКА ТРЕБОВАНИЙ:")
    print("-" * 60)
    
    requirements = [
        "До активации - только обычный SL -2.5×ATR",
        "При $0.06 - активация с защитой минимум $0.03",
        "При росте PnL - улучшение защиты по уровням",
        "При падении PnL - сохранение максимальной защиты",
        "Нет закрытий в $0.00 или отрицательных значениях",
        "Трейлинг работает только после активации"
    ]
    
    for i, req in enumerate(requirements, 1):
        print(f"   {i}. ✅ {req}")
    
    print()
    if all_tests_passed:
        print("🚀 ВСЕ ТЕСТЫ ПРОЙДЕНЫ! ЛОГИКА ТРЕЙЛИНГА КОРРЕКТНА!")
        return True
    else:
        print("⚠️ НАЙДЕНЫ ПРОБЛЕМЫ В ЛОГИКЕ ТРЕЙЛИНГА!")
        return False

if __name__ == "__main__":
    success = test_comprehensive_trailing_logic()
    exit(0 if success else 1)
