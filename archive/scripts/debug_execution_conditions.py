#!/usr/bin/env python3
"""
Проверка всех условий выполнения сигналов
"""

import os
import sys
import time
import yaml
import json
from dotenv import load_dotenv
import ccxt

def check_execution_conditions():
    """Проверить все условия для выполнения сигналов"""
    
    print("🔍 ПРОВЕРКА УСЛОВИЙ ВЫПОЛНЕНИЯ СИГНАЛОВ")
    print("=" * 80)
    
    # Загрузить конфигурацию
    with open('signalwarden_lite/config/config_production.yaml', 'r') as f:
        cfg = yaml.safe_load(f)
    
    print(f"📊 Конфигурация загружена: {cfg['profile']}")
    print(f"💰 Margin per position: {cfg['risk']['margin_usdt']} USDT")
    print(f"📈 Leverage: {cfg['risk']['leverage']}x")
    print(f"🎯 Symbols: {cfg['symbols']}")
    print()
    
    # Проверить API подключение
    try:
        exchange = ccxt.binanceusdm({
            'apiKey': os.getenv('BINANCE_API_KEY'),
            'secret': os.getenv('BINANCE_SECRET'),
            'sandbox': False,
            'rateLimit': True
        })
        
        # Проверить баланс
        print("💰 Проверка баланса...")
        balance = exchange.fetch_balance()
        free_usdt = balance.get('USDT', {}).get('free', 0)
        used_usdt = balance.get('USDT', {}).get('used', 0)
        total_usdt = balance.get('USDT', {}).get('total', 0)
        
        print(f"   Free USDT: {free_usdt:.2f}")
        print(f"   Used USDT: {used_usdt:.2f}")
        print(f"   Total USDT: {total_usdt:.2f}")
        
        # Рассчитать требуемый маржин
        actual_margin_per_position = cfg['risk']['margin_usdt'] / cfg['risk']['leverage']
        required_margin = actual_margin_per_position * 1.05  # 5% buffer
        
        print(f"   Required margin per position: {required_margin:.2f} USDT")
        print(f"   Can open positions: {'✅ YES' if free_usdt >= required_margin else '❌ NO'}")
        
        if free_usdt < required_margin:
            print(f"   ⚠️ НЕДОСТАТОЧНО СРЕДСТВ! Нужно: {required_margin:.2f}, есть: {free_usdt:.2f}")
        
        print()
        
        # Проверить активные позиции
        print("📈 Проверка активных позиций...")
        positions = exchange.fetch_positions()
        active_positions = [pos for pos in positions if float(pos['contracts']) != 0]
        
        if active_positions:
            print(f"   Активных позиций: {len(active_positions)}")
            for pos in active_positions:
                symbol = pos['symbol']
                size = float(pos['contracts'])
                side = pos['side']
                unrealized_pnl = float(pos['unrealizedPnl'])
                print(f"   - {symbol}: {side} {size:.6f}, PnL: {unrealized_pnl:.2f} USDT")
        else:
            print("   ✅ Нет активных позиций")
        
        print()
        
        # Проверить состояние trading_state
        print("📊 Проверка trading_state...")
        active_positions_state = {}
        try:
            with open('trading_state_v1_6_TXB.json', 'r') as f:
                trading_state = json.load(f)
            
            # Проверить новый формат (symbols -> symbol -> active_position)
            symbols_data = trading_state.get('symbols', {})
            for symbol, data in symbols_data.items():
                if data.get('active_position') is not None:
                    active_positions_state[symbol] = data['active_position']
            
            # Также проверить старый формат
            if 'active_positions' in trading_state:
                active_positions_state.update(trading_state['active_positions'])
            
            print(f"   Позиций в состоянии: {len(active_positions_state)}")
            
            for symbol, pos_info in active_positions_state.items():
                print(f"   - {symbol}: {pos_info.get('side', 'UNKNOWN')} @ {pos_info.get('entry', 0):.6f}")
            
            if not active_positions_state:
                print("   ✅ Нет сохраненных позиций в состоянии")
                
        except FileNotFoundError:
            print("   ⚠️ Файл trading_state_v1_6_TXB.json не найден")
            active_positions_state = {}
        except Exception as e:
            print(f"   ❌ Ошибка чтения состояния: {e}")
            active_positions_state = {}
        
        print()
        
        # Проверить конкретные пары с сигналами
        pairs_to_check = ['ADA_USDT', 'PNUT_USDT']
        
        for symbol in pairs_to_check:
            print(f"🎯 Проверка условий для {symbol}...")
            
            # Проверить, есть ли открытая позиция
            symbol_positions = [pos for pos in active_positions if pos['symbol'].replace('/', '').replace(':USDT', '_USDT') == symbol]
            has_position = len(symbol_positions) > 0
            
            print(f"   Открытая позиция: {'❌ YES' if has_position else '✅ NO'}")
            
            if has_position:
                pos = symbol_positions[0]
                print(f"   - Сторона: {pos['side']}")
                print(f"   - Размер: {float(pos['contracts']):.6f}")
                print(f"   - PnL: {float(pos['unrealizedPnl']):.2f} USDT")
            
            # Проверить в trading_state
            state_has_position = symbol in active_positions_state
            print(f"   Позиция в состоянии: {'❌ YES' if state_has_position else '✅ NO'}")
            
            if state_has_position:
                pos_info = active_positions_state[symbol]
                print(f"   - Сторона: {pos_info.get('side', 'UNKNOWN')}")
                print(f"   - Вход: {pos_info.get('entry', 0):.6f}")
            
            # Общий вывод
            can_execute = not has_position and not state_has_position and free_usdt >= required_margin
            print(f"   МОЖЕТ ВЫПОЛНИТЬ СИГНАЛ: {'✅ YES' if can_execute else '❌ NO'}")
            
            if not can_execute:
                reasons = []
                if has_position:
                    reasons.append("есть активная позиция на бирже")
                if state_has_position:
                    reasons.append("есть позиция в состоянии системы")
                if free_usdt < required_margin:
                    reasons.append("недостаточно средств")
                print(f"   Причины: {', '.join(reasons)}")
            
            print()
        
    except Exception as e:
        print(f"❌ Ошибка подключения к Binance: {e}")
        return
    
    print("=" * 80)
    print("🎯 РЕКОМЕНДАЦИИ:")
    print("1. Убедиться, что нет активных позиций")
    print("2. Проверить баланс USDT")
    print("3. Очистить trading_state если нужно")
    print("4. Перезапустить live систему")

if __name__ == "__main__":
    load_dotenv()
    check_execution_conditions()
