#!/usr/bin/env python3
"""
Диагностический тест проблемы с трейлингом в live системе
"""

import sys
sys.path.append('.')

import json
from signalwarden_lite.core.trailing import TrailingConfig, update_trailing_pnl_based
from signalwarden_lite.core.types import Position, Side

def analyze_doge_position():
    """
    Анализируем состояние позиции DOGE из JSON файла
    """
    print("🔍 ДИАГНОСТИКА ПРОБЛЕМЫ С ТРЕЙЛИНГОМ DOGE")
    print("=" * 70)
    
    # Читаем состояние из JSON
    with open('trading_state_v1_6_TXB.json', 'r') as f:
        state = json.load(f)
    
    # Анализируем записи DOGE
    doge_main = state.get('DOGE_USDT', {})
    doge_position = state.get('DOGE_USDT_position', {})
    
    print("📊 СОСТОЯНИЕ ПОЗИЦИЙ DOGE:")
    print(f"1. DOGE_USDT (основная запись):")
    if 'active_position' in doge_main:
        pos = doge_main['active_position']
        print(f"   Entry: {pos.get('entry', 'N/A')}")
        print(f"   Qty: {pos.get('qty', 'N/A')}")
        print(f"   SL Current: {pos.get('sl_current', 'N/A')}")
        print(f"   SL Initial: {pos.get('sl_initial', 'N/A')}")
        print(f"   Trailing Active: {pos.get('trailing_active', 'N/A')}")
        print(f"   Peak PnL: {pos.get('peak_pnl_usdt', 'N/A')}")
    
    print(f"\n2. DOGE_USDT_position (отдельная запись):")
    print(f"   Entry: {doge_position.get('entry', 'N/A')}")
    print(f"   Qty: {doge_position.get('qty', 'N/A')}")
    print(f"   SL Current: {doge_position.get('sl_current', 'N/A')}")
    print(f"   SL Initial: {doge_position.get('sl_initial', 'N/A')}")
    print(f"   Trailing Active: {doge_position.get('trailing_active', 'N/A')}")
    print(f"   Peak PnL: {doge_position.get('peak_pnl_usdt', 'N/A')}")
    
    print(f"\n🚨 ПРОБЛЕМА ОБНАРУЖЕНА:")
    print(f"   Есть ДВЕ записи для одной позиции!")
    print(f"   Основная запись: trailing_active = {doge_main.get('active_position', {}).get('trailing_active', False)}")
    print(f"   Отдельная запись: trailing_active = {doge_position.get('trailing_active', False)}")
    print()
    
    return doge_main.get('active_position', {}), doge_position

def simulate_correct_trailing():
    """
    Симулируем правильную работу трейлинга с текущими данными DOGE
    """
    print("🎯 СИМУЛЯЦИЯ ПРАВИЛЬНОГО ТРЕЙЛИНГА")
    print("=" * 70)
    
    # Конфигурация трейлинга из production.yaml
    cfg = TrailingConfig(
        activate_pnl_usdt=0.10,
        level_1_pnl=0.10, level_1_keep_pct=0.50,
        level_2_pnl=0.20, level_2_keep_pct=0.60,
        level_3_pnl=0.30, level_3_keep_pct=0.70,
        level_4_pnl=0.40, level_4_keep_pct=0.80
    )
    
    # Данные DOGE из JSON (используем более актуальную запись)
    entry = 0.23653200000000002
    qty = 88.78291309421135
    sl_initial = 0.23043200000000003
    current_price = 0.238  # Примерная текущая цена
    
    # Расчет текущего PnL (если цена 0.238)
    current_pnl = (current_price - entry) * qty
    
    print(f"Данные позиции DOGE:")
    print(f"   Entry: ${entry:.6f}")
    print(f"   Qty: {qty:.2f}")
    print(f"   Current Price: ${current_price:.6f}")
    print(f"   Current PnL: ${current_pnl:.3f} USDT")
    print(f"   Порог активации: ${cfg.activate_pnl_usdt:.2f} USDT")
    print()
    
    # Создаем Position объект
    pos = Position(
        side=Side.LONG,
        entry=entry,
        qty=qty,
        remaining_qty=qty,
        r_per_unit=entry - sl_initial,  # ATR * sl_atr_mult
        sl=sl_initial,
        sl_initial=sl_initial,
        peak_pnl_usdt=0.0  # Начинаем с нуля для теста
    )
    
    print(f"Тест трейлинга:")
    
    # Тест 1: PnL = 0.13 USDT (как в реальности)
    test_pnl = 0.13
    test_price = entry + (test_pnl / qty)
    
    print(f"\n1. PnL = ${test_pnl:.3f} USDT (реальный случай)")
    print(f"   Цена: ${test_price:.6f}")
    print(f"   Трейлинг должен быть активен: {test_pnl >= cfg.activate_pnl_usdt}")
    
    updated_pos = update_trailing_pnl_based(pos, test_price, test_pnl, cfg)
    debug = getattr(updated_pos, 'trailing_debug', {})
    
    print(f"   Результат:")
    print(f"     Peak PnL: ${updated_pos.peak_pnl_usdt:.3f}")
    print(f"     Уровень: {debug.get('level', 'N/A')}")
    print(f"     Сохранить: {debug.get('keep_pct', 0)*100:.0f}%")
    print(f"     SL: ${pos.sl:.6f} → ${updated_pos.sl:.6f}")
    print(f"     SL обновлен: {debug.get('sl_updated', False)}")
    
    if debug.get('sl_updated', False):
        print(f"   ✅ ТРЕЙЛИНГ РАБОТАЕТ ПРАВИЛЬНО!")
        protected_profit = (updated_pos.sl - entry) * qty
        print(f"   💰 Защищенная прибыль: ${protected_profit:.3f} USDT")
    else:
        print(f"   ❌ ТРЕЙЛИНГ НЕ АКТИВИРОВАЛСЯ!")
    
    print()

