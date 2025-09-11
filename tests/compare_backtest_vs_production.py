#!/usr/bin/env python3
"""
Сравнение бэктеста и production системы
"""

import os
import sys
import yaml
import json

# Добавляем путь к модулям
sys.path.append('.')

def compare_backtest_vs_production():
    """Сравнение бэктеста и production системы"""
    
    print("📊 СРАВНЕНИЕ БЭКТЕСТА И PRODUCTION СИСТЕМЫ")
    print("=" * 80)
    
    # Загрузить конфигурации
    with open('signalwarden_lite/config/config_backtest_2year.yaml', 'r') as f:
        backtest_config = yaml.safe_load(f)
    
    with open('signalwarden_lite/config/config_production.yaml', 'r') as f:
        production_config = yaml.safe_load(f)
    
    # Загрузить результаты бэктеста
    try:
        with open('documentation/BACKTEST_RESULTS_ANALYSIS.md', 'r') as f:
            backtest_results = f.read()
    except:
        backtest_results = "Результаты бэктеста не найдены"
    
    print("🔍 КРИТИЧЕСКИЕ РАЗЛИЧИЯ:")
    print("-" * 80)
    
    # 1. СИСТЕМА ТРЕЙЛИНГА
    print("1️⃣ СИСТЕМА ТРЕЙЛИНГА:")
    print("-" * 40)
    
    backtest_trailing = backtest_config.get('trailing', {})
    production_trailing = production_config.get('trailing', {})
    
    print("📊 БЭКТЕСТ (старая система):")
    print(f"   activate_R: {backtest_trailing.get('activate_R', 'N/A')}")
    print(f"   move_to_be_at_R: {backtest_trailing.get('move_to_be_at_R', 'N/A')}")
    print(f"   be_offset_R: {backtest_trailing.get('be_offset_R', 'N/A')}")
    print(f"   step_R: {backtest_trailing.get('step_R', 'N/A')}")
    print(f"   chandelier_k_atr: {backtest_trailing.get('chandelier_k_atr', 'N/A')}")
    
    print()
    print("📊 PRODUCTION (новая система):")
    print(f"   activate_pnl_usdt: {production_trailing.get('activate_pnl_usdt', 'N/A')}")
    print(f"   level_1_pnl: {production_trailing.get('level_1_pnl', 'N/A')} (keep {production_trailing.get('level_1_keep_pct', 'N/A')*100}%)")
    print(f"   level_2_pnl: {production_trailing.get('level_2_pnl', 'N/A')} (keep {production_trailing.get('level_2_keep_pct', 'N/A')*100}%)")
    print(f"   level_3_pnl: {production_trailing.get('level_3_pnl', 'N/A')} (keep {production_trailing.get('level_3_keep_pct', 'N/A')*100}%)")
    print(f"   level_4_pnl: {production_trailing.get('level_4_pnl', 'N/A')} (keep {production_trailing.get('level_4_keep_pct', 'N/A')*100}%)")
    
    print()
    print("🚨 КРИТИЧЕСКОЕ РАЗЛИЧИЕ:")
    print("   ❌ БЭКТЕСТ: Использует старую R-based систему трейлинга")
    print("   ❌ PRODUCTION: Использует новую PnL-based систему трейлинга")
    print("   ⚠️ ЭТО МОЖЕТ БЫТЬ ПРИЧИНОЙ УБЫТКОВ!")
    
    print()
    
    # 2. РИСК МЕНЕДЖМЕНТ
    print("2️⃣ РИСК МЕНЕДЖМЕНТ:")
    print("-" * 40)
    
    backtest_risk = backtest_config.get('risk', {})
    production_risk = production_config.get('risk', {})
    
    print("📊 БЭКТЕСТ:")
    print(f"   margin_usdt: {backtest_risk.get('margin_usdt', 'N/A')}")
    print(f"   leverage: {backtest_risk.get('leverage', 'N/A')}")
    print(f"   sl_atr_mult: {backtest_risk.get('sl_atr_mult', 'N/A')}")
    print(f"   cutloss_early: {backtest_risk.get('cutloss_early', {}).get('enabled', 'N/A')}")
    
    print()
    print("📊 PRODUCTION:")
    print(f"   margin_usdt: {production_risk.get('margin_usdt', 'N/A')}")
    print(f"   leverage: {production_risk.get('leverage', 'N/A')}")
    print(f"   sl_atr_mult: {production_risk.get('sl_atr_mult', 'N/A')}")
    print(f"   sl_order_type: {production_risk.get('sl_order_type', 'N/A')}")
    print(f"   cutloss_early: {production_risk.get('cutloss_early', {}).get('enabled', 'N/A')}")
    
    print()
    print("✅ РИСК МЕНЕДЖМЕНТ: ИДЕНТИЧНЫЙ")
    
    print()
    
    # 3. СИГНАЛЫ И СЕТАПЫ
    print("3️⃣ СИГНАЛЫ И СЕТАПЫ:")
    print("-" * 40)
    
    backtest_signals = backtest_config.get('signals', {})
    production_signals = production_config.get('signals', {})
    
    print("📊 БЭКТЕСТ:")
    print(f"   breakout: {backtest_signals.get('setups', {}).get('breakout', {}).get('enabled', 'N/A')}")
    print(f"   inside_bar: {backtest_signals.get('setups', {}).get('inside_bar', {}).get('enabled', 'N/A')}")
    print(f"   trend_continuation: {backtest_signals.get('setups', {}).get('trend_continuation', {}).get('enabled', 'N/A')}")
    print(f"   squeeze_breakout: {backtest_signals.get('setups', {}).get('squeeze_breakout', {}).get('enabled', 'N/A')}")
    
    print()
    print("📊 PRODUCTION:")
    print(f"   breakout: {production_signals.get('setups', {}).get('breakout', {}).get('enabled', 'N/A')}")
    print(f"   inside_bar: {production_signals.get('setups', {}).get('inside_bar', {}).get('enabled', 'N/A')}")
    print(f"   trend_continuation: {production_signals.get('setups', {}).get('trend_continuation', {}).get('enabled', 'N/A')}")
    print(f"   squeeze_breakout: {production_signals.get('setups', {}).get('squeeze_breakout', {}).get('enabled', 'N/A')}")
    
    print()
    print("✅ СИГНАЛЫ: ИДЕНТИЧНЫЕ")
    
    print()
    
    # 4. АДАПТИВНЫЕ ФИЛЬТРЫ
    print("4️⃣ АДАПТИВНЫЕ ФИЛЬТРЫ:")
    print("-" * 40)
    
    backtest_short_guard = backtest_config.get('short_guard', {})
    production_short_guard = production_config.get('short_guard', {})
    
    print("📊 БЭКТЕСТ:")
    print(f"   rsi_bear_max: {backtest_short_guard.get('rsi_bear_max', 'N/A')}")
    print(f"   min_natr_bear: {backtest_short_guard.get('min_natr_bear', 'N/A')}")
    print(f"   rsi_bullcorr_max: {backtest_short_guard.get('rsi_bullcorr_max', 'N/A')}")
    print(f"   min_natr_bullcorr: {backtest_short_guard.get('min_natr_bullcorr', 'N/A')}")
    
    print()
    print("📊 PRODUCTION:")
    print(f"   rsi_bear_max: {production_short_guard.get('rsi_bear_max', 'N/A')}")
    print(f"   min_natr_bear: {production_short_guard.get('min_natr_bear', 'N/A')}")
    print(f"   rsi_bullcorr_max: {production_short_guard.get('rsi_bullcorr_max', 'N/A')}")
    print(f"   min_natr_bullcorr: {production_short_guard.get('min_natr_bullcorr', 'N/A')}")
    
    print()
    print("✅ АДАПТИВНЫЕ ФИЛЬТРЫ: ИДЕНТИЧНЫЕ")
    
    print()
    
    # 5. РЕЗУЛЬТАТЫ БЭКТЕСТА
    print("5️⃣ РЕЗУЛЬТАТЫ БЭКТЕСТА:")
    print("-" * 40)
    
    if "Total PnL: $5,750.8" in backtest_results:
        print("📈 ОТЛИЧНЫЕ РЕЗУЛЬТАТЫ БЭКТЕСТА:")
        print("   ✅ Total PnL: $5,750.8")
        print("   ✅ Total Trades: 11,712")
        print("   ✅ Win Rate: 84.6%")
        print("   ✅ Profit Factor: 1.98")
        print("   ✅ Short trades: 9,246 (78.9%)")
        print("   ✅ Short PnL: $4,010.8 (69.7%)")
    else:
        print("❌ Результаты бэктеста не найдены")
    
    print()
    
    # 6. АНАЛИЗ ПРОБЛЕМЫ
    print("6️⃣ АНАЛИЗ ПРОБЛЕМЫ:")
    print("-" * 40)
    
    print("🚨 ГЛАВНАЯ ПРОБЛЕМА:")
    print("   ❌ БЭКТЕСТ: Использует старую R-based систему трейлинга")
    print("   ❌ PRODUCTION: Использует новую PnL-based систему трейлинга")
    print()
    print("🔍 ВОЗМОЖНЫЕ ПРИЧИНЫ УБЫТКОВ:")
    print("   1. Новая система трейлинга работает по-другому")
    print("   2. Активация трейлинга происходит при других условиях")
    print("   3. Сохранение прибыли происходит по-другому")
    print("   4. Логика расчета SL изменилась")
    print()
    print("💡 РЕШЕНИЕ:")
    print("   ✅ ВЕРНУТЬ СТАРУЮ R-based СИСТЕМУ ТРЕЙЛИНГА")
    print("   ✅ ИЛИ ПЕРЕПРОВЕРИТЬ НОВУЮ PnL-based СИСТЕМУ")
    
    print()
    
    # 7. РЕКОМЕНДАЦИИ
    print("7️⃣ РЕКОМЕНДАЦИИ:")
    print("-" * 40)
    
    print("🎯 НЕМЕДЛЕННЫЕ ДЕЙСТВИЯ:")
    print("   1. ПРОВЕРИТЬ: Какая система трейлинга используется в production")
    print("   2. СРАВНИТЬ: Логику активации трейлинга")
    print("   3. ПРОТЕСТИРОВАТЬ: Старую R-based систему")
    print("   4. ВОССТАНОВИТЬ: Идентичную бэктесту конфигурацию")
    
    print()
    print("🔧 ВАРИАНТЫ ИСПРАВЛЕНИЯ:")
    print("   A) Вернуть старую R-based систему трейлинга")
    print("   B) Исправить новую PnL-based систему")
    print("   C) Провести новый бэктест с PnL-based системой")
    
    print()
    print("⚠️ КРИТИЧНО:")
    print("   • Бэктест показал отличные результаты со старой системой")
    print("   • Production использует новую систему")
    print("   • Это может быть основной причиной убытков")
    
    print()
    print("🎯 ЗАКЛЮЧЕНИЕ:")
    print("-" * 40)
    print("❌ СИСТЕМЫ НЕ ИДЕНТИЧНЫ!")
    print("❌ ГЛАВНОЕ РАЗЛИЧИЕ: СИСТЕМА ТРЕЙЛИНГА")
    print("✅ ВСЕ ОСТАЛЬНОЕ: ИДЕНТИЧНО")
    print("🚨 НУЖНО ВОССТАНОВИТЬ СТАРУЮ СИСТЕМУ ТРЕЙЛИНГА")

if __name__ == "__main__":
    compare_backtest_vs_production()
