#!/usr/bin/env python3

import json
import sys
sys.path.append('.')

from signalwarden_lite.core.types import Position, Side
from signalwarden_lite.core.trailing_pnl_only import update_trailing_pnl_only, TrailingConfigPnLOnly

def test_real_trailing():
    """Тест реального трейлинга с текущими позициями"""
    
    print('🧪 ТЕСТ РЕАЛЬНОГО ТРЕЙЛИНГА')
    print('=' * 80)
    
    # Конфигурация трейлинга (как в production)
    trailing_config = TrailingConfigPnLOnly(
        level_1_pnl=0.06,     # При $0.06 прибыли
        level_1_keep_pct=0.50, # сохранить 50% = минимум $0.03
        level_2_pnl=0.15,     # При $0.15 прибыли  
        level_2_keep_pct=0.60, # сохранить 60% = минимум $0.09
        level_3_pnl=0.25,     # При $0.25 прибыли
        level_3_keep_pct=0.70, # сохранить 70% = минимум $0.175
        level_4_pnl=0.35,     # При $0.35+ прибыли
        level_4_keep_pct=0.80  # сохранить 80% = минимум $0.28
    )
    
    # Загружаем текущие позиции
    with open('trading_state_v1_6_TXB.json', 'r') as f:
        state = json.load(f)
    
    for symbol in ['PNUT_USDT', 'WIF_USDT']:
        data = state.get('symbols', {}).get(symbol, {})
        active_pos = data.get('active_position')
        
        if not active_pos:
            continue
            
        print(f'📊 ТЕСТИРОВАНИЕ {symbol}:')
        print('-' * 60)
        
        entry = active_pos.get('entry', 0)
        qty = active_pos.get('qty', 0)
        sl_current = active_pos.get('sl_current', 0)
        peak_pnl = active_pos.get('peak_pnl_usdt', 0)
        
        print(f'   Entry: ${entry:.6f}')
        print(f'   Qty: {qty:.4f}')
        print(f'   Current SL: ${sl_current:.6f}')
        print(f'   Peak PnL: ${peak_pnl:.4f}')
        
        # Создаем Position объект
        position = Position(
            side=Side.LONG,
            entry=entry,
            sl=sl_current,
            sl_initial=sl_current,
            qty=qty,
            remaining_qty=qty,
            r_per_unit=abs(sl_current - entry),
            entry_reason="test"
        )
        
        # Устанавливаем peak_pnl_usdt из состояния
        position.peak_pnl_usdt = peak_pnl
        
        # Тестируем различные цены
        test_prices = [
            (entry + 0.001, "Небольшой рост (+0.1%)"),
            (entry + 0.003, "Средний рост (+0.3%)"),
            (entry + 0.005, "Хороший рост (+0.5%)"),
            (entry + 0.008, "Отличный рост (+0.8%)")
        ]
        
        for test_price, description in test_prices:
            current_pnl = (test_price - entry) * qty
            
            print(f'\n   🔍 {description}:')
            print(f'      Test Price: ${test_price:.6f}')
            print(f'      Current PnL: ${current_pnl:.4f}')
            
            # Применяем трейлинг
            test_pos = Position(
                side=Side.LONG,
                entry=entry,
                sl=sl_current,
                sl_initial=sl_current,
                qty=qty,
                remaining_qty=qty,
                r_per_unit=abs(sl_current - entry),
                entry_reason="test"
            )
            test_pos.peak_pnl_usdt = max(peak_pnl, current_pnl)  # Обновляем пик
            
            updated_pos = update_trailing_pnl_only(
                test_pos,
                test_price,  # hi
                test_price,  # lo
                0.004,       # atr (не используется в PnL-only)
                trailing_config
            )
            
            # Получаем отладочную информацию
            debug_info = getattr(updated_pos, 'trailing_debug', {})
            level = debug_info.get('level', 'UNKNOWN')
            keep_pct = debug_info.get('keep_pct', 0)
            target_profit = debug_info.get('target_profit', 0)
            sl_updated = debug_info.get('sl_updated', False)
            
            print(f'      New Peak PnL: ${updated_pos.peak_pnl_usdt:.4f}')
            print(f'      Level: {level}')
            print(f'      Keep %: {keep_pct*100:.0f}%')
            print(f'      Target profit: ${target_profit:.4f}')
            print(f'      New SL: ${updated_pos.sl:.6f}')
            print(f'      SL updated: {sl_updated}')
            
            # Проверяем активацию
            if current_pnl >= trailing_config.level_1_pnl:
                if level == 'INACTIVE':
                    print(f'      ❌ ПРОБЛЕМА: Трейлинг должен быть активен!')
                else:
                    print(f'      ✅ Трейлинг активен')
            else:
                print(f'      ⏸️ Трейлинг неактивен (PnL < ${trailing_config.level_1_pnl:.2f})')
        
        print()
    
    # Тест с принудительным высоким PnL
    print('🚀 ТЕСТ С ПРИНУДИТЕЛЬНО ВЫСОКИМ PnL:')
    print('-' * 60)
    
    # Используем PNUT для демонстрации
    pnut_data = state.get('symbols', {}).get('PNUT_USDT', {})
    pnut_pos = pnut_data.get('active_position')
    
    if pnut_pos:
        entry = pnut_pos.get('entry', 0)
        qty = pnut_pos.get('qty', 0)
        sl_current = pnut_pos.get('sl_current', 0)
        
        # Создаем позицию с высоким PnL
        high_pnl_pos = Position(
            side=Side.LONG,
            entry=entry,
            sl=sl_current,
            sl_initial=sl_current,
            qty=qty,
            remaining_qty=qty,
            r_per_unit=abs(sl_current - entry),
            entry_reason="test"
        )
        
        # Устанавливаем высокий peak PnL
        high_pnl_pos.peak_pnl_usdt = 0.20  # $0.20 пиковая прибыль
        
        # Текущая цена с небольшой просадкой
        current_price = entry + 0.007  # Чуть меньше пика
        current_pnl = (current_price - entry) * qty
        
        print(f'   PNUT_USDT с принудительным высоким PnL:')
        print(f'   Entry: ${entry:.6f}')
        print(f'   Current Price: ${current_price:.6f}')
        print(f'   Peak PnL: ${high_pnl_pos.peak_pnl_usdt:.4f}')
        print(f'   Current PnL: ${current_pnl:.4f}')
        
        # Применяем трейлинг
        updated_pos = update_trailing_pnl_only(
            high_pnl_pos,
            current_price,
            current_price,
            0.004,
            trailing_config
        )
        
        debug_info = getattr(updated_pos, 'trailing_debug', {})
        level = debug_info.get('level', 'UNKNOWN')
        target_profit = debug_info.get('target_profit', 0)
        sl_updated = debug_info.get('sl_updated', False)
        
        print(f'   Level: {level}')
        print(f'   Target profit: ${target_profit:.4f}')
        print(f'   Old SL: ${sl_current:.6f}')
        print(f'   New SL: ${updated_pos.sl:.6f}')
        print(f'   SL updated: {sl_updated}')
        
        if sl_updated and updated_pos.sl > sl_current:
            print(f'   ✅ ТРЕЙЛИНГ РАБОТАЕТ! SL поднят на ${updated_pos.sl - sl_current:.6f}')
        else:
            print(f'   ❌ ТРЕЙЛИНГ НЕ СРАБОТАЛ!')

if __name__ == '__main__':
    test_real_trailing()
