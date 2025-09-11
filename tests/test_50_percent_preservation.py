#!/usr/bin/env python3
"""
Тест сохранения 50% прибыли в трейлинге
"""

import os
import sys
from dataclasses import dataclass
from typing import Dict, Any

# Добавляем путь к модулям
sys.path.append('.')

from signalwarden_lite.core.types import Position, Side
from signalwarden_lite.core.trailing import TrailingConfig, update_trailing_pnl_based

def test_50_percent_preservation():
    """Тест сохранения 50% прибыли"""
    
    print("🎯 ТЕСТ СОХРАНЕНИЯ 50% ПРИБЫЛИ В ТРЕЙЛИНГЕ")
    print("=" * 80)
    
    # Конфигурация трейлинга
    cfg = TrailingConfig(
        activate_pnl_usdt=0.10,
        level_1_pnl=0.10,
        level_1_keep_pct=0.50,  # 50%
        level_2_pnl=0.20,
        level_2_keep_pct=0.60,
        level_3_pnl=0.30,
        level_3_keep_pct=0.70,
        level_4_pnl=0.40,
        level_4_keep_pct=0.80
    )
    
    print("📊 КОНФИГУРАЦИЯ:")
    print(f"   activate_pnl_usdt: {cfg.activate_pnl_usdt}")
    print(f"   level_1_keep_pct: {cfg.level_1_keep_pct} (50%)")
    print()
    
    # Создаем тестовую позицию
    entry_price = 0.8
    qty = 25.0
    sl_initial = 0.75  # Начальный SL
    
    position = Position(
        side=Side.LONG,
        entry=entry_price,
        qty=qty,
        remaining_qty=qty,
        sl=sl_initial,
        sl_initial=sl_initial,
        r_per_unit=entry_price - sl_initial,  # 0.05
        peak_pnl_usdt=0.0,
        peak_R=0.0,
        be_applied=False,
        partials_done={}
    )
    
    print("📊 ТЕСТОВАЯ ПОЗИЦИЯ:")
    print(f"   Entry: ${entry_price:.6f}")
    print(f"   Quantity: {qty}")
    print(f"   Initial SL: ${sl_initial:.6f}")
    print()
    
    # Тестовые сценарии
    scenarios = [
        {"current_price": 0.804, "pnl": 0.10, "desc": "Активация трейлинга"},
        {"current_price": 0.808, "pnl": 0.20, "desc": "Двойная прибыль"},
        {"current_price": 0.812, "pnl": 0.30, "desc": "Тройная прибыль"},
        {"current_price": 0.816, "pnl": 0.40, "desc": "Четверная прибыль"},
    ]
    
    print("🧮 ТЕСТ СЦЕНАРИЕВ:")
    print("-" * 80)
    
    for i, scenario in enumerate(scenarios, 1):
        current_price = scenario["current_price"]
        expected_pnl = scenario["pnl"]
        desc = scenario["desc"]
        
        # Рассчитываем фактический PnL
        actual_pnl = (current_price - entry_price) * qty
        
        print(f"📊 СЦЕНАРИЙ {i}: {desc}")
        print(f"   Current Price: ${current_price:.6f}")
        print(f"   Expected PnL: {expected_pnl:.2f} USDT")
        print(f"   Actual PnL: {actual_pnl:.2f} USDT")
        
        # Обновляем трейлинг
        updated_pos = update_trailing_pnl_based(position, current_price, actual_pnl, cfg)
        
        # Проверяем результат
        debug_info = getattr(updated_pos, 'trailing_debug', {})
        peak_pnl = debug_info.get('peak_pnl', 0)
        target_profit = debug_info.get('target_profit', 0)
        keep_pct = debug_info.get('keep_pct', 0)
        
        # Рассчитываем, сколько прибыли сохраняется при новом SL
        if updated_pos.sl > entry_price:
            preserved_profit = (updated_pos.sl - entry_price) * qty
        else:
            preserved_profit = 0
        
        # Проверяем процент сохранения
        if peak_pnl > 0:
            actual_keep_pct = preserved_profit / peak_pnl
        else:
            actual_keep_pct = 0
        
        print(f"   Peak PnL: {peak_pnl:.2f} USDT")
        print(f"   Target Profit: {target_profit:.2f} USDT")
        print(f"   Expected Keep %: {keep_pct*100:.0f}%")
        print(f"   New SL: ${updated_pos.sl:.6f}")
        print(f"   Preserved Profit: {preserved_profit:.4f} USDT")
        print(f"   Actual Keep %: {actual_keep_pct*100:.1f}%")
        
        # Проверяем правильность
        if abs(actual_keep_pct - keep_pct) < 0.01:  # Допуск 1%
            print(f"   Статус: ✅ Правильно")
        else:
            print(f"   Статус: ❌ ОШИБКА! Ожидалось {keep_pct*100:.0f}%, получили {actual_keep_pct*100:.1f}%")
        
        print()
        
        # Обновляем позицию для следующего сценария
        position = updated_pos
    
    # Проверим конкретный сценарий: пик 0.20, падение до 0.15
    print("🔍 ДЕТАЛЬНЫЙ ТЕСТ: ПИК 0.20 USDT, ПАДЕНИЕ ДО 0.15 USDT")
    print("-" * 80)
    
    # Сброс позиции
    position = Position(
        side=Side.LONG,
        entry=0.8,
        qty=25.0,
        remaining_qty=25.0,
        sl=0.75,
        sl_initial=0.75,
        r_per_unit=0.05,
        peak_pnl_usdt=0.0,
        peak_R=0.0,
        be_applied=False,
        partials_done={}
    )
    
    # Достигаем пика 0.20 USDT
    peak_price = 0.808  # PnL = 0.20 USDT
    peak_pnl = 0.20
    position = update_trailing_pnl_based(position, peak_price, peak_pnl, cfg)
    
    print(f"   Пик: ${peak_price:.6f}, PnL: {peak_pnl:.2f} USDT")
    print(f"   SL после пика: ${position.sl:.6f}")
    
    # Падение до 0.15 USDT
    fall_price = 0.806  # PnL = 0.15 USDT
    fall_pnl = 0.15
    position = update_trailing_pnl_based(position, fall_price, fall_pnl, cfg)
    
    print(f"   Падение: ${fall_price:.6f}, PnL: {fall_pnl:.2f} USDT")
    print(f"   SL после падения: ${position.sl:.6f}")
    
    # Проверяем сохранение
    preserved = (position.sl - 0.8) * 25.0
    keep_pct_actual = preserved / 0.20
    
    print(f"   Сохранено: {preserved:.4f} USDT")
    print(f"   Процент сохранения: {keep_pct_actual*100:.1f}%")
    print(f"   Ожидалось: 60.0% (level 2)")
    
    if abs(keep_pct_actual - 0.60) < 0.01:
        print(f"   Статус: ✅ Правильно")
    else:
        print(f"   Статус: ❌ ОШИБКА!")
    
    print()
    print("🎯 ИТОГОВАЯ ОЦЕНКА:")
    print("-" * 60)
    print("   Проверьте результаты выше для определения проблем в трейлинге")

if __name__ == "__main__":
    test_50_percent_preservation()
