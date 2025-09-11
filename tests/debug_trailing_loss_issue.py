#!/usr/bin/env python3
"""
Диагностика проблемы трейлинга в убыток
"""

import os
import sys
import yaml

# Добавляем путь к модулям
sys.path.append('.')

def debug_trailing_loss_issue():
    """Диагностика проблемы трейлинга в убыток"""
    
    print("🚨 ДИАГНОСТИКА ПРОБЛЕМЫ: ТРЕЙЛИНГ В УБЫТОК")
    print("=" * 80)
    
    # Загрузить конфигурацию
    with open('signalwarden_lite/config/config_production.yaml', 'r') as f:
        cfg = yaml.safe_load(f)
    
    trailing_config = cfg['trailing']
    
    print("📊 ТЕКУЩАЯ КОНФИГУРАЦИЯ ТРЕЙЛИНГА:")
    print(f"   activate_pnl_usdt: {trailing_config['activate_pnl_usdt']}")
    print(f"   level_1_pnl: {trailing_config['level_1_pnl']} (keep {trailing_config['level_1_keep_pct']*100}%)")
    print()
    
    print("🚨 ПРОБЛЕМА:")
    print("   • Трейлинг активировался ПРИ УБЫТКЕ")
    print("   • SL обновлялся В СТОРОНУ УБЫТКА")
    print("   • Это НЕДОПУСТИМО!")
    print()
    
    print("❌ ВОЗМОЖНЫЕ ПРИЧИНЫ:")
    print("-" * 60)
    
    print("1. ОШИБКА В ЛОГИКЕ АКТИВАЦИИ:")
    print("   • activate_pnl_usdt может быть отрицательным")
    print("   • Или проверка PnL работает неправильно")
    print("   • Трейлинг активируется при PnL < 0")
    
    print()
    print("2. ОШИБКА В РАСЧЕТЕ TARGET PROFIT:")
    print("   • target_profit может быть отрицательным")
    print("   • Или расчет SL идет от неправильной базы")
    print("   • SL рассчитывается ниже entry для лонгов")
    
    print()
    print("3. ОШИБКА В ФУНКЦИИ update_trailing_pnl_based:")
    print("   • Неправильная проверка условий активации")
    print("   • Неправильный расчет нового SL")
    print("   • Отсутствие защиты от ухудшения SL")
    
    print()
    print("4. КОНФЛИКТ ЛОГИКИ:")
    print("   • Разные части системы используют разную логику")
    print("   • Трейлинг конфликтует с начальным SL")
    print("   • Нет проверки на минимальный PnL")
    
    print()
    
    # Симулируем проблемную ситуацию
    print("🧮 СИМУЛЯЦИЯ ПРОБЛЕМНОЙ СИТУАЦИИ:")
    print("-" * 60)
    
    # Данные из реальной позиции LTC
    entry = 115.496929
    qty = 0.181823
    sl_initial = 109.722082
    
    # Цена при убытке
    loss_price = 114.0
    current_pnl = (loss_price - entry) * qty  # Убыток
    
    print(f"📊 ТЕСТОВЫЕ ДАННЫЕ:")
    print(f"   Entry: ${entry:.6f}")
    print(f"   Current Price: ${loss_price:.6f} (УБЫТОК)")
    print(f"   Quantity: {qty:.6f}")
    print(f"   Current PnL: {current_pnl:.4f} USDT (УБЫТОК)")
    print(f"   SL Initial: ${sl_initial:.6f}")
    print()
    
    print(f"❌ ПРОБЛЕМА: PnL = {current_pnl:.4f} < 0 (УБЫТОК)")
    print(f"   НО трейлинг мог активироваться!")
    print()
    
    # Проверим разные сценарии активации
    print("🔍 ПРОВЕРКА СЦЕНАРИЕВ АКТИВАЦИИ:")
    print("-" * 60)
    
    # Сценарий 1: Неправильная проверка активации
    if abs(current_pnl) >= trailing_config['activate_pnl_usdt']:
        print(f"❌ ОШИБКА 1: Трейлинг активируется по abs(PnL)")
        print(f"   abs({current_pnl:.4f}) >= {trailing_config['activate_pnl_usdt']}")
        print(f"   ЭТО НЕПРАВИЛЬНО!")
    
    # Сценарий 2: Неправильное сравнение знака
    if current_pnl <= -trailing_config['activate_pnl_usdt']:
        print(f"❌ ОШИБКА 2: Трейлинг активируется при убытке")
        print(f"   {current_pnl:.4f} <= -{trailing_config['activate_pnl_usdt']}")
        print(f"   ЭТО НЕПРАВИЛЬНО!")
    
    # Сценарий 3: Ошибка в расчете target_profit
    if current_pnl < 0:
        wrong_target = trailing_config['level_1_pnl'] * trailing_config['level_1_keep_pct']
        wrong_sl = entry + (wrong_target / qty)
        
        print(f"❌ ОШИБКА 3: Неправильный расчет SL при убытке")
        print(f"   target_profit = {wrong_target:.4f} (положительный)")
        print(f"   new_sl = {entry:.6f} + ({wrong_target:.4f} / {qty:.6f}) = ${wrong_sl:.6f}")
        
        if wrong_sl > entry:
            print(f"   РЕЗУЛЬТАТ: SL выше entry (${wrong_sl:.6f} > ${entry:.6f})")
            print(f"   ЭТО СОЗДАЕТ УБЫТОК ПРИ СРАБАТЫВАНИИ!")
    
    print()
    print("✅ ПРАВИЛЬНАЯ ЛОГИКА:")
    print("-" * 60)
    
    print("1. АКТИВАЦИЯ ТОЛЬКО ПРИ ПРИБЫЛИ:")
    print(f"   if current_pnl >= {trailing_config['activate_pnl_usdt']} and current_pnl > 0:")
    print("   • Трейлинг активируется только при положительном PnL")
    print("   • Никогда не активируется при убытке")
    
    print()
    print("2. ЗАЩИТА ОТ УХУДШЕНИЯ SL:")
    print("   • Для лонгов: new_sl > old_sl (только улучшение)")
    print("   • Для шортов: new_sl < old_sl (только улучшение)")
    print("   • Никогда не ухудшать SL")
    
    print()
    print("3. ПРОВЕРКА МИНИМАЛЬНОГО PNL:")
    print("   • target_profit должен покрывать комиссии")
    print("   • Минимум 0.02-0.05 USDT прибыли")
    print("   • Защита от закрытия в убыток")
    
    print()
    print("🎯 ЧТО НУЖНО ИСПРАВИТЬ:")
    print("-" * 60)
    
    print("1. ПРОВЕРИТЬ ФУНКЦИЮ update_trailing_pnl_based:")
    print("   • Найти условие активации трейлинга")
    print("   • Убедиться, что проверяется current_pnl > 0")
    print("   • Добавить защиту от активации при убытке")
    
    print()
    print("2. ПРОВЕРИТЬ ФУНКЦИЮ update_trailing_stops:")
    print("   • Найти вызов update_trailing_pnl_based")
    print("   • Убедиться в правильной передаче параметров")
    print("   • Добавить дополнительные проверки")
    
    print()
    print("3. ДОБАВИТЬ ЛОГИРОВАНИЕ:")
    print("   • Логировать все попытки активации трейлинга")
    print("   • Показывать current_pnl при каждой проверке")
    print("   • Предупреждать о попытках активации при убытке")
    
    print()
    print("4. ДОБАВИТЬ АВАРИЙНУЮ ЗАЩИТУ:")
    print("   • Проверять, что new_sl не создает убыток")
    print("   • Блокировать обновления SL в убыток")
    print("   • Сохранять минимальную прибыль")

if __name__ == "__main__":
    debug_trailing_loss_issue()
