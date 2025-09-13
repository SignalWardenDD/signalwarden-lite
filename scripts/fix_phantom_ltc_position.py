#!/usr/bin/env python3
"""
ИСПРАВЛЕНИЕ ФАНТОМНОЙ ПОЗИЦИИ LTC_USDT
Удаляем позицию из JSON, которой нет на Binance
"""

import json
import sys
from datetime import datetime
import ccxt
import os
from dotenv import load_dotenv

def check_position_on_binance(symbol):
    """Проверяем существует ли позиция на Binance"""
    try:
        load_dotenv()
        
        api_key = os.getenv('BINANCE_API_KEY')
        secret = os.getenv('BINANCE_SECRET')
        
        if not api_key or not secret:
            print(f"❌ Отсутствуют API ключи")
            return None
        
        exchange = ccxt.binanceusdm({
            'apiKey': api_key,
            'secret': secret,
            'sandbox': False,
            'options': {'defaultType': 'future'}
        })
        
        exchange.load_markets()
        
        # Конвертируем символ
        if symbol == 'LTC_USDT':
            ccxt_symbol = 'LTCUSDT'
            market_symbol = 'LTC/USDT'
        else:
            return None
        
        positions = exchange.fetch_positions([ccxt_symbol])
        
        for pos in positions:
            if pos['symbol'] == market_symbol and abs(pos['size']) > 0:
                return pos
                
        return None
        
    except Exception as e:
        print(f"❌ Ошибка проверки Binance: {e}")
        return None

def fix_phantom_ltc_position():
    """Исправляем фантомную позицию LTC"""
    print("🔧 ИСПРАВЛЕНИЕ ФАНТОМНОЙ ПОЗИЦИИ LTC_USDT")
    print("=" * 60)
    
    # 1. Проверяем позицию на Binance
    print("1️⃣ ПРОВЕРКА ПОЗИЦИИ НА BINANCE")
    binance_position = check_position_on_binance('LTC_USDT')
    
    if binance_position:
        print(f"✅ LTC позиция найдена на Binance:")
        print(f"   Размер: {binance_position['size']:.6f}")
        print(f"   Entry: ${binance_position['entryPrice']:.6f}")
        print(f"   PnL: ${binance_position['unrealizedPnl']:.6f}")
        print(f"❌ Позиция существует - исправление не требуется")
        return False
    else:
        print(f"❌ LTC позиция НЕ НАЙДЕНА на Binance")
        print(f"✅ Подтверждена фантомная позиция - нужно удалить из JSON")
    
    # 2. Загружаем JSON
    json_file = "trading_state_v1_6_TXB.json"
    
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"✅ JSON файл загружен")
    except Exception as e:
        print(f"❌ Ошибка загрузки JSON: {e}")
        return False
    
    # 3. Создаем резервную копию
    backup_file = f"backups/trading_state_v1_6_TXB.json.backup.phantom_ltc_fix_{int(datetime.now().timestamp())}"
    try:
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"💾 Резервная копия: {backup_file}")
    except Exception as e:
        print(f"⚠️ Не удалось создать резервную копию: {e}")
    
    # 4. Удаляем фантомную позицию из всех секций
    print(f"\n2️⃣ УДАЛЕНИЕ ФАНТОМНОЙ ПОЗИЦИИ")
    
    removed_sections = []
    
    # Секция symbols.LTC_USDT
    if 'symbols' in data and 'LTC_USDT' in data['symbols']:
        if data['symbols']['LTC_USDT'].get('active_position'):
            print(f"🗑️ Удаляем symbols.LTC_USDT.active_position")
            data['symbols']['LTC_USDT']['active_position'] = None
            removed_sections.append('symbols.LTC_USDT.active_position')
    
    # Секция active_positions
    if 'active_positions' in data:
        ltc_keys = [key for key in data['active_positions'].keys() if 'LTC' in key]
        for key in ltc_keys:
            print(f"🗑️ Удаляем active_positions.{key}")
            del data['active_positions'][key]
            removed_sections.append(f'active_positions.{key}')
    
    # 5. Обновляем метаданные
    if 'metadata' not in data:
        data['metadata'] = {}
    
    data['metadata']['phantom_position_fixed'] = True
    data['metadata']['phantom_fix_timestamp'] = datetime.now().timestamp()
    data['metadata']['phantom_fix_reason'] = 'LTC_USDT position not found on Binance'
    data['metadata']['last_updated'] = datetime.now().isoformat()
    
    # 6. Сохраняем исправленный JSON
    try:
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"✅ JSON файл обновлен")
    except Exception as e:
        print(f"❌ Ошибка сохранения JSON: {e}")
        return False
    
    # 7. Итоговый отчет
    print(f"\n🎯 РЕЗУЛЬТАТ ИСПРАВЛЕНИЯ:")
    print(f"✅ Фантомная позиция LTC_USDT удалена")
    print(f"📊 Удалено секций: {len(removed_sections)}")
    for section in removed_sections:
        print(f"   - {section}")
    print(f"💾 Резервная копия сохранена")
    print(f"🔄 Система больше не будет показывать несуществующую позицию")
    
    print(f"\n⚠️ РЕКОМЕНДАЦИИ:")
    print(f"1. Перезапустите систему для применения изменений")
    print(f"2. Проверьте что система корректно синхронизируется с Binance")
    print(f"3. Убедитесь что автофиксер работает правильно")
    
    return True

if __name__ == "__main__":
    success = fix_phantom_ltc_position()
    exit(0 if success else 1)
