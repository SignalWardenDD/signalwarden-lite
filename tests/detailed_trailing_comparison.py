#!/usr/bin/env python3
"""
Детальное сравнение систем трейлинга
"""

import os
import sys
import yaml

# Добавляем путь к модулям
sys.path.append('.')

def detailed_trailing_comparison():
    """Детальное сравнение систем трейлинга"""
    
    print("🔍 ДЕТАЛЬНОЕ СРАВНЕНИЕ СИСТЕМ ТРЕЙЛИНГА")
    print("=" * 80)
    
    # Загрузить конфигурации
    with open('signalwarden_lite/config/config_backtest_2year.yaml', 'r') as f:
        backtest_config = yaml.safe_load(f)
    
    with open('signalwarden_lite/config/config_production.yaml', 'r') as f:
        production_config = yaml.safe_load(f)
    
    print("📊 СИСТЕМА ТРЕЙЛИНГА В БЭКТЕСТЕ:")
    print("-" * 60)
    print("🔧 ФУНКЦИЯ: update_trailing_hybrid (R-based система)")
    print("📋 ПАРАМЕТРЫ:")
    
    backtest_trailing = backtest_config.get('trailing', {})
    for key, value in backtest_trailing.items():
        print(f"   {key}: {value}")
    
    print()
    print("📊 СИСТЕМА ТРЕЙЛИНГА В PRODUCTION:")
    print("-" * 60)
    print("🔧 ФУНКЦИЯ: update_trailing_pnl_based (PnL-based система)")
    print("📋 ПАРАМЕТРЫ:")
    
    production_trailing = production_config.get('trailing', {})
    for key, value in production_trailing.items():
        if key.startswith('level_') or key.startswith('activate_pnl'):
            print(f"   {key}: {value}")
    
    print()
    print("🚨 КРИТИЧЕСКИЕ РАЗЛИЧИЯ:")
    print("-" * 60)
    
    print("1️⃣ ЛОГИКА АКТИВАЦИИ:")
    print("   📊 БЭКТЕСТ (R-based):")
    print("      • Активация: pos.peak_R >= cfg.activate_R")
    print("      • peak_R = move / r_unit (движение в R)")
    print("      • activate_R = 0.1 (10% от R)")
    print("      • R = entry - sl_initial (риск на сделку)")
    print()
    print("   📊 PRODUCTION (PnL-based):")
    print("      • Активация: current_pnl_usdt >= cfg.activate_pnl_usdt")
    print("      • current_pnl_usdt = (price - entry) * qty")
    print("      • activate_pnl_usdt = 0.10 (10 USDT)")
    print("      • Абсолютное значение в USDT")
    
    print()
    print("2️⃣ ЛОГИКА РАСЧЕТА SL:")
    print("   📊 БЭКТЕСТ (R-based):")
    print("      • new_sl_r = pos.peak_R - cfg.step_R")
    print("      • step_sl = pos.entry + new_sl_r * r_unit")
    print("      • step_R = 0.15 (15% от R)")
    print("      • SL привязан к entry и R")
    print()
    print("   📊 PRODUCTION (PnL-based):")
    print("      • target_profit = peak_pnl * keep_pct")
    print("      • new_sl = entry + (target_profit / qty)")
    print("      • keep_pct = 50%/60%/70%/80%")
    print("      • SL привязан к entry и target profit")
    
    print()
    print("3️⃣ BREAK-EVEN ЛОГИКА:")
    print("   📊 БЭКТЕСТ (R-based):")
    print("      • BE активация: pos.peak_R >= cfg.move_to_be_at_R")
    print("      • move_to_be_at_R = 0.1 (10% от R)")
    print("      • be_offset_R = 0.05 (5% от R)")
    print("      • BE = entry + be_offset_R * r_unit")
    print()
    print("   📊 PRODUCTION (PnL-based):")
    print("      • НЕТ отдельной BE логики")
    print("      • BE встроен в level_1_pnl = 0.10")
    print("      • level_1_keep_pct = 0.50 (50%)")
    print("      • Минимальная прибыль = 0.05 USDT")
    
    print()
    print("4️⃣ CHANDELIER ОГРАНИЧИТЕЛЬ:")
    print("   📊 БЭКТЕСТ (R-based):")
    print("      • chandelier_sl = hi - cfg.chandelier_k_atr * atr")
    print("      • chandelier_k_atr = 2.0")
    print("      • Дополнительная защита от откатов")
    print()
    print("   📊 PRODUCTION (PnL-based):")
    print("      • НЕТ chandelier ограничителя")
    print("      • Только PnL-based логика")
    print("      • Меньше защиты от откатов")
    
    print()
    print("🧮 ПРИМЕР РАСЧЕТА:")
    print("-" * 60)
    
    # Пример для LTC позиции
    entry = 115.50
    sl_initial = 109.50
    qty = 0.18
    current_price = 117.0
    
    print("📊 ТЕСТОВЫЕ ДАННЫЕ (LTC):")
    print(f"   Entry: ${entry:.2f}")
    print(f"   SL Initial: ${sl_initial:.2f}")
    print(f"   Quantity: {qty:.2f}")
    print(f"   Current Price: ${current_price:.2f}")
    print()
    
    # R-based расчет
    r_unit = entry - sl_initial  # 6.0
    move = current_price - entry  # 1.5
    peak_R = move / r_unit  # 0.25 (25% от R)
    current_pnl = move * qty  # 0.27 USDT
    
    print("📊 R-based СИСТЕМА (БЭКТЕСТ):")
    print(f"   R Unit: ${r_unit:.2f}")
    print(f"   Move: ${move:.2f}")
    print(f"   Peak R: {peak_R:.2f} ({peak_R*100:.0f}%)")
    print(f"   Current PnL: ${current_pnl:.2f} USDT")
    print()
    
    # Проверка активации R-based
    activate_R = 0.1
    move_to_be_at_R = 0.1
    
    if peak_R >= activate_R:
        print("   ✅ R-based ТРЕЙЛИНГ АКТИВЕН")
        new_sl_r = peak_R - 0.15  # step_R
        step_sl = entry + new_sl_r * r_unit
        print(f"   New SL: ${step_sl:.2f}")
        
        if peak_R >= move_to_be_at_R:
            be_price = entry + 0.05 * r_unit  # be_offset_R
            print(f"   BE Price: ${be_price:.2f}")
    else:
        print("   ❌ R-based ТРЕЙЛИНГ НЕ АКТИВЕН")
    
    print()
    
    # PnL-based расчет
    activate_pnl_usdt = 0.10
    
    print("📊 PnL-based СИСТЕМА (PRODUCTION):")
    print(f"   Current PnL: ${current_pnl:.2f} USDT")
    print(f"   Activate Threshold: ${activate_pnl_usdt:.2f} USDT")
    print()
    
    if current_pnl >= activate_pnl_usdt:
        print("   ✅ PnL-based ТРЕЙЛИНГ АКТИВЕН")
        
        # Определяем уровень
        if current_pnl >= 0.20:
            level_pnl = 0.20
            keep_pct = 0.60
            level_name = "L2"
        else:
            level_pnl = 0.10
            keep_pct = 0.50
            level_name = "L1"
        
        target_profit = current_pnl * keep_pct
        new_sl = entry + (target_profit / qty)
        
        print(f"   Level: {level_name}")
        print(f"   Keep %: {keep_pct*100:.0f}%")
        print(f"   Target Profit: ${target_profit:.2f} USDT")
        print(f"   New SL: ${new_sl:.2f}")
    else:
        print("   ❌ PnL-based ТРЕЙЛИНГ НЕ АКТИВЕН")
    
    print()
    print("🎯 КЛЮЧЕВЫЕ РАЗЛИЧИЯ:")
    print("-" * 60)
    
    print("1️⃣ АКТИВАЦИЯ:")
    print("   • R-based: Активируется при 10% движения от R")
    print("   • PnL-based: Активируется при 0.10 USDT прибыли")
    print("   • РАЗЛИЧИЕ: Разные пороги активации!")
    
    print()
    print("2️⃣ РАСЧЕТ SL:")
    print("   • R-based: SL = entry + (peak_R - step_R) * R")
    print("   • PnL-based: SL = entry + (target_profit / qty)")
    print("   • РАЗЛИЧИЕ: Разные формулы расчета!")
    
    print()
    print("3️⃣ BREAK-EVEN:")
    print("   • R-based: Отдельная BE логика с offset")
    print("   • PnL-based: BE встроен в level_1")
    print("   • РАЗЛИЧИЕ: Разная BE логика!")
    
    print()
    print("4️⃣ ЗАЩИТА:")
    print("   • R-based: Chandelier ограничитель")
    print("   • PnL-based: Нет chandelier")
    print("   • РАЗЛИЧИЕ: Разная защита от откатов!")
    
    print()
    print("🚨 ВЫВОД:")
    print("-" * 60)
    print("❌ СИСТЕМЫ ТРЕЙЛИНГА КАРДИНАЛЬНО РАЗЛИЧНЫ!")
    print("❌ БЭКТЕСТ: R-based система (update_trailing_hybrid)")
    print("❌ PRODUCTION: PnL-based система (update_trailing_pnl_based)")
    print("❌ ЭТО ОБЪЯСНЯЕТ УБЫТКИ В PRODUCTION!")
    print()
    print("💡 РЕШЕНИЕ:")
    print("   • Либо вернуть R-based систему")
    print("   • Либо перепроверить PnL-based систему")
    print("   • Либо провести новый бэктест с PnL-based")

if __name__ == "__main__":
    detailed_trailing_comparison()
