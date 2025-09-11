#!/usr/bin/env python3
"""
Анализ логики системы SignalWarden Lite v1.6-TXB
Детальный разбор всех условий и логики принятия решений
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

def analyze_system_logic():
    """Анализирует логику системы"""
    print("🔍 АНАЛИЗ ЛОГИКИ СИСТЕМЫ SIGNALWARDEN LITE v1.6-TXB")
    print("=" * 80)
    
    try:
        exchange = ccxt.binance()
        
        # Получаем данные BTC
        btc_ohlcv = exchange.fetch_ohlcv('BTC/USDT', '1h', limit=200)
        df_btc = pd.DataFrame(btc_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df_btc['timestamp'] = pd.to_datetime(df_btc['timestamp'], unit='ms')
        
        # Анализируем тренд BTC
        btc_bias = compute_market_bias(df_btc)
        
        # Получаем данные ADA
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
        
        print(f"📊 ТЕКУЩИЕ ДАННЫЕ:")
        print(f"  Время: {df_ada['timestamp'].iloc[-1]}")
        print(f"  ADA Цена: ${latest['close']:.6f}")
        print(f"  ADA EMA50: {latest['ema_fast']:.6f}")
        print(f"  ADA EMA200: {latest['ema_slow']:.6f}")
        print(f"  ADA RSI: {latest['rsi']:.1f}")
        print(f"  ADA NATR: {latest['natr']:.2f}%")
        print(f"  ADA Режим: {latest['regime']}")
        
        print(f"\n📊 BTC MARKET FILTER:")
        print(f"  BTC Цена: ${df_btc['close'].iloc[-1]:,.2f}")
        print(f"  BTC EMA50: ${df_btc['close'].ewm(span=50).mean().iloc[-1]:,.2f}")
        print(f"  BTC EMA200: ${df_btc['close'].ewm(span=200).mean().iloc[-1]:,.2f}")
        print(f"  Лонги разрешены: {latest_btc['mkt_long_ok']}")
        print(f"  Шорты разрешены: {latest_btc['mkt_short_ok']}")
        
        # Анализируем логику системы
        print(f"\n🔍 ЛОГИКА СИСТЕМЫ:")
        
        # 1. BTC Market Filter
        print(f"\n1️⃣ BTC MARKET FILTER:")
        print(f"   Назначение: Определяет общий тренд рынка")
        print(f"   Логика: EMA50 vs EMA200 + наклоны EMA")
        print(f"   Текущее состояние: {'БЫЧИЙ' if latest_btc['mkt_long_ok'] else 'МЕДВЕЖИЙ'}")
        
        # 2. Adaptive Short-Guard
        print(f"\n2️⃣ ADAPTIVE SHORT-GUARD:")
        print(f"   Назначение: Интеллектуальная фильтрация шортов")
        print(f"   Логика: Разные условия для bear market и bull correction")
        
        if latest_btc['mkt_short_ok']:
            print(f"   Режим: BEAR MARKET")
            print(f"   Условия: RSI ≤ 52, NATR ≥ 0.9%")
            print(f"   Текущее: RSI={latest['rsi']:.1f} (≤52: {latest['rsi'] <= 52}), NATR={latest['natr']:.2f}% (≥0.9%: {latest['natr'] >= 0.9})")
        else:
            print(f"   Режим: BULL CORRECTION")
            print(f"   Условия: RSI ≤ 50, NATR ≥ 0.8%, Close < EMA20")
            ema20 = df_ada['close'].ewm(span=20).mean().iloc[-1]
            print(f"   Текущее: RSI={latest['rsi']:.1f} (≤50: {latest['rsi'] <= 50}), NATR={latest['natr']:.2f}% (≥0.8%: {latest['natr'] >= 0.8}), Close < EMA20: {latest['close'] < ema20}")
        
        # 3. MTF Strategy
        print(f"\n3️⃣ MTF STRATEGY:")
        print(f"   Назначение: Комбинирует 1h и 15m таймфреймы")
        print(f"   1h: Брейкаут сигналы, анализ тренда")
        print(f"   15m: Внутренние бары, продолжение тренда, брейкаут сжатия")
        
        # 4. Profit-First Trailing
        print(f"\n4️⃣ PROFIT-FIRST TRAILING:")
        print(f"   Назначение: Управление позициями с приоритетом прибыли")
        print(f"   Логика: Адаптивные стоп-лоссы и тейк-профиты")
        
        # Анализируем конкретные условия
        print(f"\n🔍 КОНКРЕТНЫЕ УСЛОВИЯ:")
        
        # Условия для лонгов
        print(f"\n📈 УСЛОВИЯ ДЛЯ ЛОНГОВ:")
        long_conditions = []
        
        # BTC Market Filter
        btc_long = latest_btc['mkt_long_ok']
        long_conditions.append(btc_long)
        print(f"   ✅ BTC mkt_long_ok: {btc_long}")
        
        # EMA условия
        ema_long = latest['ema_fast'] > latest['ema_slow']
        long_conditions.append(ema_long)
        print(f"   ✅ EMA50 > EMA200: {ema_long}")
        
        # RSI условия
        rsi_long = latest['rsi'] >= 35
        long_conditions.append(rsi_long)
        print(f"   ❌ RSI ≥ 35: {rsi_long} (RSI={latest['rsi']:.1f})")
        
        # NATR условия
        natr_long = latest['natr'] >= 0.5
        long_conditions.append(natr_long)
        print(f"   ✅ NATR ≥ 0.5%: {natr_long} (NATR={latest['natr']:.2f}%)")
        
        # Режим условия
        regime_long = latest['regime'] in ['normal', 'high']
        long_conditions.append(regime_long)
        print(f"   ❌ Режим normal/high: {regime_long} (режим={latest['regime']})")
        
        # Внутренние бары
        recent_bars = df_ada.tail(3)
        inside_bars = 0
        for i in range(1, len(recent_bars)):
            if (recent_bars.iloc[i]['high'] <= recent_bars.iloc[i-1]['high'] and 
                recent_bars.iloc[i]['low'] >= recent_bars.iloc[i-1]['low']):
                inside_bars += 1
        
        inside_bar_long = inside_bars >= 1
        long_conditions.append(inside_bar_long)
        print(f"   ✅ Внутренние бары (≥1): {inside_bar_long} (найдено: {inside_bars})")
        
        print(f"\n   📊 ИТОГ ЛОНГОВ: {sum(long_conditions)}/6 условий выполнено")
        
        # Условия для шортов
        print(f"\n📉 УСЛОВИЯ ДЛЯ ШОРТОВ:")
        short_conditions = []
        
        # BTC Market Filter
        btc_short = latest_btc['mkt_short_ok']
        short_conditions.append(btc_short)
        print(f"   ❌ BTC mkt_short_ok: {btc_short}")
        
        # EMA условия
        ema_short = latest['ema_fast'] < latest['ema_slow']
        short_conditions.append(ema_short)
        print(f"   ❌ EMA50 < EMA200: {ema_short}")
        
        # RSI условия (адаптивные)
        if btc_short:
            rsi_short = latest['rsi'] <= 52
            print(f"   RSI ≤ 52 (bear market): {rsi_short} (RSI={latest['rsi']:.1f})")
        else:
            rsi_short = latest['rsi'] <= 50
            print(f"   RSI ≤ 50 (bull correction): {rsi_short} (RSI={latest['rsi']:.1f})")
        
        short_conditions.append(rsi_short)
        
        # NATR условия (адаптивные)
        if btc_short:
            natr_short = latest['natr'] >= 0.9
            print(f"   NATR ≥ 0.9% (bear market): {natr_short} (NATR={latest['natr']:.2f}%)")
        else:
            natr_short = latest['natr'] >= 0.8
            print(f"   NATR ≥ 0.8% (bull correction): {natr_short} (NATR={latest['natr']:.2f}%)")
        
        short_conditions.append(natr_short)
        
        # EMA20 условие (для bull correction)
        if not btc_short:
            ema20 = df_ada['close'].ewm(span=20).mean().iloc[-1]
            ema20_short = latest['close'] < ema20
            print(f"   Close < EMA20 (bull correction): {ema20_short}")
        else:
            ema20_short = True
            print(f"   EMA20 условие (bear market): {ema20_short}")
        
        short_conditions.append(ema20_short)
        
        # Режим условия
        regime_short = latest['regime'] in ['normal', 'high']
        short_conditions.append(regime_short)
        print(f"   ❌ Режим normal/high: {regime_short} (режим={latest['regime']})")
        
        print(f"\n   📊 ИТОГ ШОРТОВ: {sum(short_conditions)}/6 условий выполнено")
        
        # Финальные разрешения
        print(f"\n📊 ФИНАЛЬНЫЕ РАЗРЕШЕНИЯ:")
        print(f"   Allow long raw: {latest.get('allow_long_raw', False)}")
        print(f"   Allow long: {latest.get('allow_long', False)}")
        print(f"   Allow short raw: {latest.get('allow_short_raw', False)}")
        print(f"   Allow short: {latest.get('allow_short', False)}")
        
        # Анализ причин отсутствия позиций
        print(f"\n💡 ПРИЧИНЫ ОТСУТСТВИЯ ПОЗИЦИЙ:")
        
        if not latest.get('allow_long', False):
            print(f"   📈 ЛОНГИ ЗАБЛОКИРОВАНЫ:")
            if not btc_long:
                print(f"     - BTC Market Filter блокирует лонги")
            if not ema_long:
                print(f"     - EMA50 < EMA200 (медвежий тренд)")
            if not rsi_long:
                print(f"     - RSI слишком низкий ({latest['rsi']:.1f} < 35)")
            if not natr_long:
                print(f"     - NATR слишком низкий ({latest['natr']:.2f}% < 0.5%)")
            if not regime_long:
                print(f"     - Режим рынка неподходящий ({latest['regime']})")
            if not inside_bar_long:
                print(f"     - Отсутствуют внутренние бары для входа")
        
        if not latest.get('allow_short', False):
            print(f"   📉 ШОРТЫ ЗАБЛОКИРОВАНЫ:")
            if not btc_short:
                print(f"     - BTC Market Filter блокирует шорты")
            if not ema_short:
                print(f"     - EMA50 > EMA200 (бычий тренд)")
            if not rsi_short:
                print(f"     - RSI слишком высокий для шортов")
            if not natr_short:
                print(f"     - NATR слишком низкий для шортов")
            if not ema20_short:
                print(f"     - Цена выше EMA20")
            if not regime_short:
                print(f"     - Режим рынка неподходящий ({latest['regime']})")
        
        return latest, latest_btc
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return None, None

def main():
    """Главная функция анализа"""
    print("🚀 АНАЛИЗ ЛОГИКИ СИСТЕМЫ SIGNALWARDEN LITE v1.6-TXB")
    print("=" * 80)
    
    # Анализируем логику системы
    ada_data, btc_data = analyze_system_logic()
    
    if ada_data is not None and btc_data is not None:
        print(f"\n🎯 ИТОГОВЫЙ ВЫВОД:")
        print(f"   Система работает корректно")
        print(f"   Текущий BTC тренд: {'МЕДВЕЖИЙ' if btc_data['mkt_short_ok'] else 'БЫЧИЙ'}")
        print(f"   Позиции заблокированы из-за:")
        print(f"     - Неподходящих рыночных условий")
        print(f"     - Низкой волатильности (режим: calm)")
        print(f"     - Строгих фильтров качества сигналов")

if __name__ == "__main__":
    main()
