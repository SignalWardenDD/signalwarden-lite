#!/usr/bin/env python3
"""
Комплексные тесты трейлинга SignalWarden v1.6-TXB
Проверяем все критические аспекты:
1. Улучшение трейлинга при росте PnL на уровне 0
2. Трейлинг никогда не сбрасывается локально  
3. Отсутствие проблем с синхронизацией
4. Полные тесты для лонгов и шортов
"""

import sys
sys.path.append('.')

from signalwarden_lite.core.trailing import TrailingConfig, update_trailing_pnl_based
from signalwarden_lite.core.types import Position, Side
import copy

def test_pnl_improvement_at_zero_level():
    """
    КРИТИЧЕСКИЙ ТЕСТ: При росте PnL на уровне 0 трейлинг должен улучшаться
    """
    print("🎯 ТЕСТ: УЛУЧШЕНИЕ ТРЕЙЛИНГА ПРИ РОСТЕ PNL НА УРОВНЕ 0")
    print("=" * 70)
    
    cfg = TrailingConfig(
        activate_pnl_usdt=0.10,
        level_1_pnl=0.10, level_1_keep_pct=0.50,  # 50%
        level_2_pnl=0.20, level_2_keep_pct=0.60,  # 60%
        level_3_pnl=0.30, level_3_keep_pct=0.70,  # 70%
        level_4_pnl=0.40, level_4_keep_pct=0.80   # 80%
    )
    
    # Позиция в убытке, но приближается к уровню 0
    pos = Position(
        side=Side.LONG,
        entry=1.0000,
        qty=20.0,
        remaining_qty=20.0,
        r_per_unit=0.0500,
        sl=0.9500,
        sl_initial=0.9500,
        peak_pnl_usdt=0.0
    )
    
    # Шаг 1: PnL = -$0.20 (убыток)
    current_price = 0.9900
    current_pnl = (current_price - pos.entry) * pos.qty  # -$2.00
    print(f"Шаг 1: Цена ${current_price:.4f}, PnL = ${current_pnl:.2f}")
    updated_pos = update_trailing_pnl_based(pos, current_price, current_pnl, cfg)
    print(f"   Трейлинг активен: {current_pnl >= cfg.activate_pnl_usdt} (PnL < порога)")
    print(f"   SL: ${updated_pos.sl:.4f} (не изменился)")
    print()
    
    # Шаг 2: PnL = $0.00 (безубыток)
    current_price = 1.0000
    current_pnl = (current_price - pos.entry) * pos.qty  # $0.00
    print(f"Шаг 2: Цена ${current_price:.4f}, PnL = ${current_pnl:.2f}")
    updated_pos = update_trailing_pnl_based(updated_pos, current_price, current_pnl, cfg)
    print(f"   Трейлинг активен: {current_pnl >= cfg.activate_pnl_usdt} (PnL = 0, но < порога)")
    print(f"   SL: ${updated_pos.sl:.4f} (не изменился)")
    print()
    
    # Шаг 3: PnL = +$0.10 (активация трейлинга)
    current_price = 1.0050
    current_pnl = (current_price - pos.entry) * pos.qty  # +$1.00
    print(f"Шаг 3: Цена ${current_price:.4f}, PnL = ${current_pnl:.2f}")
    updated_pos = update_trailing_pnl_based(updated_pos, current_price, current_pnl, cfg)
    debug = getattr(updated_pos, 'trailing_debug', {})
    print(f"   Трейлинг активен: {current_pnl >= cfg.activate_pnl_usdt} ✅")
    print(f"   Уровень: {debug.get('level', 'N/A')}")
    print(f"   Peak PnL: ${debug.get('peak_pnl', 0):.2f}")
    print(f"   Target Profit: ${debug.get('target_profit', 0):.2f}")
    print(f"   SL обновлен: {debug.get('sl_updated', False)} ✅")
    print(f"   Новый SL: ${updated_pos.sl:.4f}")
    print()
    
    # Шаг 4: Рост PnL до +$0.15 (улучшение трейлинга)
    current_price = 1.0075
    current_pnl = (current_price - pos.entry) * pos.qty  # +$1.50
    old_sl = updated_pos.sl
    print(f"Шаг 4: Цена ${current_price:.4f}, PnL = ${current_pnl:.2f}")
    updated_pos = update_trailing_pnl_based(updated_pos, current_price, current_pnl, cfg)
    debug = getattr(updated_pos, 'trailing_debug', {})
    print(f"   Старый SL: ${old_sl:.4f}")
    print(f"   Peak PnL: ${debug.get('peak_pnl', 0):.2f} (увеличился)")
    print(f"   Target Profit: ${debug.get('target_profit', 0):.2f}")
    print(f"   SL обновлен: {debug.get('sl_updated', False)}")
    print(f"   Новый SL: ${updated_pos.sl:.4f}")
    
    sl_improved = updated_pos.sl > old_sl
    print(f"   ✅ SL УЛУЧШИЛСЯ: {sl_improved}")
    assert sl_improved, "SL должен улучшиться при росте PnL!"
    print()

