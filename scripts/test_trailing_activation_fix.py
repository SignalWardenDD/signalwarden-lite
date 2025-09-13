#!/usr/bin/env python3
"""
Тест для проверки исправлений активации трейлинга
"""

import sys
import os
sys.path.append('.')

from signalwarden_lite.core.trailing_pnl_only import update_trailing_pnl_only, TrailingConfigPnLOnly
from signalwarden_lite.core.types import Position, Side

def test_trailing_activation_fix():
    """Тест исправлений активации трейлинга"""
    
    print("🧪 ТЕСТ: Исправления активации трейлинга")
    print("=" * 60)
    
    # Конфигурация трейлинга
    cfg = TrailingConfigPnLOnly()
    
    # Тест 1: Нормальная активация трейлинга
    print("\n📊 ТЕСТ 1: Нормальная активация трейлинга")
    pos = Position(
        side=Side.LONG,
        entry=1.0,
        sl=0.95,  # -5% SL
        qty=100,
        remaining_qty=100,
        r_per_unit=0.05,
        atr=0.02,
        sl_initial=0.95
    )
    pos.peak_pnl_usdt = 0.0  # Начальное значение
    
    # Симулируем рост цены до $0.07 прибыли (выше порога $0.06)
    hi = 1.0007  # +0.07% прибыль = $0.07 при qty=100
    lo = 1.0007
    
    updated_pos = update_trailing_pnl_only(pos, hi, lo, 0.02, cfg)
    
    print(f"   Entry: ${pos.entry:.2f}")
    print(f"   Current Price: ${hi:.2f}")
    print(f"   Current PnL: ${(hi - pos.entry) * pos.qty:.2f}")
    print(f"   Peak PnL: ${updated_pos.peak_pnl_usdt:.2f}")
    print(f"   Old SL: ${pos.sl:.6f}")
    print(f"   New SL: ${updated_pos.sl:.6f}")
    
    debug = updated_pos.trailing_debug
    print(f"   Level: {debug['level']}")
    print(f"   Keep %: {debug['keep_pct']*100:.0f}%")
    print(f"   Target Profit: ${debug['target_profit']:.2f}")
    print(f"   SL Updated: {debug['sl_updated']}")
    print(f"   Protected SL: ${debug.get('protected_sl', 'N/A')}")
    print(f"   Price Protection: {debug.get('price_protection', False)}")
    
    assert abs(updated_pos.peak_pnl_usdt - 0.07) < 0.001, f"Peak PnL должен быть ~0.07, получен {updated_pos.peak_pnl_usdt}"
    assert debug['level'] == 'L1', f"Уровень должен быть L1, получен {debug['level']}"
    assert debug['sl_updated'] == True, "SL должен быть обновлен"
    # SL должен быть выше entry для защиты прибыли
    assert updated_pos.sl > pos.entry, f"Новый SL {updated_pos.sl:.6f} должен быть выше entry {pos.entry:.6f}"
    
    print("   ✅ ТЕСТ 1 ПРОЙДЕН")
    
    # Тест 2: Защита от SL выше текущей цены
    print("\n📊 ТЕСТ 2: Защита от SL выше текущей цены")
    pos2 = Position(
        side=Side.LONG,
        entry=1.0,
        sl=0.95,
        qty=100,
        remaining_qty=100,
        r_per_unit=0.05,
        atr=0.02,
        sl_initial=0.95
    )
    pos2.peak_pnl_usdt = 0.50  # Очень высокий пик PnL ($50)
    
    # Цена упала после пика - SL будет рассчитан на основе пика $50
    # Но current_pnl будет отрицательным, чтобы не обновить peak_pnl_usdt
    hi = 0.98  # -2% от входа = -$2 убыток
    lo = 0.98
    
    updated_pos2 = update_trailing_pnl_only(pos2, hi, lo, 0.02, cfg)
    
    print(f"   Entry: ${pos2.entry:.2f}")
    print(f"   Current Price: ${hi:.2f}")
    print(f"   Peak PnL: ${updated_pos2.peak_pnl_usdt:.2f}")
    print(f"   Old SL: ${pos2.sl:.2f}")
    print(f"   New SL: ${updated_pos2.sl:.2f}")
    
    debug2 = updated_pos2.trailing_debug
    print(f"   Level: {debug2['level']}")
    print(f"   SL Updated: {debug2['sl_updated']}")
    print(f"   Price Protection: {debug2.get('price_protection', False)}")
    
    # SL должен быть ниже текущей цены
    assert updated_pos2.sl < hi, f"SL {updated_pos2.sl:.6f} должен быть ниже цены {hi:.6f}"
    assert debug2.get('price_protection', False) == True, "Должна быть активирована защита от цены"
    
    print("   ✅ ТЕСТ 2 ПРОЙДЕН")
    
    # Тест 3: SHORT позиция с защитой
    print("\n📊 ТЕСТ 3: SHORT позиция с защитой")
    pos3 = Position(
        side=Side.SHORT,
        entry=1.0,
        sl=1.05,  # +5% SL
        qty=100,
        remaining_qty=100,
        r_per_unit=0.05,
        atr=0.02,
        sl_initial=1.05
    )
    pos3.peak_pnl_usdt = 0.08  # Высокий пик PnL
    
    # Цена выросла после пика
    hi = 0.98  # -2% от входа
    lo = 0.98
    
    updated_pos3 = update_trailing_pnl_only(pos3, hi, lo, 0.02, cfg)
    
    print(f"   Entry: ${pos3.entry:.2f}")
    print(f"   Current Price: ${lo:.2f}")
    print(f"   Peak PnL: ${updated_pos3.peak_pnl_usdt:.2f}")
    print(f"   Old SL: ${pos3.sl:.2f}")
    print(f"   New SL: ${updated_pos3.sl:.2f}")
    
    debug3 = updated_pos3.trailing_debug
    print(f"   Level: {debug3['level']}")
    print(f"   SL Updated: {debug3['sl_updated']}")
    print(f"   Price Protection: {debug3.get('price_protection', False)}")
    
    # SL должен быть выше текущей цены
    assert updated_pos3.sl > lo, f"SL {updated_pos3.sl:.6f} должен быть выше цены {lo:.6f}"
    
    print("   ✅ ТЕСТ 3 ПРОЙДЕН")
    
    # Тест 4: Минимальная защита $0.03
    print("\n📊 ТЕСТ 4: Минимальная защита $0.03")
    pos4 = Position(
        side=Side.LONG,
        entry=1.0,
        sl=0.95,
        qty=100,
        remaining_qty=100,
        r_per_unit=0.05,
        atr=0.02,
        sl_initial=0.95
    )
    pos4.peak_pnl_usdt = 0.06  # Точно на пороге
    
    hi = 1.0006  # +0.06% прибыль = $0.06 при qty=100
    lo = 1.0006
    
    updated_pos4 = update_trailing_pnl_only(pos4, hi, lo, 0.02, cfg)
    
    print(f"   Entry: ${pos4.entry:.2f}")
    print(f"   Current Price: ${hi:.2f}")
    print(f"   Peak PnL: ${updated_pos4.peak_pnl_usdt:.2f}")
    print(f"   Old SL: ${pos4.sl:.2f}")
    print(f"   New SL: ${updated_pos4.sl:.2f}")
    
    debug4 = updated_pos4.trailing_debug
    print(f"   Level: {debug4['level']}")
    print(f"   Target Profit: ${debug4['target_profit']:.2f}")
    print(f"   Protection Applied: {debug4.get('protection_applied', False)}")
    
    # Проверяем минимальную защиту $0.03
    min_profit = (updated_pos4.sl - pos4.entry) * pos4.qty
    assert min_profit >= 0.029, f"Минимальная прибыль должна быть >= $0.03, получена ${min_profit:.2f}"
    assert debug4['level'] == 'L1', f"Уровень должен быть L1, получен {debug4['level']}"
    
    print("   ✅ ТЕСТ 4 ПРОЙДЕН")
    
    print("\n🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
    print("✅ Трейлинг активируется правильно")
    print("✅ Защита от SL выше/ниже цены работает")
    print("✅ Минимальная защита $0.03 работает")
    print("✅ SHORT позиции защищены")

if __name__ == "__main__":
    test_trailing_activation_fix()
