#!/usr/bin/env python3
"""
Детальный анализ логики системы и условий для открытия позиций
Проверяет все условия и логику принятия решений
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

def analyze_signal_generation():
    """Анализирует генерацию сигналов"""
    print("🔍 АНАЛИЗ ГЕНЕРАЦИИ СИГНАЛОВ")
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
        
        print(f"📊 ТЕКУЩИЕ ДАННЫЕ ADA:")
        print(f"  Время: {df_ada['timestamp'].iloc[-1]}")
        print(f"  Цена: ${latest['close']:.6f}")
        print(f"  EMA50: {latest['ema_fast']:.6f}")
        print(f"  EMA200: {latest['ema_slow']:.6f}")
        print(f"  RSI: {latest['rsi']:.1f}")
        print(f"  NATR: {latest['natr']:.2f}%")
        print(f"  Режим: {latest['regime']}")
        
        print(f"\n📊 BTC MARKET FILTER:")
        print(f"  Лонги разрешены: {latest_btc['mkt_long_ok']}")
        print(f"  Шорты разрешены: {latest_btc['mkt_short_ok']}")
        
        # Анализируем все условия для лонгов
        print(f"\n🔍 УСЛОВИЯ ДЛЯ ЛОНГОВ:")
        
        # 1. BTC Market Filter
        btc_long_ok = latest_btc['mkt_long_ok']
        print(f"  1. BTC mkt_long_ok: {btc_long_ok}")
        
        # 2. EMA условия
        ema_long_condition = latest['ema_fast'] > latest['ema_slow']
        print(f"  2. EMA50 > EMA200: {ema_long_condition}")
        
        # 3. RSI условия
        rsi_long_condition = latest['rsi'] >= 35
        print(f"  3. RSI ≥ 35: {rsi_long_condition}")
        
        # 4. NATR условия
        natr_long_condition = latest['natr'] >= 0.5
        print(f"  4. NATR ≥ 0.5%: {natr_long_condition}")
        
        # 5. Режим условия
        regime_long_condition = latest['regime'] in ['normal', 'high']
        print(f"  5. Режим normal/high: {regime_long_condition}")
        
        # 6. Внутренние бары (для 15m)
        # Проверяем последние 3 бара
        recent_bars = df_ada.tail(3)
        inside_bars = 0
        for i in range(1, len(recent_bars)):
            if (recent_bars.iloc[i]['high'] <= recent_bars.iloc[i-1]['high'] and 
                recent_bars.iloc[i]['low'] >= recent_bars.iloc[i-1]['low']):
                inside_bars += 1
        
        inside_bar_condition = inside_bars >= 1
        print(f"  6. Внутренние бары (≥1 из 3): {inside_bar_condition}")
        
        # Общее условие для лонгов
        long_conditions = [
            btc_long_ok,
            ema_long_condition,
            rsi_long_condition,
            natr_long_condition,
            regime_long_condition,
            inside_bar_condition
        ]
        
        all_long_conditions = all(long_conditions)
        print(f"\n📊 ОБЩЕЕ УСЛОВИЕ ДЛЯ ЛОНГОВ:")
        print(f"  Все условия выполнены: {all_long_conditions}")
        print(f"  Количество выполненных: {sum(long_conditions)}/6")
        
        # Анализируем все условия для шортов
        print(f"\n🔍 УСЛОВИЯ ДЛЯ ШОРТОВ:")
        
        # 1. BTC Market Filter
        btc_short_ok = latest_btc['mkt_short_ok']
        print(f"  1. BTC mkt_short_ok: {btc_short_ok}")
        
        # 2. EMA условия
        ema_short_condition = latest['ema_fast'] < latest['ema_slow']
        print(f"  2. EMA50 < EMA200: {ema_short_condition}")
        
        # 3. RSI условия (адаптивные)
        if btc_short_ok:
            # Bear market условия
            rsi_short_condition = latest['rsi'] <= 52
            print(f"  3. RSI ≤ 52 (bear market): {rsi_short_condition}")
        else:
            # Bull correction условия
            rsi_short_condition = latest['rsi'] <= 50
            print(f"  3. RSI ≤ 50 (bull correction): {rsi_short_condition}")
        
        # 4. NATR условия (адаптивные)
        if btc_short_ok:
            # Bear market условия
            natr_short_condition = latest['natr'] >= 0.9
            print(f"  4. NATR ≥ 0.9% (bear market): {natr_short_condition}")
        else:
            # Bull correction условия
            natr_short_condition = latest['natr'] >= 0.8
            print(f"  4. NATR ≥ 0.8% (bull correction): {natr_short_condition}")
        
        # 5. EMA20 условие (для bull correction)
        if not btc_short_ok:
            ema20 = df_ada['close'].ewm(span=20).mean().iloc[-1]
            ema20_condition = latest['close'] < ema20
            print(f"  5. Close < EMA20 (bull correction): {ema20_condition}")
        else:
            ema20_condition = True
            print(f"  5. EMA20 условие (bear market): {ema20_condition}")
        
        # 6. Режим условия
        regime_short_condition = latest['regime'] in ['normal', 'high']
        print(f"  6. Режим normal/high: {regime_short_condition}")
        
        # Общее условие для шортов
        short_conditions = [
            btc_short_ok,
            ema_short_condition,
            rsi_short_condition,
            natr_short_condition,
            ema20_condition,
            regime_short_condition
        ]
        
        all_short_conditions = all(short_conditions)
        print(f"\n📊 ОБЩЕЕ УСЛОВИЕ ДЛЯ ШОРТОВ:")
        print(f"  Все условия выполнены: {all_short_conditions}")
        print(f"  Количество выполненных: {sum(short_conditions)}/6")
        
        # Анализируем финальные разрешения
        print(f"\n📊 ФИНАЛЬНЫЕ РАЗРЕШЕНИЯ:")
        print(f"  Allow long raw: {latest.get('allow_long_raw', False)}")
        print(f"  Allow long: {latest.get('allow_long', False)}")
        print(f"  Allow short raw: {latest.get('allow_short_raw', False)}")
        print(f"  Allow short: {latest.get('allow_short', False)}")
        
        return latest, latest_btc
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return None, None

def analyze_mtf_strategy():
    """Анализирует MTF стратегию"""
    print("\n🔍 АНАЛИЗ MTF СТРАТЕГИИ")
    print("=" * 60)
    
    try:
        exchange = ccxt.binance()
        
        # Получаем данные 1h
        ada_1h = exchange.fetch_ohlcv('ADA/USDT', '1h', limit=200)
        df_1h = pd.DataFrame(ada_1h, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df_1h['timestamp'] = pd.to_datetime(df_1h['timestamp'], unit='ms')
        
        # Получаем данные 15m
        ada_15m = exchange.fetch_ohlcv('ADA/USDT', '15m', limit=200)
        df_15m = pd.DataFrame(ada_15m, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df_15m['timestamp'] = pd.to_datetime(df_15m['timestamp'], unit='ms')
        
        # Добавляем индикаторы
        df_1h = add_indicators(df_1h, ema_fast=50, ema_slow=200)
        df_15m = add_indicators(df_15m, ema_fast=50, ema_slow=200)
        
        latest_1h = df_1h.iloc[-1]
        latest_15m = df_15m.iloc[-1]
        
        print(f"📊 1H TIMEFRAME:")
        print(f"  Цена: ${latest_1h['close']:.6f}")
        print(f"  EMA50: {latest_1h['ema_fast']:.6f}")
        print(f"  EMA200: {latest_1h['ema_slow']:.6f}")
        print(f"  EMA50 > EMA200: {latest_1h['ema_fast'] > latest_1h['ema_slow']}")
        
        print(f"\n📊 15M TIMEFRAME:")
        print(f"  Цена: ${latest_15m['close']:.6f}")
        print(f"  EMA50: {latest_15m['ema_fast']:.6f}")
        print(f"  EMA200: {latest_15m['ema_slow']:.6f}")
        print(f"  EMA50 > EMA200: {latest_15m['ema_fast'] > latest_15m['ema_slow']}")
        
        # Анализируем внутренние бары на 15m
        print(f"\n🔍 АНАЛИЗ ВНУТРЕННИХ БАРОВ (15M):")
        recent_15m = df_15m.tail(5)
        inside_bars = 0
        for i in range(1, len(recent_15m)):
            if (recent_15m.iloc[i]['high'] <= recent_15m.iloc[i-1]['high'] and 
                recent_15m.iloc[i]['low'] >= recent_15m.iloc[i-1]['low']):
                inside_bars += 1
                print(f"  Бар {i}: Внутренний ✅")
            else:
                print(f"  Бар {i}: Обычный ❌")
        
        print(f"  Всего внутренних баров: {inside_bars}/4")
        
        return df_1h, df_15m
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return None, None

def analyze_breakout_conditions():
    """Анализирует условия для брейкаутов"""
    print("\n🔍 АНАЛИЗ УСЛОВИЙ ДЛЯ БРЕЙКАУТОВ")
    print("=" * 60)
    
    try:
        exchange = ccxt.binance()
        
        # Получаем данные ADA
        ada_ohlcv = exchange.fetch_ohlcv('ADA/USDT', '1h', limit=200)
        df = pd.DataFrame(ada_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        # Добавляем индикаторы
        df = add_indicators(df, ema_fast=50, ema_slow=200)
        df = add_regime(df, RegimeThresholds())
        
        latest = df.iloc[-1]
        
        print(f"📊 УСЛОВИЯ ДЛЯ БРЕЙКАУТОВ:")
        
        # 1. Режим
        regime_condition = latest['regime'] in ['normal', 'high']
        print(f"  1. Режим normal/high: {regime_condition} (режим: {latest['regime']})")
        
        # 2. NATR
        natr_condition = latest['natr'] >= 0.5
        print(f"  2. NATR ≥ 0.5%: {natr_condition} (NATR: {latest['natr']:.2f}%)")
        
        # 3. RSI
        rsi_condition = 30 <= latest['rsi'] <= 70
        print(f"  3. RSI 30-70: {rsi_condition} (RSI: {latest['rsi']:.1f})")
        
        # 4. EMA
        ema_condition = latest['ema_fast'] > latest['ema_slow']
        print(f"  4. EMA50 > EMA200: {ema_condition}")
        
        # 5. Цена выше EMA50
        price_ema_condition = latest['close'] > latest['ema_fast']
        print(f"  5. Close > EMA50: {price_ema_condition}")
        
        # Общее условие
        breakout_conditions = [
            regime_condition,
            natr_condition,
            rsi_condition,
            ema_condition,
            price_ema_condition
        ]
        
        all_breakout_conditions = all(breakout_conditions)
        print(f"\n📊 ОБЩЕЕ УСЛОВИЕ ДЛЯ БРЕЙКАУТОВ:")
        print(f"  Все условия выполнены: {all_breakout_conditions}")
        print(f"  Количество выполненных: {sum(breakout_conditions)}/5")
        
        return latest
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return None

def main():
    """Главная функция анализа"""
    print("🚀 ДЕТАЛЬНЫЙ АНАЛИЗ ЛОГИКИ СИСТЕМЫ")
    print("=" * 80)
    
    # Анализируем генерацию сигналов
    ada_data, btc_data = analyze_signal_generation()
    
    # Анализируем MTF стратегию
    df_1h, df_15m = analyze_mtf_strategy()
    
    # Анализируем условия для брейкаутов
    breakout_data = analyze_breakout_conditions()
    
    print(f"\n🎯 ИТОГОВЫЙ АНАЛИЗ:")
    if ada_data is not None and btc_data is not None:
        print(f"  Текущий BTC тренд: {'МЕДВЕЖИЙ' if btc_data['mkt_short_ok'] else 'БЫЧИЙ'}")
        print(f"  Лонги разрешены: {ada_data.get('allow_long', False)}")
        print(f"  Шорты разрешены: {ada_data.get('allow_short', False)}")
        
        if not ada_data.get('allow_long', False) and not ada_data.get('allow_short', False):
            print(f"\n💡 ПРИЧИНЫ ОТСУТСТВИЯ ПОЗИЦИЙ:")
            print(f"  1. BTC Market Filter блокирует все позиции")
            print(f"  2. Не выполнены условия для конкретного типа позиций")
            print(f"  3. Недостаточно волатильности (NATR)")
            print(f"  4. Неподходящий режим рынка")
            print(f"  5. Отсутствуют внутренние бары для входа")

if __name__ == "__main__":
    main()
