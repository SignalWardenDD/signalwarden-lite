#!/usr/bin/env python3
"""
Отладка точного порога активации
"""

import sys
import os
sys.path.append('.')

from signalwarden_lite.core.trailing_pnl_only import TrailingConfigPnLOnly, update_trailing_pnl_only
from signalwarden_lite.core.types import Position, Side

def debug_threshold():
    """Отладка порога активации"""
    print("🔍 ОТЛАДКА ПОРОГА АКТИВАЦИИ")
    print("=" * 40)
    
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
    
    print(f"Порог level_1_pnl: {trailing_cfg.level_1_pnl}")
    print(f"Точность: {repr(trailing_cfg.level_1_pnl)}")
    print()
    
    entry = 1.0000  # Упрощаем для точности
    qty = 21.0      # Упрощаем
    atr = 0.0200
    
    # Тестируем точно 0.06
    target_pnl = 0.06
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
    
    print(f"Target PnL: {target_pnl}")
    print(f"Target price: {target_price}")
    print(f"Entry: {entry}")
    print(f"Qty: {qty}")
    print()
    
    updated_pos = update_trailing_pnl_only(position, target_price, 0, atr, trailing_cfg)
    actual_pnl = (target_price - entry) * qty
    
    print(f"Actual PnL: {actual_pnl}")
    print(f"Peak PnL: {updated_pos.peak_pnl_usdt}")
    print(f"Peak PnL repr: {repr(updated_pos.peak_pnl_usdt)}")
    print()
    
    # Проверяем сравнение
    threshold = trailing_cfg.level_1_pnl
    peak = updated_pos.peak_pnl_usdt
    
    print(f"Threshold: {threshold} ({repr(threshold)})")
    print(f"Peak PnL:  {peak} ({repr(peak)})")
    print(f"peak >= threshold: {peak >= threshold}")
    print(f"peak > threshold: {peak > threshold}")
    print(f"peak == threshold: {peak == threshold}")
    print(f"Difference: {peak - threshold}")
    print()
    
    if hasattr(updated_pos, 'trailing_debug'):
        debug = updated_pos.trailing_debug
        print(f"Debug info:")
        for key, value in debug.items():
            print(f"  {key}: {value}")

if __name__ == "__main__":
    debug_threshold()
