#!/usr/bin/env python3
"""
ТЕСТ: ТРЕЙЛИНГ НИКОГДА НЕ УХУДШАЕТСЯ
Проверяем что все исправления работают и трейлинг защищает минимум $0.03
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from signalwarden_lite.core.trailing_pnl_only import update_trailing_pnl_only, TrailingConfigPnLOnly
from signalwarden_lite.core.types import Position, Side

def test_trailing_never_worsen():
    """Тест что трейлинг никогда не ухудшается"""
    print("🧪 ТЕСТ: ТРЕЙЛИНГ НИКОГДА НЕ УХУДШАЕТСЯ")
    print("=" * 70)
    
    cfg = TrailingConfigPnLOnly()
    
    # ТЕСТ 1: Трейлинг должен защитить минимум $0.03 при любом уровне
    print("\n1️⃣ ТЕСТ: Минимальная защита $0.03")
    
    test_cases = [
        {"pnl": 0.06, "level": "L1", "keep_pct": 50, "expected_min": 0.03},
        {"pnl": 0.15, "level": "L2", "keep_pct": 60, "expected_min": 0.03},
        {"pnl": 0.25, "level": "L3", "keep_pct": 70, "expected_min": 0.03},
        {"pnl": 0.35, "level": "L4", "keep_pct": 80, "expected_min": 0.03},
    ]
    
    all_passed = True
    
    for i, case in enumerate(test_cases):
        position = Position(
            side=Side.LONG,
            entry=100.0,
            sl=95.0,  # Исходный SL
            qty=10.0,
            remaining_qty=10.0,
            r_per_unit=5.0,
            atr=2.0,
            sl_initial=95.0
        )
        position.peak_pnl_usdt = case["pnl"]
        
        # Тестируем на цене которая дает текущий PnL = 0 (упала после пика)
        current_price = position.entry  # PnL = 0
        
        updated_pos = update_trailing_pnl_only(position, current_price, current_price, 2.0, cfg)
        
        debug = updated_pos.trailing_debug
        actual_protection = (updated_pos.sl - position.entry) * position.qty
        
        print(f"   {case['level']}: Peak ${case['pnl']:.2f} → Защита ${actual_protection:.3f}")
        
        if actual_protection >= case["expected_min"]:
            print(f"   ✅ {case['level']} защищает минимум ${case['expected_min']:.2f}")
        else:
            print(f"   ❌ {case['level']} НЕ защищает минимум ${case['expected_min']:.2f}!")
            all_passed = False
    
    # ТЕСТ 2: SL никогда не ухудшается
    print("\n2️⃣ ТЕСТ: SL никогда не ухудшается")
    
    position = Position(
        side=Side.LONG,
        entry=100.0,
        sl=102.0,  # УЖЕ хороший трейлинг SL
        qty=10.0,
        remaining_qty=10.0,
        r_per_unit=5.0,
        atr=2.0,
        sl_initial=95.0
    )
    position.peak_pnl_usdt = 0.25  # L3
    
    # Цена упала - текущий PnL стал отрицательным
    current_price = 99.5  # PnL = -0.5
    
    updated_pos = update_trailing_pnl_only(position, current_price, current_price, 2.0, cfg)
    
    print(f"   Исходный SL: {position.sl:.2f}")
    print(f"   Новый SL: {updated_pos.sl:.2f}")
    print(f"   Current PnL: {(current_price - position.entry) * position.qty:.2f}")
    print(f"   Peak PnL: {position.peak_pnl_usdt:.2f}")
    
    if updated_pos.sl >= position.sl:
        print(f"   ✅ SL не ухудшился (остался {updated_pos.sl:.2f} >= {position.sl:.2f})")
    else:
        print(f"   ❌ SL УХУДШИЛСЯ! {position.sl:.2f} → {updated_pos.sl:.2f}")
        all_passed = False
    
    # ТЕСТ 3: Трейлинг работает при отрицательном текущем PnL
    print("\n3️⃣ ТЕСТ: Трейлинг при отрицательном текущем PnL")
    
    position = Position(
        side=Side.LONG,
        entry=100.0,
        sl=95.0,
        qty=10.0,
        remaining_qty=10.0,
        r_per_unit=5.0,
        atr=2.0,
        sl_initial=95.0
    )
    position.peak_pnl_usdt = 0.15  # L2 - был пик $0.15
    
    # Текущий PnL отрицательный
    current_price = 99.0  # PnL = -1.0
    
    updated_pos = update_trailing_pnl_only(position, current_price, current_price, 2.0, cfg)
    
    debug = updated_pos.trailing_debug
    protection = (updated_pos.sl - position.entry) * position.qty
    
    print(f"   Current PnL: {debug['current_pnl']:.2f} (отрицательный)")
    print(f"   Peak PnL: {updated_pos.peak_pnl_usdt:.2f}")
    print(f"   Уровень: {debug['level']}")
    print(f"   Защита: ${protection:.3f}")
    
    if debug['level'] == 'L2' and protection >= 0.03:
        print(f"   ✅ Трейлинг работает при отрицательном PnL")
    else:
        print(f"   ❌ Трейлинг НЕ работает при отрицательном PnL")
        all_passed = False
    
    # ТЕСТ 4: Критический сценарий - защита при резком падении
    print("\n4️⃣ ТЕСТ: Защита при резком падении цены")
    
    position = Position(
        side=Side.LONG,
        entry=100.0,
        sl=95.0,
        qty=10.0,
        remaining_qty=10.0,
        r_per_unit=5.0,
        atr=2.0,
        sl_initial=95.0
    )
    position.peak_pnl_usdt = 0.35  # L4 - был высокий пик
    
    # Резкое падение - цена ниже entry
    current_price = 98.0  # PnL = -2.0 (большой убыток)
    
    updated_pos = update_trailing_pnl_only(position, current_price, current_price, 2.0, cfg)
    
    debug = updated_pos.trailing_debug
    protection = (updated_pos.sl - position.entry) * position.qty
    
    print(f"   Резкое падение: ${current_price:.1f} (PnL: {debug['current_pnl']:.1f})")
    print(f"   Peak PnL: ${updated_pos.peak_pnl_usdt:.2f}")
    print(f"   Уровень: {debug['level']}")
    print(f"   Защита: ${protection:.3f}")
    
    if debug['level'] == 'L4' and protection >= 0.03:
        print(f"   ✅ Трейлинг защищает даже при резком падении")
    else:
        print(f"   ❌ Трейлинг НЕ защищает при резком падении")
        all_passed = False
    
    # ИТОГИ
    print(f"\n🎯 ИТОГИ ТЕСТИРОВАНИЯ:")
    if all_passed:
        print(f"✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ - Трейлинг работает правильно!")
        print(f"✅ Минимальная защита $0.03 гарантирована")
        print(f"✅ SL никогда не ухудшается")
        print(f"✅ Трейлинг работает при любом текущем PnL")
        return True
    else:
        print(f"❌ ЕСТЬ ПРОБЛЕМЫ - Трейлинг работает неправильно!")
        return False

if __name__ == "__main__":
    success = test_trailing_never_worsen()
    exit(0 if success else 1)