def test_no_local_reset():
    """
    КРИТИЧЕСКИЙ ТЕСТ: Трейлинг никогда не сбрасывается локально
    """
    print("🔒 ТЕСТ: ТРЕЙЛИНГ НИКОГДА НЕ СБРАСЫВАЕТСЯ ЛОКАЛЬНО")
    print("=" * 70)
    
    cfg = TrailingConfig(
        activate_pnl_usdt=0.10,
        level_1_pnl=0.10, level_1_keep_pct=0.50,
        level_2_pnl=0.20, level_2_keep_pct=0.60,
        level_3_pnl=0.30, level_3_keep_pct=0.70,
        level_4_pnl=0.40, level_4_keep_pct=0.80
    )
    
    pos = Position(
        side=Side.LONG,
        entry=1.0000,
        qty=20.0,
        remaining_qty=20.0,
        r_per_unit=0.0500,
        sl=0.9500,
        sl_initial=0.9500,
        peak_pnl_usdt=0.0
    )
    
    # Устанавливаем высокий пик
    current_price = 1.0300
    current_pnl = (current_price - pos.entry) * pos.qty  # +$6.00
    print(f"Установка пика: Цена ${current_price:.4f}, PnL = ${current_pnl:.2f}")
    updated_pos = update_trailing_pnl_based(pos, current_price, current_pnl, cfg)
    debug = getattr(updated_pos, 'trailing_debug', {})
    peak_pnl = debug.get('peak_pnl', 0)
    peak_sl = updated_pos.sl
    print(f"   Peak PnL: ${peak_pnl:.2f}")
    print(f"   Peak SL: ${peak_sl:.4f}")
    print()
    
    # Серия падений цены - SL НЕ ДОЛЖЕН ухудшаться
    test_prices = [1.0250, 1.0200, 1.0150, 1.0100, 1.0050]
    
    for i, price in enumerate(test_prices, 1):
        current_pnl = (price - pos.entry) * pos.qty
        old_sl = updated_pos.sl
        old_peak = updated_pos.peak_pnl_usdt
        
        print(f"Тест {i}: Цена падает до ${price:.4f}, PnL = ${current_pnl:.2f}")
        updated_pos = update_trailing_pnl_based(updated_pos, price, current_pnl, cfg)
        debug = getattr(updated_pos, 'trailing_debug', {})
        
        # КРИТИЧЕСКИЕ ПРОВЕРКИ
        peak_unchanged = updated_pos.peak_pnl_usdt == old_peak
        sl_not_worse = updated_pos.sl >= old_sl
        
        print(f"   Peak PnL: ${updated_pos.peak_pnl_usdt:.2f} (не изменился: {peak_unchanged})")
        print(f"   SL: ${updated_pos.sl:.4f} (не ухудшился: {sl_not_worse})")
        print(f"   SL обновлен: {debug.get('sl_updated', False)}")
        
        assert peak_unchanged, f"Peak PnL НЕ должен сбрасываться! Был {old_peak}, стал {updated_pos.peak_pnl_usdt}"
        assert sl_not_worse, f"SL НЕ должен ухудшаться! Был {old_sl}, стал {updated_pos.sl}"
        print()
    
    print("✅ ТРЕЙЛИНГ НЕ СБРАСЫВАЕТСЯ - ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ")
    print()

