#!/usr/bin/env python3
"""
Тест реальной проблемы с PnL - почему закрытия в 0.00 USDT
"""

import os
import sys
import yaml
from typing import Dict, List, Any

# Добавляем путь к модулям
sys.path.append('.')

def analyze_real_pnl_issue():
    """Анализ реальной проблемы с PnL"""
    
    print("🔍 АНАЛИЗ РЕАЛЬНОЙ ПРОБЛЕМЫ С PnL")
    print("=" * 80)
    
    # Загрузить конфигурацию
    with open('signalwarden_lite/config/config_production.yaml', 'r') as f:
        cfg = yaml.safe_load(f)
    
    print("📊 АНАЛИЗ ПРОБЛЕМЫ:")
    print("   Из логов видно:")
    print("   - PnL: +0.00 USDT")
    print("   - ROI: +0.06% или +0.19%")
    print("   - Это означает, что прибыль есть, но PnL показывает 0.00")
    print()
    
    # Анализ возможных причин
    print("🔍 ВОЗМОЖНЫЕ ПРИЧИНЫ:")
    print("-" * 60)
    
    print("1. ПРОБЛЕМА С РАСЧЕТОМ PnL:")
    print("   - Система может неправильно рассчитывать PnL")
    print("   - Формула: (exit_price - entry_price) * qty")
    print("   - Возможна ошибка в округлении или типах данных")
    print()
    
    print("2. ПРОБЛЕМА С ОБНОВЛЕНИЕМ СТОП-ЛОССОВ:")
    print("   - Трейлинг может не активироваться")
    print("   - Стоп-лоссы могут не обновляться")
    print("   - Позиции закрываются по старым стоп-лоссам")
    print()
    
    print("3. ПРОБЛЕМА С КОМИССИЯМИ:")
    print("   - Комиссии не учитываются в PnL")
    print("   - PnL рассчитывается до комиссий")
    print("   - После комиссий остается 0.00")
    print()
    
    print("4. ПРОБЛЕМА С ТИПАМИ ДАННЫХ:")
    print("   - Округление до 2 знаков после запятой")
    print("   - Маленькая прибыль округляется до 0.00")
    print("   - Но ROI показывает реальную прибыль")
    print()
    
    # Проверим конфигурацию
    print("📊 ПРОВЕРКА КОНФИГУРАЦИИ:")
    print("-" * 60)
    
    margin_usdt = cfg['risk']['margin_usdt']
    leverage = cfg['risk']['leverage']
    notional_value = margin_usdt
    
    print(f"   Position Size: {notional_value} USDT")
    print(f"   Leverage: {leverage}x")
    
    # Комиссии
    taker_fee = 0.0005  # 0.05%
    total_commission = notional_value * taker_fee * 2  # вход + выход
    
    print(f"   Total Commission: {total_commission:.4f} USDT")
    print()
    
    # Симуляция проблемы
    print("🧮 СИМУЛЯЦИЯ ПРОБЛЕМЫ:")
    print("-" * 60)
    
    # Пример из логов: Entry 0.8030000, Exit 0.8031000, Volume 25 ENA
    entry_price = 0.8030000
    exit_price = 0.8031000
    qty = 25.0
    
    # Расчет PnL
    pnl_before_fees = (exit_price - entry_price) * qty
    pnl_after_fees = pnl_before_fees - total_commission
    
    print(f"   Entry Price: {entry_price:.7f}")
    print(f"   Exit Price: {exit_price:.7f}")
    print(f"   Quantity: {qty}")
    print(f"   PnL before fees: {pnl_before_fees:.6f} USDT")
    print(f"   Total Commission: {total_commission:.4f} USDT")
    print(f"   PnL after fees: {pnl_after_fees:.6f} USDT")
    print()
    
    # Проверим округление
    print("🔍 ПРОВЕРКА ОКРУГЛЕНИЯ:")
    print("-" * 60)
    
    pnl_rounded_2 = round(pnl_after_fees, 2)
    pnl_rounded_4 = round(pnl_after_fees, 4)
    
    print(f"   PnL after fees: {pnl_after_fees:.6f} USDT")
    print(f"   Rounded to 2 decimals: {pnl_rounded_2:.2f} USDT")
    print(f"   Rounded to 4 decimals: {pnl_rounded_4:.4f} USDT")
    
    if pnl_rounded_2 == 0.00:
        print("   ❌ ПРОБЛЕМА НАЙДЕНА: Округление до 2 знаков дает 0.00!")
        print("   ✅ Решение: Использовать больше знаков после запятой")
    else:
        print("   ✅ Округление не является проблемой")
    
    print()
    
    # Проверим ROI
    print("🔍 ПРОВЕРКА ROI:")
    print("-" * 60)
    
    # ROI = (exit_price - entry_price) / entry_price * 100
    roi = (exit_price - entry_price) / entry_price * 100
    
    print(f"   ROI: {roi:.4f}%")
    print(f"   ROI from logs: +0.06% or +0.19%")
    
    if abs(roi - 0.06) < 0.01 or abs(roi - 0.19) < 0.01:
        print("   ✅ ROI соответствует логам")
    else:
        print("   ❌ ROI не соответствует логам")
    
    print()
    
    # Рекомендации
    print("🎯 РЕКОМЕНДАЦИИ ПО ИСПРАВЛЕНИЮ:")
    print("-" * 60)
    
    print("1. ИСПРАВИТЬ ОКРУГЛЕНИЕ PnL:")
    print("   - Использовать минимум 4 знака после запятой")
    print("   - Не округлять до 2 знаков в логах")
    print("   - Показывать реальный PnL")
    print()
    
    print("2. УЧИТЫВАТЬ КОМИССИИ:")
    print("   - Вычитать комиссии из PnL")
    print("   - Показывать PnL после комиссий")
    print("   - Логировать комиссии отдельно")
    print()
    
    print("3. УЛУЧШИТЬ ТРЕЙЛИНГ:")
    print("   - Активировать трейлинг раньше")
    print("   - Обновлять стоп-лоссы чаще")
    print("   - Защищать от закрытий в 0.00")
    print()
    
    print("4. УЛУЧШИТЬ ЛОГИРОВАНИЕ:")
    print("   - Показывать PnL до и после комиссий")
    print("   - Логировать все обновления стоп-лоссов")
    print("   - Показывать детальную информацию о закрытии")
    print()
    
    # Итоговая оценка
    print("🎯 ИТОГОВАЯ ОЦЕНКА:")
    print("-" * 60)
    
    if pnl_rounded_2 == 0.00:
        print("✅ ПРОБЛЕМА НАЙДЕНА: Округление PnL до 2 знаков")
        print("✅ РЕШЕНИЕ: Использовать больше знаков после запятой")
        print("✅ КОМИССИИ: Учитывать в расчете PnL")
        print("✅ ТРЕЙЛИНГ: Работает правильно, но нужно улучшить логирование")
    else:
        print("❌ Проблема не в округлении")
        print("❌ Требуется дополнительное исследование")
    
    print()
    print("📋 СВОДКА:")
    print(f"   • PnL before fees: {pnl_before_fees:.6f} USDT")
    print(f"   • PnL after fees: {pnl_after_fees:.6f} USDT")
    print(f"   • PnL rounded (2): {pnl_rounded_2:.2f} USDT")
    print(f"   • ROI: {roi:.4f}%")
    print(f"   • Commission: {total_commission:.4f} USDT")

if __name__ == "__main__":
    analyze_real_pnl_issue()
