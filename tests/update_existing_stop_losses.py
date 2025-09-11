#!/usr/bin/env python3
"""
Обновление существующих стоп-лоссов с минимальным ATR
"""

import os
import sys
import json
import yaml

# Добавляем путь к модулям
sys.path.append('.')

def update_existing_stop_losses():
    """Обновление существующих стоп-лоссов"""
    
    print("🔧 ОБНОВЛЕНИЕ СУЩЕСТВУЮЩИХ СТОП-ЛОССОВ")
    print("=" * 80)
    
    # Загрузить конфигурацию
    with open('signalwarden_lite/config/config_production.yaml', 'r') as f:
        cfg = yaml.safe_load(f)
    
    sl_atr_mult = cfg['risk']['sl_atr_mult']
    min_atr_pct = 0.02  # 2% минимум
    
    print(f"📊 КОНФИГУРАЦИЯ:")
    print(f"   sl_atr_mult: {sl_atr_mult}")
    print(f"   min_atr_pct: {min_atr_pct*100:.1f}%")
    print()
    
    # Загрузить состояние системы
    try:
        with open('trading_state_v1_6_TXB.json', 'r') as f:
            state = json.load(f)
    except Exception as e:
        print(f"❌ Не удалось прочитать состояние системы: {e}")
        return
    
    print("🔍 АНАЛИЗ СУЩЕСТВУЮЩИХ ПОЗИЦИЙ:")
    print("-" * 80)
    
    updated_positions = []
    
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
            print(f"   Current ATR: {atr:.6f} ({atr/entry*100:.2f}%)")
            print(f"   Current SL: ${sl_current:.6f}")
            
            # Рассчитываем новый SL с минимальным ATR
            min_atr = entry * min_atr_pct
            effective_atr = max(atr, min_atr)
            
            if side == 'LONG':
                new_sl = entry - (sl_atr_mult * effective_atr)
            else:
                new_sl = entry + (sl_atr_mult * effective_atr)
            
            print(f"   Min ATR: {min_atr:.6f} ({min_atr_pct*100:.1f}%)")
            print(f"   Effective ATR: {effective_atr:.6f} ({effective_atr/entry*100:.2f}%)")
            print(f"   New SL: ${new_sl:.6f}")
            
            # Проверяем, нужно ли обновление
            if effective_atr > atr:
                sl_change = abs(new_sl - sl_current) / entry * 100
                print(f"   ✅ НУЖНО ОБНОВИТЬ: SL изменится на {sl_change:.2f}%")
                
                # Обновляем в данных
                active_pos['atr'] = effective_atr
                active_pos['sl_initial'] = new_sl
                active_pos['sl_current'] = new_sl
                
                updated_positions.append({
                    'symbol': symbol,
                    'old_sl': sl_current,
                    'new_sl': new_sl,
                    'old_atr': atr,
                    'new_atr': effective_atr
                })
                
            else:
                print(f"   ✅ ОБНОВЛЕНИЕ НЕ ТРЕБУЕТСЯ")
            
            print()
    
    if updated_positions:
        print("💾 СОХРАНЕНИЕ ОБНОВЛЕНИЙ:")
        print("-" * 60)
        
        # Создаем резервную копию
        backup_file = 'trading_state_v1_6_TXB_backup_before_sl_fix.json'
        with open(backup_file, 'w') as f:
            json.dump(state, f, indent=2)
        print(f"✅ Создана резервная копия: {backup_file}")
        
        # Сохраняем обновленное состояние
        with open('trading_state_v1_6_TXB.json', 'w') as f:
            json.dump(state, f, indent=2)
        print(f"✅ Обновлено состояние системы")
        
        print()
        print("📋 ОБНОВЛЕННЫЕ ПОЗИЦИИ:")
        print("-" * 60)
        
        for pos in updated_positions:
            symbol = pos['symbol']
            old_sl = pos['old_sl']
            new_sl = pos['new_sl']
            old_atr = pos['old_atr']
            new_atr = pos['new_atr']
            
            print(f"📊 {symbol}:")
            print(f"   ATR: {old_atr:.6f} → {new_atr:.6f}")
            print(f"   SL: ${old_sl:.6f} → ${new_sl:.6f}")
            print()
        
        print("⚠️ ВАЖНО:")
        print("   • Стоп-лоссы обновлены только в системе")
        print("   • На бирже они обновятся при следующем цикле трейлинга")
        print("   • Или можно перезапустить систему для немедленного обновления")
        
    else:
        print("✅ ВСЕ ПОЗИЦИИ УЖЕ ИМЕЮТ ПРАВИЛЬНЫЕ СТОП-ЛОССЫ")
    
    print()
    print("🎯 РЕЗУЛЬТАТ:")
    print("-" * 60)
    print(f"✅ Проанализировано позиций: {len([s for s in state.get('symbols', {}).keys() if not s.endswith('_position') and state['symbols'][s].get('active_position')])}")
    print(f"✅ Обновлено позиций: {len(updated_positions)}")
    print(f"✅ Минимальный ATR: {min_atr_pct*100:.1f}%")
    print(f"✅ Минимальное расстояние SL: {min_atr_pct * sl_atr_mult * 100:.1f}%")

if __name__ == "__main__":
    update_existing_stop_losses()
