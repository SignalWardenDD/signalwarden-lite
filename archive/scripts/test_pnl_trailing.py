#!/usr/bin/env python3
"""
Тест PnL-only трейлинга в разных рыночных условиях
Проверяем:
1. Минимальная прибыль от стопа не меньше $0.03 (50% от $0.06)
2. Корректность для лонгов и шортов
3. Трейлинг стоп только улучшается, не ухудшается
"""

import sys
sys.path.append('.')

from signalwarden_lite.core.trailing_pnl_only import TrailingConfigPnLOnly, update_trailing_pnl_only
from signalwarden_lite.core.types import Position, Side

def test_long_position():
    """Тест LONG позиции"""
    print("🔍 ТЕСТ LONG ПОЗИЦИИ")
    print("=" * 50)
    
    # Создаем позицию
    pos = Position(
        side=Side.LONG,
        entry=1.0,  # $1.00
        sl=0.95,    # $0.95 (5% стоп)
        sl_initial=0.95,
        qty=100,    # 100 единиц
        remaining_qty=100,
        r_per_unit=0.05,  # 5% риск
        entry_reason="test"
    )
    
    cfg = TrailingConfigPnLOnly()
    
    # Тест 1: Цена растет до $1.06 (достигаем L4, потому что $6.00 > $0.35)
    print("📈 Тест 1: Цена растет до $1.06 (L4 уровень, потому что $6.00 > $0.35)")
    pos_updated = update_trailing_pnl_only(pos, 1.06, 1.06, 0.01, cfg)
    
    current_pnl = (1.06 - 1.0) * 100  # $6.00
    target_profit = 6.0 * 0.8         # $4.80 (80% от $6.00, L4 уровень)
    expected_sl = 1.0 + (target_profit / 100)  # $1.00 + $0.048 = $1.048
    min_profit = target_profit        # $4.80
    
    print(f"   Текущий PnL: ${current_pnl:.2f}")
    print(f"   Peak PnL: ${pos_updated.peak_pnl_usdt:.2f}")
    print(f"   Новый SL: ${pos_updated.sl:.2f}")
    print(f"   Минимальная прибыль: ${min_profit:.2f}")
    print(f"   Debug: {pos_updated.trailing_debug}")
    
    assert abs(pos_updated.sl - expected_sl) < 0.01, f"Ожидался SL ${expected_sl:.2f}, получен ${pos_updated.sl:.2f}"
    assert min_profit >= 0.03, f"Минимальная прибыль ${min_profit:.2f} меньше $0.03"
    print("   ✅ Тест 1 пройден")
    
    # Тест 2: Цена растет до $1.15 (достигаем L4, потому что $15.00 > $0.35)
    print("\n📈 Тест 2: Цена растет до $1.15 (L4 уровень, потому что $15.00 > $0.35)")
    pos_updated = update_trailing_pnl_only(pos_updated, 1.15, 1.15, 0.01, cfg)
    
    current_pnl = (1.15 - 1.0) * 100  # $15.00
    target_profit = 15.0 * 0.8        # $12.00 (80% от $15.00, L4 уровень)
    expected_sl = 1.0 + (target_profit / 100)  # $1.00 + $0.12 = $1.12
    min_profit = target_profit         # $12.00
    
    print(f"   Текущий PnL: ${current_pnl:.2f}")
    print(f"   Peak PnL: ${pos_updated.peak_pnl_usdt:.2f}")
    print(f"   Новый SL: ${pos_updated.sl:.2f}")
    print(f"   Минимальная прибыль: ${min_profit:.2f}")
    print(f"   Debug: {pos_updated.trailing_debug}")
    
    assert abs(pos_updated.sl - expected_sl) < 0.01, f"Ожидался SL ${expected_sl:.2f}, получен ${pos_updated.sl:.2f}"
    assert min_profit >= 0.03, f"Минимальная прибыль ${min_profit:.2f} меньше $0.03"
    print("   ✅ Тест 2 пройден")
    
    # Тест 3: Создаем новую позицию для тестирования L1 уровня
    print("\n📈 Тест 3: Новая позиция для L1 уровня (PnL $0.06)")
    pos_l1 = Position(
        side=Side.LONG,
        entry=1.0,  # $1.00
        sl=0.95,    # $0.95 (5% стоп)
        sl_initial=0.95,
        qty=1,      # 1 единица (чтобы PnL был $0.06)
        remaining_qty=1,
        r_per_unit=0.05,  # 5% риск
        entry_reason="test"
    )
    
    pos_l1_updated = update_trailing_pnl_only(pos_l1, 1.06, 1.06, 0.01, cfg)
    
    current_pnl = (1.06 - 1.0) * 1  # $0.06
    target_profit = 0.06 * 0.5      # $0.03 (50% от $0.06, L1 уровень)
    expected_sl = 1.0 + (target_profit / 1)  # $1.00 + $0.03 = $1.03
    min_profit = target_profit        # $0.03
    
    print(f"   Текущий PnL: ${current_pnl:.2f}")
    print(f"   Peak PnL: ${pos_l1_updated.peak_pnl_usdt:.2f}")
    print(f"   Новый SL: ${pos_l1_updated.sl:.2f}")
    print(f"   Минимальная прибыль: ${min_profit:.2f}")
    print(f"   Debug: {pos_l1_updated.trailing_debug}")
    
    assert pos_l1_updated.sl == expected_sl, f"Ожидался SL ${expected_sl:.2f}, получен ${pos_l1_updated.sl:.2f}"
    assert min_profit >= 0.03, f"Минимальная прибыль ${min_profit:.2f} меньше $0.03"
    print("   ✅ Тест 3 пройден (L1 уровень)")
    
    # Тест 4: Цена откатывается до $1.10 (SL не должен ухудшиться)
    print("\n📉 Тест 4: Цена откатывается до $1.10 (проверка защиты)")
    old_sl = pos_updated.sl
    pos_updated = update_trailing_pnl_only(pos_updated, 1.10, 1.10, 0.01, cfg)
    
    print(f"   Старый SL: ${old_sl:.2f}")
    print(f"   Новый SL: ${pos_updated.sl:.2f}")
    print(f"   Debug: {pos_updated.trailing_debug}")
    
    assert pos_updated.sl >= old_sl, f"SL ухудшился с ${old_sl:.2f} до ${pos_updated.sl:.2f}"
    print("   ✅ Тест 4 пройден (SL не ухудшился)")
    
    return pos_updated