def test_synchronization_consistency():
    """
    ТЕСТ: Проверка отсутствия проблем с синхронизацией
    """
    print("🔄 ТЕСТ: ОТСУТСТВИЕ ПРОБЛЕМ С СИНХРОНИЗАЦИЕЙ")
    print("=" * 70)
    
    cfg = TrailingConfig(
        activate_pnl_usdt=0.10,
        level_1_pnl=0.10, level_1_keep_pct=0.50,
        level_2_pnl=0.20, level_2_keep_pct=0.60,
        level_3_pnl=0.30, level_3_keep_pct=0.70,
        level_4_pnl=0.40, level_4_keep_pct=0.80
    )
    
    # Создаем две идентичные позиции
    pos1 = Position(
        side=Side.LONG,
        entry=1.0000,
        qty=20.0,
        remaining_qty=20.0,
        r_per_unit=0.0500,
        sl=0.9500,
        sl_initial=0.9500,
        peak_pnl_usdt=0.0
    )
    
    pos2 = copy.deepcopy(pos1)
    
    # Применяем одинаковые обновления в разном порядке
    prices_sequence_1 = [1.0100, 1.0200, 1.0150, 1.0250, 1.0180]
    prices_sequence_2 = [1.0100, 1.0150, 1.0200, 1.0180, 1.0250]
    
    print("Последовательность 1:", [f"${p:.4f}" for p in prices_sequence_1])
    for price in prices_sequence_1:
        current_pnl = (price - pos1.entry) * pos1.qty
        pos1 = update_trailing_pnl_based(pos1, price, current_pnl, cfg)
    
    print("Последовательность 2:", [f"${p:.4f}" for p in prices_sequence_2])
    for price in prices_sequence_2:
        current_pnl = (price - pos2.entry) * pos2.qty
        pos2 = update_trailing_pnl_based(pos2, price, current_pnl, cfg)
    
    # Финальное состояние должно быть одинаковым (максимальный PnL одинаковый)
    final_price = 1.0200
    final_pnl = (final_price - pos1.entry) * pos1.qty
    
    pos1 = update_trailing_pnl_based(pos1, final_price, final_pnl, cfg)
    pos2 = update_trailing_pnl_based(pos2, final_price, final_pnl, cfg)
    
    print(f"\nФинальное состояние при цене ${final_price:.4f}:")
    print(f"Позиция 1: Peak PnL = ${pos1.peak_pnl_usdt:.2f}, SL = ${pos1.sl:.4f}")
    print(f"Позиция 2: Peak PnL = ${pos2.peak_pnl_usdt:.2f}, SL = ${pos2.sl:.4f}")
    
    peak_consistent = abs(pos1.peak_pnl_usdt - pos2.peak_pnl_usdt) < 0.001
    sl_consistent = abs(pos1.sl - pos2.sl) < 0.0001
    
    print(f"Peak PnL консистентен: {peak_consistent} ✅")
    print(f"SL консистентен: {sl_consistent} ✅")
    
    assert peak_consistent, f"Peak PnL должен быть одинаковым! {pos1.peak_pnl_usdt} vs {pos2.peak_pnl_usdt}"
    assert sl_consistent, f"SL должен быть одинаковым! {pos1.sl} vs {pos2.sl}"
    print()

