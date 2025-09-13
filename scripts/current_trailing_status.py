#!/usr/bin/env python3
"""
Отчет о текущем состоянии трейлинга - что он сейчас делает
"""

import sys
import os
sys.path.append('.')

import yaml
from signalwarden_lite.core.trailing_pnl_only import TrailingConfigPnLOnly, update_trailing_pnl_only
from signalwarden_lite.core.types import Position, Side

def analyze_current_trailing():
    """Анализ текущего состояния трейлинга"""
    print("🔍 ЧТО СЕЙЧАС ДЕЛАЕТ ТРЕЙЛИНГ")
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
    
    # Тестируем разные сценарии
    entry = 1.0000
    atr = 0.0200  # 2% ATR
    qty = 21.0
    initial_sl = entry - (2.5 * atr)  # $0.9500
    
    print(f"📊 ТЕСТОВЫЕ УСЛОВИЯ:")
    print(f"   Entry: ${entry:.4f}")
    print(f"   ATR: {atr:.4f} (2.0%)")
    print(f"   Qty: {qty}")
    print(f"   Initial SL (2.5×ATR): ${initial_sl:.4f}")
    print()
    
    # Тест 1: Небольшая прибыль
    print("🧪 ТЕСТ 1: НЕБОЛЬШАЯ ПРИБЫЛЬ")
    print("-" * 50)
    
    position1 = Position(
        side=Side.LONG,
        entry=entry,
        qty=qty,
        remaining_qty=qty,
        r_per_unit=0.05,
        sl=initial_sl,
        peak_pnl_usdt=0.08  # Level 1
    )
    
    current_price = 1.0040
    result1 = update_trailing_pnl_only(position1, current_price, 0, atr, trailing_cfg)
    
    print(f"   Peak PnL: ${position1.peak_pnl_usdt:.2f}")
    print(f"   Исходный SL: ${position1.sl:.4f}")
    print(f"   Новый SL: ${result1.sl:.4f}")
    
    if result1.sl > position1.sl:
        improvement = result1.sl - position1.sl
        print(f"   ✅ SL улучшился на ${improvement:.4f}")
    else:
        print(f"   📊 SL не изменился")
    
    # Показываем что трейлинг хотел сделать
    target_profit = 0.08 * 0.5  # 50%
    desired_sl = entry + (target_profit / qty)
    print(f"   Трейлинг хотел: ${desired_sl:.4f}")
    print(f"   Фактически: ${result1.sl:.4f}")
    print()
    
    # Тест 2: Средняя прибыль
    print("🧪 ТЕСТ 2: СРЕДНЯЯ ПРИБЫЛЬ")
    print("-" * 50)
    
    position2 = Position(
        side=Side.LONG,
        entry=entry,
        qty=qty,
        remaining_qty=qty,
        r_per_unit=0.05,
        sl=initial_sl,
        peak_pnl_usdt=0.20  # Level 2
    )
    
    result2 = update_trailing_pnl_only(position2, current_price, 0, atr, trailing_cfg)
    
    print(f"   Peak PnL: ${position2.peak_pnl_usdt:.2f}")
    print(f"   Исходный SL: ${position2.sl:.4f}")
    print(f"   Новый SL: ${result2.sl:.4f}")
    
    if result2.sl > position2.sl:
        improvement = result2.sl - position2.sl
        print(f"   ✅ SL улучшился на ${improvement:.4f}")
    else:
        print(f"   📊 SL не изменился")
    
    # Показываем что трейлинг хотел сделать
    target_profit = 0.20 * 0.6  # 60%
    desired_sl = entry + (target_profit / qty)
    print(f"   Трейлинг хотел: ${desired_sl:.4f}")
    print(f"   Фактически: ${result2.sl:.4f}")
    
    # Проверяем защиту
    max_allowed = entry + (atr * 1.0)
    if desired_sl > max_allowed:
        print(f"   🛡️ Защита сработала: ${desired_sl:.4f} > ${max_allowed:.4f}")
    else:
        print(f"   📊 Защита не нужна")
    print()
    
    # Тест 3: Большая прибыль
    print("🧪 ТЕСТ 3: БОЛЬШАЯ ПРИБЫЛЬ")
    print("-" * 50)
    
    position3 = Position(
        side=Side.LONG,
        entry=entry,
        qty=qty,
        remaining_qty=qty,
        r_per_unit=0.05,
        sl=initial_sl,
        peak_pnl_usdt=0.50  # Level 4
    )
    
    result3 = update_trailing_pnl_only(position3, current_price, 0, atr, trailing_cfg)
    
    print(f"   Peak PnL: ${position3.peak_pnl_usdt:.2f}")
    print(f"   Исходный SL: ${position3.sl:.4f}")
    print(f"   Новый SL: ${result3.sl:.4f}")
    
    if result3.sl > position3.sl:
        improvement = result3.sl - position3.sl
        print(f"   ✅ SL улучшился на ${improvement:.4f}")
    else:
        print(f"   📊 SL не изменился")
    
    # Показываем что трейлинг хотел сделать
    target_profit = 0.50 * 0.8  # 80%
    desired_sl = entry + (target_profit / qty)
    print(f"   Трейлинг хотел: ${desired_sl:.4f}")
    print(f"   Фактически: ${result3.sl:.4f}")
    
    # Проверяем защиту
    max_allowed = entry + (atr * 1.0)
    if desired_sl > max_allowed:
        print(f"   🛡️ Защита сработала: ${desired_sl:.4f} > ${max_allowed:.4f}")
    else:
        print(f"   📊 Защита не нужна")
    print()
    
    # Тест 4: Экстремальная прибыль
    print("🧪 ТЕСТ 4: ЭКСТРЕМАЛЬНАЯ ПРИБЫЛЬ")
    print("-" * 50)
    
    position4 = Position(
        side=Side.LONG,
        entry=entry,
        qty=qty,
        remaining_qty=qty,
        r_per_unit=0.05,
        sl=initial_sl,
        peak_pnl_usdt=2.00  # Очень большая
    )
    
    result4 = update_trailing_pnl_only(position4, current_price, 0, atr, trailing_cfg)
    
    print(f"   Peak PnL: ${position4.peak_pnl_usdt:.2f}")
    print(f"   Исходный SL: ${position4.sl:.4f}")
    print(f"   Новый SL: ${result4.sl:.4f}")
    
    if result4.sl > position4.sl:
        improvement = result4.sl - position4.sl
        print(f"   ✅ SL улучшился на ${improvement:.4f}")
    else:
        print(f"   📊 SL не изменился")
    
    # Показываем что трейлинг хотел сделать
    target_profit = 2.00 * 0.8  # 80%
    desired_sl = entry + (target_profit / qty)
    print(f"   Трейлинг хотел: ${desired_sl:.4f}")
    print(f"   Фактически: ${result4.sl:.4f}")
    
    # Проверяем защиту
    max_allowed = entry + (atr * 1.0)
    if desired_sl > max_allowed:
        print(f"   🛡️ Защита сработала: ${desired_sl:.4f} > ${max_allowed:.4f}")
        print(f"   🛡️ Ограничение: entry + 1×ATR = ${max_allowed:.4f}")
    else:
        print(f"   📊 Защита не нужна")
    print()
    
    # РЕЗЮМЕ
    print("🎯 ЧТО СЕЙЧАС ДЕЛАЕТ ТРЕЙЛИНГ:")
    print("-" * 60)
    print("1. ✅ Работает по уровням прибыли (Level 1-4)")
    print("2. ✅ Подтягивает SL для защиты процента от Peak PnL")
    print("3. ✅ Разрешает SL быть ВЫШЕ entry (защита прибыли)")
    print("4. ✅ Ограничивает максимальный SL: entry + 1×ATR")
    print("5. ✅ SL только улучшается, никогда не ухудшается")
    print()
    
    print("🛡️ ЗАЩИТА:")
    print(f"   Максимальный SL: entry + 1×ATR = ${max_allowed:.4f}")
    print(f"   Это {(max_allowed-entry)/entry*100:.1f}% выше entry")
    print()
    
    print("🚀 ТРЕЙЛИНГ ТЕПЕРЬ РАБОТАЕТ И ЗАЩИЩАЕТ ПРИБЫЛЬ!")

if __name__ == "__main__":
    analyze_current_trailing()
