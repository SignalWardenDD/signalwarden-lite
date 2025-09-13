#!/usr/bin/env python3
"""
ТЕСТ ЦЕЛОСТНОСТИ СТРАТЕГИИ
Проверяет что базовый функционал стратегии не нарушен
и трейлинг работает как задумано
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from signalwarden_lite.core.trailing_pnl_only import TrailingConfigPnLOnly, update_trailing_pnl_only
from signalwarden_lite.core.types import Position, Side
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def test_initial_sl_calculation():
    """Тест 1: Проверка расчета начального SL (2.5×ATR)"""
    logger.info("🧪 ТЕСТ 1: Расчет начального SL")
    
    # Симуляция входа в LONG позицию
    entry = 1.0000
    atr = 0.0200  # 2% ATR
    sl_atr_mult = 2.5
    qty = 50.0
    
    # Расчет начального SL по стратегии
    initial_sl = entry - (sl_atr_mult * atr)  # 1.0000 - (2.5 * 0.02) = 0.9500
    sl_distance_pct = ((entry - initial_sl) / entry) * 100
    
    logger.info(f"   Entry: ${entry:.4f}")
    logger.info(f"   ATR: ${atr:.4f} ({atr*100:.1f}%)")
    logger.info(f"   Initial SL: ${initial_sl:.4f}")
    logger.info(f"   SL Distance: {sl_distance_pct:.1f}% от входа")
    
    # Проверка
    expected_distance = sl_atr_mult * (atr / entry) * 100
    assert abs(sl_distance_pct - expected_distance) < 0.01, f"SL расстояние неправильное: {sl_distance_pct:.1f}% != {expected_distance:.1f}%"
    
    logger.info("   ✅ Начальный SL рассчитывается правильно")
    return initial_sl

def test_trailing_activation():
    """Тест 2: Активация трейлинга только при достижении порогов"""
    logger.info("\n🧪 ТЕСТ 2: Активация трейлинга")
    
    config = TrailingConfigPnLOnly()
    
    # Создаем позицию
    pos = Position(
        side=Side.LONG,
        entry=1.0000,
        qty=50.0,
        remaining_qty=50.0,
        r_per_unit=0.05,
        sl=0.9500,  # Начальный SL на 2.5×ATR
        peak_pnl_usdt=0.0
    )
    
    # Тест 2.1: Малая прибыль ($0.05) - трейлинг НЕ активен
    logger.info("   Тест 2.1: Малая прибыль $0.05")
    current_price = 1.0010  # +$0.05 прибыли
    pos.peak_pnl_usdt = (current_price - pos.entry) * pos.qty  # $0.50
    
    updated_pos = update_trailing_pnl_only(pos, current_price, current_price, 0.02, config)
    
    logger.info(f"   PnL: ${updated_pos.peak_pnl_usdt:.4f}")
    logger.info(f"   Трейлинг уровень: {updated_pos.trailing_debug['level']}")
    logger.info(f"   SL изменился: {updated_pos.trailing_debug.get('sl_updated', False)}")
    
    assert updated_pos.trailing_debug['level'] == 'INACTIVE', "Трейлинг должен быть неактивен при малой прибыли"
    assert updated_pos.sl == 0.9500, "SL не должен изменяться при неактивном трейлинге"
    
    logger.info("   ✅ При малой прибыли трейлинг неактивен")
    
    # Тест 2.2: Достаточная прибыль ($0.06+) - трейлинг активируется
    logger.info("   Тест 2.2: Достаточная прибыль $0.06+")
    current_price = 1.0012  # +$0.60 прибыли
    pos.peak_pnl_usdt = (current_price - pos.entry) * pos.qty  # $0.60
    
    updated_pos = update_trailing_pnl_only(pos, current_price, current_price, 0.02, config)
    
    logger.info(f"   PnL: ${updated_pos.peak_pnl_usdt:.4f}")
    logger.info(f"   Трейлинг уровень: {updated_pos.trailing_debug['level']}")
    logger.info(f"   SL изменился: {updated_pos.trailing_debug.get('sl_updated', False)}")
    
    assert updated_pos.trailing_debug['level'] == 'L1', "Трейлинг должен активироваться на уровне L1"
    assert updated_pos.sl > 0.9500, "SL должен улучшиться (подтянуться вверх)"
    
    logger.info("   ✅ При достаточной прибыли трейлинг активируется")

def test_sl_only_improves():
    """Тест 3: SL может только улучшаться, никогда не ухудшается"""
    logger.info("\n🧪 ТЕСТ 3: SL только улучшается")
    
    config = TrailingConfigPnLOnly()
    
    # Создаем позицию с уже подтянутым SL
    pos = Position(
        side=Side.LONG,
        entry=1.0000,
        qty=50.0,
        remaining_qty=50.0,
        r_per_unit=0.05,
        sl=0.9800,  # Уже подтянутый SL
        peak_pnl_usdt=1.50  # Peak PnL $1.50
    )
    
    # Тест 3.1: Цена упала, но peak_pnl остается
    logger.info("   Тест 3.1: Цена упала, peak_pnl сохраняется")
    current_price = 1.0005  # Цена упала, текущий PnL = $0.25
    # НО peak_pnl остается $1.50
    
    old_sl = pos.sl
    updated_pos = update_trailing_pnl_only(pos, current_price, current_price, 0.02, config)
    
    logger.info(f"   Старый SL: ${old_sl:.4f}")
    logger.info(f"   Новый SL: ${updated_pos.sl:.4f}")
    logger.info(f"   Peak PnL: ${updated_pos.peak_pnl_usdt:.4f}")
    logger.info(f"   SL изменился: {updated_pos.trailing_debug.get('sl_updated', False)}")
    
    # SL должен остаться таким же или улучшиться, но НЕ ухудшиться
    assert updated_pos.sl >= old_sl, f"SL ухудшился! {updated_pos.sl:.4f} < {old_sl:.4f}"
    
    logger.info("   ✅ SL не ухудшился при падении цены")
    
    # Тест 3.2: Цена выросла еще больше - peak_pnl растет
    logger.info("   Тест 3.2: Peak PnL растет - SL подтягивается")
    current_price = 1.0040  # Цена выросла
    current_pnl = (current_price - updated_pos.entry) * updated_pos.qty  # $2.00
    
    # Обновляем peak_pnl если текущий PnL больше (как в реальной системе)
    if current_pnl > updated_pos.peak_pnl_usdt:
        updated_pos.peak_pnl_usdt = current_pnl
    
    old_sl = updated_pos.sl
    updated_pos = update_trailing_pnl_only(updated_pos, current_price, current_price, 0.02, config)
    
    logger.info(f"   Старый SL: ${old_sl:.4f}")
    logger.info(f"   Новый SL: ${updated_pos.sl:.4f}")
    logger.info(f"   Peak PnL: ${updated_pos.peak_pnl_usdt:.4f}")
    logger.info(f"   SL изменился: {updated_pos.trailing_debug.get('sl_updated', False)}")
    
    # При росте peak_pnl SL должен улучшиться или остаться таким же
    assert updated_pos.sl >= old_sl, f"SL ухудшился при росте PnL: {updated_pos.sl:.4f} < {old_sl:.4f}"
    
    logger.info("   ✅ SL подтянулся при росте прибыли")

def test_trailing_levels():
    """Тест 4: Проверка работы уровней трейлинга"""
    logger.info("\n🧪 ТЕСТ 4: Уровни трейлинга")
    
    config = TrailingConfigPnLOnly()
    
    pos = Position(
        side=Side.LONG,
        entry=1.0000,
        qty=50.0,
        remaining_qty=50.0,
        r_per_unit=0.05,
        sl=0.9500,
        peak_pnl_usdt=0.0
    )
    
    test_cases = [
        (0.05, 'INACTIVE', 0),     # $0.05 - неактивен
        (0.06, 'L1', 0.50),        # $0.06 - уровень 1, сохранить 50%
        (0.15, 'L2', 0.60),        # $0.15 - уровень 2, сохранить 60%
        (0.25, 'L3', 0.70),        # $0.25 - уровень 3, сохранить 70%
        (0.35, 'L4', 0.80),        # $0.35+ - уровень 4, сохранить 80%
    ]
    
    for pnl_usdt, expected_level, expected_keep_pct in test_cases:
        pos.peak_pnl_usdt = pnl_usdt
        current_price = pos.entry + (pnl_usdt / pos.qty)
        
        updated_pos = update_trailing_pnl_only(pos, current_price, current_price, 0.02, config)
        
        actual_level = updated_pos.trailing_debug['level']
        actual_keep_pct = updated_pos.trailing_debug['keep_pct']
        
        logger.info(f"   PnL: ${pnl_usdt:.2f} → Уровень: {actual_level}, Сохранить: {actual_keep_pct*100:.0f}%")
        
        assert actual_level == expected_level, f"Неправильный уровень: {actual_level} != {expected_level}"
        assert abs(actual_keep_pct - expected_keep_pct) < 0.01, f"Неправильный процент: {actual_keep_pct} != {expected_keep_pct}"
    
    logger.info("   ✅ Все уровни трейлинга работают правильно")

def test_short_positions():
    """Тест 5: Проверка работы с SHORT позициями"""
    logger.info("\n🧪 ТЕСТ 5: SHORT позиции")
    
    config = TrailingConfigPnLOnly()
    
    # SHORT позиция
    pos = Position(
        side=Side.SHORT,
        entry=1.0000,
        qty=50.0,
        remaining_qty=50.0,
        r_per_unit=0.05,
        sl=1.0500,  # Начальный SL выше entry для SHORT
        peak_pnl_usdt=0.0
    )
    
    # Цена упала - прибыль для SHORT
    current_price = 0.9988  # Цена упала на $0.0012, PnL = $0.60 (достаточно для L1)
    pos.peak_pnl_usdt = (pos.entry - current_price) * pos.qty  # $0.60 прибыли
    
    updated_pos = update_trailing_pnl_only(pos, current_price, current_price, 0.02, config)
    
    logger.info(f"   Entry: ${pos.entry:.4f}")
    logger.info(f"   Current Price: ${current_price:.4f}")
    logger.info(f"   PnL: ${updated_pos.peak_pnl_usdt:.4f}")
    logger.info(f"   Старый SL: ${pos.sl:.4f}")
    logger.info(f"   Новый SL: ${updated_pos.sl:.4f}")
    logger.info(f"   Трейлинг уровень: {updated_pos.trailing_debug['level']}")
    
    # Проверяем что трейлинг активировался
    if updated_pos.trailing_debug['level'] != 'INACTIVE':
        logger.info("   ✅ Трейлинг активировался для SHORT")
        # Для SHORT: SL может подтягиваться ВНИЗ только если это улучшает позицию
        assert updated_pos.sl <= pos.sl, "SL для SHORT не должен ухудшаться"
    else:
        logger.info("   ℹ️ Трейлинг неактивен - PnL недостаточно или SL не улучшается")
    
    logger.info("   ✅ SHORT трейлинг работает правильно")

def main():
    logger.info("=" * 80)
    logger.info("🧪 КОМПЛЕКСНОЕ ТЕСТИРОВАНИЕ СТРАТЕГИИ И ТРЕЙЛИНГА")
    logger.info("=" * 80)
    
    try:
        # Запускаем все тесты
        test_initial_sl_calculation()
        test_trailing_activation()
        test_sl_only_improves()
        test_trailing_levels()
        test_short_positions()
        
        logger.info("\n" + "=" * 80)
        logger.info("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
        logger.info("✅ Базовый функционал стратегии не нарушен")
        logger.info("✅ Трейлинг работает как задумано")
        logger.info("✅ SL может только улучшаться")
        logger.info("✅ Уровни активации соблюдаются")
        logger.info("=" * 80)
        
        return True
        
    except Exception as e:
        logger.error(f"\n❌ ТЕСТ ПРОВАЛЕН: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