def test_comprehensive_long_short():
    """
    ПОЛНЫЕ ТЕСТЫ для лонгов и шортов
    """
    print("📊 ПОЛНЫЕ ТЕСТЫ ДЛЯ ЛОНГОВ И ШОРТОВ")
    print("=" * 70)
    
    cfg = TrailingConfig(
        activate_pnl_usdt=0.10,
        level_1_pnl=0.10, level_1_keep_pct=0.50,
        level_2_pnl=0.20, level_2_keep_pct=0.60,
        level_3_pnl=0.30, level_3_keep_pct=0.70,
        level_4_pnl=0.40, level_4_keep_pct=0.80
    )
    
    # ТЕСТ ЛОНГОВ
    print("🟢 ТЕСТ ЛОНГОВ")
    print("-" * 40)
    
    long_pos = Position(
        side=Side.LONG,
        entry=1.0000,
        qty=20.0,
        remaining_qty=20.0,
        r_per_unit=0.0500,
        sl=0.9500,
        sl_initial=0.9500,
        peak_pnl_usdt=0.0
    )
    
    # Проходим через все уровни
    long_test_scenarios = [
        (1.0050, "Активация трейлинга"),
        (1.0100, "Уровень L1"),
        (1.0150, "Переход к L2"), 
        (1.0200, "Уровень L2"),
        (1.0250, "Переход к L3"),
        (1.0300, "Уровень L3"),
        (1.0350, "Переход к L4"),
        (1.0400, "Уровень L4"),
        (1.0350, "Падение цены - трейлинг держится"),
    ]
    
    for price, description in long_test_scenarios:
        current_pnl = (price - long_pos.entry) * long_pos.qty
        old_sl = long_pos.sl
        long_pos = update_trailing_pnl_based(long_pos, price, current_pnl, cfg)
        debug = getattr(long_pos, 'trailing_debug', {})
        
        print(f"${price:.4f} - {description}")
        print(f"   PnL: ${current_pnl:.2f}, Уровень: {debug.get('level', 'N/A')}")
        print(f"   SL: ${old_sl:.4f} → ${long_pos.sl:.4f} ({'улучшен' if long_pos.sl > old_sl else 'не изменен'})")
        
        # Проверяем что SL никогда не ухудшается
        assert long_pos.sl >= old_sl, f"SL ухудшился для лонга! {old_sl} → {long_pos.sl}"
        print()
    
    # ТЕСТ ШОРТОВ
    print("🔴 ТЕСТ ШОРТОВ")
    print("-" * 40)
    
    short_pos = Position(
        side=Side.SHORT,
        entry=1.0000,
        qty=-20.0,
        remaining_qty=-20.0,
        r_per_unit=0.0500,
        sl=1.0500,
        sl_initial=1.0500,
        peak_pnl_usdt=0.0
    )
    
    # Проходим через все уровни (цена падает для прибыли шорта)
    short_test_scenarios = [
        (0.9950, "Активация трейлинга"),
        (0.9900, "Уровень L1"),
        (0.9850, "Переход к L2"),
        (0.9800, "Уровень L2"),
        (0.9750, "Переход к L3"),
        (0.9700, "Уровень L3"),
        (0.9650, "Переход к L4"),
        (0.9600, "Уровень L4"),
        (0.9650, "Рост цены - трейлинг держится"),
    ]
    
    for price, description in short_test_scenarios:
        current_pnl = (short_pos.entry - price) * abs(short_pos.qty)  # Для шорта
        old_sl = short_pos.sl
        short_pos = update_trailing_pnl_based(short_pos, price, current_pnl, cfg)
        debug = getattr(short_pos, 'trailing_debug', {})
        
        print(f"${price:.4f} - {description}")
        print(f"   PnL: ${current_pnl:.2f}, Уровень: {debug.get('level', 'N/A')}")
        print(f"   SL: ${old_sl:.4f} → ${short_pos.sl:.4f} ({'улучшен' if short_pos.sl < old_sl else 'не изменен'})")
        
        # Проверяем что SL никогда не ухудшается для шорта
        assert short_pos.sl <= old_sl, f"SL ухудшился для шорта! {old_sl} → {short_pos.sl}"
        print()
    
    print("✅ ВСЕ ТЕСТЫ ЛОНГОВ И ШОРТОВ ПРОЙДЕНЫ")
    print()

