#!/usr/bin/env python3
"""
Проверка всех пар и условий для каждой
Составляет таблицу с детальным анализом условий
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

def check_all_pairs_conditions():
    """Проверяет все пары и условия для каждой"""
    print("🔍 ПРОВЕРКА ВСЕХ ПАР И УСЛОВИЙ")
    print("=" * 80)
    
    try:
        exchange = ccxt.binance()
        
        # Получаем данные BTC
        btc_ohlcv = exchange.fetch_ohlcv('BTC/USDT', '1h', limit=200)
        df_btc = pd.DataFrame(btc_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df_btc['timestamp'] = pd.to_datetime(df_btc['timestamp'], unit='ms')
        
        # Анализируем тренд BTC
        btc_bias = compute_market_bias(df_btc)
        latest_btc = btc_bias.iloc[-1]
        
        # Список всех пар
        symbols = ['ADA/USDT', 'LTC/USDT', 'DOGE/USDT', 'ENA/USDT', 'HBAR/USDT', 'WIF/USDT', 'PNUT/USDT']
        
        # Параметры сигналов
        signal_params = SignalParams()
        
        # Результаты
        results = []
        
        print(f"📊 BTC MARKET FILTER:")
        print(f"  BTC Цена: ${df_btc['close'].iloc[-1]:,.2f}")
        print(f"  BTC EMA50: ${df_btc['close'].ewm(span=50).mean().iloc[-1]:,.2f}")
        print(f"  BTC EMA200: ${df_btc['close'].ewm(span=200).mean().iloc[-1]:,.2f}")
        print(f"  Лонги разрешены: {latest_btc['mkt_long_ok']}")
        print(f"  Шорты разрешены: {latest_btc['mkt_short_ok']}")
        print()
        
        for symbol in symbols:
            try:
                print(f"📊 АНАЛИЗ {symbol}:")
                
                # Получаем данные
                ohlcv = exchange.fetch_ohlcv(symbol, '1h', limit=200)
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                
                # Добавляем индикаторы
                df = add_indicators(df, ema_fast=50, ema_slow=200)
                df = add_regime(df, RegimeThresholds())
                
                # Генерируем сигналы
                signals = generate_signals(df, signal_params, btc_bias)
                latest = signals.iloc[-1]
                
                # Анализируем условия для лонгов
                long_conditions = []
                
                # 1. BTC Market Filter
                btc_long_ok = latest_btc['mkt_long_ok']
                long_conditions.append(btc_long_ok)
                
                # 2. EMA условия
                ema_long_condition = latest['ema_fast'] > latest['ema_slow']
                long_conditions.append(ema_long_condition)
                
                # 3. RSI условия
                rsi_long_condition = latest['rsi'] >= 35
                long_conditions.append(rsi_long_condition)
                
                # 4. NATR условия
                natr_long_condition = latest['natr'] >= 0.5
                long_conditions.append(natr_long_condition)
                
                # 5. Режим условия
                regime_long_condition = latest['regime'] in ['normal', 'high']
                long_conditions.append(regime_long_condition)
                
                # 6. Внутренние бары
                recent_bars = df.tail(3)
                inside_bars = 0
                for i in range(1, len(recent_bars)):
                    if (recent_bars.iloc[i]['high'] <= recent_bars.iloc[i-1]['high'] and 
                        recent_bars.iloc[i]['low'] >= recent_bars.iloc[i-1]['low']):
                        inside_bars += 1
                
                inside_bar_condition = inside_bars >= 1
                long_conditions.append(inside_bar_condition)
                
                # Анализируем условия для шортов
                short_conditions = []
                
                # 1. BTC Market Filter
                btc_short_ok = latest_btc['mkt_short_ok']
                short_conditions.append(btc_short_ok)
                
                # 2. EMA условия
                ema_short_condition = latest['ema_fast'] < latest['ema_slow']
                short_conditions.append(ema_short_condition)
                
                # 3. RSI условия (адаптивные)
                if btc_short_ok:
                    rsi_short_condition = latest['rsi'] <= 52
                else:
                    rsi_short_condition = latest['rsi'] <= 50
                short_conditions.append(rsi_short_condition)
                
                # 4. NATR условия (адаптивные)
                if btc_short_ok:
                    natr_short_condition = latest['natr'] >= 0.9
                else:
                    natr_short_condition = latest['natr'] >= 0.8
                short_conditions.append(natr_short_condition)
                
                # 5. EMA20 условие (для bull correction)
                if not btc_short_ok:
                    ema20 = df['close'].ewm(span=20).mean().iloc[-1]
                    ema20_condition = latest['close'] < ema20
                else:
                    ema20_condition = True
                short_conditions.append(ema20_condition)
                
                # 6. Режим условия
                regime_short_condition = latest['regime'] in ['normal', 'high']
                short_conditions.append(regime_short_condition)
                
                # Подсчитываем выполненные условия
                long_fulfilled = sum(long_conditions)
                short_fulfilled = sum(short_conditions)
                
                # Финальные разрешения
                allow_long = latest.get('allow_long', False)
                allow_short = latest.get('allow_short', False)
                
                # Сохраняем результаты
                result = {
                    'symbol': symbol,
                    'price': latest['close'],
                    'ema50': latest['ema_fast'],
                    'ema200': latest['ema_slow'],
                    'rsi': latest['rsi'],
                    'natr': latest['natr'],
                    'regime': latest['regime'],
                    'btc_long_ok': btc_long_ok,
                    'btc_short_ok': btc_short_ok,
                    'ema_long_ok': ema_long_condition,
                    'ema_short_ok': ema_short_condition,
                    'rsi_long_ok': rsi_long_condition,
                    'rsi_short_ok': rsi_short_condition,
                    'natr_long_ok': natr_long_condition,
                    'natr_short_ok': natr_short_condition,
                    'regime_long_ok': regime_long_condition,
                    'regime_short_ok': regime_short_condition,
                    'inside_bars': inside_bar_condition,
                    'ema20_ok': ema20_condition,
                    'long_fulfilled': long_fulfilled,
                    'short_fulfilled': short_fulfilled,
                    'allow_long': allow_long,
                    'allow_short': allow_short
                }
                
                results.append(result)
                
                print(f"  Цена: ${latest['close']:.6f}")
                print(f"  EMA50: {latest['ema_fast']:.6f}")
                print(f"  EMA200: {latest['ema_slow']:.6f}")
                print(f"  RSI: {latest['rsi']:.1f}")
                print(f"  NATR: {latest['natr']:.2f}%")
                print(f"  Режим: {latest['regime']}")
                print(f"  Лонги: {long_fulfilled}/6 условий выполнено")
                print(f"  Шорты: {short_fulfilled}/6 условий выполнено")
                print(f"  Allow long: {allow_long}")
                print(f"  Allow short: {allow_short}")
                print()
                
            except Exception as e:
                print(f"  ❌ Ошибка: {e}")
                print()
        
        return results
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return []

def create_conditions_table(results):
    """Создает таблицу условий"""
    print("📊 ТАБЛИЦА УСЛОВИЙ ДЛЯ ВСЕХ ПАР")
    print("=" * 120)
    
    if not results:
        print("❌ Нет данных для создания таблицы")
        return
    
    # Создаем DataFrame
    df = pd.DataFrame(results)
    
    # Основная таблица
    print("📈 ОСНОВНЫЕ ДАННЫЕ:")
    print(f"{'Пара':<12} {'Цена':<12} {'RSI':<6} {'NATR':<8} {'Режим':<8} {'Лонги':<8} {'Шорты':<8} {'Allow L':<8} {'Allow S':<8}")
    print("-" * 120)
    
    for _, row in df.iterrows():
        print(f"{row['symbol']:<12} ${row['price']:<11.6f} {row['rsi']:<6.1f} {row['natr']:<7.2f}% {row['regime']:<8} {row['long_fulfilled']:<8} {row['short_fulfilled']:<8} {row['allow_long']:<8} {row['allow_short']:<8}")
    
    print()
    
    # Детальная таблица условий для лонгов
    print("📈 ДЕТАЛЬНЫЕ УСЛОВИЯ ДЛЯ ЛОНГОВ:")
    print(f"{'Пара':<12} {'BTC':<4} {'EMA':<4} {'RSI':<4} {'NATR':<4} {'Режим':<6} {'Внутр':<6} {'Итого':<6}")
    print("-" * 60)
    
    for _, row in df.iterrows():
        print(f"{row['symbol']:<12} {'✅' if row['btc_long_ok'] else '❌':<4} {'✅' if row['ema_long_ok'] else '❌':<4} {'✅' if row['rsi_long_ok'] else '❌':<4} {'✅' if row['natr_long_ok'] else '❌':<4} {'✅' if row['regime_long_ok'] else '❌':<6} {'✅' if row['inside_bars'] else '❌':<6} {row['long_fulfilled']:<6}")
    
    print()
    
    # Детальная таблица условий для шортов
    print("📉 ДЕТАЛЬНЫЕ УСЛОВИЯ ДЛЯ ШОРТОВ:")
    print(f"{'Пара':<12} {'BTC':<4} {'EMA':<4} {'RSI':<4} {'NATR':<4} {'EMA20':<6} {'Режим':<6} {'Итого':<6}")
    print("-" * 60)
    
    for _, row in df.iterrows():
        print(f"{row['symbol']:<12} {'✅' if row['btc_short_ok'] else '❌':<4} {'✅' if row['ema_short_ok'] else '❌':<4} {'✅' if row['rsi_short_ok'] else '❌':<4} {'✅' if row['natr_short_ok'] else '❌':<4} {'✅' if row['ema20_ok'] else '❌':<6} {'✅' if row['regime_short_ok'] else '❌':<6} {row['short_fulfilled']:<6}")
    
    print()
    
    # Сводная статистика
    print("📊 СВОДНАЯ СТАТИСТИКА:")
    print(f"  Всего пар: {len(results)}")
    print(f"  Пар с разрешенными лонгами: {sum(1 for r in results if r['allow_long'])}")
    print(f"  Пар с разрешенными шортами: {sum(1 for r in results if r['allow_short'])}")
    print(f"  Пар без позиций: {sum(1 for r in results if not r['allow_long'] and not r['allow_short'])}")
    
    # Анализ по режимам
    print(f"\n📊 АНАЛИЗ ПО РЕЖИМАМ:")
    regime_counts = {}
    for r in results:
        regime = r['regime']
        if regime not in regime_counts:
            regime_counts[regime] = 0
        regime_counts[regime] += 1
    
    for regime, count in regime_counts.items():
        print(f"  {regime}: {count} пар")
    
    # Анализ по RSI
    print(f"\n📊 АНАЛИЗ ПО RSI:")
    rsi_ranges = {
        'Перепродан (RSI < 30)': sum(1 for r in results if r['rsi'] < 30),
        'Низкий (30-40)': sum(1 for r in results if 30 <= r['rsi'] < 40),
        'Средний (40-60)': sum(1 for r in results if 40 <= r['rsi'] < 60),
        'Высокий (60-70)': sum(1 for r in results if 60 <= r['rsi'] < 70),
        'Перекуплен (RSI > 70)': sum(1 for r in results if r['rsi'] > 70)
    }
    
    for range_name, count in rsi_ranges.items():
        print(f"  {range_name}: {count} пар")

def main():
    """Главная функция"""
    print("🚀 ПРОВЕРКА ВСЕХ ПАР И УСЛОВИЙ")
    print("=" * 80)
    
    # Проверяем все пары
    results = check_all_pairs_conditions()
    
    # Создаем таблицу
    create_conditions_table(results)

if __name__ == "__main__":
    main()
