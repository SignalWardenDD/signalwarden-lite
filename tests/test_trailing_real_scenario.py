#!/usr/bin/env python3
"""
Тест реального сценария трейлинга - рост и падение PnL
"""

import os
import sys
from dataclasses import dataclass
from typing import Dict, Any

# Добавляем путь к модулям
sys.path.append('.')

from signalwarden_lite.core.types import Position, Side
from signalwarden_lite.core.trailing import TrailingConfig, update_trailing_pnl_based

def test_trailing_real_scenario():
    """Тест реального сценария трейлинга"""
    
    print("🎯 ТЕСТ РЕАЛЬНОГО СЦЕНАРИЯ ТРЕЙЛИНГА")
    print("=" * 80)
    
    # Конфигурация трейлинга
    cfg = TrailingConfig(
        activate_pnl_usdt=0.10,
        level_1_pnl=0.10,
        level_1_keep_pct=0.50,  # 50%
        level_2_pnl=0.20,
        level_2_keep_pct=0.60,  # 60%
        level_3_pnl=0.30,
        level_3_keep_pct=0.70,  # 70%
        level_4_pnl=0.40,
        level_4_keep_pct=0.80   # 80%
    )
    
    print("📊 КОНФИГУРАЦИЯ:")
    print(f"   activate_pnl_usdt: {cfg.activate_pnl_usdt}")
    print(f"   level_2_pnl: {cfg.level_2_pnl} -> {cfg.level_2_keep_pct*100:.0f}%")
    print()
    
    # Создаем позицию (как в реальной торговле)
    entry_price = 0.8
    qty = 25.0
    sl_initial = 0.75
    
    position = Position(
        side=Side.LONG,
        entry=entry_price,
        qty=qty,
        remaining_qty=qty,
        sl=sl_initial,
        sl_initial=sl_initial,
        r_per_unit=entry_price - sl_initial,
        peak_pnl_usdt=0.0,
        peak_R=0.0,
        be_applied=False,
        partials_done={}
    )
    
    print("📊 НАЧАЛЬНАЯ ПОЗИЦИЯ:")
    print(f"   Entry: ${entry_price:.6f}")
    print(f"   Quantity: {qty}")
    print(f"   Initial SL: ${sl_initial:.6f}")
    print()
    
    # Симуляция движения цены
    price_movements = [
        {"price": 0.804, "desc": "Активация трейлинга"},
        {"price": 0.806, "desc": "Рост PnL до 0.15"},
        {"price": 0.808, "desc": "Рост PnL до 0.20 - должен быть 60%"},
        {"price": 0.810, "desc": "Рост PnL до 0.25"},
        {"price": 0.812, "desc": "Рост PnL до 0.30 - должен быть 70%"},
        {"price": 0.810, "desc": "Падение до 0.25 - SL не должен опуститься"},
        {"price": 0.808, "desc": "Падение до 0.20 - SL не должен опуститься"},
        {"price": 0.806, "desc": "Падение до 0.15 - SL не должен опуститься"},
    ]
    
    print("🎬 СИМУЛЯЦИЯ ДВИЖЕНИЯ ЦЕНЫ:")
    print("-" * 80)
    
    for i, movement in enumerate(price_movements, 1):
        current_price = movement["price"]
        desc = movement["desc"]
        
        # Рассчитываем текущий PnL
        current_pnl = (current_price - entry_price) * qty
        
        # Сохраняем старый SL для сравнения
        old_sl = position.sl
        old_peak_pnl = position.peak_pnl_usdt
        
        # Обновляем трейлинг
        position = update_trailing_pnl_based(position, current_price, current_pnl, cfg)
        
        # Получаем отладочную информацию
        debug_info = getattr(position, 'trailing_debug', {})
        level = debug_info.get('level', 'N/A')
        keep_pct = debug_info.get('keep_pct', 0)
        target_profit = debug_info.get('target_profit', 0)
        sl_updated = debug_info.get('sl_updated', False)
        
        # Рассчитываем сохраненную прибыль
        if position.sl > entry_price:
            preserved_profit = (position.sl - entry_price) * qty
        else:
            preserved_profit = 0
        
        # Рассчитываем процент сохранения от пика
        if position.peak_pnl_usdt > 0:
            actual_keep_pct = preserved_profit / position.peak_pnl_usdt
        else:
            actual_keep_pct = 0
        
        print(f"📊 ШАГ {i}: {desc}")
        print(f"   Price: ${current_price:.6f}")
        print(f"   Current PnL: {current_pnl:.2f} USDT")
        print(f"   Peak PnL: {position.peak_pnl_usdt:.2f} USDT (было {old_peak_pnl:.2f})")
        print(f"   Level: {level} -> {keep_pct*100:.0f}%")
        print(f"   Target Profit: {target_profit:.4f} USDT")
        print(f"   Old SL: ${old_sl:.6f}")
        print(f"   New SL: ${position.sl:.6f}")
        print(f"   SL Updated: {'✅' if sl_updated else '❌'}")
        print(f"   Preserved: {preserved_profit:.4f} USDT ({actual_keep_pct*100:.1f}%)")
        
        # Проверяем правильность
        if current_pnl < old_peak_pnl:  # Падение PnL
            if position.sl != old_sl:
                print(f"   ❌ ОШИБКА: SL изменился при падении PnL!")
            else:
                print(f"   ✅ Правильно: SL не изменился при падении")
        elif current_pnl > old_peak_pnl:  # Рост PnL
            if position.sl > old_sl:
                print(f"   ✅ Правильно: SL поднялся при росте PnL")
            else:
                print(f"   ❌ ОШИБКА: SL не поднялся при росте PnL!")
        
        # Проверяем уровни сохранения
        if position.peak_pnl_usdt >= 0.20 and position.peak_pnl_usdt < 0.30:
            expected_keep = 0.60  # 60% для level 2
            if abs(actual_keep_pct - expected_keep) > 0.01:
                print(f"   ❌ ОШИБКА: Ожидалось {expected_keep*100:.0f}%, получили {actual_keep_pct*100:.1f}%")
            else:
                print(f"   ✅ Правильно: Сохраняется {expected_keep*100:.0f}%")
        elif position.peak_pnl_usdt >= 0.30:
            expected_keep = 0.70  # 70% для level 3
            if abs(actual_keep_pct - expected_keep) > 0.01:
                print(f"   ❌ ОШИБКА: Ожидалось {expected_keep*100:.0f}%, получили {actual_keep_pct*100:.1f}%")
            else:
                print(f"   ✅ Правильно: Сохраняется {expected_keep*100:.0f}%")
        
        print()
    
    # Итоговая проверка
    print("🎯 ИТОГОВАЯ ПРОВЕРКА:")
    print("-" * 60)
    
    final_preserved = (position.sl - entry_price) * qty
    final_keep_pct = final_preserved / position.peak_pnl_usdt if position.peak_pnl_usdt > 0 else 0
    
    print(f"   Пик PnL: {position.peak_pnl_usdt:.2f} USDT")
    print(f"   Финальный SL: ${position.sl:.6f}")
    print(f"   Сохранено: {final_preserved:.4f} USDT")
    print(f"   Процент сохранения: {final_keep_pct*100:.1f}%")
    
    # Определяем ожидаемый процент
    if position.peak_pnl_usdt >= 0.30:
        expected_final = 0.70
        level_name = "Level 3 (70%)"
    elif position.peak_pnl_usdt >= 0.20:
        expected_final = 0.60
        level_name = "Level 2 (60%)"
    else:
        expected_final = 0.50
        level_name = "Level 1 (50%)"
    
    print(f"   Ожидается: {level_name}")
    
    if abs(final_keep_pct - expected_final) < 0.01:
        print(f"   ✅ ТРЕЙЛИНГ РАБОТАЕТ ПРАВИЛЬНО")
    else:
        print(f"   ❌ ТРЕЙЛИНГ РАБОТАЕТ НЕПРАВИЛЬНО!")
        print(f"   ❌ Ожидалось {expected_final*100:.0f}%, получили {final_keep_pct*100:.1f}%")

if __name__ == "__main__":
    test_trailing_real_scenario()
