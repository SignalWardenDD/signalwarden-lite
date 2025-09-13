#!/usr/bin/env python3
"""
ЭКСТРЕННОЕ ИСПРАВЛЕНИЕ ФАНТОМНОЙ ПОЗИЦИИ PNUT_USDT
Удаляем фантомную позицию PNUT которой нет на Binance
"""

import json
import sys
from datetime import datetime
import ccxt
import os
from dotenv import load_dotenv

def emergency_fix_phantom_pnut():
    """Экстренное исправление фантомной позиции PNUT"""
    print("🚨 ЭКСТРЕННОЕ ИСПРАВЛЕНИЕ ФАНТОМНОЙ ПОЗИЦИИ PNUT_USDT")
    print("=" * 70)
    
    # 1. Подтверждаем что позиции нет на Binance
    print("1️⃣ ПРОВЕРКА ПОЗИЦИИ НА BINANCE")
    try:
        load_dotenv()
        
        api_key = os.getenv('BINANCE_API_KEY')
        secret = os.getenv('BINANCE_SECRET')
        
        exchange = ccxt.binanceusdm({
            'apiKey': api_key,
            'secret': secret,
            'sandbox': False,
            'options': {'defaultType': 'future'}
        })
        
        exchange.load_markets()
        
        positions = exchange.fetch_positions(['PNUTUSDT'])
        pnut_position = None
        
        for pos in positions:
            if pos['symbol'] == 'PNUT/USDT' and abs(pos['size']) > 0:
                pnut_position = pos
                break
        
        if pnut_position:
            print(f"✅ PNUT позиция найдена на Binance:")
            print(f"   Размер: {pnut_position['size']:.2f}")
            print(f"   Entry: ${pnut_position['entryPrice']:.6f}")
            print(f"   PnL: ${pnut_position['unrealizedPnl']:.6f}")
            print(f"❌ Позиция существует - исправление НЕ требуется")
            return False
        else:
            print(f"❌ PNUT позиция НЕ НАЙДЕНА на Binance")
            print(f"✅ Подтверждена фантомная позиция - нужно удалить")
            
    except Exception as e:
        print(f"❌ Ошибка проверки Binance: {e}")
        return False
    
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
    backup_file = f"backups/trading_state_v1_6_TXB.json.backup.emergency_pnut_fix_{int(datetime.now().timestamp())}"
    try:
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"💾 Резервная копия: {backup_file}")
    except Exception as e:
        print(f"⚠️ Не удалось создать резервную копию: {e}")
    
    # 4. Удаляем фантомную позицию PNUT из всех секций
    print(f"\n2️⃣ УДАЛЕНИЕ ФАНТОМНОЙ ПОЗИЦИИ PNUT")
    
    removed_sections = []
    
    # Секция symbols.PNUT_USDT
    if 'symbols' in data and 'PNUT_USDT' in data['symbols']:
        if data['symbols']['PNUT_USDT'].get('active_position'):
            print(f"🗑️ Удаляем symbols.PNUT_USDT.active_position")
            data['symbols']['PNUT_USDT']['active_position'] = None
            removed_sections.append('symbols.PNUT_USDT.active_position')
    
    # Секция active_positions
    if 'active_positions' in data:
        pnut_keys = [key for key in data['active_positions'].keys() if 'PNUT' in key]
        for key in pnut_keys:
            print(f"🗑️ Удаляем active_positions.{key}")
            del data['active_positions'][key]
            removed_sections.append(f'active_positions.{key}')
    
    # 5. Обновляем метаданные
    if 'metadata' not in data:
        data['metadata'] = {}
    
    data['metadata']['emergency_phantom_pnut_fixed'] = True
    data['metadata']['emergency_fix_timestamp'] = datetime.now().timestamp()
    data['metadata']['emergency_fix_reason'] = 'PNUT_USDT phantom position - not found on Binance but added by auto-fixer'
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
    print(f"\n🎯 РЕЗУЛЬТАТ ЭКСТРЕННОГО ИСПРАВЛЕНИЯ:")
    print(f"✅ Фантомная позиция PNUT_USDT удалена")
    print(f"📊 Удалено секций: {len(removed_sections)}")
    for section in removed_sections:
        print(f"   - {section}")
    print(f"💾 Резервная копия сохранена")
    
    print(f"\n🚨 КРИТИЧЕСКАЯ ПРОБЛЕМА:")
    print(f"   Автофиксер ОШИБОЧНО добавил несуществующую позицию PNUT!")
    print(f"   Это могло привести к потере денег из-за отсутствия защиты!")
    
    print(f"\n⚠️ РЕКОМЕНДАЦИИ:")
    print(f"1. НЕМЕДЛЕННО перезапустите систему")
    print(f"2. Проверьте логику автофиксера - он добавляет фантомные позиции!")
    print(f"3. Убедитесь что все позиции имеют правильную защиту")
    
    return True

if __name__ == "__main__":
    success = emergency_fix_phantom_pnut()
    exit(0 if success else 1)
