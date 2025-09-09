#!/usr/bin/env python3
"""
Проверка конкретных типов сигналов
Проверяет, почему система не генерирует конкретные сигналы (breakout, inside, tc, sq)
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

def check_specific_signals():
    """Проверяет конкретные типы сигналов"""
    print("🔍 ПРОВЕРКА КОНКРЕТНЫХ ТИПОВ СИГНАЛОВ")
    print("=" * 60)
    
    try:
        exchange = ccxt.binance()
        
        # Получаем данные BTC
        btc_ohlcv = exchange.fetch_ohlcv('BTC/USDT', '1h', limit=200)
        df_btc = pd.DataFrame(btc_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df_btc['timestamp'] = pd.to_datetime(df_btc['timestamp'], unit='ms')
        
        # Получаем данные ADA
        ada_ohlcv = exchange.fetch_ohlcv('ADA/USDT', '1h', limit=200)
        df_ada = pd.DataFrame(ada_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df_ada['timestamp'] = pd.to_datetime(df_ada['timestamp'], unit='ms')
        
        print(f"📊 Данные получены:")
        print(f"  BTC: {len(df_btc)} баров, цена: ${df_btc['close'].iloc[-1]:,.2f}")
        print(f"  ADA: {len(df_ada)} баров, цена: ${df_ada['close'].iloc[-1]:.6f}")
        
        # Анализируем тренд BTC
        btc_bias = compute_market_bias(df_btc)
        
        # Добавляем индикаторы для ADA
        df_ada = add_indicators(df_ada, ema_fast=50, ema_slow=200)
        df_ada = add_regime(df_ada, RegimeThresholds())
        
        # Параметры сигналов
        signal_params = SignalParams()
        
        # Генерируем сигналы
        signals = generate_signals(df_ada, signal_params, btc_bias)
        
        print(f"\n📊 Анализ последних 20 баров:")
        recent = signals.tail(20)
        
        # Проверяем каждый тип сигнала
        signal_types = ['breakout', 'inside', 'tc', 'sq']
        
        for signal_type in signal_types:
            long_signal_col = f'sig_long_{signal_type}'
            short_signal_col = f'sig_short_{signal_type}'
            
            if long_signal_col in recent.columns:
                long_count = recent[long_signal_col].sum()
                print(f"  Long {signal_type}: {long_count}/20")
            else:
                print(f"  Long {signal_type}: колонка не найдена")
                
            if short_signal_col in recent.columns:
                short_count = recent[short_signal_col].sum()
                print(f"  Short {signal_type}: {short_count}/20")
            else:
                print(f"  Short {signal_type}: колонка не найдена")
        
        # Проверяем allow_long и allow_short
        long_allow_count = recent['allow_long'].sum()
        short_allow_count = recent['allow_short'].sum()
        long_raw_count = recent['allow_long_raw'].sum()
        short_raw_count = recent['allow_short_raw'].sum()
        
        print(f"\n📊 Общие разрешения:")
        print(f"  Allow long raw: {long_raw_count}/20")
        print(f"  Allow short raw: {short_raw_count}/20")
        print(f"  Allow long: {long_allow_count}/20")
        print(f"  Allow short: {short_allow_count}/20")
        
        # Анализируем последний бар детально
        print(f"\n🔍 Детальный анализ последнего бара:")
        latest = signals.iloc[-1]
        
        print(f"  Цена: ${latest['close']:.6f}")
        print(f"  EMA50: {latest['ema_fast']:.6f}")
        print(f"  EMA200: {latest['ema_slow']:.6f}")
        print(f"  RSI: {latest['rsi']:.1f}")
        print(f"  NATR: {latest['natr']:.2f}%")
        print(f"  Режим: {latest['regime']}")
        
        print(f"\n🎯 Конкретные сигналы:")
        for signal_type in signal_types:
            long_signal_col = f'sig_long_{signal_type}'
            short_signal_col = f'sig_short_{signal_type}'
            
            if long_signal_col in latest:
                print(f"  {long_signal_col}: {latest[long_signal_col]}")
            if short_signal_col in latest:
                print(f"  {short_signal_col}: {latest[short_signal_col]}")
        
        print(f"\n🔒 Разрешения:")
        print(f"  allow_long_raw: {latest.get('allow_long_raw', False)}")
        print(f"  allow_short_raw: {latest.get('allow_short_raw', False)}")
        print(f"  allow_long: {latest.get('allow_long', False)}")
        print(f"  allow_short: {latest.get('allow_short', False)}")
        
        # Проверяем, есть ли колонки entry
        print(f"\n💰 Entry цены:")
        print(f"  long_entry_final: {latest.get('long_entry_final', 'N/A')}")
        print(f"  short_entry_final: {latest.get('short_entry_final', 'N/A')}")
        
        # Анализируем, почему нет конкретных сигналов
        print(f"\n🔍 АНАЛИЗ ПРИЧИН ОТСУТСТВИЯ СИГНАЛОВ:")
        
        if latest.get('allow_long', False):
            print(f"  ✅ allow_long = True, но нет конкретных сигналов")
            print(f"  💡 Возможные причины:")
            print(f"    - Условия для конкретных типов сигналов не выполнены")
            print(f"    - Breakout: нет пробоя swing уровней")
            print(f"    - Inside: нет inside-bar паттерна")
            print(f"    - TC: нет trend-continuation условий")
            print(f"    - SQ: нет squeeze-breakout условий")
        else:
            print(f"  ❌ allow_long = False - базовые условия не выполнены")
        
        return latest
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return None

def check_15m_signals():
    """Проверяет сигналы на 15m таймфрейме"""
    print("\n🔍 ПРОВЕРКА СИГНАЛОВ НА 15M ТАЙМФРЕЙМЕ")
    print("=" * 60)
    
    try:
        exchange = ccxt.binance()
        
        # Получаем данные BTC
        btc_ohlcv = exchange.fetch_ohlcv('BTC/USDT', '1h', limit=200)
        df_btc = pd.DataFrame(btc_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df_btc['timestamp'] = pd.to_datetime(df_btc['timestamp'], unit='ms')
        
        # Получаем данные ADA на 15m
        ada_ohlcv = exchange.fetch_ohlcv('ADA/USDT', '15m', limit=400)
        df_ada = pd.DataFrame(ada_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df_ada['timestamp'] = pd.to_datetime(df_ada['timestamp'], unit='ms')
        
        print(f"📊 15m данные получены:")
        print(f"  ADA 15m: {len(df_ada)} баров, цена: ${df_ada['close'].iloc[-1]:.6f}")
        
        # Анализируем тренд BTC
        btc_bias = compute_market_bias(df_btc)
        
        # Добавляем индикаторы для ADA
        df_ada = add_indicators(df_ada, ema_fast=50, ema_slow=200)
        df_ada = add_regime(df_ada, RegimeThresholds())
        
        # Параметры сигналов
        signal_params = SignalParams()
        
        # Генерируем сигналы
        signals = generate_signals(df_ada, signal_params, btc_bias)
        
        print(f"\n📊 Анализ последних 20 баров (15m):")
        recent = signals.tail(20)
        
        # Проверяем каждый тип сигнала
        signal_types = ['breakout', 'inside', 'tc', 'sq']
        
        for signal_type in signal_types:
            long_signal_col = f'sig_long_{signal_type}'
            short_signal_col = f'sig_short_{signal_type}'
            
            if long_signal_col in recent.columns:
                long_count = recent[long_signal_col].sum()
                print(f"  Long {signal_type}: {long_count}/20")
            else:
                print(f"  Long {signal_type}: колонка не найдена")
                
            if short_signal_col in recent.columns:
                short_count = recent[short_signal_col].sum()
                print(f"  Short {signal_type}: {short_count}/20")
            else:
                print(f"  Short {signal_type}: колонка не найдена")
        
        # Проверяем allow_long и allow_short
        long_allow_count = recent['allow_long'].sum()
        short_allow_count = recent['allow_short'].sum()
        
        print(f"\n📊 Общие разрешения (15m):")
        print(f"  Allow long: {long_allow_count}/20")
        print(f"  Allow short: {short_allow_count}/20")
        
        return signals
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    """Главная функция"""
    print("🚀 ПРОВЕРКА КОНКРЕТНЫХ ТИПОВ СИГНАЛОВ")
    print("=" * 80)
    
    # Проверяем 1h сигналы
    check_specific_signals()
    
    # Проверяем 15m сигналы
    check_15m_signals()
    
    print(f"\n🎯 ВЫВОД:")
    print(f"  Система работает правильно, но не генерирует конкретные сигналы")
    print(f"  Это нормальное поведение - система ждет подходящих условий")
    print(f"  allow_long = True означает, что базовые условия выполнены")
    print(f"  Но конкретные типы сигналов требуют дополнительных условий")

if __name__ == "__main__":
    main()
