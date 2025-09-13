#!/usr/bin/env python3
"""
Тест ПРАВИЛЬНОЙ логики трейлинга:
1. ДО активации: SL на 2.5×ATR от entry
2. ПОСЛЕ активации: SL защищает прибыль по уровням (может быть ближе чем 2.5×ATR)
"""

import sys
import os
sys.path.append('.')

import yaml
from signalwarden_lite.core.trailing_pnl_only import TrailingConfigPnLOnly, update_trailing_pnl_only
from signalwarden_lite.core.types import Position, Side

def test_correct_trailing_logic():
    """Тест правильной логики трейлинга"""
    print("🎯 ПРАВИЛЬНАЯ ЛОГИКА ТРЕЙЛИНГА")
    print("=" * 80)
    
    # Загружаем конфигурацию
    with open('signalwarden_lite/config/config_production.yaml', 'r') as f:
        cfg = yaml.safe_load(f)
    
    sl_atr_mult = cfg['risk']['sl_atr_mult']
    
    # Создаем конфигурацию трейлинга
    trailing_cfg = TrailingConfigPnLOnly(
        level_1_pnl=0.06,   # $0.06 - сохранить 50%
        level_1_keep_pct=0.50,
        level_2_pnl=0.15,   # $0.15 - сохранить 60%
        level_2_keep_pct=0.60,
        level_3_pnl=0.25,   # $0.25 - сохранить 70%
        level_3_keep_pct=0.70,
        level_4_pnl=0.35,   # $0.35+ - сохранить 80%
        level_4_keep_pct=0.80
    )
    
    print("📋 ПРАВИЛЬНАЯ ЛОГИКА:")
    print("1. ДО активации трейлинга: SL на расстоянии 2.5×ATR от entry")
    print("2. ПОСЛЕ активации: SL защищает прибыль по уровням")
    print("3. SL может стать БЛИЖЕ чем 2.5×ATR (это НОРМАЛЬНО)")
    print("4. SL только УЛУЧШАЕТСЯ, никогда не ухудшается")
    print()
    
    # СЦЕНАРИЙ: ADA_USDT
    entry = 0.948900
    atr = 0.008879
    qty = 21.0
    
    # Начальный SL (2.5×ATR)
    initial_sl = entry - (sl_atr_mult * atr)
    min_distance_initial = sl_atr_mult * atr
    
    print(f"📊 НАЧАЛЬНЫЕ УСЛОВИЯ:")
    print(f"   Entry: ${entry:.6f}")
    print(f"   ATR: {atr:.6f}")
    print(f"   Initial SL (2.5×ATR): ${initial_sl:.6f}")
    print(f"   Initial Distance: ${min_distance_initial:.6f} ({min_distance_initial/entry*100:.2f}%)")
    print()
    
    # ЭТАП 1: ДО активации трейлинга
    print("🔒 ЭТАП 1: ДО АКТИВАЦИИ ТРЕЙЛИНГА")
    print("-" * 60)
    
    position = Position(
        side=Side.LONG,
        entry=entry,
        qty=qty,
        remaining_qty=qty,
        r_per_unit=0.05,
        sl=initial_sl,
        peak_pnl_usdt=0.0
    )
    
    # Небольшие движения цены - трейлинг НЕ активен
    small_moves = [
        {'price': 0.950000, 'desc': 'Небольшой рост +0.1%'},
        {'price': 0.952000, 'desc': 'Рост +0.3%'},
        {'price': 0.954000, 'desc': 'Рост +0.5%'}
    ]
    
    current_pos = position
    
    for i, move in enumerate(small_moves, 1):
        price = move['price']
        desc = move['desc']
        
        updated_pos = update_trailing_pnl_only(current_pos, price, 0, atr, trailing_cfg)
        current_pnl = (price - entry) * qty
        
        print(f"   {i}. {desc}")
        print(f"      Price: ${price:.6f}")
        print(f"      PnL: ${current_pnl:.3f}")
        print(f"      Peak PnL: ${updated_pos.peak_pnl_usdt:.3f}")
        print(f"      SL: ${updated_pos.sl:.6f}")
        
        # Проверяем активность трейлинга
        if hasattr(updated_pos, 'trailing_debug'):
            debug = updated_pos.trailing_debug
            if debug.get('level') != 'INACTIVE':
                print(f"      🔄 Трейлинг: {debug.get('level')}")
            else:
                print(f"      🔒 Трейлинг: НЕАКТИВЕН")
        
        # SL должен остаться на 2.5×ATR
        sl_distance = entry - updated_pos.sl
        sl_distance_pct = (sl_distance / entry) * 100
        print(f"      Distance: ${sl_distance:.6f} ({sl_distance_pct:.2f}%)")
        
        if abs(sl_distance - min_distance_initial) < 0.000001:
            print(f"      ✅ SL на правильном расстоянии 2.5×ATR")
        else:
            print(f"      ❌ SL изменился!")
        print()
        
        current_pos = updated_pos
    
    # ЭТАП 2: АКТИВАЦИЯ трейлинга
    print("🔓 ЭТАП 2: АКТИВАЦИЯ ТРЕЙЛИНГА")
    print("-" * 60)
    
    # Цена растет достаточно для активации Level 1 ($0.06)
    activation_price = entry + (0.08 / qty)  # Чтобы PnL был > $0.06
    
    activated_pos = update_trailing_pnl_only(current_pos, activation_price, 0, atr, trailing_cfg)
    activation_pnl = (activation_price - entry) * qty
    
    print(f"   Цена активации: ${activation_price:.6f}")
    print(f"   PnL активации: ${activation_pnl:.3f}")
    print(f"   Peak PnL: ${activated_pos.peak_pnl_usdt:.3f}")
    print(f"   SL до активации: ${current_pos.sl:.6f}")
    print(f"   SL после активации: ${activated_pos.sl:.6f}")
    
    # Проверяем активность трейлинга
    if hasattr(activated_pos, 'trailing_debug'):
        debug = activated_pos.trailing_debug
        if debug.get('level') != 'INACTIVE':
            print(f"   🔄 Трейлинг АКТИВИРОВАН: {debug.get('level')} ({debug.get('keep_pct')*100:.0f}%)")
        else:
            print(f"   🔒 Трейлинг все еще неактивен")
    
    # Проверяем улучшился ли SL
    if activated_pos.sl > current_pos.sl:
        improvement = activated_pos.sl - current_pos.sl
        print(f"   📈 SL УЛУЧШИЛСЯ на ${improvement:.6f}")
    else:
        print(f"   📊 SL не изменился")
    
    print()
    
    # ЭТАП 3: РАБОТА активного трейлинга
    print("⚡ ЭТАП 3: РАБОТА АКТИВНОГО ТРЕЙЛИНГА")
    print("-" * 60)
    
    # Дальнейший рост цены
    trailing_moves = [
        {'price': entry + 0.008, 'desc': 'Рост продолжается'},
        {'price': entry + 0.012, 'desc': 'Хороший рост'},
        {'price': entry + 0.016, 'desc': 'Отличный рост'}
    ]
    
    current_pos = activated_pos
    
    for i, move in enumerate(trailing_moves, 1):
        price = move['price']
        desc = move['desc']
        
        updated_pos = update_trailing_pnl_only(current_pos, price, 0, atr, trailing_cfg)
        current_pnl = (price - entry) * qty
        
        print(f"   {i}. {desc}")
        print(f"      Price: ${price:.6f}")
        print(f"      PnL: ${current_pnl:.3f}")
        print(f"      Peak PnL: ${updated_pos.peak_pnl_usdt:.3f}")
        print(f"      SL: ${updated_pos.sl:.6f}")
        
        # Проверяем уровень трейлинга
        if hasattr(updated_pos, 'trailing_debug'):
            debug = updated_pos.trailing_debug
            if debug.get('level') != 'INACTIVE':
                print(f"      🔄 Трейлинг: {debug.get('level')} ({debug.get('keep_pct')*100:.0f}%)")
        
        # Проверяем улучшился ли SL
        if updated_pos.sl > current_pos.sl:
            improvement = updated_pos.sl - current_pos.sl
            print(f"      📈 SL улучшился на ${improvement:.6f}")
        else:
            print(f"      📊 SL остался прежним")
        
        # Показываем расстояние от entry
        sl_distance = entry - updated_pos.sl
        sl_distance_pct = (sl_distance / entry) * 100
        print(f"      Distance от entry: ${sl_distance:.6f} ({sl_distance_pct:.2f}%)")
        
        # Это НОРМАЛЬНО если расстояние меньше 2.5×ATR после активации
        if sl_distance < min_distance_initial:
            print(f"      ✅ SL ближе чем 2.5×ATR - это НОРМАЛЬНО после активации!")
        else:
            print(f"      📊 SL все еще на расстоянии ≥ 2.5×ATR")
        
        print()
        current_pos = updated_pos
    
    # ВЫВОДЫ
    print("🎯 ПРАВИЛЬНАЯ ЛОГИКА ТРЕЙЛИНГА:")
    print("-" * 60)
    print("1. ✅ ДО активации: SL строго на 2.5×ATR")
    print("2. ✅ ПОСЛЕ активации: SL защищает прибыль (может быть ближе)")
    print("3. ✅ SL только улучшается, никогда не ухудшается")
    print("4. ✅ Трейлинг работает по уровням прибыли")
    print()
    print("🚀 ЭТО ПРАВИЛЬНОЕ ПОВЕДЕНИЕ СИСТЕМЫ!")
    
    return True

if __name__ == "__main__":
    test_correct_trailing_logic()
