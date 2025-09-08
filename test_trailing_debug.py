#!/usr/bin/env python3
"""
Детальный тест трейлинга с отладочной информацией
"""

import sys
sys.path.append('.')

from signalwarden_lite.core.trailing import TrailingConfig, update_trailing_pnl_based
from signalwarden_lite.core.types import Position, Side

def test_pnut_exact_scenario():
    """
    Точный тест сценария PNUT
    """
    print("🔍 ТОЧНЫЙ ТЕСТ СЦЕНАРИЯ PNUT")
    print("=" * 70)
    
    cfg = TrailingConfig(
        activate_pnl_usdt=0.10,
        level_1_pnl=0.10, level_1_keep_pct=0.50,
        level_2_pnl=0.20, level_2_keep_pct=0.60,
        level_3_pnl=0.30, level_3_keep_pct=0.70,
        level_4_pnl=0.40, level_4_keep_pct=0.80
    )
    
    # Точные данные PNUT из логов
    entry = 0.233207
    qty = 90.048909
    sl_initial = 0.223694
    
    pos = Position(
        side=Side.LONG,
        entry=entry,
        qty=qty,
        remaining_qty=qty,
        r_per_unit=entry - sl_initial,
        sl=sl_initial,
        sl_initial=sl_initial,
        peak_pnl_usdt=0.0
    )
    
    print(f"📊 PNUT позиция:")
    print(f"   Entry: ${entry:.6f}")
    print(f"   Qty: {qty:.6f}")
    print(f"   Initial SL: ${sl_initial:.6f}")
    print()
    
    # Тестируем точно на пороге активации
    activation_pnl = 0.10
    activation_price = entry + (activation_pnl / qty)
    
    print(f"🎯 Тест активации трейлинга:")
    print(f"   PnL: ${activation_pnl:.3f} USDT")
    print(f"   Цена: ${activation_price:.6f}")
    
    updated_pos = update_trailing_pnl_based(pos, activation_price, activation_pnl, cfg)
    debug = getattr(updated_pos, 'trailing_debug', {})
    
    print(f"\n📋 Результат трейлинга:")
    print(f"   Peak PnL: ${updated_pos.peak_pnl_usdt:.3f} USDT")
    print(f"   Уровень: {debug.get('level', 'N/A')}")
    print(f"   Keep %: {debug.get('keep_pct', 0)*100:.1f}%")
    print(f"   Target profit: ${debug.get('target_profit', 0):.3f} USDT")
    print(f"   Old SL: ${debug.get('old_sl', 0):.6f}")
    print(f"   New SL: ${debug.get('new_sl', 0):.6f}")
    print(f"   SL updated: {debug.get('sl_updated', False)}")
    
    if 'reason' in debug:
        print(f"   Reason: {debug['reason']}")
    
    if updated_pos.sl > pos.sl:
        protected_profit = (updated_pos.sl - entry) * qty
        print(f"\n✅ SL улучшился!")
        print(f"   Защищенная прибыль: ${protected_profit:.3f} USDT")
        
        if protected_profit >= 0.05:
            print(f"   ✅ Минимальная прибыль OK")
        else:
            print(f"   ❌ Прибыль слишком мала!")
    else:
        print(f"\n❌ SL не обновился!")
        
        # Детальная диагностика
        target_profit = activation_pnl * cfg.level_1_keep_pct
        expected_sl = entry + (target_profit / qty)
        
        print(f"\n🔍 Диагностика:")
        print(f"   Ожидаемый target_profit: ${target_profit:.3f}")
        print(f"   Ожидаемый SL: ${expected_sl:.6f}")
        print(f"   Текущий SL: ${pos.sl:.6f}")
        print(f"   Разница: ${expected_sl - pos.sl:.6f}")
        
        if expected_sl <= pos.sl:
            print(f"   ❌ ПРОБЛЕМА: Ожидаемый SL не лучше текущего!")
            print(f"   💡 Возможно, initial SL уже слишком хорош?")

def test_step_by_step_trailing():
    """
    Пошаговый тест трейлинга
    """
    print("\n📈 ПОШАГОВЫЙ ТЕСТ ТРЕЙЛИНГА")
    print("=" * 70)
    
    cfg = TrailingConfig(
        activate_pnl_usdt=0.10,
        level_1_pnl=0.10, level_1_keep_pct=0.50,
        level_2_pnl=0.20, level_2_keep_pct=0.60,
        level_3_pnl=0.30, level_3_keep_pct=0.70,
        level_4_pnl=0.40, level_4_keep_pct=0.80
    )
    
    # Простой пример для понимания
    entry = 1.0
    qty = 100.0
    sl_initial = 0.95  # 5% SL
    
    pos = Position(
        side=Side.LONG,
        entry=entry,
        qty=qty,
        remaining_qty=qty,
        r_per_unit=entry - sl_initial,
        sl=sl_initial,
        sl_initial=sl_initial,
        peak_pnl_usdt=0.0
    )
    
    print(f"📊 Простой пример:")
    print(f"   Entry: ${entry:.2f}")
    print(f"   Qty: {qty:.0f}")
    print(f"   Initial SL: ${sl_initial:.2f}")
    
    # Шаги роста PnL
    test_steps = [
        (0.05, "Ниже порога"),
        (0.10, "Порог активации L1"),
        (0.15, "Выше L1"),
        (0.20, "Порог L2"),
        (0.25, "Выше L2"),
        (0.30, "Порог L3"),
        (0.40, "Порог L4")
    ]
    
    for pnl_usdt, description in test_steps:
        price = entry + (pnl_usdt / qty)
        
        print(f"\n🔄 {description}: PnL ${pnl_usdt:.2f}")
        print(f"   Цена: ${price:.3f}")
        
        old_sl = pos.sl
        updated_pos = update_trailing_pnl_based(pos, price, pnl_usdt, cfg)
        debug = getattr(updated_pos, 'trailing_debug', {})
        
        if updated_pos.sl > old_sl:
            protected_profit = (updated_pos.sl - entry) * qty
            print(f"   ✅ SL: ${old_sl:.3f} → ${updated_pos.sl:.3f}")
            print(f"   ✅ Защищено: ${protected_profit:.2f} USDT ({debug.get('level', 'N/A')})")
            pos = updated_pos  # Обновляем для следующего шага
        else:
            print(f"   ➖ SL остался: ${pos.sl:.3f}")
            
        pos.peak_pnl_usdt = max(pos.peak_pnl_usdt, pnl_usdt)

def main():
    print("🧪 ДЕТАЛЬНЫЙ ТЕСТ ТРЕЙЛИНГА")
    print("=" * 70)
    
    test_pnut_exact_scenario()
    test_step_by_step_trailing()
    
    print("\n💡 ВЫВОДЫ:")
    print("=" * 70)
    print("Если SL не обновляется в простых примерах,")
    print("проблема в базовой логике трейлинга!")

if __name__ == '__main__':
    main()
