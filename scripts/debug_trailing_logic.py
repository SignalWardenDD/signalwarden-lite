#!/usr/bin/env python3
"""
Отладка логики трейлинга - почему SL не обновляется
"""

import sys
import os
sys.path.append('.')

import yaml
from signalwarden_lite.core.trailing_pnl_only import TrailingConfigPnLOnly, update_trailing_pnl_only
from signalwarden_lite.core.types import Position, Side

def debug_trailing_logic():
    """Отладка логики трейлинга"""
    print("🔍 ОТЛАДКА ЛОГИКИ ТРЕЙЛИНГА")
    print("=" * 80)
    
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
    
    entry = 0.948900
    atr = 0.008879
    qty = 21.0
    initial_sl = entry - (2.5 * atr)  # $0.926702
    
    print(f"Entry: ${entry:.6f}")
    print(f"ATR: {atr:.6f}")
    print(f"Qty: {qty}")
    print(f"Initial SL: ${initial_sl:.6f}")
    print()
    
    # Создаем позицию с Peak PnL = $0.168 (Level 2)
    position = Position(
        side=Side.LONG,
        entry=entry,
        qty=qty,
        remaining_qty=qty,
        r_per_unit=0.05,
        sl=initial_sl,
        peak_pnl_usdt=0.168  # Level 2
    )
    
    print(f"Peak PnL: ${position.peak_pnl_usdt:.3f}")
    print(f"Current SL: ${position.sl:.6f}")
    print()
    
    # Применяем трейлинг
    current_price = 0.956900
    updated_position = update_trailing_pnl_only(position, current_price, 0, atr, trailing_cfg)
    
    print(f"Current Price: ${current_price:.6f}")
    print(f"Updated SL: ${updated_position.sl:.6f}")
    print()
    
    # Ручной расчет что должно происходить
    print("🧮 РУЧНОЙ РАСЧЕТ:")
    
    # Level 2: keep 60% of $0.168 = $0.1008
    target_profit = 0.168 * 0.60
    print(f"Target Profit (60% of ${0.168:.3f}): ${target_profit:.4f}")
    
    # SL для сохранения этой прибыли: entry + (target_profit / qty)
    calculated_sl = entry + (target_profit / qty)
    print(f"Calculated SL: ${entry:.6f} + (${target_profit:.4f} / {qty}) = ${calculated_sl:.6f}")
    
    # Проверяем улучшается ли SL
    if calculated_sl > initial_sl:
        print(f"✅ SL улучшается: ${initial_sl:.6f} → ${calculated_sl:.6f}")
    else:
        print(f"❌ SL НЕ улучшается: ${calculated_sl:.6f} ≤ ${initial_sl:.6f}")
    
    print()
    
    # Проверяем отладочную информацию
    if hasattr(updated_position, 'trailing_debug'):
        debug = updated_position.trailing_debug
        print("🔍 ОТЛАДОЧНАЯ ИНФОРМАЦИЯ:")
        for key, value in debug.items():
            print(f"   {key}: {value}")
    
    print()
    
    # Тест с большим Peak PnL
    print("🔥 ТЕСТ С БОЛЬШИМ PEAK PnL:")
    
    big_position = Position(
        side=Side.LONG,
        entry=entry,
        qty=qty,
        remaining_qty=qty,
        r_per_unit=0.05,
        sl=initial_sl,
        peak_pnl_usdt=0.50  # Большой Peak PnL
    )
    
    big_updated = update_trailing_pnl_only(big_position, current_price, 0, atr, trailing_cfg)
    
    print(f"Big Peak PnL: ${big_position.peak_pnl_usdt:.2f}")
    print(f"Big Updated SL: ${big_updated.sl:.6f}")
    
    # Ручной расчет для большого Peak PnL
    big_target_profit = 0.50 * 0.80  # Level 4: 80% of $0.50 = $0.40
    big_calculated_sl = entry + (big_target_profit / qty)
    
    print(f"Big Target Profit (80%): ${big_target_profit:.2f}")
    print(f"Big Calculated SL: ${big_calculated_sl:.6f}")
    
    if big_calculated_sl > initial_sl:
        print(f"✅ Big SL должен улучшиться: ${initial_sl:.6f} → ${big_calculated_sl:.6f}")
    else:
        print(f"❌ Big SL НЕ должен улучшиться")
    
    print()
    
    # Проверяем защиту
    print("🛡️ ПРОВЕРКА ЗАЩИТЫ:")
    min_distance = 2.5 * atr
    current_distance = entry - initial_sl
    
    print(f"Min Distance (2.5×ATR): ${min_distance:.6f}")
    print(f"Current Distance: ${current_distance:.6f}")
    print(f"Is at initial distance: {abs(current_distance - min_distance) < 0.001}")
    
    if big_calculated_sl > (entry - min_distance):
        print(f"🚨 Big SL выше минимального: ${big_calculated_sl:.6f} > ${entry - min_distance:.6f}")
        print(f"   Защита должна сработать!")
    else:
        print(f"✅ Big SL в пределах нормы")

if __name__ == "__main__":
    debug_trailing_logic()