def diagnose_live_system_issue():
    """
    Диагностируем проблемы в live системе
    """
    print("🔧 ДИАГНОСТИКА ПРОБЛЕМ LIVE СИСТЕМЫ")
    print("=" * 70)
    
    issues = []
    
    # Проблема 1: Дублирующие записи позиций
    with open('trading_state_v1_6_TXB.json', 'r') as f:
        state = json.load(f)
    
    if 'DOGE_USDT' in state and 'DOGE_USDT_position' in state:
        issues.append("1. Дублирующие записи позиций в JSON (DOGE_USDT и DOGE_USDT_position)")
    
    # Проблема 2: Несинхронизированное состояние трейлинга
    doge_main = state.get('DOGE_USDT', {}).get('active_position', {})
    doge_pos = state.get('DOGE_USDT_position', {})
    
    main_trailing = doge_main.get('trailing_active', False)
    pos_trailing = doge_pos.get('trailing_active', False)
    
    if main_trailing != pos_trailing:
        issues.append(f"2. Несинхронизированное состояние трейлинга: main={main_trailing}, pos={pos_trailing}")
    
    # Проблема 3: Отсутствие peak_pnl_usdt в основной записи
    if 'peak_pnl_usdt' not in doge_main and 'peak_pnl_usdt' in doge_pos:
        issues.append("3. peak_pnl_usdt отсутствует в основной записи, но есть в отдельной")
    
    print("🚨 ОБНАРУЖЕННЫЕ ПРОБЛЕМЫ:")
    for issue in issues:
        print(f"   {issue}")
    
    if not issues:
        print("   Проблемы не обнаружены")
    
    print(f"\n💡 РЕКОМЕНДАЦИИ ДЛЯ ИСПРАВЛЕНИЯ:")
    print(f"   1. Очистить дублирующие записи в JSON")
    print(f"   2. Убедиться что peak_pnl_usdt сохраняется в основной записи")
    print(f"   3. Проверить что трейлинг поток запущен (start_trailing_thread)")
    print(f"   4. Добавить больше отладочных логов в update_trailing_stops")
    print()

def create_fix_script():
    """
    Создаем скрипт для исправления проблемы
    """
    print("🛠️  СОЗДАНИЕ СКРИПТА ИСПРАВЛЕНИЯ")
    print("=" * 70)
    
    fix_code = '''
# Исправление проблемы с дублирующими записями позиций
def fix_position_state():
    import json
    
    with open('trading_state_v1_6_TXB.json', 'r') as f:
        state = json.load(f)
    
    # Объединяем данные из дублирующих записей
    if 'DOGE_USDT_position' in state:
        pos_data = state['DOGE_USDT_position']
        
        if 'DOGE_USDT' in state and 'active_position' in state['DOGE_USDT']:
            # Обновляем основную запись данными из отдельной
            main_pos = state['DOGE_USDT']['active_position']
            main_pos['peak_pnl_usdt'] = pos_data.get('peak_pnl_usdt', 0.0)
            main_pos['trailing_active'] = pos_data.get('trailing_active', False)
            main_pos['sl_current'] = pos_data.get('sl_current', main_pos.get('sl_current'))
        
        # Удаляем дублирующую запись
        del state['DOGE_USDT_position']
        
        # Сохраняем исправленное состояние
        with open('trading_state_v1_6_TXB.json.fixed', 'w') as f:
            json.dump(state, f, indent=2)
        
        print("✅ Состояние исправлено и сохранено в trading_state_v1_6_TXB.json.fixed")
'''
    
    print("Код для исправления:")
    print(fix_code)
    
    # Сохраняем скрипт
    with open('fix_doge_position.py', 'w') as f:
        f.write(fix_code)
    
    print("💾 Скрипт сохранен в fix_doge_position.py")
    print()

if __name__ == '__main__':
    print("🚀 ДИАГНОСТИКА ПРОБЛЕМЫ С ТРЕЙЛИНГОМ DOGE v1.6-TXB")
    print("=" * 80)
    print()
    
    try:
        main_pos, separate_pos = analyze_doge_position()
        simulate_correct_trailing()
        diagnose_live_system_issue()
        create_fix_script()
        
        print("📋 ЗАКЛЮЧЕНИЕ:")
        print("   Проблема в дублирующих записях позиций в JSON файле")
        print("   Система создает две записи: основную и отдельную")
        print("   Трейлинг обновляет отдельную запись, но live система читает основную")
        print("   Результат: PnL 0.13 USDT, но трейлинг не активен в основной записи")
        print()
        print("🔧 РЕШЕНИЕ:")
        print("   1. Запустить fix_doge_position.py для исправления JSON")
        print("   2. Перезапустить live систему")
        print("   3. Убедиться что трейлинг поток запущен")
        
    except Exception as e:
        print(f"💥 ОШИБКА В ДИАГНОСТИКЕ: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
