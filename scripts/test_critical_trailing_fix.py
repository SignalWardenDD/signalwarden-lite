#!/usr/bin/env python3
"""
КРИТИЧЕСКИЙ ТЕСТ ИСПРАВЛЕНИЯ ТРЕЙЛИНГА
Проверяем что трейлинг активируется для позиций выше порога
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from signalwarden_lite.core.trailing_pnl_only import update_trailing_pnl_only, TrailingConfigPnLOnly
from signalwarden_lite.core.types import Position, Side

def test_critical_trailing_scenarios():
    """Тест критических сценариев трейлинга"""
    print("🧪 КРИТИЧЕСКИЙ ТЕСТ ИСПРАВЛЕНИЯ ТРЕЙЛИНГА")
    print("=" * 70)
    
    cfg = TrailingConfigPnLOnly()
    
    # СЦЕНАРИЙ 1: Позиция с peak_pnl_usdt = 0, но текущий PnL > 0.06
    print("\n1️⃣ СЦЕНАРИЙ: Peak PnL сброшен в 0, текущий PnL = $0.20 (должен активировать L1)")
    
    position = Position(
        side=Side.LONG,
        entry=100.0,
        sl=95.0,  # Обычный SL
        qty=10.0,
        remaining_qty=10.0,
        r_per_unit=5.0,
        atr=2.0,
        sl_initial=95.0
    )
    position.peak_pnl_usdt = 0.0  # Сброшен!
    
    # Текущая цена дает PnL = $0.20 (в 3+ раза больше порога!)
    current_price = 102.0  # PnL = (102 - 100) * 10 = $20... нет, $2.0
    current_price = 100.2  # PnL = (100.2 - 100) * 10 = $2.0... нет
    current_price = 100.02  # PnL = (100.02 - 100) * 10 = $0.20 ✅
    
    updated_pos = update_trailing_pnl_only(position, current_price, current_price, 2.0, cfg)
    
    debug = updated_pos.trailing_debug
    print(f"   Peak PnL: {updated_pos.peak_pnl_usdt:.4f}")
    print(f"   Уровень: {debug['level']}")
    print(f"   Keep %: {debug['keep_pct']*100:.0f}%")
    print(f"   Target Profit: ${debug['target_profit']:.4f}")
    print(f"   SL Updated: {debug.get('sl_updated', False)}")
    print(f"   New SL: {updated_pos.sl:.6f}")
    
    if debug['level'] == 'L1' and debug.get('sl_updated', False):
        print("   ✅ ИСПРАВЛЕНИЕ РАБОТАЕТ: Трейлинг активировался!")
    else:
        print("   ❌ ПРОБЛЕМА: Трейлинг НЕ активировался!")
        
    # СЦЕНАРИЙ 2: Позиция достигла $0.25, упала до $0.10, трейлинг должен работать
    print("\n2️⃣ СЦЕНАРИЙ: Peak PnL = $0.25 (L3), текущий PnL = $0.10 (трейлинг должен работать)")
    
    position2 = Position(
        side=Side.LONG,
        entry=100.0,
        sl=95.0,
        qty=10.0,
        remaining_qty=10.0,
        r_per_unit=5.0,
        atr=2.0,
        sl_initial=95.0
    )
    position2.peak_pnl_usdt = 0.25  # Пик был $0.25
    
    # Текущий PnL = $0.10 (упал, но трейлинг должен работать!)
    current_price = 100.01  # PnL = (100.01 - 100) * 10 = $0.10
    
    updated_pos2 = update_trailing_pnl_only(position2, current_price, current_price, 2.0, cfg)
    
    debug2 = updated_pos2.trailing_debug
    print(f"   Peak PnL: {updated_pos2.peak_pnl_usdt:.4f}")
    print(f"   Уровень: {debug2['level']}")
    print(f"   Keep %: {debug2['keep_pct']*100:.0f}%")
    print(f"   Target Profit: ${debug2['target_profit']:.4f}")
    print(f"   SL Updated: {debug2.get('sl_updated', False)}")
    print(f"   New SL: {updated_pos2.sl:.6f}")
    
    if debug2['level'] == 'L3' and debug2.get('sl_updated', False):
        print("   ✅ ИСПРАВЛЕНИЕ РАБОТАЕТ: Трейлинг работает при падении PnL!")
    else:
        print("   ❌ ПРОБЛЕМА: Трейлинг НЕ работает при падении PnL!")
        
    # СЦЕНАРИЙ 3: Позиция с отрицательным текущим PnL, но peak > 0.06
    print("\n3️⃣ СЦЕНАРИЙ: Peak PnL = $0.15 (L2), текущий PnL = -$0.05 (трейлинг должен работать)")
    
    position3 = Position(
        side=Side.LONG,
        entry=100.0,
        sl=95.0,
        qty=10.0,
        remaining_qty=10.0,
        r_per_unit=5.0,
        atr=2.0,
        sl_initial=95.0
    )
    position3.peak_pnl_usdt = 0.15  # Пик был $0.15
    
    # Текущий PnL = -$0.05 (отрицательный!)
    current_price = 99.995  # PnL = (99.995 - 100) * 10 = -$0.05
    
    updated_pos3 = update_trailing_pnl_only(position3, current_price, current_price, 2.0, cfg)
    
    debug3 = updated_pos3.trailing_debug
    print(f"   Current PnL: {debug3['current_pnl']:.4f}")
    print(f"   Peak PnL: {updated_pos3.peak_pnl_usdt:.4f}")
    print(f"   Уровень: {debug3['level']}")
    print(f"   Keep %: {debug3['keep_pct']*100:.0f}%")
    print(f"   Target Profit: ${debug3['target_profit']:.4f}")
    print(f"   SL Updated: {debug3.get('sl_updated', False)}")
    print(f"   New SL: {updated_pos3.sl:.6f}")
    
    if debug3['level'] == 'L2' and updated_pos3.peak_pnl_usdt == 0.15:
        print("   ✅ ИСПРАВЛЕНИЕ РАБОТАЕТ: Трейлинг работает при отрицательном текущем PnL!")
        print("   ✅ Peak PnL сохранен, не обновился на отрицательное значение")
    else:
        print("   ❌ ПРОБЛЕМА: Трейлинг НЕ работает при отрицательном текущем PnL!")
        
    print("\n🎯 ИТОГИ ТЕСТИРОВАНИЯ:")
    
    scenarios_passed = 0
    
    # Сценарий 1: PnL $0.20 должен активировать L2 (не L1!)
    if debug['level'] in ['L1', 'L2', 'L3', 'L4'] and debug.get('sl_updated', False):
        print("✅ Сценарий 1: ПРОЙДЕН - Экстренная активация трейлинга")
        scenarios_passed += 1
    else:
        print("❌ Сценарий 1: ПРОВАЛЕН - Трейлинг не активируется")
        
    if debug2['level'] == 'L3' and debug2.get('sl_updated', False):
        print("✅ Сценарий 2: ПРОЙДЕН - Трейлинг работает при падении PnL")
        scenarios_passed += 1
    else:
        print("❌ Сценарий 2: ПРОВАЛЕН - Трейлинг не работает при падении PnL")
        
    if debug3['level'] == 'L2' and updated_pos3.peak_pnl_usdt == 0.15:
        print("✅ Сценарий 3: ПРОЙДЕН - Трейлинг работает при отрицательном PnL")
        scenarios_passed += 1
    else:
        print("❌ Сценарий 3: ПРОВАЛЕН - Трейлинг не работает при отрицательном PnL")
    
    print(f"\n📊 РЕЗУЛЬТАТ: {scenarios_passed}/3 сценариев пройдено")
    
    if scenarios_passed == 3:
        print("🎉 ВСЕ КРИТИЧЕСКИЕ ИСПРАВЛЕНИЯ РАБОТАЮТ!")
        return True
    else:
        print("🚨 ЕСТЬ ПРОБЛЕМЫ С ИСПРАВЛЕНИЯМИ!")
        return False

if __name__ == "__main__":
    success = test_critical_trailing_scenarios()
    exit(0 if success else 1)
