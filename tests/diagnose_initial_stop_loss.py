#!/usr/bin/env python3
"""
Диагностика проблем с начальными стоп-лоссами
"""

import os
import sys
import yaml
import json
from typing import Dict, List, Any

# Добавляем путь к модулям
sys.path.append('.')

def diagnose_initial_stop_loss():
    """Диагностика начальных стоп-лоссов"""
    
    print("🔍 ДИАГНОСТИКА НАЧАЛЬНЫХ СТОП-ЛОССОВ")
    print("=" * 80)
    
    # Загрузить конфигурацию
    with open('signalwarden_lite/config/config_production.yaml', 'r') as f:
        cfg = yaml.safe_load(f)
    
    sl_atr_mult = cfg['risk']['sl_atr_mult']
    
    print(f"📊 КОНФИГУРАЦИЯ: sl_atr_mult = {sl_atr_mult}")
    print()
    
    # Проверяем состояние системы
    try:
        with open('trading_state_v1_6_TXB.json', 'r') as f:
            state = json.load(f)
    except Exception as e:
        print(f"❌ Не удалось прочитать состояние системы: {e}")
        return
    
    print("🔍 АНАЛИЗ СТОП-ЛОССОВ В СИСТЕМЕ:")
    print("-" * 80)
    
    for symbol, data in state.get('symbols', {}).items():
        if symbol.endswith('_position'):
            continue
            
        active_pos = data.get('active_position')
        if active_pos:
            entry = active_pos.get('entry', 0)
            side = active_pos.get('side', 'UNKNOWN')
            qty = active_pos.get('qty', 0)
            sl_current = active_pos.get('sl_current', 0)
            sl_initial = active_pos.get('sl_initial', 0)
            atr = active_pos.get('atr')
            
            print(f"📊 {symbol}:")
            print(f"   Entry: ${entry:.6f}")
            print(f"   SL Initial: ${sl_initial:.6f}")
            print(f"   SL Current: ${sl_current:.6f}")
            print(f"   ATR: {atr}")
            
            # Рассчитываем расстояние SL
            if side == 'LONG':
                sl_distance_initial = (entry - sl_initial) / entry * 100
                sl_distance_current = (entry - sl_current) / entry * 100
            else:
                sl_distance_initial = (sl_initial - entry) / entry * 100
                sl_distance_current = (sl_current - entry) / entry * 100
            
            print(f"   SL Initial Distance: {sl_distance_initial:.2f}%")
            print(f"   SL Current Distance: {sl_distance_current:.2f}%")
            
            # Проверяем правильность расчета
            if atr is not None:
                expected_sl_distance = (atr * sl_atr_mult) / entry * 100
                print(f"   Expected SL Distance: {expected_sl_distance:.2f}% (ATR * {sl_atr_mult})")
                
                # Проверяем соответствие
                if abs(sl_distance_initial - expected_sl_distance) < 1.0:
                    print(f"   ✅ SL расстояние правильное")
                else:
                    print(f"   ❌ SL расстояние НЕПРАВИЛЬНОЕ!")
                    print(f"      Ожидалось: {expected_sl_distance:.2f}%")
                    print(f"      Фактически: {sl_distance_initial:.2f}%")
                    
                    # Проверим, какой ATR использовался
                    actual_atr_used = (entry - sl_initial) / sl_atr_mult if side == 'LONG' else (sl_initial - entry) / sl_atr_mult
                    actual_atr_pct = actual_atr_used / entry * 100
                    print(f"      Фактически использованный ATR: {actual_atr_used:.6f} ({actual_atr_pct:.2f}%)")
            else:
                print(f"   ❌ ATR отсутствует!")
            
            print()
    
    print("🔍 ВОЗМОЖНЫЕ ПРОБЛЕМЫ:")
    print("-" * 80)
    
    print("1. НЕПРАВИЛЬНЫЙ РАСЧЕТ ATR:")
    print("   • ATR рассчитывается некорректно")
    print("   • Используются неправильные исторические данные")
    print("   • Период расчета ATR слишком короткий")
    
    print()
    print("2. НЕПРАВИЛЬНОЕ ПРИМЕНЕНИЕ sl_atr_mult:")
    print("   • Множитель применяется к неправильному значению")
    print("   • Формула расчета SL неверная")
    print("   • Ошибка в коде расчета")
    
    print()
    print("3. ПРОБЛЕМЫ С ДАННЫМИ:")
    print("   • ATR не сохраняется в позицию")
    print("   • Используется fallback логика (2%)")
    print("   • Данные с биржи неполные")
    
    print()
    print("4. ОШИБКИ В ЛОГИКЕ:")
    print("   • SL рассчитывается в другом месте")
    print("   • Переопределяется после создания")
    print("   • Конфликт между разными системами")
    
    print()
    print("🎯 РЕКОМЕНДАЦИИ ПО ИСПРАВЛЕНИЮ:")
    print("-" * 80)
    
    print("1. ПРОВЕРИТЬ РАСЧЕТ ATR:")
    print("   • Убедиться, что ATR рассчитывается правильно")
    print("   • Проверить исторические данные")
    print("   • Логировать ATR при создании позиций")
    
    print()
    print("2. ПРОВЕРИТЬ ФОРМУЛУ SL:")
    print("   • LONG: SL = entry - (ATR * sl_atr_mult)")
    print("   • SHORT: SL = entry + (ATR * sl_atr_mult)")
    print("   • Убедиться в правильности применения")
    
    print()
    print("3. ДОБАВИТЬ ОТЛАДКУ:")
    print("   • Логировать все параметры при создании SL")
    print("   • Показывать entry, ATR, sl_atr_mult, результат")
    print("   • Проверить каждый шаг расчета")
    
    print()
    print("4. ПРОВЕРИТЬ СОЗДАНИЕ ПОЗИЦИЙ:")
    print("   • Найти место создания initial SL")
    print("   • Убедиться, что правильные параметры передаются")
    print("   • Проверить синхронизацию с биржей")

if __name__ == "__main__":
    diagnose_initial_stop_loss()
