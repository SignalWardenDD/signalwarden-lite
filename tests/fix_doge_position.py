#!/usr/bin/env python3
"""
Исправление проблемы с дублирующими записями позиций в JSON
"""

import json
import shutil
from datetime import datetime

def fix_position_state():
    """Исправляет дублирующие записи позиций в JSON файле"""
    
    print("🔧 ИСПРАВЛЕНИЕ СОСТОЯНИЯ ПОЗИЦИЙ")
    print("=" * 50)
    
    # Создаем резервную копию
    backup_file = f"trading_state_v1_6_TXB_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    shutil.copy('trading_state_v1_6_TXB.json', backup_file)
    print(f"✅ Создана резервная копия: {backup_file}")
    
    # Читаем текущее состояние
    with open('trading_state_v1_6_TXB.json', 'r') as f:
        state = json.load(f)
    
    print(f"📊 Анализ состояния...")
    
    # Находим все дублирующие записи позиций
    position_keys = [key for key in state.keys() if key.endswith('_position')]
    main_keys = [key.replace('_position', '') for key in position_keys]
    
    print(f"   Найдено дублирующих записей: {len(position_keys)}")
    
    fixes_applied = 0
    
    for pos_key, main_key in zip(position_keys, main_keys):
        if main_key in state and pos_key in state:
            print(f"\n🔄 Исправление {main_key}:")
            
            pos_data = state[pos_key]
            main_data = state.get(main_key, {})
            
            # Проверяем есть ли active_position в основной записи
            if 'active_position' in main_data:
                main_pos = main_data['active_position']
                
                # Объединяем данные - приоритет у отдельной записи (более актуальной)
                if 'peak_pnl_usdt' in pos_data:
                    old_peak = main_pos.get('peak_pnl_usdt', 0.0)
                    main_pos['peak_pnl_usdt'] = pos_data['peak_pnl_usdt']
                    print(f"     Peak PnL: {old_peak:.3f} → {pos_data['peak_pnl_usdt']:.3f}")
                
                if 'trailing_active' in pos_data:
                    old_trailing = main_pos.get('trailing_active', False)
                    main_pos['trailing_active'] = pos_data['trailing_active']
                    print(f"     Trailing Active: {old_trailing} → {pos_data['trailing_active']}")
                
                if 'sl_current' in pos_data and pos_data['sl_current'] != main_pos.get('sl_current'):
                    old_sl = main_pos.get('sl_current', 'N/A')
                    main_pos['sl_current'] = pos_data['sl_current']
                    print(f"     SL Current: {old_sl} → {pos_data['sl_current']}")
                
                # Удаляем дублирующую запись
                del state[pos_key]
                fixes_applied += 1
                print(f"     ✅ Дублирующая запись удалена")
            else:
                print(f"     ⚠️  Основная запись не содержит active_position")
    
    if fixes_applied > 0:
        # Сохраняем исправленное состояние
        with open('trading_state_v1_6_TXB.json', 'w') as f:
            json.dump(state, f, indent=2)
        
        print(f"\n✅ Применено исправлений: {fixes_applied}")
        print(f"💾 Состояние сохранено в trading_state_v1_6_TXB.json")
        
        # Проверяем результат
        print(f"\n🔍 ПРОВЕРКА РЕЗУЛЬТАТА:")
        if 'DOGE_USDT' in state and 'active_position' in state['DOGE_USDT']:
            doge_pos = state['DOGE_USDT']['active_position']
            print(f"   DOGE_USDT:")
            print(f"     Entry: {doge_pos.get('entry', 'N/A')}")
            print(f"     Trailing Active: {doge_pos.get('trailing_active', 'N/A')}")
            print(f"     Peak PnL: {doge_pos.get('peak_pnl_usdt', 'N/A')}")
            print(f"     SL Current: {doge_pos.get('sl_current', 'N/A')}")
    else:
        print(f"\n✅ Дублирующие записи не найдены")
    
    return fixes_applied > 0

def verify_fix():
    """Проверяем что исправление применено корректно"""
    print(f"\n🔍 ВЕРИФИКАЦИЯ ИСПРАВЛЕНИЯ")
    print("=" * 50)
    
    with open('trading_state_v1_6_TXB.json', 'r') as f:
        state = json.load(f)
    
    # Проверяем отсутствие дублирующих записей
    position_keys = [key for key in state.keys() if key.endswith('_position')]
    
    if position_keys:
        print(f"❌ Все еще есть дублирующие записи: {position_keys}")
        return False
    else:
        print(f"✅ Дублирующие записи отсутствуют")
    
    # Проверяем состояние DOGE
    if 'DOGE_USDT' in state and 'active_position' in state['DOGE_USDT']:
        doge_pos = state['DOGE_USDT']['active_position']
        has_peak_pnl = 'peak_pnl_usdt' in doge_pos
        has_trailing = 'trailing_active' in doge_pos
        
        print(f"✅ DOGE позиция содержит:")
        print(f"   Peak PnL: {has_peak_pnl} ({doge_pos.get('peak_pnl_usdt', 'N/A')})")
        print(f"   Trailing Active: {has_trailing} ({doge_pos.get('trailing_active', 'N/A')})")
        
        return has_peak_pnl and has_trailing
    else:
        print(f"⚠️  DOGE позиция не найдена")
        return False

if __name__ == '__main__':
    print("🚀 ИСПРАВЛЕНИЕ ПРОБЛЕМЫ С ДУБЛИРУЮЩИМИ ЗАПИСЯМИ ПОЗИЦИЙ")
    print("=" * 70)
    print()
    
    try:
        fixed = fix_position_state()
        
        if fixed:
            success = verify_fix()
            if success:
                print(f"\n🎉 ИСПРАВЛЕНИЕ ЗАВЕРШЕНО УСПЕШНО!")
                print(f"💡 Рекомендации:")
                print(f"   1. Перезапустите live систему")
                print(f"   2. Проверьте что трейлинг поток запущен")
                print(f"   3. Мониторьте логи на предмет активации трейлинга")
            else:
                print(f"\n❌ ИСПРАВЛЕНИЕ НЕ ПОЛНОСТЬЮ УСПЕШНО")
                print(f"   Проверьте состояние вручную")
        else:
            print(f"\n✅ ИСПРАВЛЕНИЯ НЕ ТРЕБОВАЛИСЬ")
            
    except Exception as e:
        print(f"💥 ОШИБКА ПРИ ИСПРАВЛЕНИИ: {e}")
        import traceback
        traceback.print_exc()