def test_edge_cases_advanced():
    """
    РАСШИРЕННЫЕ тесты граничных случаев
    """
    print("⚠️  РАСШИРЕННЫЕ ТЕСТЫ ГРАНИЧНЫХ СЛУЧАЕВ")
    print("=" * 70)
    
    cfg = TrailingConfig(
        activate_pnl_usdt=0.10,
        level_1_pnl=0.10, level_1_keep_pct=0.50,
        level_2_pnl=0.20, level_2_keep_pct=0.60,
        level_3_pnl=0.30, level_3_keep_pct=0.70,
        level_4_pnl=0.40, level_4_keep_pct=0.80
    )
    
    # Тест 1: Очень маленькие количества
    print("Тест 1: Очень маленькие количества")
    pos = Position(
        side=Side.LONG,
        entry=1.0000,
        qty=0.001,  # Очень маленькое количество
        remaining_qty=0.001,
        r_per_unit=0.0500,
        sl=0.9500,
        sl_initial=0.9500,
        peak_pnl_usdt=0.0
    )
    
    current_pnl = 0.15  # Достаточно для активации
    updated_pos = update_trailing_pnl_based(pos, 1.1500, current_pnl, cfg)
    debug = getattr(updated_pos, 'trailing_debug', {})
    print(f"   Qty: {pos.qty}, PnL: ${current_pnl:.3f}")
    print(f"   Трейлинг активен: {debug.get('level', 'N/A') != 'N/A'}")
    print(f"   SL обновлен: {debug.get('sl_updated', False)}")
    print()
    
    # Тест 2: Нулевой PnL на границе активации
    print("Тест 2: Точно на границе активации")
    pos = Position(
        side=Side.LONG,
        entry=1.0000,
        qty=20.0,
        remaining_qty=20.0,
        r_per_unit=0.0500,
        sl=0.9500,
        sl_initial=0.9500,
        peak_pnl_usdt=0.0
    )
    
    current_pnl = cfg.activate_pnl_usdt  # Точно на границе
    updated_pos = update_trailing_pnl_based(pos, 1.0050, current_pnl, cfg)
    debug = getattr(updated_pos, 'trailing_debug', {})
    print(f"   PnL: ${current_pnl:.3f} (точно на границе ${cfg.activate_pnl_usdt:.2f})")
    print(f"   Трейлинг активен: {current_pnl >= cfg.activate_pnl_usdt}")
    print(f"   SL обновлен: {debug.get('sl_updated', False)}")
    print()
    
    # Тест 3: Переходы между уровнями
    print("Тест 3: Переходы между уровнями")
    boundary_tests = [
        (cfg.level_1_pnl, "L1"),
        (cfg.level_2_pnl, "L2"), 
        (cfg.level_3_pnl, "L3"),
        (cfg.level_4_pnl, "L4")
    ]
    
    for boundary_pnl, expected_level in boundary_tests:
        pos.peak_pnl_usdt = 0.0  # Сброс для чистого теста
        updated_pos = update_trailing_pnl_based(pos, 1.0000, boundary_pnl, cfg)
        debug = getattr(updated_pos, 'trailing_debug', {})
        actual_level = debug.get('level', 'N/A')
        
        print(f"   PnL: ${boundary_pnl:.2f} → Уровень: {actual_level} (ожидался {expected_level})")
        assert actual_level == expected_level, f"Неправильный уровень! Ожидался {expected_level}, получен {actual_level}"
    
    print("✅ ВСЕ ГРАНИЧНЫЕ СЛУЧАИ ПРОЙДЕНЫ")
    print()

if __name__ == '__main__':
    print("🚀 КОМПЛЕКСНОЕ ТЕСТИРОВАНИЕ ТРЕЙЛИНГА SignalWarden v1.6-TXB")
    print("=" * 80)
    print()
    
    try:
        test_pnl_improvement_at_zero_level()
        test_no_local_reset()
        test_synchronization_consistency()
        test_comprehensive_long_short()
        test_edge_cases_advanced()
        
        print("🎉 ВСЕ КОМПЛЕКСНЫЕ ТЕСТЫ УСПЕШНО ПРОЙДЕНЫ!")
        print("✅ Трейлинг работает корректно по всем критериям")
        
    except AssertionError as e:
        print(f"❌ ОШИБКА В ТЕСТЕ: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"💥 НЕОЖИДАННАЯ ОШИБКА: {e}")
        sys.exit(1)
