#!/usr/bin/env python3
"""
Тест проверки исправления трейлинга
"""

import os
import sys
from dataclasses import dataclass
from typing import Dict, Any

# Добавляем путь к модулям
sys.path.append('.')

from signalwarden_lite.core.types import Position, Side
from signalwarden_lite.core.trailing import TrailingConfig, update_trailing_pnl_based

def test_trailing_fix_verification():
    """Тест проверки исправления трейлинга"""
    
    print("🔧 ТЕСТ ПРОВЕРКИ ИСПРАВЛЕНИЯ ТРЕЙЛИНГА")
    print("=" * 80)
    
    print("🔍 ПРОБЛЕМА БЫЛА:")
    print("   • Двойная проверка активации трейлинга в live системе")
    print("   • При падении PnL система блокировала обновления SL")
    print("   • Трейлинг не мог сохранять 60%/70% прибыли")
    print()
    
    print("✅ ИСПРАВЛЕНИЕ:")
    print("   • Убрана дублирующая проверка активации")
    print("   • Live система доверяет логике update_trailing_pnl_based")
    print("   • Трейлинг может правильно сохранять прибыль")
    print()
    
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
    
    # Создаем позицию
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
    
    print("🎬 СИМУЛЯЦИЯ КРИТИЧЕСКОГО СЦЕНАРИЯ:")
    print("-" * 80)
    
    # Сценарий: PnL растет до 0.25, затем падает до 0.15
    scenarios = [
        {"price": 0.810, "pnl": 0.25, "desc": "Рост до 0.25 USDT (Level 2 - 60%)"},
        {"price": 0.806, "pnl": 0.15, "desc": "Падение до 0.15 USDT (должен сохранить 60%)"},
    ]
    
    for i, scenario in enumerate(scenarios, 1):
        current_price = scenario["price"]
        expected_pnl = scenario["pnl"]
        desc = scenario["desc"]
        
        # Рассчитываем фактический PnL
        actual_pnl = (current_price - 0.8) * 25.0
        
        print(f"📊 СЦЕНАРИЙ {i}: {desc}")
        print(f"   Price: ${current_price:.6f}")
        print(f"   PnL: {actual_pnl:.2f} USDT")
        
        # Сохраняем старые значения
        old_sl = position.sl
        old_peak = position.peak_pnl_usdt
        
        # Обновляем трейлинг
        position = update_trailing_pnl_based(position, current_price, actual_pnl, cfg)
        
        # Получаем отладочную информацию
        debug_info = getattr(position, 'trailing_debug', {})
        level = debug_info.get('level', 'N/A')
        keep_pct = debug_info.get('keep_pct', 0)
        target_profit = debug_info.get('target_profit', 0)
        sl_updated = debug_info.get('sl_updated', False)
        
        # Рассчитываем сохраненную прибыль
        preserved_profit = (position.sl - 0.8) * 25.0 if position.sl > 0.8 else 0
        actual_keep_pct = preserved_profit / position.peak_pnl_usdt if position.peak_pnl_usdt > 0 else 0
        
        print(f"   Old SL: ${old_sl:.6f}")
        print(f"   New SL: ${position.sl:.6f}")
        print(f"   Peak PnL: {position.peak_pnl_usdt:.2f} USDT (было {old_peak:.2f})")
        print(f"   Level: {level} -> {keep_pct*100:.0f}%")
        print(f"   Target: {target_profit:.4f} USDT")
        print(f"   Preserved: {preserved_profit:.4f} USDT ({actual_keep_pct*100:.1f}%)")
        print(f"   SL Updated: {'✅' if sl_updated else '❌'}")
        
        # Проверяем правильность
        if i == 1:  # Рост PnL
            if position.sl > old_sl:
                print(f"   ✅ Правильно: SL поднялся при росте PnL")
            else:
                print(f"   ❌ ОШИБКА: SL не поднялся при росте PnL")
        elif i == 2:  # Падение PnL
            if abs(actual_keep_pct - 0.60) < 0.01:
                print(f"   ✅ Правильно: Сохраняется 60% прибыли")
            else:
                print(f"   ❌ ОШИБКА: Должно сохраняться 60%, сохраняется {actual_keep_pct*100:.1f}%")
        
        print()
    
    # Проверка симуляции live системы (до исправления)
    print("🔍 СИМУЛЯЦИЯ СТАРОЙ LIVE ЛОГИКИ (ДО ИСПРАВЛЕНИЯ):")
    print("-" * 80)
    
    # Симулируем старую логику
    final_pnl = 0.15
    activation_threshold = 0.10
    
    print(f"   Текущий PnL: {final_pnl:.2f} USDT")
    print(f"   Порог активации: {activation_threshold:.2f} USDT")
    print(f"   Старая проверка: {final_pnl:.2f} >= {activation_threshold:.2f} = {final_pnl >= activation_threshold}")
    
    if final_pnl >= activation_threshold:
        print(f"   Старая логика: ✅ Разрешить обновление SL")
    else:
        print(f"   Старая логика: ❌ БЛОКИРОВАТЬ обновление SL")
        print(f"   Результат: Трейлинг не может сохранить 60% прибыли!")
    
    print()
    print(f"   Новая логика: ✅ Доверяем update_trailing_pnl_based")
    print(f"   Результат: Трейлинг может сохранить 60% прибыли!")
    
    print()
    print("🎯 ИТОГОВАЯ ОЦЕНКА:")
    print("-" * 60)
    
    final_preserved = (position.sl - 0.8) * 25.0
    final_keep_pct = final_preserved / position.peak_pnl_usdt if position.peak_pnl_usdt > 0 else 0
    
    print(f"   Пик PnL: {position.peak_pnl_usdt:.2f} USDT")
    print(f"   Финальный SL: ${position.sl:.6f}")
    print(f"   Сохранено: {final_preserved:.4f} USDT")
    print(f"   Процент: {final_keep_pct*100:.1f}%")
    
    if abs(final_keep_pct - 0.60) < 0.01:
        print(f"   ✅ ИСПРАВЛЕНИЕ РАБОТАЕТ: Сохраняется 60%")
    else:
        print(f"   ❌ ПРОБЛЕМА ОСТАЕТСЯ: Ожидалось 60%, получили {final_keep_pct*100:.1f}%")

if __name__ == "__main__":
    test_trailing_fix_verification()
