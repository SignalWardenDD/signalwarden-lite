#!/usr/bin/env python3
"""
Точный тест старого трейлинга с разными значениями PnL
"""

import sys
import os
sys.path.append('.')

from signalwarden_lite.core.trailing_pnl_only import TrailingConfigPnLOnly, update_trailing_pnl_only
from signalwarden_lite.core.types import Position, Side

def test_precise_activation():
    """Тест точной активации трейлинга"""
    print("🔍 ТОЧНЫЙ ТЕСТ АКТИВАЦИИ ТРЕЙЛИНГА")
    print("=" * 50)
    
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
    
    entry = 0.300557
    qty = 69.8703
    atr = 0.005189
    
    # Тестируем разные значения PnL вокруг порога $0.06
    test_pnls = [0.055, 0.059, 0.060, 0.061, 0.065, 0.070]
    
    for target_pnl in test_pnls:
        print(f"\n🎯 Тест PnL: ${target_pnl:.3f}")
        
        # Рассчитываем цену для достижения целевого PnL
        target_price = entry + (target_pnl / qty)
        
        position = Position(
            side=Side.LONG,
            entry=entry,
            qty=qty,
            remaining_qty=qty,
            r_per_unit=0.05,
            sl=entry - (2.5 * atr),
            peak_pnl_usdt=0.0
        )
        
        updated_pos = update_trailing_pnl_only(position, target_price, 0, atr, trailing_cfg)
        actual_pnl = (target_price - entry) * qty
        
        print(f"   Цена: ${target_price:.6f}")
        print(f"   Фактический PnL: ${actual_pnl:.4f}")
        print(f"   Peak PnL: ${updated_pos.peak_pnl_usdt:.4f}")
        
        if hasattr(updated_pos, 'trailing_debug'):
            debug = updated_pos.trailing_debug
            level = debug.get('level', 'INACTIVE')
            keep_pct = debug.get('keep_pct', 0)
            
            print(f"   Уровень: {level}")
            print(f"   Keep %: {keep_pct * 100:.0f}%")
            
            # Проверяем активацию
            should_be_active = actual_pnl >= 0.06
            is_active = level != 'INACTIVE'
            
            if should_be_active and is_active:
                print(f"   ✅ Трейлинг активирован правильно")
                protected = (updated_pos.sl - entry) * qty
                print(f"   🛡️ Защищено: ${protected:.4f}")
            elif not should_be_active and not is_active:
                print(f"   ✅ Трейлинг неактивен (правильно)")
            else:
                print(f"   ❌ ОШИБКА АКТИВАЦИИ! Должен: {should_be_active}, Факт: {is_active}")
        
        print(f"   SL: ${updated_pos.sl:.6f}")

if __name__ == "__main__":
    test_precise_activation()
