#!/usr/bin/env python3
"""
Тест СТАРОГО трейлинга на сценарии DOGE
Проверяем что трейлинг активируется при $0.06 PnL
"""

import sys
import os
sys.path.append('.')

from signalwarden_lite.core.trailing_pnl_only import TrailingConfigPnLOnly, update_trailing_pnl_only
from signalwarden_lite.core.types import Position, Side

def test_old_trailing_doge():
    """Тест старого трейлинга на DOGE"""
    print("🔄 ТЕСТ СТАРОГО ТРЕЙЛИНГА - DOGE СЦЕНАРИЙ")
    print("=" * 60)
    
    trailing_cfg = TrailingConfigPnLOnly(
        level_1_pnl=0.06,   # Порог активации $0.06
        level_1_keep_pct=0.50,  # 50%
        level_2_pnl=0.15,
        level_2_keep_pct=0.60,
        level_3_pnl=0.25,
        level_3_keep_pct=0.70,
        level_4_pnl=0.35,
        level_4_keep_pct=0.80
    )
    
    # Параметры DOGE
    entry = 0.300557
    qty = 69.8703
    atr = 0.005189
    
    print(f"📊 DOGE_USDT (старый трейлинг):")
    print(f"   Entry: ${entry:.6f}")
    print(f"   Qty: {qty:.4f}")
    print(f"   ATR: {atr:.6f}")
    print()
    
    # Создаем позицию
    position = Position(
        side=Side.LONG,
        entry=entry,
        qty=qty,
        remaining_qty=qty,
        r_per_unit=0.05,
        sl=entry - (2.5 * atr),
        peak_pnl_usdt=0.0
    )
    
    print(f"   Начальный SL: ${position.sl:.6f}")
    print()
    
    # Критический тест: достижение $0.06 PnL
    target_pnl = 0.06
    target_price = entry + (target_pnl / qty)
    
    print(f"🎯 КРИТИЧЕСКИЙ ТЕСТ: Достижение ${target_pnl:.2f} PnL")
    print(f"   Целевая цена: ${target_price:.6f}")
    
    # Применяем трейлинг
    updated_pos = update_trailing_pnl_only(position, target_price, 0, atr, trailing_cfg)
    actual_pnl = (target_price - entry) * qty
    
    print(f"   Фактический PnL: ${actual_pnl:.4f}")
    print(f"   Peak PnL: ${updated_pos.peak_pnl_usdt:.4f}")
    
    if hasattr(updated_pos, 'trailing_debug'):
        debug = updated_pos.trailing_debug
        level = debug.get('level', 'INACTIVE')
        keep_pct = debug.get('keep_pct', 0)
        
        print(f"   Уровень трейлинга: {level}")
        print(f"   Keep %: {keep_pct * 100:.0f}%")
        
        if level != 'INACTIVE':
            protected_profit = (updated_pos.sl - entry) * qty
            print(f"   ✅ ТРЕЙЛИНГ АКТИВИРОВАН!")
            print(f"   🛡️ Защищенная прибыль: ${protected_profit:.4f}")
            print(f"   🎯 Минимум защищен: ${target_pnl * keep_pct:.4f}")
        else:
            print(f"   ❌ ТРЕЙЛИНГ НЕ АКТИВИРОВАН!")
    else:
        print(f"   ❌ Нет debug информации о трейлинге!")
    
    print(f"   Новый SL: ${updated_pos.sl:.6f}")
    
    # Проверяем улучшение SL
    sl_improved = updated_pos.sl > position.sl
    print(f"   SL улучшился: {sl_improved}")
    
    if sl_improved:
        sl_improvement = updated_pos.sl - position.sl
        print(f"   Улучшение SL: +${sl_improvement:.6f}")
    
    print()
    
    # Тест падения цены
    print("📉 ТЕСТ: Падение цены после активации")
    print("-" * 40)
    
    # Цена падает, но Peak PnL сохраняется
    falling_price = entry + 0.0005  # Небольшой рост от entry
    
    # Создаем позицию с сохраненным Peak PnL
    test_pos = Position(
        side=Side.LONG,
        entry=entry,
        qty=qty,
        remaining_qty=qty,
        r_per_unit=0.05,
        sl=updated_pos.sl,  # Используем улучшенный SL
        peak_pnl_usdt=updated_pos.peak_pnl_usdt  # Сохраняем Peak PnL
    )
    
    final_pos = update_trailing_pnl_only(test_pos, falling_price, 0, atr, trailing_cfg)
    current_pnl = (falling_price - entry) * qty
    final_protected = (final_pos.sl - entry) * qty
    
    print(f"   Цена после падения: ${falling_price:.6f}")
    print(f"   Текущий PnL: ${current_pnl:.4f}")
    print(f"   Peak PnL: ${final_pos.peak_pnl_usdt:.4f} (сохранен)")
    print(f"   SL: ${final_pos.sl:.6f}")
    print(f"   Защищенная прибыль: ${final_protected:.4f}")
    
    if final_protected >= 0.029:  # ~$0.03
        print(f"   ✅ Минимальная защита сохранена!")
    else:
        print(f"   ❌ Минимальная защита потеряна!")
    
    print()
    print("🎯 ИТОГ:")
    if level != 'INACTIVE' and final_protected >= 0.029:
        print("✅ СТАРЫЙ ТРЕЙЛИНГ РАБОТАЕТ ПРАВИЛЬНО!")
        print("🛡️ Активируется при $0.06 и защищает минимум $0.03")
        return True
    else:
        print("❌ ПРОБЛЕМЫ СО СТАРЫМ ТРЕЙЛИНГОМ!")
        return False

if __name__ == "__main__":
    success = test_old_trailing_doge()
    exit(0 if success else 1)
