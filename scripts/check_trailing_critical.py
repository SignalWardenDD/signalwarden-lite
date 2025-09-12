#!/usr/bin/env python3

import json
from datetime import datetime

def check_trailing_critical():
    """Критическая проверка трейлинга для PNUT и WIF"""
    
    print('🚨 КРИТИЧЕСКАЯ ПРОВЕРКА ТРЕЙЛИНГА PNUT И WIF:')
    print('=' * 80)
    
    # Проверяем текущие позиции PNUT и WIF
    with open('trading_state_v1_6_TXB.json', 'r') as f:
        state = json.load(f)

    critical_issues = []

    for symbol in ['PNUT_USDT', 'WIF_USDT']:
        data = state.get('symbols', {}).get(symbol, {})
        active_pos = data.get('active_position')
        
        if active_pos:
            entry = active_pos.get('entry', 0)
            sl_current = active_pos.get('sl_current', 0)
            sl_initial = active_pos.get('sl_initial', 0)
            qty = active_pos.get('qty', 0)
            timestamp = active_pos.get('timestamp', 0)
            
            print(f'📊 {symbol}:')
            print(f'   Entry: ${entry:.6f}')
            print(f'   Current SL: ${sl_current:.6f}')
            print(f'   Initial SL: ${sl_initial:.6f}')
            print(f'   Qty: {qty:.4f}')
            
            # Время открытия позиции
            if timestamp:
                open_time = datetime.fromtimestamp(timestamp)
                print(f'   Opened: {open_time.strftime("%Y-%m-%d %H:%M:%S")}')
            
            # Проверяем, изменился ли SL от начального
            sl_moved = abs(sl_current - sl_initial) > 0.000001
            print(f'   SL moved: {sl_moved}')
            
            if not sl_moved:
                critical_issues.append(f'{symbol}: SL НЕ ОБНОВЛЯЛСЯ!')
                print(f'   ❌ КРИТИЧЕСКАЯ ПРОБЛЕМА: SL НЕ ОБНОВЛЯЛСЯ!')
            else:
                print(f'   ✅ SL обновлялся')
            
            # Проверяем peak_pnl_usdt
            peak_pnl = active_pos.get('peak_pnl_usdt', 0)
            print(f'   Peak PnL: ${peak_pnl:.4f}')
            
            if peak_pnl <= 0:
                critical_issues.append(f'{symbol}: Peak PnL не отслеживается!')
                print(f'   ❌ КРИТИЧЕСКАЯ ПРОБЛЕМА: Peak PnL не отслеживается!')
            else:
                print(f'   ✅ Peak PnL отслеживается')
            
            # Проверяем трейлинг настройки
            trailing_level = active_pos.get('trailing_level', 'НЕИЗВЕСТНО')
            print(f'   Trailing level: {trailing_level}')
            
            print()
        else:
            print(f'📊 {symbol}: НЕТ АКТИВНОЙ ПОЗИЦИИ')
            print()

    print('🔍 ДИАГНОСТИКА ПРОБЛЕМ:')
    print('-' * 60)
    
    if critical_issues:
        print('❌ НАЙДЕНЫ КРИТИЧЕСКИЕ ПРОБЛЕМЫ:')
        for issue in critical_issues:
            print(f'   • {issue}')
    else:
        print('✅ Критических проблем не найдено')
    
    print('\n🛠️ ВОЗМОЖНЫЕ ПРИЧИНЫ:')
    print('1. Трейлинг не активируется из-за недостаточного PnL')
    print('2. Ошибка в логике update_trailing_pnl_only')
    print('3. Проблема с обновлением peak_pnl_usdt')
    print('4. Неправильная конфигурация уровней трейлинга')
    
    return len(critical_issues) == 0

if __name__ == '__main__':
    check_trailing_critical()
