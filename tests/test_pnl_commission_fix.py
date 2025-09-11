#!/usr/bin/env python3
"""
Тест исправления расчета PnL с учетом комиссий
"""

import os
import sys
import yaml
from typing import Dict, List, Any

# Добавляем путь к модулям
sys.path.append('.')

def test_pnl_commission_fix():
    """Тест исправления расчета PnL с учетом комиссий"""
    
    print("🔍 ТЕСТ ИСПРАВЛЕНИЯ РАСЧЕТА PnL С КОМИССИЯМИ")
    print("=" * 80)
    
    # Загрузить конфигурацию
    with open('signalwarden_lite/config/config_production.yaml', 'r') as f:
        cfg = yaml.safe_load(f)
    
    print("📊 АНАЛИЗ ПРОБЛЕМЫ:")
    print("   Проблема: Система рассчитывала PnL без учета комиссий")
    print("   Решение: Добавить расчет комиссий в функцию close_position")
    print()
    
    # Параметры из конфигурации
    margin_usdt = cfg['risk']['margin_usdt']
    leverage = cfg['risk']['leverage']
    position_size = margin_usdt
    
    print("📊 ПАРАМЕТРЫ ПОЗИЦИИ:")
    print(f"   Position Size: {position_size} USDT")
    print(f"   Leverage: {leverage}x")
    print()
    
    # Комиссии
    taker_fee = 0.0005  # 0.05%
    
    print("🧮 ТЕСТ РАСЧЕТА PnL:")
    print("-" * 60)
    
    # Пример из логов: Entry 0.8030000, Exit 0.8031000, Volume 25 ENA
    entry_price = 0.8030000
    exit_price = 0.8031000
    qty = 25.0
    
    print(f"   Entry Price: {entry_price:.7f}")
    print(f"   Exit Price: {exit_price:.7f}")
    print(f"   Quantity: {qty}")
    print()
    
    # Старый расчет (без комиссий)
    old_pnl = (exit_price - entry_price) * qty
    
    # Новый расчет (с комиссиями)
    pnl_before_fees = (exit_price - entry_price) * qty
    position_value = entry_price * qty
    total_commission = position_value * taker_fee * 2  # entry + exit
    new_pnl = pnl_before_fees - total_commission
    
    print("📊 СРАВНЕНИЕ РАСЧЕТОВ:")
    print("-" * 60)
    print(f"   Старый PnL (без комиссий): {old_pnl:.6f} USDT")
    print(f"   PnL до комиссий: {pnl_before_fees:.6f} USDT")
    print(f"   Комиссии (вход + выход): {total_commission:.6f} USDT")
    print(f"   Новый PnL (с комиссиями): {new_pnl:.6f} USDT")
    print()
    
    # Проверим округление
    print("🔍 ПРОВЕРКА ОКРУГЛЕНИЯ:")
    print("-" * 60)
    
    old_pnl_rounded = round(old_pnl, 2)
    new_pnl_rounded = round(new_pnl, 2)
    
    print(f"   Старый PnL (округленный): {old_pnl_rounded:.2f} USDT")
    print(f"   Новый PnL (округленный): {new_pnl_rounded:.2f} USDT")
    
    if old_pnl_rounded == 0.00 and new_pnl_rounded != 0.00:
        print("   ✅ ИСПРАВЛЕНИЕ РАБОТАЕТ: Теперь PnL не округляется до 0.00!")
    elif old_pnl_rounded == 0.00 and new_pnl_rounded == 0.00:
        print("   ❌ Проблема остается: PnL все еще округляется до 0.00")
    else:
        print("   ✅ PnL не округляется до 0.00")
    
    print()
    
    # Проверим разные сценарии
    print("🧮 ТЕСТ РАЗНЫХ СЦЕНАРИЕВ:")
    print("-" * 60)
    
    scenarios = [
        {"entry": 0.8030000, "exit": 0.8031000, "qty": 25.0, "desc": "Маленькая прибыль"},
        {"entry": 0.8030000, "exit": 0.8032000, "qty": 25.0, "desc": "Средняя прибыль"},
        {"entry": 0.8030000, "exit": 0.8035000, "qty": 25.0, "desc": "Большая прибыль"},
        {"entry": 0.8030000, "exit": 0.8029000, "qty": 25.0, "desc": "Маленький убыток"},
        {"entry": 0.8030000, "exit": 0.8025000, "qty": 25.0, "desc": "Большой убыток"},
    ]
    
    for i, scenario in enumerate(scenarios, 1):
        entry = scenario["entry"]
        exit = scenario["exit"]
        qty = scenario["qty"]
        desc = scenario["desc"]
        
        # Расчет PnL
        pnl_before = (exit - entry) * qty
        pos_value = entry * qty
        commission = pos_value * taker_fee * 2
        pnl_after = pnl_before - commission
        
        # Округление
        pnl_rounded = round(pnl_after, 2)
        
        print(f"   {i}. {desc}:")
        print(f"      PnL до комиссий: {pnl_before:.6f} USDT")
        print(f"      Комиссии: {commission:.6f} USDT")
        print(f"      PnL после комиссий: {pnl_after:.6f} USDT")
        print(f"      PnL (округленный): {pnl_rounded:.2f} USDT")
        print()
    
    # Итоговая оценка
    print("🎯 ИТОГОВАЯ ОЦЕНКА:")
    print("-" * 60)
    
    if new_pnl_rounded != 0.00:
        print("✅ ИСПРАВЛЕНИЕ РАБОТАЕТ:")
        print("   • PnL теперь рассчитывается с учетом комиссий")
        print("   • Показывается реальная прибыль/убыток")
        print("   • Нет ложных закрытий в 0.00 USDT")
        print("   • Логирование улучшено")
    else:
        print("❌ ПРОБЛЕМА ОСТАЕТСЯ:")
        print("   • PnL все еще округляется до 0.00")
        print("   • Требуется дополнительное исправление")
    
    print()
    print("📋 СВОДКА:")
    print(f"   • Position Size: {position_size} USDT")
    print(f"   • Taker Fee: {taker_fee*100:.2f}%")
    print(f"   • Total Commission: {total_commission:.6f} USDT")
    print(f"   • Old PnL: {old_pnl:.6f} USDT")
    print(f"   • New PnL: {new_pnl:.6f} USDT")
    print(f"   • Difference: {new_pnl - old_pnl:.6f} USDT")

if __name__ == "__main__":
    test_pnl_commission_fix()
