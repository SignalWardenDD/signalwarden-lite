#!/usr/bin/env python3
"""
Тест с реальными данными BTC для проверки смены тренда
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import numpy as np
from signalwarden_lite.core.market import compute_market_bias
import ccxt

def fetch_btc_data():
    """Получает реальные данные BTC"""
    try:
        exchange = ccxt.binance()
        
        # Получаем данные за последние 500 часов
        ohlcv = exchange.fetch_ohlcv('BTC/USDT', '1h', limit=500)
        
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        print(f"✅ Получены данные BTC: {len(df)} часов")
        print(f"   Период: {df['timestamp'].iloc[0]} - {df['timestamp'].iloc[-1]}")
        print(f"   Цена: ${df['close'].iloc[0]:.2f} - ${df['close'].iloc[-1]:.2f}")
        
        return df
        
    except Exception as e:
        print(f"❌ Ошибка получения данных BTC: {e}")
        return None

def analyze_trend_changes(df_btc):
    """Анализирует изменения тренда"""
    print("\n🔍 АНАЛИЗ ИЗМЕНЕНИЙ ТРЕНДА BTC")
    print("=" * 50)
    
    # Вычисляем тренд
    bias = compute_market_bias(df_btc)
    
    # Анализируем последние 100 часов
    recent = bias.tail(100)
    
    # Находим изменения тренда
    changes = []
    for i in range(1, len(recent)):
        prev = recent.iloc[i-1]
        curr = recent.iloc[i]
        
        if (prev['mkt_long_ok'] != curr['mkt_long_ok']) or (prev['mkt_short_ok'] != curr['mkt_short_ok']):
            timestamp = df_btc.iloc[recent.index[i]]['timestamp']
            price = df_btc.iloc[recent.index[i]]['close']
            
            changes.append({
                'timestamp': timestamp,
                'price': price,
                'old_long': prev['mkt_long_ok'],
                'new_long': curr['mkt_long_ok'],
                'old_short': prev['mkt_short_ok'],
                'new_short': curr['mkt_short_ok']
            })
    
    print(f"📊 Найдено {len(changes)} изменений тренда за последние 100 часов:")
    print("-" * 50)
    
    for change in changes[-10:]:  # Показываем последние 10 изменений
        timestamp = change['timestamp'].strftime('%Y-%m-%d %H:%M')
        price = change['price']
        
        if change['new_long'] and not change['old_long']:
            trend_change = "🟢 BULL (лонги разрешены)"
        elif change['new_short'] and not change['old_short']:
            trend_change = "🔴 BEAR (шорты разрешены)"
        elif not change['new_long'] and change['old_long']:
            trend_change = "❌ Лонги запрещены"
        elif not change['new_short'] and change['old_short']:
            trend_change = "❌ Шорты запрещены"
        else:
            trend_change = "🟡 Нейтрально"
        
        print(f"{timestamp} | ${price:,.2f} | {trend_change}")
    
    # Статистика
    long_hours = recent['mkt_long_ok'].sum()
    short_hours = recent['mkt_short_ok'].sum()
    neutral_hours = len(recent) - long_hours - short_hours
    
    print(f"\n📈 СТАТИСТИКА (последние 100 часов):")
    print(f"  🟢 Лонги разрешены: {long_hours} часов ({long_hours}%)")
    print(f"  🔴 Шорты разрешены: {short_hours} часов ({short_hours}%)")
    print(f"  🟡 Нейтрально: {neutral_hours} часов ({neutral_hours}%)")
    
    return bias

def test_current_market_state():
    """Тестирует текущее состояние рынка"""
    print("\n🧪 ТЕСТ ТЕКУЩЕГО СОСТОЯНИЯ РЫНКА")
    print("=" * 50)
    
    df_btc = fetch_btc_data()
    if df_btc is None:
        return
    
    bias = analyze_trend_changes(df_btc)
    
    # Текущее состояние
    latest = bias.iloc[-1]
    current_price = df_btc.iloc[-1]['close']
    current_time = df_btc.iloc[-1]['timestamp']
    
    print(f"\n🎯 ТЕКУЩЕЕ СОСТОЯНИЕ:")
    print(f"  Время: {current_time}")
    print(f"  Цена BTC: ${current_price:,.2f}")
    
    if latest['mkt_long_ok'] and latest['mkt_short_ok']:
        market_state = "🟡 NEUTRAL (лонги и шорты разрешены)"
    elif latest['mkt_long_ok']:
        market_state = "🟢 BULL (только лонги разрешены)"
    elif latest['mkt_short_ok']:
        market_state = "🔴 BEAR (только шорты разрешены)"
    else:
        market_state = "⚫ SIDEWAYS (все запрещено)"
    
    print(f"  Рыночное состояние: {market_state}")
    
    # Рекомендации
    print(f"\n💡 РЕКОМЕНДАЦИИ:")
    if latest['mkt_short_ok']:
        print("  ✅ Система должна открывать ШОРТЫ")
        print("  ❌ Система НЕ должна открывать лонги")
    elif latest['mkt_long_ok']:
        print("  ✅ Система должна открывать ЛОНГИ")
        print("  ❌ Система НЕ должна открывать шорты")
    else:
        print("  ⚠️ Система должна быть в режиме ожидания")
    
    return latest

def main():
    """Главная функция"""
    print("🚀 ТЕСТ РЕАЛЬНОГО ТРЕНДА BTC")
    print("=" * 60)
    
    try:
        current_state = test_current_market_state()
        
        print("\n✅ ТЕСТ ЗАВЕРШЕН!")
        print("\n📋 ВЫВОДЫ:")
        print("  • Система должна автоматически адаптироваться к тренду BTC")
        print("  • При падении рынка система должна переключаться на шорты")
        print("  • При росте рынка система должна переключаться на лонги")
        
        if current_state is not None:
            if current_state.get('mkt_short_ok', False):
                print("  🚨 ВНИМАНИЕ: Текущий тренд медвежий - система должна открывать шорты!")
            elif current_state.get('mkt_long_ok', False):
                print("  🚨 ВНИМАНИЕ: Текущий тренд бычий - система должна открывать лонги!")
        
    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
