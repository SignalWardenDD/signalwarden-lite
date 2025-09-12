#!/usr/bin/env python3

import json
import sys
sys.path.append('.')

def diagnose_trailing_issue():
    """Диагностика проблем с трейлингом"""
    
    print('🔍 ДИАГНОСТИКА ПРОБЛЕМ С ТРЕЙЛИНГОМ')
    print('=' * 80)
    
    # Проверяем текущее состояние
    with open('trading_state_v1_6_TXB.json', 'r') as f:
        state = json.load(f)
    
    print('1. ПРОВЕРКА ПОЗИЦИЙ В ФАЙЛЕ:')
    print('-' * 60)
    
    for symbol in ['PNUT_USDT', 'WIF_USDT']:
        data = state.get('symbols', {}).get(symbol, {})
        active_pos = data.get('active_position')
        
        if active_pos:
            entry = active_pos.get('entry', 0)
            qty = active_pos.get('qty', 0)
            peak_pnl = active_pos.get('peak_pnl_usdt', 0)
            
            print(f'   {symbol}:')
            print(f'     Entry: ${entry:.6f}')
            print(f'     Qty: {qty:.4f}')
            print(f'     Peak PnL: ${peak_pnl:.4f}')
            
            # Симулируем текущую цену (немного выше entry)
            simulated_current_price = entry * 1.003  # +0.3%
            simulated_pnl = (simulated_current_price - entry) * qty
            
            print(f'     Симулированная цена: ${simulated_current_price:.6f}')
            print(f'     Симулированный PnL: ${simulated_pnl:.4f}')
            
            # Проверяем условие блокировки трейлинга
            if simulated_pnl <= 0:
                print(f'     ❌ ПРОБЛЕМА: PnL <= 0, трейлинг будет заблокирован!')
            else:
                print(f'     ✅ PnL > 0, трейлинг должен работать')
        else:
            print(f'   {symbol}: НЕТ АКТИВНОЙ ПОЗИЦИИ')
        print()
    
    print('2. АНАЛИЗ КОДА ТРЕЙЛИНГА:')
    print('-' * 60)
    print('   Проблемы в update_trailing_stops():')
    print('   • Строка 765: if real_pnl <= 0: continue')
    print('   • get_position_pnl_from_exchange() может возвращать 0.0')
    print('   • Это блокирует весь трейлинг!')
    print()
    
    print('3. ВОЗМОЖНЫЕ ПРИЧИНЫ:')
    print('-' * 60)
    print('   A. Paper mode (возвращает 0.0)')
    print('   B. Позиция не найдена на бирже (возвращает 0.0)')
    print('   C. Ошибка при fetch_positions (возвращает 0.0)')
    print('   D. Неправильный ccxt_symbol формат')
    print()
    
    print('4. РЕШЕНИЯ:')
    print('-' * 60)
    print('   ✅ Убрать проверку real_pnl <= 0 или сделать ее менее строгой')
    print('   ✅ Использовать расчетный PnL если биржевый недоступен')
    print('   ✅ Добавить диагностику get_position_pnl_from_exchange')
    print('   ✅ Обеспечить загрузку позиций напрямую с Binance')
    print()
    
    print('5. КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ:')
    print('-' * 60)
    print('   Нужно исправить логику в update_trailing_stops():')
    print('   • Не блокировать трейлинг при PnL <= 0')
    print('   • Использовать расчетный PnL как fallback')
    print('   • Обновлять peak_pnl_usdt даже при небольшом PnL')
    print()
    
    return True

if __name__ == '__main__':
    diagnose_trailing_issue()
