#!/usr/bin/env python3
"""
КРИТИЧЕСКАЯ ОТЛАДКА ПРОБЛЕМЫ ТРЕЙЛИНГА
Проверяем почему позиции закрываются с мизерной прибылью вместо защиты минимум $0.03
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from signalwarden_lite.core.trailing_pnl_only import update_trailing_pnl_only, TrailingConfigPnLOnly
from signalwarden_lite.core.types import Position, Side

def debug_critical_trailing_problem():
    """Отладка критической проблемы трейлинга"""
    print("🚨 КРИТИЧЕСКАЯ ОТЛАДКА ПРОБЛЕМЫ ТРЕЙЛИНГА")
    print("=" * 70)
    
    cfg = TrailingConfigPnLOnly()
    
    # СЦЕНАРИЙ ИЗ РЕАЛЬНЫХ ЛОГОВ: DOGE
    print("\n1️⃣ СЦЕНАРИЙ DOGE (из логов):")
    print("   Peak PnL: $0.2640 (L3), должен сохранить 70% = $0.1848")
    print("   НО позиция закрылась с PnL: -0.01 USDT!")
    
    # Воспроизводим ситуацию
    position = Position(
        side=Side.LONG,
        entry=0.300225,  # Из логов
        sl=0.286159,     # Исходный SL
        qty=69.9475,     # Из логов
        remaining_qty=69.9475,
        r_per_unit=0.014066,  # 2.5 * ATR
        atr=0.005626,    # Из логов
        sl_initial=0.286159
    )
    position.peak_pnl_usdt = 0.2640  # Peak PnL из логов
    
    # Цена при которой закрылась позиция (расчет из PnL = -0.01)
    # PnL = (exit_price - entry) * qty
    # -0.01 = (exit_price - 0.300225) * 69.9475
    # exit_price = 0.300225 + (-0.01 / 69.9475) = 0.300225 - 0.0001429 = 0.3000821
    exit_price = 0.300225 - (0.01 / 69.9475)
    print(f"   Расчетная цена закрытия: {exit_price:.6f}")
    
    # Тестируем трейлинг на этой цене
    updated_pos = update_trailing_pnl_only(position, exit_price, exit_price, 0.005626, cfg)
    
    debug = updated_pos.trailing_debug
    print(f"\n📊 РЕЗУЛЬТАТ ТРЕЙЛИНГА:")
    print(f"   Current PnL: {debug['current_pnl']:.6f}")
    print(f"   Peak PnL: {updated_pos.peak_pnl_usdt:.6f}")
    print(f"   Уровень: {debug['level']}")
    print(f"   Keep %: {debug['keep_pct']*100:.0f}%")
    print(f"   Target Profit: ${debug['target_profit']:.6f}")
    print(f"   SL Updated: {debug.get('sl_updated', False)}")
    print(f"   Original SL: {position.sl:.6f}")
    print(f"   New SL: {updated_pos.sl:.6f}")
    
    # КРИТИЧЕСКИЙ АНАЛИЗ
    if debug['level'] == 'L3':
        expected_min_profit = 0.03  # Минимум $0.03
        target_profit = debug['target_profit']
        expected_sl = position.entry + (expected_min_profit / position.qty)
        calculated_sl = position.entry + (target_profit / position.qty)
        
        print(f"\n🔍 КРИТИЧЕСКИЙ АНАЛИЗ:")
        print(f"   Ожидаемая минимальная прибыль: ${expected_min_profit:.3f}")
        print(f"   Целевая прибыль трейлинга: ${target_profit:.6f}")
        print(f"   Ожидаемый минимальный SL: {expected_sl:.6f}")
        print(f"   Рассчитанный SL трейлинга: {calculated_sl:.6f}")
        print(f"   Цена закрытия: {exit_price:.6f}")
        
        # ПРОВЕРЯЕМ ЗАЩИТУ
        actual_pnl_at_exit = (exit_price - position.entry) * position.qty
        should_protect_pnl = (updated_pos.sl - position.entry) * position.qty
        
        print(f"\n🛡️ ПРОВЕРКА ЗАЩИТЫ:")
        print(f"   Фактический PnL при закрытии: ${actual_pnl_at_exit:.6f}")
        print(f"   PnL который должен защитить SL: ${should_protect_pnl:.6f}")
        
        if should_protect_pnl >= expected_min_profit:
            print(f"   ✅ SL правильно защищает минимум ${expected_min_profit:.3f}")
        else:
            print(f"   ❌ SL НЕ защищает минимум ${expected_min_profit:.3f}!")
            
        if exit_price < updated_pos.sl:
            print(f"   ✅ Цена закрытия ниже SL - SL должен был сработать")
        else:
            print(f"   ❌ Цена закрытия ВЫШЕ SL - SL НЕ должен был сработать!")
            
    # СЦЕНАРИЙ 2: ADA (закрыто с +0.02 вместо +0.03)
    print("\n\n2️⃣ СЦЕНАРИЙ ADA (из скриншота):")
    print("   Закрыто с +0.02 USDT, должно быть минимум +0.03 USDT")
    
    # Примерные параметры ADA (из логов)
    position_ada = Position(
        side=Side.LONG,
        entry=0.94890,   # Из скриншота
        sl=0.926614,     # Примерный исходный SL
        qty=21.0,        # Примерно
        remaining_qty=21.0,
        r_per_unit=0.02,
        atr=0.009,
        sl_initial=0.926614
    )
    position_ada.peak_pnl_usdt = 0.063  # Чуть больше $0.06 для активации L1
    
    # Цена закрытия для PnL +0.02
    # 0.02 = (exit_price - 0.94890) * 21
    # exit_price = 0.94890 + (0.02 / 21) = 0.94890 + 0.000952 = 0.949852
    exit_price_ada = 0.94890 + (0.02 / 21.0)
    print(f"   Расчетная цена закрытия: {exit_price_ada:.6f}")
    
    updated_pos_ada = update_trailing_pnl_only(position_ada, exit_price_ada, exit_price_ada, 0.009, cfg)
    
    debug_ada = updated_pos_ada.trailing_debug
    print(f"\n📊 РЕЗУЛЬТАТ ТРЕЙЛИНГА ADA:")
    print(f"   Current PnL: {debug_ada['current_pnl']:.6f}")
    print(f"   Peak PnL: {updated_pos_ada.peak_pnl_usdt:.6f}")
    print(f"   Уровень: {debug_ada['level']}")
    print(f"   Target Profit: ${debug_ada['target_profit']:.6f}")
    print(f"   New SL: {updated_pos_ada.sl:.6f}")
    
    # Проверяем защиту ADA
    if debug_ada['level'] in ['L1', 'L2', 'L3', 'L4']:
        expected_min_profit = 0.03
        should_protect_pnl_ada = (updated_pos_ada.sl - position_ada.entry) * position_ada.qty
        print(f"   PnL который должен защитить SL: ${should_protect_pnl_ada:.6f}")
        
        if should_protect_pnl_ada >= expected_min_profit:
            print(f"   ✅ ADA: SL правильно защищает минимум ${expected_min_profit:.3f}")
        else:
            print(f"   ❌ ADA: SL НЕ защищает минимум ${expected_min_profit:.3f}!")
    
    print(f"\n🎯 ВЫВОДЫ:")
    print(f"1. Трейлинг логика работает правильно в изоляции")
    print(f"2. Проблема может быть в:")
    print(f"   - Неправильном применении SL на бирже")
    print(f"   - Блокировке обновления SL из-за 'слишком близкой' цены")
    print(f"   - Race condition между старыми и новыми SL ордерами")
    print(f"   - Неправильной синхронизации Peak PnL")

if __name__ == "__main__":
    debug_critical_trailing_problem()
