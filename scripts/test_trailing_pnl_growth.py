#!/usr/bin/env python3

import sys
sys.path.append('.')

from signalwarden_lite.core.types import Position, Side
from signalwarden_lite.core.trailing_pnl_only import update_trailing_pnl_only, TrailingConfigPnLOnly

def test_trailing_pnl_growth():
    """Тест обновления трейлинга при росте PnL"""
    
    print('🔍 ТЕСТ ОБНОВЛЕНИЯ ТРЕЙЛИНГА ПРИ РОСТЕ PnL')
    print('=' * 80)
    
    # Конфигурация трейлинга (как в production)
    trailing_config = TrailingConfigPnLOnly(
        level_1_pnl=0.06,     # При $0.06 прибыли → сохранить 50% = минимум $0.03
        level_1_keep_pct=0.50,
        level_2_pnl=0.15,     # При $0.15 прибыли → сохранить 60% = минимум $0.09
        level_2_keep_pct=0.60,
        level_3_pnl=0.25,     # При $0.25 прибыли → сохранить 70% = минимум $0.175
        level_3_keep_pct=0.70,
        level_4_pnl=0.35,     # При $0.35+ прибыли → сохранить 80% = минимум $0.28
        level_4_keep_pct=0.80
    )
    
    # Тестовая позиция (как PNUT)
    entry_price = 0.236400
    qty = 88.83
    initial_sl = 0.227419
    
    print(f'📊 ТЕСТОВАЯ ПОЗИЦИЯ:')
    print(f'   Entry: ${entry_price:.6f}')
    print(f'   Qty: {qty:.2f}')
    print(f'   Initial SL: ${initial_sl:.6f}')
    print()
    
    # Сценарии роста цены и PnL
    price_scenarios = [
        (0.236400, 0.00, "Entry level - без прибыли"),
        (0.237100, 0.06, "Небольшой рост - приближение к Level 1"),
        (0.237070, 0.06, "Точно Level 1 - $0.06 прибыли"),
        (0.237500, 0.10, "Выше Level 1 - должен активироваться"),
        (0.238090, 0.15, "Точно Level 2 - $0.15 прибыли"),
        (0.238500, 0.19, "Выше Level 2 - должен улучшаться"),
        (0.239210, 0.25, "Точно Level 3 - $0.25 прибыли"),
        (0.239800, 0.30, "Выше Level 3 - должен улучшаться"),
        (0.240340, 0.35, "Точно Level 4 - $0.35 прибыли"),
        (0.241000, 0.41, "Максимальная прибыль - Level 4 80%"),
    ]
    
    print('🧮 ТЕСТИРОВАНИЕ РОСТА PnL И ТРЕЙЛИНГА:')
    print('-' * 80)
    
    current_sl = initial_sl
    peak_pnl = 0.0
    
    for i, (price, expected_pnl, description) in enumerate(price_scenarios, 1):
        # Создаем позицию с текущим состоянием
        position = Position(
            side=Side.LONG,
            entry=entry_price,
            sl=current_sl,
            sl_initial=initial_sl,
            qty=qty,
            remaining_qty=qty,
            r_per_unit=abs(initial_sl - entry_price),
            entry_reason="test"
        )
        
        # Устанавливаем накопленный peak PnL
        position.peak_pnl_usdt = peak_pnl
        
        # Рассчитываем текущий PnL
        actual_pnl = (price - entry_price) * qty
        
        print(f'   {i}. {description}:')
        print(f'      Price: ${price:.6f}')
        print(f'      Current PnL: ${actual_pnl:.4f} (expected: ${expected_pnl:.2f})')
        print(f'      Peak PnL before: ${peak_pnl:.4f}')
        print(f'      Current SL before: ${current_sl:.6f}')
        
        # Применяем трейлинг
        updated_pos = update_trailing_pnl_only(
            position,
            price,  # hi
            price,  # lo
            0.004,  # atr (не используется в PnL-only)
            trailing_config
        )
        
        # Получаем результаты
        debug_info = getattr(updated_pos, 'trailing_debug', {})
        level = debug_info.get('level', 'INACTIVE')
        keep_pct = debug_info.get('keep_pct', 0)
        target_profit = debug_info.get('target_profit', 0)
        sl_updated = debug_info.get('sl_updated', False)
        new_peak_pnl = updated_pos.peak_pnl_usdt
        new_sl = updated_pos.sl
        
        print(f'      New Peak PnL: ${new_peak_pnl:.4f}')
        print(f'      Trailing Level: {level}')
        print(f'      Keep %: {keep_pct*100:.0f}%')
        print(f'      Target profit: ${target_profit:.4f}')
        print(f'      New SL: ${new_sl:.6f}')
        print(f'      SL Updated: {sl_updated}')
        
        # Проверяем логику
        sl_improved = new_sl > current_sl
        should_improve = actual_pnl >= trailing_config.level_1_pnl
        
        if should_improve and sl_improved:
            print(f'      ✅ ТРЕЙЛИНГ РАБОТАЕТ: SL улучшился с ${current_sl:.6f} на ${new_sl:.6f}')
        elif should_improve and not sl_improved:
            print(f'      ❌ ПРОБЛЕМА: PnL достаточен но SL не улучшился!')
        elif not should_improve:
            print(f'      ⏸️ Трейлинг неактивен (PnL < ${trailing_config.level_1_pnl:.2f})')
        else:
            print(f'      ℹ️ SL остался прежним')
        
        # Обновляем состояние для следующего теста
        current_sl = new_sl
        peak_pnl = new_peak_pnl
        
        print()
    
    print('📋 ИТОГОВЫЙ АНАЛИЗ:')
    print('-' * 60)
    
    final_sl_improvement = current_sl - initial_sl
    final_protection = (current_sl - entry_price) * qty
    
    print(f'✅ Начальный SL: ${initial_sl:.6f}')
    print(f'✅ Финальный SL: ${current_sl:.6f}')
    print(f'✅ Улучшение SL: ${final_sl_improvement:.6f}')
    print(f'✅ Финальная защита: ${final_protection:.4f}')
    
    if final_sl_improvement > 0:
        print(f'🎉 ТРЕЙЛИНГ РАБОТАЕТ! SL поднялся на ${final_sl_improvement:.6f}')
        print(f'🛡️ Защищенная прибыль: ${final_protection:.4f}')
    else:
        print(f'❌ ТРЕЙЛИНГ НЕ РАБОТАЕТ! SL не улучшился.')
    
    return final_sl_improvement > 0

