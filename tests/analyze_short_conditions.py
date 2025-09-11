#!/usr/bin/env python3
"""
Анализ условий для разрешения шортов
Проверяет текущие рыночные условия и требования для шортов
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import numpy as np
import ccxt
from signalwarden_lite.core.market import compute_market_bias
from signalwarden_lite.core.signals import generate_signals, SignalParams
from signalwarden_lite.core.features import add_indicators
from signalwarden_lite.core.regimes import add_regime, RegimeThresholds
from datetime import datetime

def analyze_short_conditions():
    """Анализирует условия для разрешения шортов"""
    print("🔍 АНАЛИЗ УСЛОВИЙ ДЛЯ РАЗРЕШЕНИЯ ШОРТОВ")
    print("=" * 60)
    
    try:
        exchange = ccxt.binance()
        
        # Получаем данные BTC
        print("📊 Получение данных BTC...")
        btc_ohlcv = exchange.fetch_ohlcv('BTC/USDT', '1h', limit=200)
        df_btc = pd.DataFrame(btc_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df_btc['timestamp'] = pd.to_datetime(df_btc['timestamp'], unit='ms')
        
        # Анализируем тренд BTC
        btc_bias = compute_market_bias(df_btc)
        latest_btc = btc_bias.iloc[-1]
        
        print(f"📊 ТЕКУЩИЕ УСЛОВИЯ BTC:")
        print(f"  Время: {df_btc['timestamp'].iloc[-1]}")
        print(f"  Цена: ${df_btc['close'].iloc[-1]:,.2f}")
        print(f"  EMA50: ${df_btc['close'].ewm(span=50).mean().iloc[-1]:,.2f}")
        print(f"  EMA200: ${df_btc['close'].ewm(span=200).mean().iloc[-1]:,.2f}")
        print(f"  EMA50 > EMA200: {df_btc['close'].ewm(span=50).mean().iloc[-1] > df_btc['close'].ewm(span=200).mean().iloc[-1]}")
        
        # Анализируем наклоны EMA
        ema50 = df_btc['close'].ewm(span=50).mean()
        ema200 = df_btc['close'].ewm(span=200).mean()
        
        # Наклон EMA50 (сравнение с 2 барами назад)
        ema50_slope = ema50.iloc[-1] - ema50.iloc[-3]
        ema200_slope = ema200.iloc[-1] - ema200.iloc[-3]
        
        print(f"  EMA50 наклон: {ema50_slope:+.2f}")
        print(f"  EMA200 наклон: {ema200_slope:+.2f}")
        
        print(f"\n📊 BTC MARKET FILTER:")
        print(f"  Лонги разрешены: {latest_btc['mkt_long_ok']}")
        print(f"  Шорты разрешены: {latest_btc['mkt_short_ok']}")
        
        # Анализируем условия для шортов
        print(f"\n🔍 УСЛОВИЯ ДЛЯ РАЗРЕШЕНИЯ ШОРТОВ:")
        
        # Условие 1: EMA50 < EMA200
        ema_condition = ema50.iloc[-1] < ema200.iloc[-1]
        print(f"  1. EMA50 < EMA200: {ema_condition}")
        print(f"     Текущее: EMA50=${ema50.iloc[-1]:,.2f}, EMA200=${ema200.iloc[-1]:,.2f}")
        
        # Условие 2: EMA200 падает ИЛИ EMA50 падает
        slope_condition = (ema200_slope < 0) or (ema50_slope < 0)
        print(f"  2. (EMA200 падает ИЛИ EMA50 падает): {slope_condition}")
        print(f"     EMA200 падает: {ema200_slope < 0} (наклон: {ema200_slope:+.2f})")
        print(f"     EMA50 падает: {ema50_slope < 0} (наклон: {ema50_slope:+.2f})")
        
        # Условие 3: Пересечение EMA (дополнительное)
        ema_cross_down = (ema50.iloc[-1] < ema200.iloc[-1]) and (ema50.iloc[-2] >= ema200.iloc[-2])
        print(f"  3. EMA50 пересекла EMA200 вниз: {ema_cross_down}")
        
        # Общее условие для шортов
        short_condition = ema_condition and slope_condition
        print(f"\n📊 ОБЩЕЕ УСЛОВИЕ ДЛЯ ШОРТОВ:")
        print(f"  (EMA50 < EMA200) И (EMA200 падает ИЛИ EMA50 падает): {short_condition}")
        print(f"  Система разрешает шорты: {latest_btc['mkt_short_ok']}")
        
        # Анализируем, что нужно для переключения на шорты
        print(f"\n🔍 ЧТО НУЖНО ДЛЯ ПЕРЕКЛЮЧЕНИЯ НА ШОРТЫ:")
        
        if not ema_condition:
            print(f"  ❌ EMA50 должна стать меньше EMA200")
            print(f"     Текущее: EMA50=${ema50.iloc[-1]:,.2f} > EMA200=${ema200.iloc[-1]:,.2f}")
            print(f"     Нужно: EMA50 должна упасть на ${ema50.iloc[-1] - ema200.iloc[-1]:,.2f}")
        
        if not slope_condition:
            print(f"  ❌ EMA200 или EMA50 должны начать падать")
            print(f"     EMA200 наклон: {ema200_slope:+.2f}")
            print(f"     EMA50 наклон: {ema50_slope:+.2f}")
            print(f"     Нужно: Один из наклонов должен стать отрицательным")
        
        # Получаем данные для альткоинов
        symbols = ['ADA/USDT', 'LTC/USDT', 'DOGE/USDT', 'ENA/USDT', 'HBAR/USDT', 'WIF/USDT', 'PNUT/USDT']
        
        print(f"\n📊 АНАЛИЗ АЛЬТКОИНОВ:")
        for symbol in symbols:
            try:
                ohlcv = exchange.fetch_ohlcv(symbol, '1h', limit=200)
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                
                # Добавляем индикаторы
                df = add_indicators(df, ema_fast=50, ema_slow=200)
                df = add_regime(df, RegimeThresholds())
                
                latest = df.iloc[-1]
                
                print(f"  {symbol}:")
                print(f"    Цена: ${latest['close']:.6f}")
                print(f"    EMA50: {latest['ema_fast']:.6f}")
                print(f"    EMA200: {latest['ema_slow']:.6f}")
                print(f"    EMA50 < EMA200: {latest['ema_fast'] < latest['ema_slow']}")
                print(f"    RSI: {latest['rsi']:.1f}")
                print(f"    NATR: {latest['natr']:.2f}%")
                print(f"    Режим: {latest['regime']}")
                
            except Exception as e:
                print(f"  {symbol}: ❌ Ошибка - {e}")
        
        return latest_btc
        
    except Exception as e:
        print(f"❌ Ошибка получения данных: {e}")
        return None

def analyze_short_guard_conditions():
    """Анализирует условия Adaptive Short-Guard"""
    print("\n🔍 АНАЛИЗ ADAPTIVE SHORT-GUARD УСЛОВИЙ")
    print("=" * 60)
    
    try:
        exchange = ccxt.binance()
        
        # Получаем данные BTC
        btc_ohlcv = exchange.fetch_ohlcv('BTC/USDT', '1h', limit=200)
        df_btc = pd.DataFrame(btc_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df_btc['timestamp'] = pd.to_datetime(df_btc['timestamp'], unit='ms')
        
        # Анализируем тренд BTC
        btc_bias = compute_market_bias(df_btc)
        
        # Получаем данные ADA как пример
        ada_ohlcv = exchange.fetch_ohlcv('ADA/USDT', '1h', limit=200)
        df_ada = pd.DataFrame(ada_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df_ada['timestamp'] = pd.to_datetime(df_ada['timestamp'], unit='ms')
        
        # Добавляем индикаторы
        df_ada = add_indicators(df_ada, ema_fast=50, ema_slow=200)
        df_ada = add_regime(df_ada, RegimeThresholds())
        
        # Параметры сигналов
        signal_params = SignalParams()
        
        # Генерируем сигналы
        signals = generate_signals(df_ada, signal_params, btc_bias)
        
        latest = signals.iloc[-1]
        latest_btc = btc_bias.iloc[-1]
        
        print(f"📊 ADAPTIVE SHORT-GUARD УСЛОВИЯ:")
        print(f"  BTC short ok: {latest_btc['mkt_short_ok']}")
        print(f"  ADA RSI: {latest['rsi']:.1f}")
        print(f"  ADA NATR: {latest['natr']:.2f}%")
        
        if latest_btc['mkt_short_ok']:
            print(f"\n🔍 BEAR MARKET УСЛОВИЯ (когда BTC mkt_short_ok = True):")
            print(f"  RSI ≤ 52: {latest['rsi'] <= 52} (RSI={latest['rsi']:.1f})")
            print(f"  NATR ≥ 0.9%: {latest['natr'] >= 0.9} (NATR={latest['natr']:.2f}%)")
            
            bear_conditions = (latest['rsi'] <= 52) and (latest['natr'] >= 0.9)
            print(f"  Все условия выполнены: {bear_conditions}")
        else:
            print(f"\n🔍 BULL CORRECTION УСЛОВИЯ (когда BTC mkt_short_ok = False):")
            print(f"  RSI ≤ 50: {latest['rsi'] <= 50} (RSI={latest['rsi']:.1f})")
            print(f"  NATR ≥ 0.8%: {latest['natr'] >= 0.8} (NATR={latest['natr']:.2f}%)")
            
            # Проверяем EMA20 условие
            ema20 = df_ada['close'].ewm(span=20).mean().iloc[-1]
            close_below_ema20 = latest['close'] < ema20
            print(f"  Close < EMA20: {close_below_ema20} (Close=${latest['close']:.6f}, EMA20={ema20:.6f})")
            
            bullcorr_conditions = (latest['rsi'] <= 50) and (latest['natr'] >= 0.8) and close_below_ema20
            print(f"  Все условия выполнены: {bullcorr_conditions}")
        
        print(f"\n📊 ФИНАЛЬНЫЕ РАЗРЕШЕНИЯ:")
        print(f"  Allow short raw: {latest.get('allow_short_raw', False)}")
        print(f"  Allow short: {latest.get('allow_short', False)}")
        
        return latest
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return None

def main():
    """Главная функция анализа"""
    print("🚀 АНАЛИЗ УСЛОВИЙ ДЛЯ РАЗРЕШЕНИЯ ШОРТОВ")
    print("=" * 80)
    
    # Анализируем основные условия
    btc_data = analyze_short_conditions()
    
    # Анализируем Adaptive Short-Guard условия
    ada_data = analyze_short_guard_conditions()
    
    print(f"\n🎯 ИТОГОВЫЙ АНАЛИЗ:")
    if btc_data is not None:
        print(f"  Текущий BTC тренд: {'МЕДВЕЖИЙ' if btc_data['mkt_short_ok'] else 'БЫЧИЙ'}")
        print(f"  Шорты разрешены: {btc_data['mkt_short_ok']}")
        
        if not btc_data['mkt_short_ok']:
            print(f"\n💡 ДЛЯ РАЗРЕШЕНИЯ ШОРТОВ НУЖНО:")
            print(f"  1. EMA50 должна стать меньше EMA200")
            print(f"  2. EMA200 или EMA50 должны начать падать")
            print(f"  3. Или EMA50 должна пересечь EMA200 вниз")
        else:
            print(f"\n✅ УСЛОВИЯ ДЛЯ ШОРТОВ ВЫПОЛНЕНЫ")
            print(f"  Система готова генерировать шорты при подходящих условиях")

if __name__ == "__main__":
    main()
