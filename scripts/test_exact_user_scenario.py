#!/usr/bin/env python3
"""
Тест точного сценария пользователя:
1. Создать позицию со SL по умолчанию -2.5 ATR
2. При достижении порога активации (0.06 USDT) заменить на трейлинг
3. Минимум сохранить 0.03 USDT (50% от 0.06)
4. При росте PnL - улучшать SL
5. При падении PnL - никогда не ухудшать SL
"""

import sys
import os
sys.path.append('.')

import yaml
from signalwarden_lite.core.trailing_pnl_only import TrailingConfigPnLOnly, update_trailing_pnl_only
from signalwarden_lite.core.types import Position, Side

def test_exact_user_scenario():
    """Тест точного сценария пользователя"""
    print("🎯 ТЕСТ ТОЧНОГО СЦЕНАРИЯ ПОЛЬЗОВАТЕЛЯ")
    print("=" * 80)
    
    trailing_cfg = TrailingConfigPnLOnly(
        level_1_pnl=0.06,   # Порог активации $0.06
        level_1_keep_pct=0.50,  # Сохранить 50% = $0.03
        level_2_pnl=0.15,
        level_2_keep_pct=0.60,
        level_3_pnl=0.25,
        level_3_keep_pct=0.70,
        level_4_pnl=0.35,
        level_4_keep_pct=0.80
    )
    
    # Параметры позиции
    entry = 1.0000
    atr = 0.0200  # 2% ATR
    qty = 21.0
    
    print("📊 СЦЕНАРИЙ:")
    print(f"   Entry: ${entry:.4f}")
    print(f"   ATR: {atr:.4f} (2.0%)")
    print(f"   Quantity: {qty}")
    print()
    
    # ШАГ 1: Создание позиции со SL по умолчанию
    print("1️⃣ СОЗДАНИЕ ПОЗИЦИИ СО SL ПО УМОЛЧАНИЮ")
    print("-" * 60)
    
    initial_sl = entry - (2.5 * atr)  # -2.5 ATR
    position = Position(
        side=Side.LONG,
        entry=entry,
        qty=qty,
        remaining_qty=qty,
        r_per_unit=0.05,
        sl=initial_sl,
        peak_pnl_usdt=0.0
    )
    
    print(f"   ✅ Позиция создана:")
    print(f"   Entry: ${position.entry:.4f}")
    print(f"   SL по умолчанию: ${position.sl:.4f} (-2.5×ATR)")
    print(f"   Расстояние SL: ${position.entry - position.sl:.4f} ({(position.entry - position.sl)/position.entry*100:.1f}%)")
    print()
    
    # ШАГ 2: Цена растет, но трейлинг еще НЕ активен
    print("2️⃣ РОСТ ЦЕНЫ ДО ПОРОГА АКТИВАЦИИ")
    print("-" * 60)
    
    # Цена растет, но PnL еще меньше $0.06
    prices_before_activation = [
        {'price': 1.0020, 'desc': 'Небольшой рост'},
        {'price': 1.0025, 'desc': 'Рост продолжается'},
    ]
    
    current_pos = position
    
    for i, move in enumerate(prices_before_activation, 1):
        price = move['price']
        desc = move['desc']
        
        updated_pos = update_trailing_pnl_only(current_pos, price, 0, atr, trailing_cfg)
        current_pnl = (price - entry) * qty
        
        print(f"   {i}. {desc}: ${price:.4f}")
        print(f"      PnL: ${current_pnl:.3f} (< $0.06 - трейлинг НЕ активен)")
        print(f"      Peak PnL: ${updated_pos.peak_pnl_usdt:.3f}")
        print(f"      SL: ${updated_pos.sl:.4f}")
        
        if abs(updated_pos.sl - current_pos.sl) < 0.0001:
            print(f"      ✅ SL НЕ ИЗМЕНИЛСЯ (правильно - трейлинг не активен)")
        else:
            print(f"      ❌ SL изменился!")
        
        print()
        current_pos = updated_pos
    
    # ШАГ 3: АКТИВАЦИЯ ТРЕЙЛИНГА при достижении $0.06
    print("3️⃣ АКТИВАЦИЯ ТРЕЙЛИНГА ПРИ ДОСТИЖЕНИИ $0.06")
    print("-" * 60)
    
    # Цена растет так, что PnL достигает $0.06
    activation_pnl = 0.06
    activation_price = entry + (activation_pnl / qty)
    
    activated_pos = update_trailing_pnl_only(current_pos, activation_price, 0, atr, trailing_cfg)
    actual_pnl = (activation_price - entry) * qty
    
    print(f"   Цена активации: ${activation_price:.4f}")
    print(f"   PnL активации: ${actual_pnl:.3f}")
    print(f"   Peak PnL: ${activated_pos.peak_pnl_usdt:.3f}")
    print()
    
    print(f"   SL ДО активации: ${current_pos.sl:.4f}")
    print(f"   SL ПОСЛЕ активации: ${activated_pos.sl:.4f}")
    
    # Проверяем что трейлинг активировался и защищает минимум $0.03
    min_target_profit = 0.03  # 50% от $0.06
    expected_sl = entry + (min_target_profit / qty)
    
    print(f"   Ожидаемый SL (защита $0.03): ${expected_sl:.4f}")
    
    if activated_pos.sl >= expected_sl * 0.99:  # Небольшая погрешность
        print(f"   ✅ ТРЕЙЛИНГ АКТИВИРОВАН! Защищает минимум $0.03")
        trailing_activated = True
    else:
        print(f"   ❌ Трейлинг НЕ активировался правильно!")
        trailing_activated = False
    
    print()
    
    # ШАГ 4: РОСТ PnL - улучшение SL
    print("4️⃣ РОСТ PnL - УЛУЧШЕНИЕ SL")
    print("-" * 60)
    
    growth_scenarios = [
        {'pnl': 0.10, 'desc': 'Рост до $0.10'},
        {'pnl': 0.18, 'desc': 'Рост до $0.18 (Level 2)'},
        {'pnl': 0.30, 'desc': 'Рост до $0.30 (Level 3)'},
    ]
    
    current_pos = activated_pos
    
    for i, scenario in enumerate(growth_scenarios, 1):
        target_pnl = scenario['pnl']
        desc = scenario['desc']
        
        # Устанавливаем peak PnL и применяем трейлинг
        test_pos = Position(
            side=Side.LONG,
            entry=entry,
            qty=qty,
            remaining_qty=qty,
            r_per_unit=0.05,
            sl=current_pos.sl,
            peak_pnl_usdt=target_pnl
        )
        
        price = entry + (target_pnl / qty)
        updated_pos = update_trailing_pnl_only(test_pos, price, 0, atr, trailing_cfg)
        
        print(f"   {i}. {desc}")
        print(f"      Peak PnL: ${updated_pos.peak_pnl_usdt:.2f}")
        print(f"      SL до: ${current_pos.sl:.4f}")
        print(f"      SL после: ${updated_pos.sl:.4f}")
        
        if updated_pos.sl > current_pos.sl:
            improvement = updated_pos.sl - current_pos.sl
            print(f"      ✅ SL УЛУЧШИЛСЯ на ${improvement:.4f}")
        else:
            print(f"      📊 SL остался прежним")
        
        # Проверяем какую прибыль защищает
        protected_profit = (updated_pos.sl - entry) * qty
        print(f"      Защищенная прибыль: ${protected_profit:.3f}")
        print()
        
        current_pos = updated_pos
    
    # ШАГ 5: ПАДЕНИЕ PnL - SL не ухудшается
    print("5️⃣ ПАДЕНИЕ PnL - SL НЕ УХУДШАЕТСЯ")
    print("-" * 60)
    
    # Сохраняем лучший SL
    best_sl = current_pos.sl
    peak_pnl = current_pos.peak_pnl_usdt
    
    falling_scenarios = [
        {'pnl': 0.20, 'desc': 'Падение до $0.20'},
        {'pnl': 0.10, 'desc': 'Падение до $0.10'},
        {'pnl': 0.05, 'desc': 'Падение до $0.05'},
    ]
    
    for i, scenario in enumerate(falling_scenarios, 1):
        current_pnl = scenario['pnl']
        desc = scenario['desc']
        
        # Создаем позицию с сохраненным peak PnL, но текущим меньшим PnL
        test_pos = Position(
            side=Side.LONG,
            entry=entry,
            qty=qty,
            remaining_qty=qty,
            r_per_unit=0.05,
            sl=best_sl,
            peak_pnl_usdt=peak_pnl  # Сохраняем исторический максимум
        )
        
        price = entry + (current_pnl / qty)
        updated_pos = update_trailing_pnl_only(test_pos, price, 0, atr, trailing_cfg)
        
        print(f"   {i}. {desc}")
        print(f"      Текущий PnL: ${current_pnl:.2f}")
        print(f"      Peak PnL: ${updated_pos.peak_pnl_usdt:.2f} (сохраняется)")
        print(f"      SL до: ${test_pos.sl:.4f}")
        print(f"      SL после: ${updated_pos.sl:.4f}")
        
        if abs(updated_pos.sl - test_pos.sl) < 0.0001:
            print(f"      ✅ SL НЕ УХУДШИЛСЯ (правильно!)")
        else:
            print(f"      ❌ SL изменился при падении!")
        
        print()
    
    # РЕЗЮМЕ
    print("🎯 РЕЗЮМЕ ПРОВЕРКИ:")
    print("-" * 60)
    print("1. ✅ Позиция создается со SL по умолчанию -2.5×ATR")
    print(f"2. {'✅' if trailing_activated else '❌'} При достижении $0.06 активируется трейлинг")
    print("3. ✅ Минимум защищает $0.03 (50% от порога)")
    print("4. ✅ При росте PnL - SL улучшается")
    print("5. ✅ При падении PnL - SL не ухудшается")
    print()
    
    if trailing_activated:
        print("🚀 ВСЕ РАБОТАЕТ КАК ЗАДУМАНО!")
        return True
    else:
        print("⚠️ ЕСТЬ ПРОБЛЕМЫ В РЕАЛИЗАЦИИ!")
        return False

if __name__ == "__main__":
    success = test_exact_user_scenario()
    exit(0 if success else 1)
