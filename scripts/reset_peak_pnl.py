#!/usr/bin/env python3
"""
Сброс неправильных Peak PnL значений
"""

import json
import os

def reset_peak_pnl():
    """Сбрасывает неправильные Peak PnL значения"""
    
    files_to_reset = [
        'trading_state_v1_6_TXB.json',
        'trailing_backup_primary.json',
        'trailing_backup_secondary.json', 
        'trailing_backup_tertiary.json',
        'trailing_state_live.json'
    ]
    
    for filename in files_to_reset:
        if os.path.exists(filename):
            try:
                with open(filename, 'r') as f:
                    data = json.load(f)
                
                # Обновляем Peak PnL для всех позиций
                if 'symbols' in data:
                    for symbol, symbol_data in data['symbols'].items():
                        if symbol.endswith('_position'):
                            continue
                            
                        if 'active_position' in symbol_data and symbol_data['active_position'] is not None:
                            pos = symbol_data['active_position']
                            if 'peak_pnl_usdt' in pos:
                                old_peak = pos['peak_pnl_usdt']
                                pos['peak_pnl_usdt'] = 0.0
                                print(f"✅ {symbol}: Peak PnL сброшен {old_peak:.4f} → 0.0000")
                            
                            if 'trailing_active' in pos:
                                pos['trailing_active'] = False
                                print(f"✅ {symbol}: Трейлинг деактивирован")
                
                # Сохраняем файл
                with open(filename, 'w') as f:
                    json.dump(data, f, indent=2)
                
                print(f"✅ Обновлен файл: {filename}")
                
            except Exception as e:
                print(f"❌ Ошибка обработки {filename}: {e}")
        else:
            print(f"⚠️ Файл не найден: {filename}")

if __name__ == "__main__":
    print("🔄 СБРОС НЕПРАВИЛЬНЫХ PEAK PNL ЗНАЧЕНИЙ")
    print("=" * 50)
    reset_peak_pnl()
    print("\n🎯 ГОТОВО! Перезапустите систему.")
