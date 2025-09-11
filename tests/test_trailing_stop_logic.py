#!/usr/bin/env python3
"""
Тест логики трейлинг стоп-лоссов - проверка отсутствия закрытий в 0
"""

import os
import sys
import yaml
from typing import Dict, List, Any

# Добавляем путь к модулям
sys.path.append('.')

from signalwarden_lite.core.trailing import TrailingConfig, update_trailing_pnl_based
from signalwarden_lite.core.types import Position, Side

def test_trailing_stop_logic():
    """Тест логики трейлинг стоп-лоссов"""
    
    print("🛡️ ТЕСТ ЛОГИКИ ТРЕЙЛИНГ СТОП-ЛОССОВ")
    print("=" * 80)
    
    # Загрузить конфигурацию
    with open('signalwarden_lite/config/config_production.yaml', 'r') as f:
        cfg = yaml.safe_load(f)
    
    print("📊 КОНФИГУРАЦИЯ ТРЕЙЛИНГА:")
    print(f"   activate_pnl_usdt: {cfg['trailing']['activate_pnl_usdt']}")
    print(f"   level_1_pnl: {cfg['trailing']['level_1_pnl']}")
    print(f"   level_1_keep_pct: {cfg['trailing']['level_1_keep_pct']}")
    print()
    
    # Создать тестовую позицию
    entry_price = 0.884021
    qty = 23.76
    sl_price = 0.873843  # Начальный стоп-лосс
    
    test_position = Position(
        side=Side.LONG,
        entry=entry_price,
        qty=qty,
        remaining_qty=qty,
        r_per_unit=entry_price - sl_price,
        sl=sl_price,
        sl_initial=sl_price,
        peak_pnl_usdt=0.0
    )
    
    # Создать конфигурацию трейлинга
    trailing_config = TrailingConfig(
        activate_pnl_usdt=cfg['trailing']['activate_pnl_usdt'],
        level_1_pnl=cfg['trailing']['level_1_pnl'],
        level_1_keep_pct=cfg['trailing']['level_1_keep_pct'],
        level_2_pnl=cfg['trailing']['level_2_pnl'],
        level_2_keep_pct=cfg['trailing']['level_2_keep_pct'],
        level_3_pnl=cfg['trailing']['level_3_pnl'],
        level_3_keep_pct=cfg['trailing']['level_3_keep_pct'],
        level_4_pnl=cfg['trailing']['level_4_pnl'],
        level_4_keep_pct=cfg['trailing']['level_4_keep_pct']
    )
    
    print("🔍 ТЕСТ 1: ПРОВЕРКА ОТСУТСТВИЯ ЗАКРЫТИЙ В 0")
    print("-" * 60)
    
    # Тест разных сценариев PnL
    test_scenarios = [
        {"pnl": 0.05, "description": "Ниже активации"},
        {"pnl": 0.10, "description": "Точно активация"},
        {"pnl": 0.15, "description": "Выше активации"},
        {"pnl": 0.20, "description": "Второй уровень"},
        {"pnl": 0.30, "description": "Третий уровень"},
        {"pnl": 0.40, "description": "Четвертый уровень"},
        {"pnl": 0.50, "description": "Выше четвертого уровня"}
    ]
    
    print(f"   {'PnL':<8} {'Description':<20} {'New SL':<12} {'SL > Entry':<10} {'Status':<8}")
    print(f"   {'-'*8} {'-'*20} {'-'*12} {'-'*10} {'-'*8}")
    
    issues = []
    
    for scenario in test_scenarios:
        pnl = scenario["pnl"]
        description = scenario["description"]
        
        # Сбросить позицию для чистого теста
        test_position.peak_pnl_usdt = 0.0
        test_position.sl = sl_price  # Вернуть к начальному SL
        
        # Обновить трейлинг
        updated_position = update_trailing_pnl_based(test_position, entry_price, pnl, trailing_config)
        debug_info = getattr(updated_position, 'trailing_debug', {})
        
        new_sl = updated_position.sl
        sl_above_entry = new_sl > entry_price
        sl_updated = debug_info.get('sl_updated', False)
        
        # Проверить, что SL не равен entry (закрытие в 0)
        if abs(new_sl - entry_price) < 0.0001:
            status = "❌ ЗАКРЫТИЕ В 0!"
            issues.append(f"PnL {pnl}: SL = Entry (закрытие в 0)")
        elif new_sl <= entry_price:
            status = "❌ SL <= Entry"
            issues.append(f"PnL {pnl}: SL <= Entry (убыток)")
        elif sl_updated:
            status = "✅ SL Updated"
        else:
            status = "⏸️ No Update"
        
        print(f"   {pnl:<8.2f} {description:<20} {new_sl:<12.6f} {'✅' if sl_above_entry else '❌':<10} {status:<8}")
    
    print()
    
    # Тест 2: Проверка логики сохранения прибыли
    print("🔍 ТЕСТ 2: ПРОВЕРКА ЛОГИКИ СОХРАНЕНИЯ ПРИБЫЛИ")
    print("-" * 60)
    
    print(f"   {'PnL':<8} {'Peak PnL':<10} {'Keep %':<8} {'Target':<10} {'SL Price':<12} {'Profit':<10}")
    print(f"   {'-'*8} {'-'*10} {'-'*8} {'-'*10} {'-'*12} {'-'*10}")
    
    # Симуляция роста прибыли
    peak_pnl = 0.0
    for pnl in [0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50]:
        # Обновить трейлинг
        updated_position = update_trailing_pnl_based(test_position, entry_price, pnl, trailing_config)
        debug_info = getattr(updated_position, 'trailing_debug', {})
        
        peak_pnl = updated_position.peak_pnl_usdt
        keep_pct = debug_info.get('keep_pct', 0) * 100
        target_profit = debug_info.get('target_profit', 0)
        new_sl = updated_position.sl
        actual_profit = (new_sl - entry_price) * qty
        
        print(f"   {pnl:<8.2f} {peak_pnl:<10.2f} {keep_pct:<8.0f} {target_profit:<10.4f} {new_sl:<12.6f} {actual_profit:<10.4f}")
        
        # Проверить, что SL всегда выше entry
        if new_sl <= entry_price:
            issues.append(f"PnL {pnl}: SL {new_sl:.6f} <= Entry {entry_price:.6f}")
        
        # Обновить позицию для следующей итерации
        test_position = updated_position
    
    print()
    
    # Тест 3: Проверка сценария падения прибыли
    print("🔍 ТЕСТ 3: ПРОВЕРКА СЦЕНАРИЯ ПАДЕНИЯ ПРИБЫЛИ")
    print("-" * 60)
    
    # Сначала поднять прибыль до 0.40 USDT
    test_position.peak_pnl_usdt = 0.0
    test_position.sl = sl_price
    
    # Достичь пика
    updated_position = update_trailing_pnl_based(test_position, entry_price, 0.40, trailing_config)
    peak_sl = updated_position.sl
    peak_debug = getattr(updated_position, 'trailing_debug', {})
    peak_target = peak_debug.get('target_profit', 0)
    
    print(f"   Пик прибыли 0.40 USDT:")
    print(f"     SL: {peak_sl:.6f}")
    print(f"     Target Profit: {peak_target:.4f} USDT")
    print(f"     Keep %: {peak_debug.get('keep_pct', 0) * 100:.0f}%")
    print()
    
    # Теперь проверить падение прибыли
    print(f"   {'PnL':<8} {'SL':<12} {'SL Changed':<12} {'Status':<15}")
    print(f"   {'-'*8} {'-'*12} {'-'*12} {'-'*15}")
    
    for pnl in [0.35, 0.30, 0.25, 0.20, 0.15, 0.10, 0.05, 0.00, -0.05]:
        # Обновить трейлинг
        updated_position = update_trailing_pnl_based(test_position, entry_price, pnl, trailing_config)
        debug_info = getattr(updated_position, 'trailing_debug', {})
        
        current_sl = updated_position.sl
        sl_changed = abs(current_sl - peak_sl) > 0.0001
        sl_updated = debug_info.get('sl_updated', False)
        
        if current_sl <= entry_price:
            status = "❌ SL <= Entry"
            issues.append(f"Падение PnL {pnl}: SL {current_sl:.6f} <= Entry {entry_price:.6f}")
        elif sl_changed and not sl_updated:
            status = "✅ SL Protected"
        elif sl_updated:
            status = "✅ SL Updated"
        else:
            status = "⏸️ No Change"
        
        print(f"   {pnl:<8.2f} {current_sl:<12.6f} {'✅' if sl_changed else '❌':<12} {status:<15}")
    
    print()
    
    # Тест 4: Проверка break-even логики
    print("🔍 ТЕСТ 4: ПРОВЕРКА BREAK-EVEN ЛОГИКИ")
    print("-" * 60)
    
    # Комиссии
    notional_value = 21  # Размер позиции
    taker_fee = 0.0005  # 0.05%
    total_commission = notional_value * taker_fee * 2  # вход + выход
    
    print(f"   Total Commission: {total_commission:.4f} USDT")
    print(f"   Activation PnL: {cfg['trailing']['activate_pnl_usdt']} USDT")
    
    # Проверить, что при активации сохраняется больше комиссий
    test_position.peak_pnl_usdt = 0.0
    test_position.sl = sl_price
    
    pnl = cfg['trailing']['activate_pnl_usdt']
    updated_position = update_trailing_pnl_based(test_position, entry_price, pnl, trailing_config)
    debug_info = getattr(updated_position, 'trailing_debug', {})
    target_profit = debug_info.get('target_profit', 0)
    
    print(f"   Target Profit at activation: {target_profit:.4f} USDT")
    print(f"   Net Profit: {target_profit - total_commission:.4f} USDT")
    
    if target_profit > total_commission:
        print(f"   ✅ Сохраняется больше комиссий")
    else:
        print(f"   ❌ Сохраняется меньше комиссий")
        issues.append(f"При активации сохраняется {target_profit:.4f} < комиссий {total_commission:.4f}")
    
    print()
    
    # Итоговая оценка
    print("🎯 ИТОГОВАЯ ОЦЕНКА ТРЕЙЛИНГ СТОП-ЛОССОВ:")
    print("-" * 60)
    
    if not issues:
        print("✅ ТРЕЙЛИНГ СТОП-ЛОССЫ РАБОТАЮТ ПРАВИЛЬНО!")
        print("✅ НЕТ ЗАКРЫТИЙ В 0 (безубыток)")
        print("✅ SL ВСЕГДА ВЫШЕ ENTRY")
        print("✅ ПРИБЫЛЬ ЗАЩИЩЕНА ОТ ПАДЕНИЯ")
        print("✅ ЛОГИКА СОХРАНЕНИЯ РАБОТАЕТ КОРРЕКТНО")
    else:
        print("❌ НАЙДЕНЫ ПРОБЛЕМЫ В ТРЕЙЛИНГ СТОП-ЛОССАХ:")
        for issue in issues:
            print(f"   - {issue}")
        print("❌ ТРЕБУЕТСЯ ИСПРАВЛЕНИЕ ПЕРЕД LIVE ТОРГОВЛЕЙ")
    
    print()
    print("📋 СВОДКА ПО ТРЕЙЛИНГ СТОП-ЛОССАМ:")
    print(f"   • Активация: {cfg['trailing']['activate_pnl_usdt']} USDT")
    print(f"   • Минимальное сохранение: {cfg['trailing']['level_1_pnl'] * cfg['trailing']['level_1_keep_pct']:.3f} USDT")
    print(f"   • Комиссии: {total_commission:.4f} USDT")
    print(f"   • Защита от закрытий в 0: {'✅' if not issues else '❌'}")

if __name__ == "__main__":
    test_trailing_stop_logic()