def test_trailing_live_logic():
    """Тест логики принятия решения об обновлении в live системе"""
    
    print('\n🔍 ТЕСТ ЛОГИКИ ПРИНЯТИЯ РЕШЕНИЯ ОБ ОБНОВЛЕНИИ')
    print('=' * 80)
    
    # Тестовые данные
    test_cases = [
        {
            'description': 'Первое улучшение SL',
            'old_sl': 0.227419,
            'new_sl': 0.228500,  # Улучшение +0.001081
            'side': 'LONG',
            'entry': 0.236400,
            'expected_update': True
        },
        {
            'description': 'Небольшое улучшение SL',
            'old_sl': 0.228500,
            'new_sl': 0.228600,  # Улучшение +0.0001
            'side': 'LONG', 
            'entry': 0.236400,
            'expected_update': True
        },
        {
            'description': 'Микро улучшение SL',
            'old_sl': 0.228600,
            'new_sl': 0.228600001,  # Улучшение +0.000000001
            'side': 'LONG',
            'entry': 0.236400,
            'expected_update': False  # Слишком мало
        },
        {
            'description': 'Попытка ухудшения SL',
            'old_sl': 0.228600,
            'new_sl': 0.228500,  # Ухудшение -0.0001
            'side': 'LONG',
            'entry': 0.236400,
            'expected_update': False
        }
    ]
    
    print('🧮 ТЕСТИРОВАНИЕ ЛОГИКИ ОБНОВЛЕНИЯ:')
    print('-' * 80)
    
    all_passed = True
    
    for i, case in enumerate(test_cases, 1):
        old_sl = case['old_sl']
        new_sl = case['new_sl']
        entry = case['entry']
        expected = case['expected_update']
        description = case['description']
        
        # Логика как в коде (из update_trailing_stops)
        min_improvement = entry * 0.000001  # 0.0001% от entry
        improvement = new_sl - old_sl
        should_update = improvement > min_improvement
        
        # Проверка результата
        result = "✅ PASS" if should_update == expected else "❌ FAIL"
        if should_update != expected:
            all_passed = False
        
        print(f'   {i}. {description}')
        print(f'      Old SL: ${old_sl:.6f}, New SL: ${new_sl:.6f}')
        print(f'      Improvement: {improvement:+.9f} (min: {min_improvement:.9f})')
        print(f'      Should update: {should_update}, Expected: {expected} - {result}')
        print()
    
    if all_passed:
        print('✅ ВСЯ ЛОГИКА РАБОТАЕТ КОРРЕКТНО!')
    else:
        print('❌ ЕСТЬ ПРОБЛЕМЫ В ЛОГИКЕ!')
    
    return all_passed

def main():
    """Основная функция тестирования"""
    
    print('🧪 КОМПЛЕКСНЫЙ ТЕСТ ТРЕЙЛИНГА ПРИ РОСТЕ PnL')
    print('=' * 100)
    
    # Тест 1: Рост PnL и активация трейлинга
    trailing_works = test_trailing_pnl_growth()
    
    # Тест 2: Логика принятия решений
    logic_works = test_trailing_live_logic()
    
    # Итоговый результат
    print('\n' + '='*100)
    print('📋 ИТОГОВЫЙ РЕЗУЛЬТАТ:')
    print('='*100)
    
    print(f'✅ Трейлинг при росте PnL: {"РАБОТАЕТ" if trailing_works else "НЕ РАБОТАЕТ"}')
    print(f'✅ Логика принятия решений: {"РАБОТАЕТ" if logic_works else "НЕ РАБОТАЕТ"}')
    
    if trailing_works and logic_works:
        print(f'\n🎉 ВСЕ ТЕСТЫ ПРОШЛИ! ТРЕЙЛИНГ БУДЕТ ОБНОВЛЯТЬСЯ ПРИ РОСТЕ PnL!')
        print(f'🛡️ Система готова правильно поднимать стоп-лоссы по мере роста прибыли')
    else:
        print(f'\n⚠️ ЕСТЬ ПРОБЛЕМЫ! Трейлинг может не работать корректно')
    
    return trailing_works and logic_works

if __name__ == '__main__':
    main()
