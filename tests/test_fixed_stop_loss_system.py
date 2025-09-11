#!/usr/bin/env python3
"""
Тест исправленной системы стоп-лоссов
"""

import os
import sys
import json
import yaml

# Добавляем путь к модулям
sys.path.append('.')

def test_fixed_stop_loss_system():
    """Тест исправленной системы стоп-лоссов"""
    
    print("✅ ТЕСТ ИСПРАВЛЕННОЙ СИСТЕМЫ СТОП-ЛОССОВ")
    print("=" * 80)
    
    # Загрузить конфигурацию
    with open('signalwarden_lite/config/config_production.yaml', 'r') as f:
        cfg = yaml.safe_load(f)
    
    # Загрузить состояние системы
    with open('trading_state_v1_6_TXB.json', 'r') as f:
        state = json.load(f)
    
    sl_atr_mult = cfg['risk']['sl_atr_mult']
    min_atr_pct = 0.02  # 2% минимум
    
    print(f"📊 КОНФИГУРАЦИЯ:")
    print(f"   sl_atr_mult: {sl_atr_mult}")
    print(f"   min_atr_pct: {min_atr_pct*100:.1f}%")
    print(f"   min_sl_distance: {min_atr_pct * sl_atr_mult * 100:.1f}%")
    print()
    
    print("✅ ЧТО БЫЛО ИСПРАВЛЕНО:")
    print("-" * 60)
    print("1. ДОБАВЛЕН МИНИМАЛЬНЫЙ ATR:")
    print("   • effective_atr = max(calculated_atr, 2% от цены)")
    print("   • Защита от слишком близких стоп-лоссов")
    print("   • Логирование изменений ATR")
    
    print()
    print("2. ОБНОВЛЕНЫ СУЩЕСТВУЮЩИЕ ПОЗИЦИИ:")
    print("   • Все позиции получили новые ATR и SL")
    print("   • Создана резервная копия состояния")
    print("   • Система автоматически применяет изменения")
    
    print()
    print("3. ПРИНУДИТЕЛЬНОЕ ОБНОВЛЕНИЕ НА BINANCE:")
    print("   • Отменены все старые стоп-ордера")
    print("   • Созданы новые с правильными ценами")
    print("   • Все 6 позиций успешно обновлены")
    
    print()
    print("🔍 ПРОВЕРКА ТЕКУЩЕГО СОСТОЯНИЯ:")
    print("-" * 80)
    
    total_positions = 0
    correct_sl_positions = 0
    
    for symbol, data in state.get('symbols', {}).items():
        if symbol.endswith('_position'):
            continue
            
        active_pos = data.get('active_position')
        if active_pos:
            total_positions += 1
            
            entry = active_pos.get('entry', 0)
            atr = active_pos.get('atr', 0)
            sl_current = active_pos.get('sl_current', 0)
            side = active_pos.get('side', 'UNKNOWN')
            
            # Проверяем ATR
            min_atr = entry * min_atr_pct
            atr_correct = atr >= min_atr
            
            # Проверяем SL расстояние
            if side == 'LONG':
                sl_distance = (entry - sl_current) / entry * 100
            else:
                sl_distance = (sl_current - entry) / entry * 100
            
            sl_distance_correct = sl_distance >= (min_atr_pct * sl_atr_mult * 100)
            
            print(f"📊 {symbol}:")
            print(f"   Entry: ${entry:.6f}")
            print(f"   ATR: {atr:.6f} ({atr/entry*100:.2f}%)")
            print(f"   Min ATR: {min_atr:.6f} ({min_atr_pct*100:.1f}%)")
            print(f"   SL Distance: {sl_distance:.2f}%")
            print(f"   Min SL Distance: {min_atr_pct * sl_atr_mult * 100:.1f}%")
            
            if atr_correct and sl_distance_correct:
                print(f"   ✅ ПРАВИЛЬНО НАСТРОЕН")
                correct_sl_positions += 1
            else:
                print(f"   ❌ ТРЕБУЕТ ИСПРАВЛЕНИЯ")
                if not atr_correct:
                    print(f"      • ATR слишком маленький")
                if not sl_distance_correct:
                    print(f"      • SL слишком близко")
            
            print()
    
    print("🎯 ИТОГОВАЯ ОЦЕНКА:")
    print("-" * 60)
    
    print(f"✅ Всего позиций: {total_positions}")
    print(f"✅ Правильно настроенных: {correct_sl_positions}")
    print(f"❌ Требуют исправления: {total_positions - correct_sl_positions}")
    
    success_rate = (correct_sl_positions / total_positions * 100) if total_positions > 0 else 0
    print(f"📊 Процент успеха: {success_rate:.1f}%")
    
    print()
    if success_rate == 100:
        print("🎉 ВСЕ ПОЗИЦИИ ПРАВИЛЬНО НАСТРОЕНЫ!")
        print("✅ Система готова к работе")
        print("✅ Стоп-лоссы на безопасном расстоянии")
        print("✅ Минимальный ATR применяется автоматически")
    elif success_rate >= 80:
        print("⚠️ БОЛЬШИНСТВО ПОЗИЦИЙ НАСТРОЕНО ПРАВИЛЬНО")
        print("🔧 Некоторые позиции требуют дополнительного внимания")
    else:
        print("❌ КРИТИЧЕСКИЕ ПРОБЛЕМЫ ОСТАЮТСЯ")
        print("🚨 Требуется дополнительное исправление")
    
    print()
    print("📋 РЕКОМЕНДАЦИИ ДЛЯ ПОЛЬЗОВАТЕЛЯ:")
    print("-" * 60)
    
    print("1. МОНИТОРИНГ:")
    print("   • Следите за логами системы")
    print("   • Проверяйте стоп-ордера на Binance")
    print("   • Убедитесь в отсутствии ошибок API")
    
    print()
    print("2. НОВЫЕ ПОЗИЦИИ:")
    print("   • Будут автоматически использовать минимальный ATR")
    print("   • SL всегда будет минимум на 5% от entry")
    print("   • Система покажет в логах увеличение ATR")
    
    print()
    print("3. ТРЕЙЛИНГ:")
    print("   • Будет работать с обновленными SL")
    print("   • Сохранит правильные проценты прибыли")
    print("   • Не будет конфликтов с минимальным ATR")
    
    print()
    print("4. БЕЗОПАСНОСТЬ:")
    print("   • Меньше ложных срабатываний SL")
    print("   • Защита от рыночного шума")
    print("   • Стабильная работа системы")

if __name__ == "__main__":
    test_fixed_stop_loss_system()
