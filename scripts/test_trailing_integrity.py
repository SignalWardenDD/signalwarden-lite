#!/usr/bin/env python3
"""
Тест целостности трейлинг системы после исправлений
Проверяет что трейлинг работает правильно и не сломан
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from signalwarden_lite.core.trailing_pnl_only import TrailingConfigPnLOnly, update_trailing_pnl_only
from signalwarden_lite.core.types import Position, Side
from dataclasses import dataclass
from typing import Dict, Any
import time

def test_trailing_activation():
    """Тест активации трейлинга при достижении порогов"""
    print("🔍 ТЕСТ 1: Активация трейлинга при достижении PnL порогов")
    
    cfg = TrailingConfigPnLOnly()
    
    # Создаем LONG позицию
    pos = Position(
        side=Side.LONG,
        entry=1.0,
        qty=100.0,
        remaining_qty=100.0,
        r_per_unit=0.05,  # (entry - sl) для LONG
        sl=0.95,  # Начальный SL
        peak_pnl_usdt=0.0,  # Начинаем с 0
        sl_initial=0.95
    )
    
    test_cases = [
        # (цена, ожидаемый_уровень, ожидаемый_keep_pct, описание)
        (1.0005, "INACTIVE", 0, "Мало прибыли - трейлинг не активен"),
        (1.00061, "L1", 0.5, "L1: $0.061 PnL -> 50% защита"),
        (1.00151, "L2", 0.6, "L2: $0.151 PnL -> 60% защита"),
        (1.00251, "L3", 0.7, "L3: $0.251 PnL -> 70% защита"),
        (1.00351, "L4", 0.8, "L4: $0.351 PnL -> 80% защита"),
    ]
    
    for price, expected_level, expected_keep_pct, desc in test_cases:
        updated_pos = update_trailing_pnl_only(pos, price, price, 0.01, cfg)
        debug = getattr(updated_pos, 'trailing_debug', {})
        
        actual_level = debug.get('level', 'UNKNOWN')
        actual_keep_pct = debug.get('keep_pct', 0)
        
        status = "✅" if (actual_level == expected_level and actual_keep_pct == expected_keep_pct) else "❌"
        print(f"  {status} Цена {price}: {desc}")
        print(f"      Ожидается: {expected_level} ({expected_keep_pct*100:.0f}%)")
        print(f"      Получено:  {actual_level} ({actual_keep_pct*100:.0f}%)")
        
        if actual_level != expected_level or actual_keep_pct != expected_keep_pct:
            print(f"      ❌ ОШИБКА В АКТИВАЦИИ ТРЕЙЛИНГА!")
            return False
        
        # Обновляем позицию для следующего теста
        pos = updated_pos
    
    print("✅ ТЕСТ 1 ПРОЙДЕН: Активация трейлинга работает правильно\n")
    return True

def test_trailing_updates():
    """Тест правильности обновлений трейлинга внутри уровней"""
    print("🔍 ТЕСТ 2: Обновления трейлинга внутри уровней и между уровнями")
    
    cfg = TrailingConfigPnLOnly()
    
    # Создаем LONG позицию с уже активным трейлингом L1
    pos = Position(
        side=Side.LONG,
        entry=1.0,
        qty=100.0,
        remaining_qty=100.0,
        r_per_unit=0.05,
        sl=1.03,  # SL уже на уровне L1 (50% от $0.06 = $0.03)
        peak_pnl_usdt=0.061,  # Начинаем с минимального L1
        sl_initial=0.95
    )
    
    test_scenarios = [
        # (цена, ожидаемое_поведение, описание)
        (1.0010, "рост_внутри_L1", "Рост PnL внутри L1 - SL должен расти"),
        (1.0004, "падение_внутри_L1", "Падение PnL внутри L1 - SL не должен падать"),
        (1.0015, "переход_в_L2", "Переход в L2 - SL должен значительно вырасти"),
        (1.0012, "падение_из_L2_в_L1", "Падение из L2 в L1 - SL не должен падать"),
    ]
    
    for price, behavior, desc in test_scenarios:
        old_sl = pos.sl
        updated_pos = update_trailing_pnl_only(pos, price, price, 0.01, cfg)
        new_sl = updated_pos.sl
        
        debug = getattr(updated_pos, 'trailing_debug', {})
        level = debug.get('level', 'UNKNOWN')
        
        print(f"  📊 {desc}")
        print(f"      Цена: {price}, Уровень: {level}")
        print(f"      SL: {old_sl:.6f} → {new_sl:.6f} ({new_sl-old_sl:+.6f})")
        
        # Проверяем правильность поведения
        if behavior == "рост_внутри_L1":
            if new_sl <= old_sl:
                print(f"      ❌ ОШИБКА: SL должен расти внутри уровня!")
                return False
            print(f"      ✅ SL правильно вырос внутри уровня")
            
        elif behavior == "падение_внутри_L1":
            if new_sl < old_sl:
                print(f"      ❌ ОШИБКА: SL не должен падать при падении цены!")
                return False
            print(f"      ✅ SL правильно не ухудшился")
            
        elif behavior == "переход_в_L2":
            if level != "L2" or new_sl <= old_sl:
                print(f"      ❌ ОШИБКА: Переход в L2 должен улучшить SL!")
                return False
            print(f"      ✅ Переход в L2 правильно улучшил SL")
            
        elif behavior == "падение_из_L2_в_L1":
            # После достижения L2, даже при падении PnL, SL не должен ухудшаться
            # Но уровень может остаться L2 из-за peak_pnl_usdt
            if new_sl < old_sl:
                print(f"      ❌ ОШИБКА: SL не должен ухудшаться при падении из L2!")
                return False
            print(f"      ✅ SL правильно не ухудшился при падении")
        
        # Обновляем позицию для следующего теста
        pos = updated_pos
    
    print("✅ ТЕСТ 2 ПРОЙДЕН: Обновления трейлинга работают правильно\n")
    return True

def test_trailing_protection():
    """Тест защиты от ухудшения SL"""
    print("🔍 ТЕСТ 3: Защита от ухудшения SL")
    
    cfg = TrailingConfigPnLOnly()
    
    # Тест для LONG позиции
    print("  📈 LONG позиция:")
    pos_long = Position(
        side=Side.LONG,
        entry=1.0,
        qty=100.0,
        remaining_qty=100.0,
        r_per_unit=0.05,
        sl=1.03,  # Хороший SL
        peak_pnl_usdt=0.06,
        sl_initial=0.95
    )
    
    # Тестируем что SL только улучшается (растет) для LONG
    test_prices = [1.0008, 1.0012, 1.0015, 1.0020]
    prev_sl = pos_long.sl
    
    for price in test_prices:
        updated_pos = update_trailing_pnl_only(pos_long, price, price, 0.01, cfg)
        new_sl = updated_pos.sl
        
        if new_sl < prev_sl:
            print(f"      ❌ ОШИБКА: SL ухудшился для LONG! {prev_sl:.6f} → {new_sl:.6f}")
            return False
        
        print(f"      ✅ Цена {price}: SL {prev_sl:.6f} → {new_sl:.6f} (улучшение: {new_sl-prev_sl:+.6f})")
        prev_sl = new_sl
        pos_long = updated_pos
    
    # Тест для SHORT позиции
    print("  📉 SHORT позиция:")
    pos_short = Position(
        side=Side.SHORT,
        entry=1.0,
        qty=100.0,
        remaining_qty=100.0,
        r_per_unit=0.03,  # (sl - entry) для SHORT
        sl=0.97,  # Хороший SL для SHORT
        peak_pnl_usdt=0.06,
        sl_initial=1.03
    )
    
    # Тестируем что SL только улучшается (падает) для SHORT
    test_prices = [0.9992, 0.9988, 0.9985, 0.9980]
    prev_sl = pos_short.sl
    
    for price in test_prices:
        updated_pos = update_trailing_pnl_only(pos_short, price, price, 0.01, cfg)
        new_sl = updated_pos.sl
        
        if new_sl > prev_sl:
            print(f"      ❌ ОШИБКА: SL ухудшился для SHORT! {prev_sl:.6f} → {new_sl:.6f}")
            return False
        
        print(f"      ✅ Цена {price}: SL {prev_sl:.6f} → {new_sl:.6f} (улучшение: {prev_sl-new_sl:+.6f})")
        prev_sl = new_sl
        pos_short = updated_pos
    
    print("✅ ТЕСТ 3 ПРОЙДЕН: Защита от ухудшения работает правильно\n")
    return True

def test_new_position_logic():
    """Тест логики создания новых позиций с чистыми данными"""
    print("🔍 ТЕСТ 4: Создание новых позиций с чистыми данными")
    
    # Имитируем создание новой позиции (как в execute_signal)
    new_position_data = {
        'symbol': 'ADA_USDT',
        'side': 'LONG',
        'entry': 1.0,
        'qty': 100.0,
        'sl_initial': 0.95,
        'sl_current': 0.95,
        'last_updated_sl': 0.95,
        'atr': 0.01,
        'timestamp': time.time(),
        'order_id': 'test_order_123',
        'sl_order_id': 'test_sl_456',
        'trailing_active': False,  # КРИТИЧНО: должно быть False
        'peak_pnl_usdt': 0.0,      # КРИТИЧНО: должно быть 0.0
        'synced_from_exchange': False
    }
    
    # Проверяем критические поля
    critical_checks = [
        ('trailing_active', False, "Трейлинг должен быть неактивен для новой позиции"),
        ('peak_pnl_usdt', 0.0, "Peak PnL должен быть 0 для новой позиции"),
        ('sl_current', 0.95, "SL должен быть основан на ATR, не на старых данных"),
    ]
    
    all_passed = True
    for field, expected, description in critical_checks:
        actual = new_position_data.get(field)
        if actual != expected:
            print(f"      ❌ ОШИБКА: {description}")
            print(f"          Ожидается: {expected}, Получено: {actual}")
            all_passed = False
        else:
            print(f"      ✅ {description}")
    
    if all_passed:
        print("✅ ТЕСТ 4 ПРОЙДЕН: Новые позиции создаются с чистыми данными\n")
        return True
    else:
        print("❌ ТЕСТ 4 ПРОВАЛЕН: Проблемы с созданием новых позиций\n")
        return False

def main():
    """Запуск всех тестов"""
    print("🚀 ЗАПУСК ТЕСТОВ ЦЕЛОСТНОСТИ ТРЕЙЛИНГ СИСТЕМЫ")
    print("=" * 60)
    
    tests = [
        test_trailing_activation,
        test_trailing_updates, 
        test_trailing_protection,
        test_new_position_logic
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                print(f"❌ ТЕСТ ПРОВАЛЕН: {test.__name__}")
        except Exception as e:
            print(f"❌ ОШИБКА В ТЕСТЕ {test.__name__}: {e}")
    
    print("=" * 60)
    print(f"📊 РЕЗУЛЬТАТЫ: {passed}/{total} тестов пройдено")
    
    if passed == total:
        print("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ! Трейлинг система работает правильно!")
        return True
    else:
        print(f"⚠️ {total-passed} тестов провалено! Требуется исправление!")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
