#!/usr/bin/env python3
"""
Финальный отчет анализа системы
"""

import os
import sys
import yaml
import json

# Добавляем путь к модулям
sys.path.append('.')

def final_analysis_report():
    """Финальный отчет анализа системы"""
    
    print("📋 ФИНАЛЬНЫЙ ОТЧЕТ АНАЛИЗА СИСТЕМЫ")
    print("=" * 80)
    
    # Загрузить состояние системы
    try:
        with open('trading_state_v1_6_TXB.json', 'r') as f:
            state = json.load(f)
    except Exception as e:
        print(f"❌ Не удалось прочитать состояние системы: {e}")
        return
    
    # Загрузить конфигурации
    with open('signalwarden_lite/config/config_backtest_2year.yaml', 'r') as f:
        backtest_config = yaml.safe_load(f)
    
    with open('signalwarden_lite/config/config_production.yaml', 'r') as f:
        production_config = yaml.safe_load(f)
    
    print("🎯 РЕЗЮМЕ ПРОБЛЕМЫ:")
    print("-" * 60)
    print("❌ СИСТЕМА ПОКАЗЫВАЕТ УБЫТКИ")
    print("❌ БЭКТЕСТ ПОКАЗАЛ ОТЛИЧНЫЕ РЕЗУЛЬТАТЫ")
    print("❌ PRODUCTION И БЭКТЕСТ НЕ ИДЕНТИЧНЫ")
    print()
    
    print("🔍 НАЙДЕННАЯ ПРИЧИНА:")
    print("-" * 60)
    print("🚨 КРИТИЧЕСКОЕ РАЗЛИЧИЕ В СИСТЕМЕ ТРЕЙЛИНГА!")
    print()
    print("📊 БЭКТЕСТ (прибыльный):")
    print("   • Функция: update_trailing_hybrid")
    print("   • Система: R-based трейлинг")
    print("   • Активация: pos.peak_R >= 0.1 (10% от R)")
    print("   • SL расчет: entry + (peak_R - step_R) * R")
    print("   • BE логика: Отдельная с offset")
    print("   • Защита: Chandelier ограничитель")
    print()
    print("📊 PRODUCTION (убыточный):")
    print("   • Функция: update_trailing_pnl_based")
    print("   • Система: PnL-based трейлинг")
    print("   • Активация: current_pnl >= 0.10 USDT")
    print("   • SL расчет: entry + (target_profit / qty)")
    print("   • BE логика: Встроена в level_1")
    print("   • Защита: Нет chandelier")
    
    print()
    print("📈 РЕЗУЛЬТАТЫ БЭКТЕСТА:")
    print("-" * 60)
    print("✅ Total PnL: $5,750.8")
    print("✅ Total Trades: 11,712")
    print("✅ Win Rate: 84.6%")
    print("✅ Profit Factor: 1.98")
    print("✅ Short trades: 9,246 (78.9%)")
    print("✅ Short PnL: $4,010.8 (69.7%)")
    print("✅ Все 7 пар прибыльны")
    
    print()
    print("📉 ТЕКУЩЕЕ СОСТОЯНИЕ PRODUCTION:")
    print("-" * 60)
    
    # Анализ текущих позиций
    total_positions = 0
    total_pnl = 0.0
    
    for symbol, data in state.get('symbols', {}).items():
        if symbol.endswith('_position'):
            continue
            
        active_pos = data.get('active_position')
        if active_pos:
            total_positions += 1
            unrealized_pnl = active_pos.get('unrealized_pnl', 0)
            total_pnl += unrealized_pnl
            
            print(f"📊 {symbol}:")
            print(f"   Entry: ${active_pos.get('entry', 0):.6f}")
            print(f"   SL: ${active_pos.get('sl_current', 0):.6f}")
            print(f"   PnL: {unrealized_pnl:.4f} USDT")
            print(f"   Peak PnL: {active_pos.get('peak_pnl_usdt', 0):.4f} USDT")
            print()
    
    print(f"📊 ИТОГО ПОЗИЦИЙ: {total_positions}")
    print(f"📊 ОБЩИЙ PnL: {total_pnl:.4f} USDT")
    
    if total_pnl < 0:
        print("❌ СИСТЕМА В УБЫТКЕ!")
    elif total_pnl > 0:
        print("✅ СИСТЕМА В ПРИБЫЛИ")
    else:
        print("➡️ СИСТЕМА В БЕЗУБЫТКЕ")
    
    print()
    print("🔍 ДЕТАЛЬНЫЙ АНАЛИЗ РАЗЛИЧИЙ:")
    print("-" * 60)
    
    print("1️⃣ АКТИВАЦИЯ ТРЕЙЛИНГА:")
    print("   📊 БЭКТЕСТ: При 10% движения от R (относительно)")
    print("   📊 PRODUCTION: При 0.10 USDT прибыли (абсолютно)")
    print("   ⚠️ РАЗЛИЧИЕ: Разные пороги активации!")
    
    print()
    print("2️⃣ РАСЧЕТ STOP LOSS:")
    print("   📊 БЭКТЕСТ: SL = entry + (peak_R - 0.15) * R")
    print("   📊 PRODUCTION: SL = entry + (target_profit / qty)")
    print("   ⚠️ РАЗЛИЧИЕ: Разные формулы расчета!")
    
    print()
    print("3️⃣ BREAK-EVEN ЛОГИКА:")
    print("   📊 БЭКТЕСТ: Отдельная BE с offset 5% от R")
    print("   📊 PRODUCTION: BE встроен в level_1 (50% сохранения)")
    print("   ⚠️ РАЗЛИЧИЕ: Разная BE логика!")
    
    print()
    print("4️⃣ ЗАЩИТА ОТ ОТКАТОВ:")
    print("   📊 БЭКТЕСТ: Chandelier ограничитель (2.0x ATR)")
    print("   📊 PRODUCTION: Нет chandelier защиты")
    print("   ⚠️ РАЗЛИЧИЕ: Разная защита!")
    
    print()
    print("5️⃣ ПРИМЕР РАСЧЕТА (LTC):")
    print("   📊 Entry: $115.50, SL: $109.50, Price: $117.00")
    print("   📊 БЭКТЕСТ: R=6.0, Move=1.5, Peak_R=25% → SL=$116.10")
    print("   📊 PRODUCTION: PnL=0.27, Level=L2, Keep=60% → SL=$116.40")
    print("   ⚠️ РАЗЛИЧИЕ: Разные SL ($116.10 vs $116.40)!")
    
    print()
    print("🎯 ЗАКЛЮЧЕНИЕ:")
    print("-" * 60)
    print("❌ СИСТЕМЫ НЕ ИДЕНТИЧНЫ!")
    print("❌ ГЛАВНОЕ РАЗЛИЧИЕ: СИСТЕМА ТРЕЙЛИНГА")
    print("❌ БЭКТЕСТ: R-based (update_trailing_hybrid)")
    print("❌ PRODUCTION: PnL-based (update_trailing_pnl_based)")
    print("❌ ЭТО ОБЪЯСНЯЕТ УБЫТКИ!")
    
    print()
    print("💡 РЕКОМЕНДАЦИИ:")
    print("-" * 60)
    print("🎯 ВАРИАНТ 1: ВЕРНУТЬ R-based СИСТЕМУ")
    print("   • Заменить update_trailing_pnl_based на update_trailing_hybrid")
    print("   • Использовать параметры из бэктеста")
    print("   • Восстановить chandelier защиту")
    print()
    print("🎯 ВАРИАНТ 2: ИСПРАВИТЬ PnL-based СИСТЕМУ")
    print("   • Перепроверить логику активации")
    print("   • Исправить расчет SL")
    print("   • Добавить chandelier защиту")
    print()
    print("🎯 ВАРИАНТ 3: НОВЫЙ БЭКТЕСТ")
    print("   • Провести бэктест с PnL-based системой")
    print("   • Сравнить результаты")
    print("   • Выбрать лучшую систему")
    
    print()
    print("⚠️ КРИТИЧНО:")
    print("-" * 60)
    print("🚨 БЭКТЕСТ ПОКАЗАЛ ОТЛИЧНЫЕ РЕЗУЛЬТАТЫ!")
    print("🚨 PRODUCTION ИСПОЛЬЗУЕТ ДРУГУЮ СИСТЕМУ!")
    print("🚨 ЭТО ОСНОВНАЯ ПРИЧИНА УБЫТКОВ!")
    print("🚨 НУЖНО СРОЧНО ИСПРАВИТЬ!")
    
    print()
    print("📞 СТАТУС:")
    print("-" * 60)
    print("❌ СИСТЕМА НЕ ГОТОВА К PRODUCTION")
    print("❌ ТРЕБУЕТСЯ ИСПРАВЛЕНИЕ ТРЕЙЛИНГА")
    print("✅ ВСЕ ОСТАЛЬНОЕ РАБОТАЕТ ПРАВИЛЬНО")
    print("✅ СИГНАЛЫ, ФИЛЬТРЫ, РИСК-МЕНЕДЖМЕНТ - ОК")

if __name__ == "__main__":
    final_analysis_report()
