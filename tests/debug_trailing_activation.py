#!/usr/bin/env python3
"""
Отладка активации трейлинга
"""

import os
import sys

# Добавляем путь к модулям
sys.path.append('.')

from signalwarden_lite.core.trailing import update_trailing_pnl_based
from signalwarden_lite.core.types import Position, Side
from dataclasses import dataclass

@dataclass
class TrailingConfig:
    activate_pnl_usdt: float = 0.10
    level_1_pnl: float = 0.10
    level_1_keep_pct: float = 0.50
    level_2_pnl: float = 0.20
    level_2_keep_pct: float = 0.60
    level_3_pnl: float = 0.30
    level_3_keep_pct: float = 0.70
    level_4_pnl: float = 0.40
    level_4_keep_pct: float = 0.80

def debug_trailing_activation():
    """Отладка активации трейлинга"""
    
    print("🔍 ОТЛАДКА АКТИВАЦИИ ТРЕЙЛИНГА")
    print("=" * 80)
    
    # Создаем тестовую позицию
    test_position = Position(
        side=Side.LONG,
        entry=115.50,
        sl=109.50,
        sl_initial=109.50,
        qty=0.18,
        remaining_qty=0.18,
        r_per_unit=6.0
    )
    test_position.peak_pnl_usdt = 0.0
    
    trailing_config = TrailingConfig()
    
    print(f"📊 КОНФИГУРАЦИЯ:")
    print(f"   activate_pnl_usdt: {trailing_config.activate_pnl_usdt}")
    print(f"   level_1_pnl: {trailing_config.level_1_pnl}")
    print(f"   level_1_keep_pct: {trailing_config.level_1_keep_pct}")
    print()
    
    print(f"📊 ПОЗИЦИЯ:")
    print(f"   Entry: ${test_position.entry:.6f}")
    print(f"   SL: ${test_position.sl:.6f}")
    print(f"   Quantity: {test_position.qty:.6f}")
    print(f"   Peak PnL: {test_position.peak_pnl_usdt:.4f}")
    print()
    
    # Тест с достаточной прибылью
    good_price = 117.0
    good_pnl = (good_price - test_position.entry) * test_position.qty
    
    print(f"💰 ТЕСТ УСЛОВИЙ:")
    print(f"   Price: ${good_price:.2f}")
    print(f"   PnL: {good_pnl:.4f} USDT")
    print()
    
    print(f"🔍 ПРОВЕРКА УСЛОВИЙ АКТИВАЦИИ:")
    print(f"   current_pnl >= activate_pnl: {good_pnl:.4f} >= {trailing_config.activate_pnl_usdt} = {good_pnl >= trailing_config.activate_pnl_usdt}")
    print(f"   current_pnl > 0: {good_pnl:.4f} > 0 = {good_pnl > 0}")
    print()
    
    if good_pnl >= trailing_config.activate_pnl_usdt and good_pnl > 0:
        print("✅ УСЛОВИЯ АКТИВАЦИИ ВЫПОЛНЕНЫ")
        
        # Определяем уровень
        if good_pnl >= trailing_config.level_2_pnl:
            level_pnl = trailing_config.level_2_pnl
            keep_pct = trailing_config.level_2_keep_pct
            level_name = "L2"
        else:
            level_pnl = trailing_config.level_1_pnl
            keep_pct = trailing_config.level_1_keep_pct
            level_name = "L1"
        
        target_profit = good_pnl * keep_pct  # На основе текущего PnL
        new_sl = test_position.entry + (target_profit / test_position.qty)
        
        print(f"📊 РАСЧЕТ ТРЕЙЛИНГА:")
        print(f"   Уровень: {level_name}")
        print(f"   Keep %: {keep_pct*100}%")
        print(f"   Peak PnL: {good_pnl:.4f} (будет обновлен)")
        print(f"   Target profit: {target_profit:.4f} USDT")
        print(f"   New SL: ${new_sl:.6f}")
        print(f"   Old SL: ${test_position.sl:.6f}")
        print()
        
        print(f"🔍 ПРОВЕРКА УЛУЧШЕНИЯ:")
        print(f"   new_sl > old_sl: ${new_sl:.6f} > ${test_position.sl:.6f} = {new_sl > test_position.sl}")
        print(f"   new_sl > entry: ${new_sl:.6f} > ${test_position.entry:.6f} = {new_sl > test_position.entry}")
        
        if new_sl > test_position.entry and new_sl > test_position.sl:
            print("✅ SL ДОЛЖЕН ОБНОВИТЬСЯ")
        else:
            print("❌ SL НЕ ОБНОВИТСЯ")
            
    else:
        print("❌ УСЛОВИЯ АКТИВАЦИИ НЕ ВЫПОЛНЕНЫ")
    
    print()
    
    # Вызываем реальную функцию
    print("🧮 ВЫЗОВ РЕАЛЬНОЙ ФУНКЦИИ:")
    print("-" * 60)
    
    result_pos = update_trailing_pnl_based(
        test_position, 
        good_price, 
        good_pnl, 
        trailing_config
    )
    
    print(f"📊 РЕЗУЛЬТАТ:")
    print(f"   Old SL: ${test_position.sl:.6f}")
    print(f"   New SL: ${result_pos.sl:.6f}")
    print(f"   Peak PnL: {result_pos.peak_pnl_usdt:.4f}")
    print(f"   SL Updated: {result_pos.sl != test_position.sl}")
    
    if hasattr(result_pos, 'trailing_debug'):
        debug_info = result_pos.trailing_debug
        print(f"📋 DEBUG INFO:")
        for key, value in debug_info.items():
            print(f"   {key}: {value}")
    
    if result_pos.sl > test_position.sl:
        print("✅ ТРЕЙЛИНГ РАБОТАЕТ!")
    else:
        print("❌ ТРЕЙЛИНГ НЕ РАБОТАЕТ!")

if __name__ == "__main__":
    debug_trailing_activation()
