#!/usr/bin/env python3
"""
Тест правильной логики трейлинга
"""

import os
import sys
import yaml
from typing import Dict, List, Any

# Добавляем путь к модулям
sys.path.append('.')

from signalwarden_lite.core.trailing import TrailingConfig, update_trailing_pnl_based
from signalwarden_lite.core.types import Position, Side

def test_trailing_logic():
    """Тест правильной логики трейлинга"""
    
    print("🧮 ТЕСТ ПРАВИЛЬНОЙ ЛОГИКИ ТРЕЙЛИНГА")
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
    sl_price = 0.873843
    
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
    
    print("🔍 ТЕСТИРОВАНИЕ ЛОГИКИ:")
    print("-" * 60)
    
    # Тест 1: Активация при 0.10 USDT
    print("📊 ТЕСТ 1: Активация при 0.10 USDT")
    current_price = entry_price
    pnl = 0.10
    
    updated_position = update_trailing_pnl_based(test_position, current_price, pnl, trailing_config)
    debug_info = getattr(updated_position, 'trailing_debug', {})
    
    print(f"   PnL: {pnl} USDT")
    print(f"   Level: {debug_info.get('level', 'N/A')}")
    print(f"   Keep %: {debug_info.get('keep_pct', 0) * 100:.0f}%")
    print(f"   Target Profit: {debug_info.get('target_profit', 0):.4f} USDT")
    print(f"   SL Updated: {'✅' if debug_info.get('sl_updated', False) else '❌'}")
    
    # Проверить, что сохраняется минимум 0.05 USDT
    target_profit = debug_info.get('target_profit', 0)
    if target_profit >= 0.05:
        print(f"   ✅ Сохраняется минимум 0.05 USDT ({target_profit:.4f} USDT)")
    else:
        print(f"   ❌ Сохраняется меньше 0.05 USDT ({target_profit:.4f} USDT)")
    
    print()
    
    # Тест 2: Проверка всех уровней
    print("📊 ТЕСТ 2: Проверка всех уровней")
    test_levels = [0.10, 0.20, 0.30, 0.40]
    expected_keep_pcts = [0.50, 0.60, 0.70, 0.80]
    expected_min_profits = [0.05, 0.12, 0.21, 0.32]
    
    print(f"   {'PnL':<8} {'Level':<6} {'Keep %':<8} {'Min Profit':<12} {'Status':<8}")
    print(f"   {'-'*8} {'-'*6} {'-'*8} {'-'*12} {'-'*8}")
    
    for i, pnl in enumerate(test_levels):
        updated_position = update_trailing_pnl_based(test_position, current_price, pnl, trailing_config)
        debug_info = getattr(updated_position, 'trailing_debug', {})
        
        level = debug_info.get('level', 'N/A')
        keep_pct = debug_info.get('keep_pct', 0) * 100
        target_profit = debug_info.get('target_profit', 0)
        expected_keep = expected_keep_pcts[i] * 100
        expected_min = expected_min_profits[i]
        
        status = "✅" if target_profit >= expected_min else "❌"
        
        print(f"   {pnl:<8.2f} {level:<6} {keep_pct:<8.0f} {target_profit:<12.4f} {status:<8}")
    
    print()
    
    # Тест 3: Проверка логики "50% от 0.10 = 0.05"
    print("📊 ТЕСТ 3: Проверка логики '50% от 0.10 = 0.05'")
    
    pnl = 0.10
    updated_position = update_trailing_pnl_based(test_position, current_price, pnl, trailing_config)
    debug_info = getattr(updated_position, 'trailing_debug', {})
    
    peak_pnl = debug_info.get('peak_pnl', 0)
    keep_pct = debug_info.get('keep_pct', 0)
    target_profit = debug_info.get('target_profit', 0)
    
    expected_target = peak_pnl * keep_pct
    
    print(f"   Peak PnL: {peak_pnl:.2f} USDT")
    print(f"   Keep %: {keep_pct * 100:.0f}%")
    print(f"   Expected Target: {expected_target:.4f} USDT")
    print(f"   Actual Target: {target_profit:.4f} USDT")
    
    if abs(target_profit - expected_target) < 0.001:
        print(f"   ✅ Логика работает правильно: {peak_pnl:.2f} × {keep_pct:.2f} = {target_profit:.4f}")
    else:
        print(f"   ❌ Логика работает неправильно")
    
    print()
    
    # Тест 4: Проверка комиссий
    print("📊 ТЕСТ 4: Проверка покрытия комиссий")
    
    # Комиссии для позиции 21 USDT
    notional_value = 21  # Размер позиции 21 USDT
    taker_fee = 0.0005  # 0.05%
    total_commission = notional_value * taker_fee * 2  # вход + выход
    
    print(f"   Notional Value: {notional_value} USDT")
    print(f"   Taker Fee: {taker_fee * 100:.3f}%")
    print(f"   Total Commission: {total_commission:.4f} USDT")
    print(f"   Activation PnL: {cfg['trailing']['activate_pnl_usdt']} USDT")
    
    if cfg['trailing']['activate_pnl_usdt'] >= total_commission:
        print(f"   ✅ Активация покрывает комиссии")
    else:
        print(f"   ❌ Активация не покрывает комиссии")
    
    # Проверить, что сохраняется минимум после комиссий
    pnl = cfg['trailing']['activate_pnl_usdt']
    updated_position = update_trailing_pnl_based(test_position, current_price, pnl, trailing_config)
    debug_info = getattr(updated_position, 'trailing_debug', {})
    target_profit = debug_info.get('target_profit', 0)
    
    net_profit = target_profit - total_commission
    
    print(f"   Target Profit: {target_profit:.4f} USDT")
    print(f"   Net Profit: {net_profit:.4f} USDT")
    
    if net_profit > 0:
        print(f"   ✅ Чистая прибыль положительная")
    else:
        print(f"   ❌ Чистая прибыль отрицательная")
    
    print()
    
    # Итоговая оценка
    print("🎯 ИТОГОВАЯ ОЦЕНКА ЛОГИКИ:")
    print("-" * 60)
    
    issues = []
    
    # Проверить активацию
    if cfg['trailing']['activate_pnl_usdt'] != 0.10:
        issues.append("Активация должна быть 0.10 USDT")
    
    # Проверить первый уровень
    if cfg['trailing']['level_1_pnl'] != 0.10:
        issues.append("Первый уровень должен быть 0.10 USDT")
    
    # Проверить процент сохранения
    if cfg['trailing']['level_1_keep_pct'] != 0.50:
        issues.append("Процент сохранения должен быть 50%")
    
    # Проверить логику
    pnl = 0.10
    # Сбросить позицию для чистого теста
    test_position.peak_pnl_usdt = 0.0
    updated_position = update_trailing_pnl_based(test_position, current_price, pnl, trailing_config)
    debug_info = getattr(updated_position, 'trailing_debug', {})
    target_profit = debug_info.get('target_profit', 0)
    
    if abs(target_profit - 0.05) > 0.001:
        issues.append(f"50% от 0.10 должно быть 0.05, получено {target_profit:.4f}")
    
    if not issues:
        print("✅ ЛОГИКА ТРЕЙЛИНГА РАБОТАЕТ ПРАВИЛЬНО!")
        print("✅ Активация при 0.10 USDT")
        print("✅ Сохранение 50% = минимум 0.05 USDT")
        print("✅ Все уровни настроены корректно")
    else:
        print("❌ НАЙДЕНЫ ПРОБЛЕМЫ В ЛОГИКЕ:")
        for issue in issues:
            print(f"   - {issue}")

if __name__ == "__main__":
    test_trailing_logic()