#!/usr/bin/env python3
"""
ИСПРАВЛЕНИЕ ДАННЫХ LTC_USDT В JSON
Синхронизируем правильные данные трейлинга между секциями
"""

import json
import sys
from datetime import datetime

def fix_ltc_json_data():
    """Исправляем данные LTC_USDT в JSON файле"""
    json_file = "trading_state_v1_6_TXB.json"
    
    print("🔧 ИСПРАВЛЕНИЕ ДАННЫХ LTC_USDT")
    print("=" * 50)
    
    # Загружаем JSON
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"✅ JSON файл загружен: {json_file}")
    except Exception as e:
        print(f"❌ Ошибка загрузки JSON: {e}")
        return False
    
    # Проверяем наличие данных
    if 'symbols' not in data or 'LTC_USDT' not in data['symbols']:
        print("❌ Секция symbols.LTC_USDT не найдена")
        return False
    
    # Ищем правильную секцию в active_positions
    ltc_position_key = None
    for key in data.get('active_positions', {}):
        if 'LTC' in key:
            ltc_position_key = key
            break
    
    if not ltc_position_key:
        print("❌ Секция LTC в active_positions не найдена")
        return False
    
    print(f"✅ Найдена секция: active_positions.{ltc_position_key}")
    
    # Получаем данные из обеих секций
    symbols_ltc = data['symbols']['LTC_USDT']['active_position']
    positions_ltc = data['active_positions'][ltc_position_key]
    
    print(f"\n📊 ТЕКУЩИЕ ДАННЫЕ:")
    print(f"symbols.LTC_USDT:")
    print(f"   Entry: {symbols_ltc['entry']:.6f}")
    print(f"   SL Current: {symbols_ltc['sl_current']:.6f}")
    print(f"   Trailing Active: {symbols_ltc['trailing_active']}")
    print(f"   Peak PnL: {symbols_ltc['peak_pnl_usdt']:.6f}")
    
    print(f"\nactive_positions.{ltc_position_key}:")
    print(f"   Entry: {positions_ltc['entry']:.6f}")
    print(f"   SL Current: {positions_ltc['sl_current']:.6f}")
    print(f"   Trailing Active: {positions_ltc['trailing_active']}")
    print(f"   Peak PnL: {positions_ltc['peak_pnl_usdt']:.6f}")
    
    # ИСПРАВЛЕНИЕ: Копируем правильные данные из active_positions в symbols
    print(f"\n🔧 ИСПРАВЛЕНИЕ:")
    
    # Создаем резервную копию
    backup_file = f"backups/trading_state_v1_6_TXB.json.backup.ltc_fix_{int(datetime.now().timestamp())}"
    try:
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"💾 Резервная копия создана: {backup_file}")
    except Exception as e:
        print(f"⚠️ Не удалось создать резервную копию: {e}")
    
    # Синхронизируем данные
    old_sl = symbols_ltc['sl_current']
    old_trailing = symbols_ltc['trailing_active']
    old_peak = symbols_ltc['peak_pnl_usdt']
    
    # Копируем правильные данные
    symbols_ltc['sl_current'] = positions_ltc['sl_current']
    symbols_ltc['trailing_active'] = positions_ltc['trailing_active']
    symbols_ltc['peak_pnl_usdt'] = positions_ltc['peak_pnl_usdt']
    
    # Обновляем timestamp
    symbols_ltc['last_updated'] = datetime.now().timestamp()
    
    print(f"   SL Current: {old_sl:.6f} → {symbols_ltc['sl_current']:.6f}")
    print(f"   Trailing Active: {old_trailing} → {symbols_ltc['trailing_active']}")
    print(f"   Peak PnL: {old_peak:.6f} → {symbols_ltc['peak_pnl_usdt']:.6f}")
    
    # Сохраняем исправленный JSON
    try:
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"✅ JSON файл обновлен: {json_file}")
    except Exception as e:
        print(f"❌ Ошибка сохранения JSON: {e}")
        return False
    
    print(f"\n🎯 РЕЗУЛЬТАТ:")
    print(f"✅ LTC_USDT данные синхронизированы")
    print(f"✅ Трейлинг SL восстановлен: ${symbols_ltc['sl_current']:.6f}")
    print(f"✅ Peak PnL восстановлен: ${symbols_ltc['peak_pnl_usdt']:.6f}")
    print(f"✅ Trailing активен: {symbols_ltc['trailing_active']}")
    
    return True

if __name__ == "__main__":
    success = fix_ltc_json_data()
    exit(0 if success else 1)
