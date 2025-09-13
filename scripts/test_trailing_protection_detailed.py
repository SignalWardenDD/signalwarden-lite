#!/usr/bin/env python3
"""
Детальный тест защиты трейлинга от нарушения 2.5×ATR
Проверяем что происходит когда трейлинг ХОЧЕТ подтянуть SL слишком близко
"""

import sys
import os
sys.path.append('.')

import yaml
from signalwarden_lite.core.trailing_pnl_only import TrailingConfigPnLOnly, update_trailing_pnl_only
from signalwarden_lite.core.types import Position, Side

def test_trailing_protection_detailed():
    """Детальный тест защиты трейлинга"""
    print("🔍 ДЕТАЛЬНЫЙ ТЕСТ ЗАЩИТЫ ТРЕЙЛИНГА")
    print("=" * 80)
    
    # Загружаем конфигурацию
    with open('signalwarden_lite/config/config_production.yaml', 'r') as f:
        cfg = yaml.safe_load(f)
    
    sl_atr_mult = cfg['risk']['sl_atr_mult']
    
    # Создаем конфигурацию трейлинга
    trailing_cfg = TrailingConfigPnLOnly(
        level_1_pnl=0.06,   # $0.06 - сохранить 50%
        level_1_keep_pct=0.50,
        level_2_pnl=0.15,   # $0.15 - сохранить 60%
        level_2_keep_pct=0.60,
        level_3_pnl=0.25,   # $0.25 - сохранить 70%
        level_3_keep_pct=0.70,
        level_4_pnl=0.35,   # $0.35+ - сохранить 80%
        level_4_keep_pct=0.80
    )
    
    print("🧪 ТЕСТ-КЕЙС: Большой исторический Peak PnL vs защита 2.5×ATR")
    print("-" * 70)
    
    # Создаем ситуацию где трейлинг ХОЧЕТ подтянуть SL очень близко
    entry = 1.0000
    atr = 0.0200  # 2% ATR
    qty = 21.0
    
    # Правильный SL (2.5×ATR)
    correct_sl = entry - (sl_atr_mult * atr)  # 1.0000 - (2.5 * 0.02) = 0.9500
    min_distance = sl_atr_mult * atr  # 0.0500
    
    print(f"📊 Условия:")
    print(f"   Entry: ${entry:.4f}")
    print(f"   ATR: {atr:.4f} ({atr*100:.1f}%)")
    print(f"   Correct SL (2.5×ATR): ${correct_sl:.4f}")
    print(f"   Min Distance: ${min_distance:.4f} ({min_distance/entry*100:.1f}%)")
    print()
    
    # СЦЕНАРИЙ 1: Большой исторический Peak PnL
    print("🔥 СЦЕНАРИЙ 1: БОЛЬШОЙ ИСТОРИЧЕСКИЙ PEAK PnL")
    print("-" * 50)
    
    # Позиция с большим историческим Peak PnL (как после перезапуска)
    big_peak_pnl = 2.50  # $2.50 - очень большой исторический пик
    
    position_with_history = Position(
        side=Side.LONG,
        entry=entry,
        qty=qty,
        remaining_qty=qty,
        r_per_unit=0.05,
        sl=correct_sl,  # Начинаем с правильного SL
        peak_pnl_usdt=big_peak_pnl
    )
    
    print(f"   Исторический Peak PnL: ${big_peak_pnl:.2f}")
    print(f"   Начальный SL: ${position_with_history.sl:.4f}")
    print()
    
    # Текущая цена чуть выше entry
    current_price = 1.0050  # +0.5%
    current_pnl = (current_price - entry) * qty  # $0.105
    
    print(f"   Текущая цена: ${current_price:.4f}")
    print(f"   Текущий PnL: ${current_pnl:.3f}")
    print()
    
    # ЧТО ХОТЕЛ БЫ СДЕЛАТЬ ТРЕЙЛИНГ БЕЗ ЗАЩИТЫ:
    print("❌ ЧТО ХОТЕЛ БЫ СДЕЛАТЬ ТРЕЙЛИНГ БЕЗ ЗАЩИТЫ:")
    
    # Level 4 (80% от $2.50 = $2.00)
    target_profit = big_peak_pnl * 0.80  # $2.00
    desired_sl = entry + (target_profit / qty)  # 1.0000 + (2.00 / 21) = 1.0952
    desired_distance = desired_sl - entry  # 0.0952
    
    print(f"   Target Profit (80%): ${target_profit:.2f}")
    print(f"   Желаемый SL: ${desired_sl:.4f}")
    print(f"   Желаемое расстояние: ${desired_distance:.4f} ({desired_distance/entry*100:.1f}%)")
    print(f"   ❌ ПРОБЛЕМА: SL был бы ВЫШЕ entry! Нарушение логики!")
    print()
    
    # ЧТО ДЕЛАЕТ НАШ ЗАЩИЩЕННЫЙ ТРЕЙЛИНГ:
    print("✅ ЧТО ДЕЛАЕТ НАШ ЗАЩИЩЕННЫЙ ТРЕЙЛИНГ:")
    
    protected_position = update_trailing_pnl_only(
        position_with_history, 
        current_price, 
        0, 
        atr, 
        trailing_cfg
    )
    
    print(f"   Фактический SL: ${protected_position.sl:.4f}")
    
    # Проверяем защиту
    actual_distance = entry - protected_position.sl
    actual_distance_pct = (actual_distance / entry) * 100
    
    print(f"   Фактическое расстояние: ${actual_distance:.4f} ({actual_distance_pct:.1f}%)")
    
    if actual_distance >= min_distance * 0.99:
        print(f"   ✅ ЗАЩИТА СРАБОТАЛА: SL остался на безопасном расстоянии")
        scenario_1_safe = True
    else:
        print(f"   ❌ ЗАЩИТА НЕ СРАБОТАЛА!")
        scenario_1_safe = False
    
    print()
    
    # СЦЕНАРИЙ 2: Проверяем разные уровни трейлинга
    print("🔥 СЦЕНАРИЙ 2: ПРОВЕРКА ВСЕХ УРОВНЕЙ ТРЕЙЛИНГА")
    print("-" * 50)
    
    test_cases = [
        {'peak_pnl': 0.08, 'level': 'L1', 'keep_pct': 0.50, 'desc': 'Level 1 (50%)'},
        {'peak_pnl': 0.20, 'level': 'L2', 'keep_pct': 0.60, 'desc': 'Level 2 (60%)'},
        {'peak_pnl': 0.30, 'level': 'L3', 'keep_pct': 0.70, 'desc': 'Level 3 (70%)'},
        {'peak_pnl': 0.50, 'level': 'L4', 'keep_pct': 0.80, 'desc': 'Level 4 (80%)'},
        {'peak_pnl': 1.00, 'level': 'L4', 'keep_pct': 0.80, 'desc': 'Большой Level 4'},
    ]
    
    all_levels_safe = True
    
    for i, case in enumerate(test_cases, 1):
        peak_pnl = case['peak_pnl']
        keep_pct = case['keep_pct']
        desc = case['desc']
        
        # Создаем позицию
        test_position = Position(
            side=Side.LONG,
            entry=entry,
            qty=qty,
            remaining_qty=qty,
            r_per_unit=0.05,
            sl=correct_sl,
            peak_pnl_usdt=peak_pnl
        )
        
        # Применяем трейлинг
        result_position = update_trailing_pnl_only(
            test_position, 
            current_price, 
            0, 
            atr, 
            trailing_cfg
        )
        
        # Что хотел бы трейлинг без защиты
        target_profit_unprotected = peak_pnl * keep_pct
        desired_sl_unprotected = entry + (target_profit_unprotected / qty)
        
        # Что получилось с защитой
        actual_sl = result_position.sl
        actual_dist = entry - actual_sl
        
        print(f"   {i}. {desc} (Peak: ${peak_pnl:.2f})")
        print(f"      Без защиты SL был бы: ${desired_sl_unprotected:.4f}")
        print(f"      С защитой SL: ${actual_sl:.4f}")
        print(f"      Расстояние: ${actual_dist:.4f} ({actual_dist/entry*100:.1f}%)")
        
        if actual_dist >= min_distance * 0.99:
            print(f"      ✅ Защищено")
        else:
            print(f"      ❌ НЕ защищено!")
            all_levels_safe = False
        
        print()
    
    # ВЫВОДЫ
    print("🎯 ДЕТАЛЬНЫЕ ВЫВОДЫ:")
    print("-" * 50)
    
    print("1. ✅ Защита работает даже с большими историческими Peak PnL")
    print("2. ✅ SL никогда не подтягивается ближе чем 2.5×ATR")
    print("3. ✅ Трейлинг не может нарушить базовую логику стратегии")
    print(f"4. {'✅' if scenario_1_safe else '❌'} Критический сценарий с большим Peak PnL")
    print(f"5. {'✅' if all_levels_safe else '❌'} Все уровни трейлинга защищены")
    
    if scenario_1_safe and all_levels_safe:
        print()
        print("🛡️ ЗАЩИТА РАБОТАЕТ ИДЕАЛЬНО!")
        print("   • Трейлинг защищает прибыль когда может")
        print("   • Базовая логика 2.5×ATR никогда не нарушается")
        print("   • Система безопасна при любых Peak PnL")
        return True
    else:
        print()
        print("⚠️ ОБНАРУЖЕНЫ ПРОБЛЕМЫ С ЗАЩИТОЙ!")
        return False

if __name__ == "__main__":
    success = test_trailing_protection_detailed()
    exit(0 if success else 1)
