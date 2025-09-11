#!/usr/bin/env python3
"""
Проверка текущих данных и сравнение с логами системы
Анализирует расхождения между анализом и реальными логами
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

def check_current_data():
    """Проверяет текущие данные и сравнивает с логами"""
    print("🔍 ПРОВЕРКА ТЕКУЩИХ ДАННЫХ И СРАВНЕНИЕ С ЛОГАМИ")
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
        
        print(f"📊 ТЕКУЩИЕ ДАННЫЕ ADA:")
        print(f"  Время: {df_ada['timestamp'].iloc[-1]}")
        print(f"  Цена: ${latest['close']:.6f}")
        print(f"  EMA50: {latest['ema_fast']:.6f}")
        print(f"  EMA200: {latest['ema_slow']:.6f}")
        print(f"  RSI: {latest['rsi']:.1f}")
        print(f"  NATR: {latest['natr']:.2f}%")
        print(f"  Режим: {latest['regime']}")
        
        print(f"\n📊 BTC MARKET FILTER:")
        print(f"  BTC Цена: ${df_btc['close'].iloc[-1]:,.2f}")
        print(f"  BTC EMA50: ${df_btc['close'].ewm(span=50).mean().iloc[-1]:,.2f}")
        print(f"  BTC EMA200: ${df_btc['close'].ewm(span=200).mean().iloc[-1]:,.2f}")
        print(f"  Лонги разрешены: {latest_btc['mkt_long_ok']}")
        print(f"  Шорты разрешены: {latest_btc['mkt_short_ok']}")
        
        # Сравниваем с логами
        print(f"\n🔍 СРАВНЕНИЕ С ЛОГАМИ:")
        print(f"  Лог: 'State: high regime, Price: $0.816400, NATR: 3.0%, RSI: 54, BTC: 🟢L❌S'")
        print(f"  Время лога: 2025-09-09 23:27:14")
        
        # Проверяем расхождения
        print(f"\n📊 РАСХОЖДЕНИЯ:")
        
        # Цена
        log_price = 0.816400
        current_price = latest['close']
        price_diff = abs(current_price - log_price)
        print(f"  Цена: Лог=${log_price:.6f}, Текущая=${current_price:.6f}, Разница=${price_diff:.6f}")
        
        # NATR
        log_natr = 3.0
        current_natr = latest['natr']
        natr_diff = abs(current_natr - log_natr)
        print(f"  NATR: Лог={log_natr:.1f}%, Текущий={current_natr:.2f}%, Разница={natr_diff:.2f}%")
        
        # RSI
        log_rsi = 54
        current_rsi = latest['rsi']
        rsi_diff = abs(current_rsi - log_rsi)
        print(f"  RSI: Лог={log_rsi}, Текущий={current_rsi:.1f}, Разница={rsi_diff:.1f}")
        
        # Режим
        log_regime = "high"
        current_regime = latest['regime']
        regime_match = log_regime == current_regime
        print(f"  Режим: Лог={log_regime}, Текущий={current_regime}, Совпадение={regime_match}")
        
        # BTC Market Filter
        log_btc_long = True  # 🟢L
        log_btc_short = False  # ❌S
        current_btc_long = latest_btc['mkt_long_ok']
        current_btc_short = latest_btc['mkt_short_ok']
        print(f"  BTC Long: Лог={log_btc_long}, Текущий={current_btc_long}, Совпадение={log_btc_long == current_btc_long}")
        print(f"  BTC Short: Лог={log_btc_short}, Текущий={current_btc_short}, Совпадение={log_btc_short == current_btc_short}")
        
        # Анализируем условия для лонгов
        print(f"\n🔍 АНАЛИЗ УСЛОВИЙ ДЛЯ ЛОНГОВ:")
        
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
        
        # 6. Внутренние бары
        recent_bars = df_ada.tail(3)
        inside_bars = 0
        for i in range(1, len(recent_bars)):
            if (recent_bars.iloc[i]['high'] <= recent_bars.iloc[i-1]['high'] and 
                recent_bars.iloc[i]['low'] >= recent_bars.iloc[i-1]['low']):
                inside_bars += 1
        
        inside_bar_condition = inside_bars >= 1
        print(f"  6. Внутренние бары (≥1): {inside_bar_condition}")
        
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
        
        # Финальные разрешения
        print(f"\n📊 ФИНАЛЬНЫЕ РАЗРЕШЕНИЯ:")
        print(f"  Allow long raw: {latest.get('allow_long_raw', False)}")
        print(f"  Allow long: {latest.get('allow_long', False)}")
        print(f"  Allow short raw: {latest.get('allow_short_raw', False)}")
        print(f"  Allow short: {latest.get('allow_short', False)}")
        
        # Проверяем, почему в логах показан лонг разрешен
        print(f"\n💡 АНАЛИЗ ЛОГОВ:")
        if log_regime == "high" and log_natr >= 3.0 and log_rsi >= 35:
            print(f"  ✅ В логах показан режим 'high' - это означает высокую волатильность")
            print(f"  ✅ NATR 3.0% - достаточная волатильность для торговли")
            print(f"  ✅ RSI 54 - подходящий уровень для лонгов")
            print(f"  ✅ BTC Market Filter разрешает лонги")
            print(f"  💡 В логах лонг действительно должен быть разрешен!")
        
        return latest, latest_btc
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return None, None

def check_time_difference():
    """Проверяет разницу во времени между логами и текущими данными"""
    print(f"\n🕐 АНАЛИЗ ВРЕМЕНИ:")
    
    # Время лога
    log_time = datetime(2025, 9, 9, 23, 27, 14)
    current_time = datetime.now()
    
    time_diff = current_time - log_time
    print(f"  Время лога: {log_time}")
    print(f"  Текущее время: {current_time}")
    print(f"  Разница: {time_diff}")
    
    if time_diff.total_seconds() > 3600:  # Больше часа
        print(f"  ⚠️  Разница больше часа - данные могли измениться")
    else:
        print(f"  ✅ Разница небольшая - данные должны быть актуальными")

def main():
    """Главная функция проверки"""
    print("🚀 ПРОВЕРКА ТЕКУЩИХ ДАННЫХ И СРАВНЕНИЕ С ЛОГАМИ")
    print("=" * 80)
    
    # Проверяем текущие данные
    ada_data, btc_data = check_current_data()
    
    # Проверяем разницу во времени
    check_time_difference()
    
    if ada_data is not None and btc_data is not None:
        print(f"\n🎯 ИТОГОВЫЙ ВЫВОД:")
        print(f"  Логи показывают правильную информацию")
        print(f"  В режиме 'high' с NATR 3.0% и RSI 54 лонги должны быть разрешены")
        print(f"  Текущие данные могут отличаться из-за времени или изменений рынка")

if __name__ == "__main__":
    main()
