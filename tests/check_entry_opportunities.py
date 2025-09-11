#!/usr/bin/env python3
"""
Анализ возможностей входа в позиции с ночи
Проверяет данные с Binance и анализирует условия для сигналов
"""

import os
import sys
import time
import yaml
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dotenv import load_dotenv
import ccxt

# Добавляем путь к модулям
sys.path.append('signalwarden_lite')

from core.features import add_indicators
from core.regimes import add_regime, RegimeThresholds
from core.market import compute_market_bias
from core.signals import generate_signals, SignalParams

def fetch_binance_data(symbol, timeframe='1h', limit=100):
    """Получить данные с Binance"""
    try:
        exchange = ccxt.binanceusdm({
            'apiKey': os.getenv('BINANCE_API_KEY'),
            'secret': os.getenv('BINANCE_SECRET'),
            'sandbox': False,
            'rateLimit': True
        })
        
        # Получить данные
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        
        # Преобразовать в DataFrame
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        # Не устанавливаем timestamp как индекс, оставляем как колонку
        
        return df
        
    except Exception as e:
        print(f"❌ Ошибка получения данных для {symbol}: {e}")
        return None

def analyze_entry_opportunities():
    """Анализ возможностей входа в позиции"""
    
    print("🔍 АНАЛИЗ ВОЗМОЖНОСТЕЙ ВХОДА В ПОЗИЦИИ")
    print("=" * 80)
    
    # Загрузить конфигурацию
    with open('signalwarden_lite/config/config_production.yaml', 'r') as f:
        cfg = yaml.safe_load(f)
    
    symbols = cfg['symbols']
    # Преобразовать символы в формат Binance
    binance_symbols = [f"{symbol.replace('_', '/')}:USDT" for symbol in symbols]
    
    # Параметры для анализа
    regime_thresholds = RegimeThresholds(
        ultra_calm=cfg['regime']['calm_thresholds']['ultra_calm'],
        calm=cfg['regime']['calm_thresholds']['calm'],
        high=cfg['regime']['calm_thresholds']['high']
    )
    
    signal_params = SignalParams(
        setup_breakout=cfg['signals']['setups']['breakout']['enabled'],
        setup_inside=cfg['signals']['setups']['inside_bar']['enabled'],
        setup_trend_cont=cfg['signals']['setups']['trend_continuation']['enabled'],
        setup_squeeze=cfg['signals']['setups']['squeeze_breakout']['enabled'],
        lookback_calm=cfg['signals']['dynamic_lookback']['calm'],
        lookback_normal=cfg['signals']['dynamic_lookback']['normal'],
        lookback_high=cfg['signals']['dynamic_lookback']['high'],
        long_cushion_calm=cfg['signals']['atr_cushion_long']['calm'],
        long_cushion_normal=cfg['signals']['atr_cushion_long']['normal'],
        long_cushion_high=cfg['signals']['atr_cushion_long']['high'],
        short_cushion_calm=cfg['signals']['atr_cushion_short']['calm'],
        short_cushion_normal=cfg['signals']['atr_cushion_short']['normal'],
        short_cushion_high=cfg['signals']['atr_cushion_short']['high'],
        ltf_thinbar_k=cfg['signals']['ltf_thinbar_k']
    )
    
    # Получить BTC данные для market filter
    print("📊 Получение BTC данных для market filter...")
    btc_data = fetch_binance_data('BTC/USDT:USDT', '1h', 200)
    if btc_data is None:
        print("❌ Не удалось получить BTC данные")
        return
    
    # Добавить индикаторы к BTC данным
    btc_data = add_indicators(btc_data, cfg['market_filter']['ema_fast'], cfg['market_filter']['ema_slow'])
    
    # Вычислить market bias
    btc_market = compute_market_bias(btc_data, cfg['market_filter']['ema_fast'], cfg['market_filter']['ema_slow'])
    latest_btc = btc_market.iloc[-1]
    latest_btc_data = btc_data.iloc[-1]
    
    print(f"🟢 BTC Market Filter: {'BULL' if latest_btc['mkt_long_ok'] else 'BEAR'} (longs: {latest_btc['mkt_long_ok']}, shorts: {latest_btc['mkt_short_ok']})")
    print(f"   EMA50: {latest_btc_data['ema_fast']:.2f}, EMA200: {latest_btc_data['ema_slow']:.2f}")
    print()
    
    opportunities_found = 0
    
    # Анализировать каждую пару
    for symbol, binance_symbol in zip(symbols, binance_symbols):
        print(f"📊 Анализ {symbol}...")
        
        # Получить данные 1h
        df_1h = fetch_binance_data(binance_symbol, '1h', 200)
        if df_1h is None:
            continue
            
        # Получить данные 15m
        df_15m = fetch_binance_data(binance_symbol, '15m', 200)
        if df_15m is None:
            continue
        
        # Добавить индикаторы
        df_1h = add_indicators(df_1h)
        df_15m = add_indicators(df_15m)
        
        # Добавить режимы
        df_1h = add_regime(df_1h, regime_thresholds)
        df_15m = add_regime(df_15m, regime_thresholds)
        
        # Генерировать сигналы
        signals_1h = generate_signals(df_1h, signal_params, btc_market)
        signals_15m = generate_signals(df_15m, signal_params, btc_market)
        
        # Анализировать последние 24 часа (24 бара для 1h)
        recent_1h = signals_1h.tail(24)
        recent_15m = signals_15m.tail(96)  # 96 баров для 15m (24 часа)
        
        # Проверить возможности входа
        long_opportunities = []
        short_opportunities = []
        
        # Проверить 1h сигналы
        for i, row in recent_1h.iterrows():
            if row.get('allow_long', False) and row.get('sig_long_breakout', False):
                long_opportunities.append({
                    'time': i,
                    'type': '1h_breakout_long',
                    'price': row['close'],
                    'regime': row['regime'],
                    'rsi': row['rsi'],
                    'natr': row['natr']
                })
            
            if row.get('allow_short', False) and row.get('sig_short_breakout', False):
                short_opportunities.append({
                    'time': i,
                    'type': '1h_breakout_short',
                    'price': row['close'],
                    'regime': row['regime'],
                    'rsi': row['rsi'],
                    'natr': row['natr']
                })
        
        # Проверить 15m сигналы
        for i, row in recent_15m.iterrows():
            if row.get('allow_long', False):
                if row.get('sig_long_inside', False):
                    long_opportunities.append({
                        'time': i,
                        'type': '15m_inside_long',
                        'price': row['close'],
                        'regime': row['regime'],
                        'rsi': row['rsi'],
                        'natr': row['natr']
                    })
                elif row.get('sig_long_tc', False):
                    long_opportunities.append({
                        'time': i,
                        'type': '15m_tc_long',
                        'price': row['close'],
                        'regime': row['regime'],
                        'rsi': row['rsi'],
                        'natr': row['natr']
                    })
                elif row.get('sig_long_sq', False):
                    long_opportunities.append({
                        'time': i,
                        'type': '15m_squeeze_long',
                        'price': row['close'],
                        'regime': row['regime'],
                        'rsi': row['rsi'],
                        'natr': row['natr']
                    })
            
            if row.get('allow_short', False):
                if row.get('sig_short_inside', False):
                    short_opportunities.append({
                        'time': i,
                        'type': '15m_inside_short',
                        'price': row['close'],
                        'regime': row['regime'],
                        'rsi': row['rsi'],
                        'natr': row['natr']
                    })
                elif row.get('sig_short_tc', False):
                    short_opportunities.append({
                        'time': i,
                        'type': '15m_tc_short',
                        'price': row['close'],
                        'regime': row['regime'],
                        'rsi': row['rsi'],
                        'natr': row['natr']
                    })
                elif row.get('sig_short_sq', False):
                    short_opportunities.append({
                        'time': i,
                        'type': '15m_squeeze_short',
                        'price': row['close'],
                        'regime': row['regime'],
                        'rsi': row['rsi'],
                        'natr': row['natr']
                    })
        
        # Показать результаты
        if long_opportunities or short_opportunities:
            opportunities_found += 1
            print(f"   ✅ Найдены возможности входа:")
            
            if long_opportunities:
                print(f"   📈 LONG сигналы ({len(long_opportunities)}):")
                for opp in long_opportunities[-5:]:  # Показать последние 5
                    time_str = opp['time'].strftime('%H:%M') if hasattr(opp['time'], 'strftime') else str(opp['time'])
                    print(f"      {time_str} - {opp['type']} @ ${opp['price']:.4f} (RSI: {opp['rsi']:.1f}, NATR: {opp['natr']:.1f}%, {opp['regime']})")
            
            if short_opportunities:
                print(f"   📉 SHORT сигналы ({len(short_opportunities)}):")
                for opp in short_opportunities[-5:]:  # Показать последние 5
                    time_str = opp['time'].strftime('%H:%M') if hasattr(opp['time'], 'strftime') else str(opp['time'])
                    print(f"      {time_str} - {opp['type']} @ ${opp['price']:.4f} (RSI: {opp['rsi']:.1f}, NATR: {opp['natr']:.1f}%, {opp['regime']})")
        else:
            print(f"   ❌ Возможности входа не найдены")
        
        # Показать текущее состояние
        latest_1h = signals_1h.iloc[-1]
        latest_15m = signals_15m.iloc[-1]
        
        print(f"   📊 Текущее состояние:")
        print(f"      1h: {latest_1h['regime']} regime, RSI: {latest_1h['rsi']:.1f}, NATR: {latest_1h['natr']:.1f}%, Allow Long: {latest_1h.get('allow_long', False)}, Allow Short: {latest_1h.get('allow_short', False)}")
        print(f"      15m: {latest_15m['regime']} regime, RSI: {latest_15m['rsi']:.1f}, NATR: {latest_15m['natr']:.1f}%, Allow Long: {latest_15m.get('allow_long', False)}, Allow Short: {latest_15m.get('allow_short', False)}")
        print()
    
    print("=" * 80)
    print(f"📊 ИТОГО: Найдено возможностей входа в {opportunities_found} из {len(symbols)} пар")
    
    if opportunities_found == 0:
        print("🤔 Возможные причины отсутствия сигналов:")
        print("   - Низкая волатильность (ultra_calm/calm режимы)")
        print("   - RSI не в подходящем диапазоне")
        print("   - BTC market filter блокирует сигналы")
        print("   - Отсутствие пробоев swing уровней")
        print("   - Недостаточная волатильность для squeeze сигналов")

if __name__ == "__main__":
    load_dotenv()
    analyze_entry_opportunities()
