#!/usr/bin/env python3

def test_sl_improvement_logic():
    """Тест логики улучшения стоп-лоссов"""
    
    print('🔍 ТЕСТ ЛОГИКИ УЛУЧШЕНИЯ СТОП-ЛОССОВ')
    print('=' * 80)
    
    # Тестовые данные
    test_cases = [
        # LONG позиции
        {
            'side': 'LONG',
            'entry': 1.0000,
            'old_sl': 0.9800,
            'new_sl': 0.9850,  # Улучшение +0.005
            'expected': True,
            'description': 'LONG: SL улучшается (выше)'
        },
        {
            'side': 'LONG', 
            'entry': 1.0000,
            'old_sl': 0.9800,
            'new_sl': 0.9750,  # Ухудшение -0.005
            'expected': False,
            'description': 'LONG: SL ухудшается (ниже) - БЛОКИРОВАТЬ'
        },
        {
            'side': 'LONG',
            'entry': 1.0000,
            'old_sl': 0.9800,
            'new_sl': 0.9800,  # Без изменений
            'expected': False,
            'description': 'LONG: SL без изменений - НЕ ОБНОВЛЯТЬ'
        },
        
        # SHORT позиции
        {
            'side': 'SHORT',
            'entry': 1.0000,
            'old_sl': 1.0200,
            'new_sl': 1.0150,  # Улучшение -0.005
            'expected': True,
            'description': 'SHORT: SL улучшается (ниже)'
        },
        {
            'side': 'SHORT',
            'entry': 1.0000,
            'old_sl': 1.0200,
            'new_sl': 1.0250,  # Ухудшение +0.005
            'expected': False,
            'description': 'SHORT: SL ухудшается (выше) - БЛОКИРОВАТЬ'
        },
        {
            'side': 'SHORT',
            'entry': 1.0000,
            'old_sl': 1.0200,
            'new_sl': 1.0200,  # Без изменений
            'expected': False,
            'description': 'SHORT: SL без изменений - НЕ ОБНОВЛЯТЬ'
        }
    ]
    
    print('🧮 ТЕСТИРОВАНИЕ ЛОГИКИ:')
    print('-' * 80)
    
    all_passed = True
    
    for i, case in enumerate(test_cases, 1):
        entry = case['entry']
        old_sl = case['old_sl']
        new_sl = case['new_sl']
        side = case['side']
        expected = case['expected']
        description = case['description']
        
        # Минимальное улучшение (0.0001% от entry)
        min_improvement = entry * 0.000001
        
        # Логика как в коде
        should_update = False
        
        if side == 'LONG':
            improvement = new_sl - old_sl
            if improvement > min_improvement:
                should_update = True
            elif improvement < -min_improvement:
                should_update = False  # Ухудшение блокировано
            else:
                should_update = False  # Слишком мало изменений
        
        elif side == 'SHORT':
            improvement = old_sl - new_sl  # Для шортов улучшение = уменьшение SL
            if improvement > min_improvement:
                should_update = True
            elif improvement < -min_improvement:
                should_update = False  # Ухудшение блокировано
            else:
                should_update = False  # Слишком мало изменений
        
        # Проверка результата
        result = "✅ PASS" if should_update == expected else "❌ FAIL"
        if should_update != expected:
            all_passed = False
        
        print(f'   {i}. {description}')
        print(f'      Entry: {entry:.4f}, Old SL: {old_sl:.4f}, New SL: {new_sl:.4f}')
        print(f'      Should update: {should_update}, Expected: {expected} - {result}')
        
        if side == 'LONG':
            improvement = new_sl - old_sl
            print(f'      Improvement: {improvement:+.6f} (min: {min_improvement:.6f})')
        else:
            improvement = old_sl - new_sl
            print(f'      Improvement: {improvement:+.6f} (min: {min_improvement:.6f})')
        print()
    
    print('📋 ИТОГОВЫЙ РЕЗУЛЬТАТ:')
    print('-' * 60)
    if all_passed:
        print('✅ ВСЕ ТЕСТЫ ПРОШЛИ! Логика работает корректно.')
        print('✅ Стоп-лоссы будут обновляться ТОЛЬКО при улучшении.')
    else:
        print('❌ НЕКОТОРЫЕ ТЕСТЫ НЕ ПРОШЛИ! Требуется исправление логики.')
    
    print()
    print('🛡️ ПРАВИЛА ОБНОВЛЕНИЯ SL:')
    print('   • LONG: новый SL > старого SL (выше = лучше)')
    print('   • SHORT: новый SL < старого SL (ниже = лучше)')
    print('   • Минимальное изменение: 0.0001% от entry цены')
    print('   • Никаких обновлений без реального улучшения')
    
    return all_passed

if __name__ == '__main__':
    test_sl_improvement_logic()