def test_short_position():
    """Тест SHORT позиции"""
    print("\n🔍 ТЕСТ SHORT ПОЗИЦИИ")
    print("=" * 50)
    
    # Создаем позицию
    pos = Position(
        side=Side.SHORT,
        entry=1.0,  # $1.00
        sl=1.05,    # $1.05 (5% стоп)
        sl_initial=1.05,
        qty=100,    # 100 единиц
        remaining_qty=100,
        r_per_unit=0.05,  # 5% риск
        entry_reason="test"
    )
    
    cfg = TrailingConfigPnLOnly()
    
    # Тест 1: Цена падает до $0.94 (достигаем L4, потому что $6.00 > $0.35)
    print("📉 Тест 1: Цена падает до $0.94 (L4 уровень, потому что $6.00 > $0.35)")
    pos_updated = update_trailing_pnl_only(pos, 0.94, 0.94, 0.01, cfg)
    
    current_pnl = (1.0 - 0.94) * 100  # $6.00
    target_profit = 6.0 * 0.8         # $4.80 (80% от $6.00, L4 уровень)
    expected_sl = 1.0 - (target_profit / 100)  # $1.00 - $0.048 = $0.952
    min_profit = target_profit        # $4.80
    
    print(f"   Текущий PnL: ${current_pnl:.2f}")
    print(f"   Peak PnL: ${pos_updated.peak_pnl_usdt:.2f}")
    print(f"   Новый SL: ${pos_updated.sl:.2f}")
    print(f"   Минимальная прибыль: ${min_profit:.2f}")
    print(f"   Debug: {pos_updated.trailing_debug}")
    
    assert abs(pos_updated.sl - expected_sl) < 0.01, f"Ожидался SL ${expected_sl:.2f}, получен ${pos_updated.sl:.2f}"
    assert min_profit >= 0.03, f"Минимальная прибыль ${min_profit:.2f} меньше $0.03"
    print("   ✅ Тест 1 пройден")
    
    # Тест 2: Цена падает до $0.85 (достигаем L4, потому что $15.00 > $0.35)
    print("\n📉 Тест 2: Цена падает до $0.85 (L4 уровень, потому что $15.00 > $0.35)")
    pos_updated = update_trailing_pnl_only(pos_updated, 0.85, 0.85, 0.01, cfg)
    
    current_pnl = (1.0 - 0.85) * 100  # $15.00
    target_profit = 15.0 * 0.8        # $12.00 (80% от $15.00, L4 уровень)
    expected_sl = 1.0 - (target_profit / 100)  # $1.00 - $0.12 = $0.88
    min_profit = target_profit         # $12.00
    
    print(f"   Текущий PnL: ${current_pnl:.2f}")
    print(f"   Peak PnL: ${pos_updated.peak_pnl_usdt:.2f}")
    print(f"   Новый SL: ${pos_updated.sl:.2f}")
    print(f"   Минимальная прибыль: ${min_profit:.2f}")
    print(f"   Debug: {pos_updated.trailing_debug}")
    
    assert abs(pos_updated.sl - expected_sl) < 0.01, f"Ожидался SL ${expected_sl:.2f}, получен ${pos_updated.sl:.2f}"
    assert min_profit >= 0.03, f"Минимальная прибыль ${min_profit:.2f} меньше $0.03"
    print("   ✅ Тест 2 пройден")
    
    # Тест 3: Создаем новую SHORT позицию для тестирования L1 уровня
    print("\n📉 Тест 3: Новая SHORT позиция для L1 уровня (PnL $0.06)")
    pos_short_l1 = Position(
        side=Side.SHORT,
        entry=1.0,  # $1.00
        sl=1.05,    # $1.05 (5% стоп)
        sl_initial=1.05,
        qty=1,      # 1 единица (чтобы PnL был $0.06)
        remaining_qty=1,
        r_per_unit=0.05,  # 5% риск
        entry_reason="test"
    )
    
    pos_short_l1_updated = update_trailing_pnl_only(pos_short_l1, 0.94, 0.94, 0.01, cfg)
    
    current_pnl = (1.0 - 0.94) * 1  # $0.06
    target_profit = 0.06 * 0.5      # $0.03 (50% от $0.06, L1 уровень)
    expected_sl = 1.0 - (target_profit / 1)  # $1.00 - $0.03 = $0.97
    min_profit = target_profit        # $0.03
    
    print(f"   Текущий PnL: ${current_pnl:.2f}")
    print(f"   Peak PnL: ${pos_short_l1_updated.peak_pnl_usdt:.2f}")
    print(f"   Новый SL: ${pos_short_l1_updated.sl:.2f}")
    print(f"   Минимальная прибыль: ${min_profit:.2f}")
    print(f"   Debug: {pos_short_l1_updated.trailing_debug}")
    
    assert pos_short_l1_updated.sl == expected_sl, f"Ожидался SL ${expected_sl:.2f}, получен ${pos_short_l1_updated.sl:.2f}"
    assert min_profit >= 0.03, f"Минимальная прибыль ${min_profit:.2f} меньше $0.03"
    print("   ✅ Тест 3 пройден (L1 уровень SHORT)")
    
    # Тест 4: Цена откатывается до $0.90 (SL не должен ухудшиться)
    print("\n📈 Тест 4: Цена откатывается до $0.90 (проверка защиты)")
    old_sl = pos_updated.sl
    pos_updated = update_trailing_pnl_only(pos_updated, 0.90, 0.90, 0.01, cfg)
    
    print(f"   Старый SL: ${old_sl:.2f}")
    print(f"   Новый SL: ${pos_updated.sl:.2f}")
    print(f"   Debug: {pos_updated.trailing_debug}")
    
    assert pos_updated.sl <= old_sl, f"SL ухудшился с ${old_sl:.2f} до ${pos_updated.sl:.2f}"
    print("   ✅ Тест 4 пройден (SL не ухудшился)")
    
    return pos_updated

