#!/usr/bin/env python3
"""
SignalWarden Emergency Cache Control
Утилита для принудительного управления кешами без перезапуска системы
"""

import os
import json
import time
from pathlib import Path

def clear_btc_cache():
    """Очистить кеш BTC (создать файл-сигнал)"""
    signal_file = Path("cache_control_signal.json")
    
    signal = {
        "action": "clear_btc_cache",
        "timestamp": time.time(),
        "reason": "Manual cache clear request"
    }
    
    with open(signal_file, 'w') as f:
        json.dump(signal, f, indent=2)
    
    print("✅ Сигнал очистки BTC кеша отправлен")
    print(f"📁 Файл создан: {signal_file}")

def force_position_sync():
    """Принудительная синхронизация позиций"""
    signal_file = Path("cache_control_signal.json")
    
    signal = {
        "action": "force_position_sync", 
        "timestamp": time.time(),
        "reason": "Manual position sync request"
    }
    
    with open(signal_file, 'w') as f:
        json.dump(signal, f, indent=2)
    
    print("✅ Сигнал принудительной синхронизации позиций отправлен")
    print(f"📁 Файл создан: {signal_file}")

def clear_all_caches():
    """Очистить все кеши"""
    signal_file = Path("cache_control_signal.json")
    
    signal = {
        "action": "clear_all_caches",
        "timestamp": time.time(), 
        "reason": "Manual clear all caches request"
    }
    
    with open(signal_file, 'w') as f:
        json.dump(signal, f, indent=2)
    
    print("✅ Сигнал очистки всех кешей отправлен")
    print(f"📁 Файл создан: {signal_file}")

def show_cache_status():
    """Показать статус кешей"""
    print("🔍 СТАТУС КЕШЕЙ СИСТЕМЫ:")
    print("="*50)
    
    # Проверяем файл состояния
    state_file = Path("trading_state_v1_6_TXB.json")
    if state_file.exists():
        try:
            with open(state_file, 'r') as f:
                state = json.load(f)
            
            positions_count = len(state.get('active_positions', {}))
            last_updated = state.get('last_updated', 0)
            
            if last_updated:
                age = time.time() - last_updated
                print(f"📊 Позиций в системе: {positions_count}")
                print(f"⏰ Последнее обновление: {age:.0f}s назад")
            else:
                print(f"📊 Позиций в системе: {positions_count}")
                print(f"⏰ Время обновления не указано")
                
        except Exception as e:
            print(f"❌ Ошибка чтения состояния: {e}")
    else:
        print("❌ Файл состояния не найден")
    
    # Проверяем сигнальный файл
    signal_file = Path("cache_control_signal.json")
    if signal_file.exists():
        try:
            with open(signal_file, 'r') as f:
                signal = json.load(f)
            
            action = signal.get('action', 'unknown')
            timestamp = signal.get('timestamp', 0)
            age = time.time() - timestamp
            
            print(f"📋 Активный сигнал: {action}")
            print(f"⏰ Создан: {age:.0f}s назад")
            
        except Exception as e:
            print(f"⚠️ Ошибка чтения сигнального файла: {e}")
    else:
        print("📋 Нет активных сигналов")

def main():
    """Главное меню"""
    while True:
        print("\n🛠️  SIGNALWARDEN EMERGENCY CACHE CONTROL")
        print("="*50)
        print("1. Показать статус кешей")
        print("2. Очистить BTC кеш")
        print("3. Принудительная синхронизация позиций")
        print("4. Очистить все кеши")
        print("5. Выход")
        print("="*50)
        
        choice = input("Выберите действие (1-5): ").strip()
        
        if choice == '1':
            show_cache_status()
        elif choice == '2':
            clear_btc_cache()
        elif choice == '3':
            force_position_sync()
        elif choice == '4':
            clear_all_caches()
        elif choice == '5':
            print("👋 Выход...")
            break
        else:
            print("❌ Неверный выбор")

if __name__ == "__main__":
    main()
