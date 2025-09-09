#!/usr/bin/env python3
"""
Мониторинг адаптации системы к тренду
Проверяет, что система правильно определяет и адаптируется к тренду BTC
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import numpy as np
from signalwarden_lite.core.market import compute_market_bias
import ccxt
import time
from datetime import datetime

def get_current_btc_trend():
    """Получает текущий тренд BTC"""
    try:
        exchange = ccxt.binance()
        ohlcv = exchange.fetch_ohlcv('BTC/USDT', '1h', limit=200)
        
        df_btc = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df_btc['timestamp'] = pd.to_datetime(df_btc['timestamp'], unit='ms')
        
        # Анализируем тренд
        bias = compute_market_bias(df_btc)
        latest = bias.iloc[-1]
        
        current_price = df_btc.iloc[-1]['close']
        current_time = df_btc.iloc[-1]['timestamp']
        
        return {
            'timestamp': current_time,
            'price': current_price,
            'long_ok': latest['mkt_long_ok'],
            'short_ok': latest['mkt_short_ok']
        }
        
    except Exception as e:
        print(f"❌ Ошибка получения данных BTC: {e}")
        return None

def monitor_trend_changes():
    """Мониторит изменения тренда"""
    print("🔍 МОНИТОРИНГ АДАПТАЦИИ СИСТЕМЫ К ТРЕНДУ")
    print("=" * 60)
    print("Нажмите Ctrl+C для остановки")
    print()
    
    last_trend = None
    change_count = 0
    
    try:
        while True:
            current_trend = get_current_btc_trend()
            
            if current_trend is None:
                print("❌ Не удалось получить данные BTC")
                time.sleep(60)
                continue
            
            # Определяем текущее состояние
            if current_trend['long_ok'] and current_trend['short_ok']:
                trend_state = "🟡 NEUTRAL"
            elif current_trend['long_ok']:
                trend_state = "🟢 BULL"
            elif current_trend['short_ok']:
                trend_state = "🔴 BEAR"
            else:
                trend_state = "⚫ SIDEWAYS"
            
            # Проверяем изменения
            trend_changed = False
            if last_trend is not None:
                if (last_trend['long_ok'] != current_trend['long_ok'] or 
                    last_trend['short_ok'] != current_trend['short_ok']):
                    trend_changed = True
                    change_count += 1
            
            # Выводим информацию
            timestamp = current_trend['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
            price = current_trend['price']
            
            status_line = f"{timestamp} | ${price:,.2f} | {trend_state}"
            
            if trend_changed:
                status_line += " 🔄 ИЗМЕНЕНИЕ!"
                print(f"🚨 {status_line}")
                print(f"   Изменений тренда: {change_count}")
                
                # Рекомендации
                if current_trend['short_ok']:
                    print("   💡 РЕКОМЕНДАЦИЯ: Система должна открывать ШОРТЫ")
                elif current_trend['long_ok']:
                    print("   💡 РЕКОМЕНДАЦИЯ: Система должна открывать ЛОНГИ")
                else:
                    print("   💡 РЕКОМЕНДАЦИЯ: Система должна быть в режиме ожидания")
                print()
            else:
                print(f"📊 {status_line}")
            
            last_trend = current_trend
            time.sleep(30)  # Проверяем каждые 30 секунд
            
    except KeyboardInterrupt:
        print(f"\n👋 Мониторинг остановлен")
        print(f"📊 Всего изменений тренда: {change_count}")

def check_system_status():
    """Проверяет текущий статус системы"""
    print("🔍 ПРОВЕРКА ТЕКУЩЕГО СТАТУСА СИСТЕМЫ")
    print("=" * 50)
    
    current_trend = get_current_btc_trend()
    
    if current_trend is None:
        print("❌ Не удалось получить данные BTC")
        return
    
    timestamp = current_trend['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
    price = current_trend['price']
    
    print(f"📊 Текущее состояние BTC:")
    print(f"  Время: {timestamp}")
    print(f"  Цена: ${price:,.2f}")
    
    if current_trend['long_ok'] and current_trend['short_ok']:
        market_state = "🟡 NEUTRAL (лонги и шорты разрешены)"
    elif current_trend['long_ok']:
        market_state = "🟢 BULL (только лонги разрешены)"
    elif current_trend['short_ok']:
        market_state = "🔴 BEAR (только шорты разрешены)"
    else:
        market_state = "⚫ SIDEWAYS (все запрещено)"
    
    print(f"  Рыночное состояние: {market_state}")
    
    print(f"\n💡 РЕКОМЕНДАЦИИ ДЛЯ СИСТЕМЫ:")
    if current_trend['short_ok']:
        print("  ✅ Система должна открывать ШОРТЫ")
        print("  ❌ Система НЕ должна открывать лонги")
    elif current_trend['long_ok']:
        print("  ✅ Система должна открывать ЛОНГИ")
        print("  ❌ Система НЕ должна открывать шорты")
    else:
        print("  ⚠️ Система должна быть в режиме ожидания")
    
    print(f"\n🔧 УПРАВЛЕНИЕ СИСТЕМОЙ:")
    print("  • Для принудительного обновления BTC кеша: python emergency_cache_control.py")
    print("  • Для проверки всех исправлений: python test_final_verification.py")
    print("  • Для мониторинга в реальном времени: python monitor_trend_adaptation.py --monitor")

def main():
    """Главная функция"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Мониторинг адаптации системы к тренду')
    parser.add_argument('--monitor', action='store_true', help='Запустить мониторинг в реальном времени')
    parser.add_argument('--status', action='store_true', help='Показать текущий статус')
    
    args = parser.parse_args()
    
    if args.monitor:
        monitor_trend_changes()
    elif args.status:
        check_system_status()
    else:
        # По умолчанию показываем статус
        check_system_status()
        print(f"\n💡 Для мониторинга в реальном времени используйте: --monitor")

if __name__ == "__main__":
    main()