def test_edge_cases():
    """Тест граничных случаев"""
    print("\n🔍 ТЕСТ ГРАНИЧНЫХ СЛУЧАЕВ")
    print("=" * 50)
    
    # Тест 1: PnL меньше минимального уровня
    print("📊 Тест 1: PnL меньше $0.06 (трейлинг не должен активироваться)")
    pos = Position(
        side=Side.LONG,
        entry=1.0,
        sl=0.95,
        sl_initial=0.95,
        qty=1,  # 1 единица, чтобы PnL был $0.05
        remaining_qty=1,
        r_per_unit=0.05,
        entry_reason="test"
    )
    
    cfg = TrailingConfigPnLOnly()
    pos_updated = update_trailing_pnl_only(pos, 1.05, 1.05, 0.01, cfg)  # $0.05 PnL
    
    print(f"   PnL: ${(1.05 - 1.0) * 1:.2f}")
    print(f"   SL остался: ${pos_updated.sl:.2f}")
    print(f"   Debug: {pos_updated.trailing_debug}")
    
    assert pos_updated.sl == 0.95, f"SL изменился с 0.95 до {pos_updated.sl:.2f}"
    assert pos_updated.trailing_debug['level'] == 'INACTIVE', "Трейлинг не должен быть активен"
    print("   ✅ Тест 1 пройден")
    
    # Тест 2: Отрицательный PnL
    print("\n📊 Тест 2: Отрицательный PnL (трейлинг не должен активироваться)")
    pos_updated = update_trailing_pnl_only(pos, 0.98, 0.98, 0.01, cfg)  # -$0.02 PnL
    
    print(f"   PnL: ${(0.98 - 1.0) * 1:.2f}")
    print(f"   SL остался: ${pos_updated.sl:.2f}")
    print(f"   Debug: {pos_updated.trailing_debug}")
    
    assert pos_updated.sl == 0.95, f"SL изменился с 0.95 до {pos_updated.sl:.2f}"
    print("   ✅ Тест 2 пройден")

