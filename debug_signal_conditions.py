#!/usr/bin/env python3
"""
Отладка условий генерации сигналов
Проверяет, почему система не генерирует сигналы при выполненных условиях
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

def debug_signal_conditions():
    """Отлаживает условия генерации сигналов"""
    print("🔍 ОТЛАДКА УСЛОВИЙ ГЕНЕРАЦИИ СИГНАЛОВ")
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
        latest_btc = btc_bias.iloc[-1]
        
        print(f"\n📊 BTC Market Filter:")
        print(f"  Лонги разрешены: {latest_btc['mkt_long_ok']}")
        print(f"  Шорты разрешены: {latest_btc['mkt_short_ok']}")
        
        # Добавляем индикаторы для ADA
        df_ada = add_indicators(df_ada, ema_fast=50, ema_slow=200)
        df_ada = add_regime(df_ada, RegimeThresholds())
        
        print(f"\n📊 ADA индикаторы:")
        latest_ada = df_ada.iloc[-1]
        print(f"  Цена: ${latest_ada['close']:.6f}")
        print(f"  EMA50: {latest_ada['ema_fast']:.6f}")
        print(f"  EMA200: {latest_ada['ema_slow']:.6f}")
        print(f"  RSI: {latest_ada['rsi']:.1f}")
        print(f"  NATR: {latest_ada['natr']:.2f}%")
        print(f"  Режим: {latest_ada['regime']}")
        
        # Параметры сигналов
        signal_params = SignalParams()
        
        print(f"\n⚙️ Параметры сигналов:")
        print(f"  Breakout: {signal_params.setup_breakout}")
        print(f"  Inside: {signal_params.setup_inside}")
        print(f"  Trend continuation: {signal_params.setup_trend_cont}")
        print(f"  Squeeze: {signal_params.setup_squeeze}")
        
        # Генерируем сигналы
        signals = generate_signals(df_ada, signal_params, btc_bias)
        
        print(f"\n🔍 Анализ последнего бара:")
        latest_signal = signals.iloc[-1]
        
        print(f"  Цена: ${latest_signal['close']:.6f}")
        print(f"  EMA50: {latest_signal['ema_fast']:.6f}")
        print(f"  EMA200: {latest_signal['ema_slow']:.6f}")
        print(f"  RSI: {latest_signal['rsi']:.1f}")
        print(f"  NATR: {latest_signal['natr']:.2f}%")
        print(f"  Режим: {latest_signal['regime']}")
        
        print(f"\n📊 Тренды:")
        print(f"  Trend long: {latest_signal['trend_long']}")
        print(f"  Trend short: {latest_signal['trend_short']}")
        
        print(f"\n🎯 Сырые сигналы:")
        print(f"  Long breakout: {latest_signal.get('sig_long_breakout', False)}")
        print(f"  Long inside: {latest_signal.get('sig_long_inside', False)}")
        print(f"  Long trend cont: {latest_signal.get('sig_long_tc', False)}")
        print(f"  Long squeeze: {latest_signal.get('sig_long_sq', False)}")
        print(f"  Short breakout: {latest_signal.get('sig_short_breakout', False)}")
        print(f"  Short inside: {latest_signal.get('sig_short_inside', False)}")
        print(f"  Short trend cont: {latest_signal.get('sig_short_tc', False)}")
        print(f"  Short squeeze: {latest_signal.get('sig_short_sq', False)}")
        
        print(f"\n🔒 Сырые разрешения:")
        print(f"  Allow long raw: {latest_signal.get('allow_long_raw', False)}")
        print(f"  Allow short raw: {latest_signal.get('allow_short_raw', False)}")
        
        print(f"\n🛡️ Фильтры:")
        print(f"  BTC long ok: {latest_signal.get('mkt_long_ok', False)}")
        print(f"  BTC short ok: {latest_signal.get('mkt_short_ok', False)}")
        
        print(f"\n✅ Финальные разрешения:")
        print(f"  Allow long: {latest_signal.get('allow_long', False)}")
        print(f"  Allow short: {latest_signal.get('allow_short', False)}")
        
        # Анализируем последние 10 баров
        print(f"\n📊 Анализ последних 10 баров:")
        recent = signals.tail(10)
        
        long_count = recent['allow_long'].sum()
        short_count = recent['allow_short'].sum()
        long_raw_count = recent['allow_long_raw'].sum()
        short_raw_count = recent['allow_short_raw'].sum()
        
        print(f"  Лонги (сырые): {long_raw_count}/10")
        print(f"  Шорты (сырые): {short_raw_count}/10")
        print(f"  Лонги (финальные): {long_count}/10")
        print(f"  Шорты (финальные): {short_count}/10")
        
        # Проверяем, где теряются сигналы
        if long_raw_count > 0 and long_count == 0:
            print(f"\n❌ ПРОБЛЕМА: Сырые лонги есть, но финальные лонги отсутствуют")
            print(f"   Проверьте BTC фильтр и другие фильтры")
        elif long_raw_count == 0:
            print(f"\n❌ ПРОБЛЕМА: Нет сырых лонгов вообще")
            print(f"   Проверьте условия генерации сигналов")
        else:
            print(f"\n✅ Система работает корректно")
        
        # Детальный анализ условий для лонгов
        print(f"\n🔍 ДЕТАЛЬНЫЙ АНАЛИЗ УСЛОВИЙ ДЛЯ ЛОНГОВ:")
        
        # Проверяем условия для каждого типа сигнала
        if signal_params.setup_breakout:
            print(f"\n  Breakout сигналы:")
            # Здесь нужно проверить условия для breakout
            # Это требует анализа swing уровней и пробоев
            
        if signal_params.setup_inside:
            print(f"\n  Inside-bar сигналы:")
            # Проверяем условия для inside-bar
            
        if signal_params.setup_trend_cont:
            print(f"\n  Trend-continuation сигналы:")
            # Проверяем условия для trend-continuation
            
        if signal_params.setup_squeeze:
            print(f"\n  Squeeze сигналы:")
            # Проверяем условия для squeeze
            
        return latest_signal
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    """Главная функция"""
    debug_signal_conditions()

if __name__ == "__main__":
    main()
