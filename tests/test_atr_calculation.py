#!/usr/bin/env python3
"""
Тест расчета ATR
"""

import os
import sys
import pandas as pd
import numpy as np

# Добавляем путь к модулям
sys.path.append('.')

from signalwarden_lite.core.features import add_indicators

def calculate_atr_manual(df: pd.DataFrame, period: int = 14) -> float:
    """Ручной расчет ATR для проверки"""
    df = df.copy()
    
    # True Range
    df['hl'] = df['high'] - df['low']
    df['hc'] = abs(df['high'] - df['close'].shift())
    df['lc'] = abs(df['low'] - df['close'].shift())
    df['tr'] = df[['hl', 'hc', 'lc']].max(axis=1)
    
    # ATR
    atr = df['tr'].rolling(window=period).mean().iloc[-1]
    
    return atr

def test_atr_calculation():
    """Тест расчета ATR"""
    
    print("🔍 ТЕСТ РАСЧЕТА ATR")
    print("=" * 80)
    
    # Создаем тестовые данные (имитируем DOGE)
    # Цена около 0.245, волатильность 3-5%
    np.random.seed(42)
    n_periods = 50
    
    # Базовая цена
    base_price = 0.245
    
    # Генерируем реалистичные OHLC данные
    data = []
    current_price = base_price
    
    for i in range(n_periods):
        # Дневная волатильность 3-5%
        daily_volatility = np.random.uniform(0.03, 0.05)
        
        # Случайное движение
        price_change = np.random.normal(0, daily_volatility * current_price)
        current_price = max(0.001, current_price + price_change)
        
        # OHLC для этого периода
        high = current_price * (1 + np.random.uniform(0, 0.02))
        low = current_price * (1 - np.random.uniform(0, 0.02))
        open_price = current_price * (1 + np.random.uniform(-0.01, 0.01))
        close = current_price
        
        data.append({
            'timestamp': i,
            'open': open_price,
            'high': high,
            'low': low,
            'close': close,
            'volume': 1000000
        })
    
    df = pd.DataFrame(data)
    
    print("📊 ТЕСТОВЫЕ ДАННЫЕ:")
    print(f"   Периодов: {len(df)}")
    print(f"   Цена: ${df['close'].iloc[-1]:.6f}")
    print(f"   Диапазон: ${df['close'].min():.6f} - ${df['close'].max():.6f}")
    print()
    
    # Ручной расчет ATR
    manual_atr = calculate_atr_manual(df, 14)
    manual_atr_pct = manual_atr / df['close'].iloc[-1] * 100
    
    print("📊 РУЧНОЙ РАСЧЕТ ATR:")
    print(f"   ATR: {manual_atr:.6f}")
    print(f"   ATR %: {manual_atr_pct:.2f}%")
    print()
    
    # Расчет через add_indicators
    df_with_indicators = add_indicators(df, atr_p=14)
    system_atr = df_with_indicators['atr'].iloc[-1]
    system_atr_pct = system_atr / df['close'].iloc[-1] * 100
    
    print("📊 СИСТЕМНЫЙ РАСЧЕТ ATR:")
    print(f"   ATR: {system_atr:.6f}")
    print(f"   ATR %: {system_atr_pct:.2f}%")
    print()
    
    # Сравнение
    print("📊 СРАВНЕНИЕ:")
    print(f"   Ручной: {manual_atr:.6f} ({manual_atr_pct:.2f}%)")
    print(f"   Системный: {system_atr:.6f} ({system_atr_pct:.2f}%)")
    print(f"   Разница: {abs(manual_atr - system_atr):.6f}")
    
    if abs(manual_atr - system_atr) < 0.000001:
        print("   ✅ ATR рассчитывается правильно")
    else:
        print("   ❌ ОШИБКА в расчете ATR!")
    
    print()
    
    # Проверим реальные данные из системы
    print("🔍 АНАЛИЗ ПРОБЛЕМЫ:")
    print("-" * 60)
    
    # Данные из диагностики
    real_positions = [
        {"symbol": "DOGE_USDT", "entry": 0.245776, "atr": 0.0014857142857142827},
        {"symbol": "WIF_USDT", "entry": 0.910212, "atr": 0.006707142857142856},
        {"symbol": "LTC_USDT", "entry": 114.168714, "atr": 0.6957142857142874},
    ]
    
    print("Реальные данные из системы:")
    for pos in real_positions:
        symbol = pos["symbol"]
        entry = pos["entry"]
        atr = pos["atr"]
        atr_pct = atr / entry * 100
        
        print(f"   {symbol}: Entry ${entry:.6f}, ATR {atr:.6f} ({atr_pct:.2f}%)")
    
    print()
    print("🔍 ВОЗМОЖНЫЕ ПРОБЛЕМЫ:")
    print("-" * 60)
    
    print("1. СЛИШКОМ КОРОТКИЕ ДАННЫЕ:")
    print("   • Если данных меньше 14 периодов, ATR будет неточным")
    print("   • Нужно минимум 20-30 периодов для стабильного ATR")
    
    print()
    print("2. НИЗКАЯ ВОЛАТИЛЬНОСТЬ РЫНКА:")
    print("   • В период низкой волатильности ATR естественно маленький")
    print("   • Но 0.6-1.8% кажется слишком мало для криптовалют")
    
    print()
    print("3. НЕПРАВИЛЬНЫЕ ДАННЫЕ:")
    print("   • Возможно, данные с биржи имеют проблемы")
    print("   • Или используется неправильный timeframe")
    
    print()
    print("4. ПРОБЛЕМА В КОДЕ:")
    print("   • Ошибка в функции add_indicators")
    print("   • Неправильная обработка данных")
    
    print()
    print("🎯 РЕКОМЕНДАЦИИ:")
    print("-" * 60)
    
    print("1. ПРОВЕРИТЬ ИСТОРИЧЕСКИЕ ДАННЫЕ:")
    print("   • Убедиться, что получаем достаточно данных (50+ периодов)")
    print("   • Проверить качество данных с Binance")
    
    print()
    print("2. ДОБАВИТЬ МИНИМАЛЬНЫЙ ATR:")
    print("   • Установить минимум 2% от цены для ATR")
    print("   • Это защитит от слишком близких стоп-лоссов")
    
    print()
    print("3. ЛОГИРОВАТЬ ATR:")
    print("   • Добавить подробное логирование расчета ATR")
    print("   • Показывать источник данных и результат")

if __name__ == "__main__":
    test_atr_calculation()