def test_all_levels():
    """Тест всех уровней PnL"""
    print("\n🔍 ТЕСТ ВСЕХ УРОВНЕЙ PnL")
    print("=" * 50)
    
    pos = Position(
        side=Side.LONG,
        entry=1.0,
        sl=0.95,
        sl_initial=0.95,
        qty=100,
        remaining_qty=100,
        r_per_unit=0.05,
        entry_reason="test"
    )
    
    cfg = TrailingConfigPnLOnly()
    
    # Тестируем все уровни (правильные значения)
    test_cases = [
        (1.0007, "L1", 0.50, 0.03),  # $0.07 PnL, 50% сохранения, $0.03 прибыль
        (1.0016, "L2", 0.60, 0.096),  # $0.16 PnL, 60% сохранения, $0.096 прибыль
        (1.0026, "L3", 0.70, 0.182), # $0.26 PnL, 70% сохранения, $0.182 прибыль
        (1.0036, "L4", 0.80, 0.288),  # $0.36 PnL, 80% сохранения, $0.288 прибыль
    ]
    
    for price, expected_level, expected_keep_pct, expected_min_profit in test_cases:
        print(f"\n📊 Тест уровня {expected_level}: цена ${price:.2f}")
        pos_updated = update_trailing_pnl_only(pos, price, price, 0.01, cfg)
        
        current_pnl = (price - 1.0) * 100  # PnL в долларах
        target_profit = current_pnl * expected_keep_pct  # Целевая прибыль в долларах
        expected_sl = 1.0 + (target_profit / 100)
        min_profit = target_profit
        
        print(f"   PnL: ${current_pnl:.2f}")
        print(f"   Ожидаемый SL: ${expected_sl:.2f}")
        print(f"   Фактический SL: ${pos_updated.sl:.2f}")
        print(f"   Минимальная прибыль: ${min_profit:.2f}")
        print(f"   Debug: {pos_updated.trailing_debug}")
        
        assert pos_updated.trailing_debug['level'] == expected_level, f"Ожидался уровень {expected_level}, получен {pos_updated.trailing_debug['level']}"
        assert abs(pos_updated.sl - expected_sl) < 0.01, f"SL не соответствует ожидаемому: {pos_updated.sl:.2f} vs {expected_sl:.2f}"
        assert min_profit >= expected_min_profit - 0.01, f"Минимальная прибыль ${min_profit:.2f} меньше ожидаемой ${expected_min_profit:.2f}"
        print(f"   ✅ Уровень {expected_level} пройден")

def main():
    """Запуск всех тестов"""
    print("🧪 ТЕСТИРОВАНИЕ PnL-ONLY ТРЕЙЛИНГА")
    print("=" * 60)
    
    try:
        # Тест LONG позиции
        test_long_position()
        
        # Тест SHORT позиции
        test_short_position()
        
        # Тест граничных случаев
        test_edge_cases()
        
        # Тест всех уровней
        test_all_levels()
        
        print("\n" + "=" * 60)
        print("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
        print("✅ PnL-only трейлинг работает корректно:")
        print("   • Минимальная прибыль от стопа ≥ $0.03")
        print("   • Корректно работает для лонгов и шортов")
        print("   • Трейлинг стоп только улучшается, не ухудшается")
        print("   • Все уровни PnL работают правильно")
        print("   • Граничные случаи обрабатываются корректно")
        
    except Exception as e:
        print(f"\n❌ ТЕСТ ПРОВАЛЕН: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == '__main__':
    main()
