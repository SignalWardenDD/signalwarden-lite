#!/usr/bin/env python3
"""
Отладка BTC gate в live системе
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
from typing import Dict, List, Any, Optional

# Добавляем путь к модулям
sys.path.append('.')

from signalwarden_lite.core.features import add_indicators
from signalwarden_lite.core.regimes import add_regime, RegimeThresholds
from signalwarden_lite.core.market import compute_market_bias
from signalwarden_lite.core.signals import generate_signals, SignalParams

def ccxt_symbol(symbol: str) -> str:
    """Convert our symbol format to CCXT format"""
    if '_' in symbol:
        # ADA_USDT -> ADA/USDT:USDT
        base, quote = symbol.split('_')
        return f"{base}/{quote}:USDT"
    
    # If no underscore, assume it's already in some other format
    return symbol

def fetch_ohlcv_live_style(exchange, symbol: str, timeframe: str, limit: int = 500) -> pd.DataFrame:
    """Fetch OHLCV data exactly like live system"""
    try:
        ccxt_sym = ccxt_symbol(symbol)
        ohlcv = exchange.fetch_ohlcv(ccxt_sym, timeframe=timeframe, limit=limit)
        
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = (df['timestamp'] // 1000).astype(int)  # Convert to seconds
        
        return df.sort_values('timestamp').reset_index(drop=True)
        
    except Exception as e:
        print(f"❌ Failed to fetch {symbol} {timeframe}: {e}")
        return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

def debug_btc_gate():
    """Отладка BTC gate"""
    
    print("🔍 ОТЛАДКА BTC GATE В LIVE СИСТЕМЕ")
    print("=" * 80)
    
    # Загрузить конфигурацию
    with open('signalwarden_lite/config/config_production.yaml', 'r') as f:
        cfg = yaml.safe_load(f)
    
    # Настроить подключение к бирже
    load_dotenv()
    exchange = ccxt.binanceusdm({
        'apiKey': os.getenv('BINANCE_API_KEY'),
        'secret': os.getenv('BINANCE_SECRET'),
        'enableRateLimit': True,
        'timeout': 30000,
        'options': {'defaultType': 'future'}
    })
    
    # Получить BTC данные для market filter
    print("📊 Получение BTC данных...")
    btc_data = fetch_ohlcv_live_style(exchange, 'BTC/USDT:USDT', '1h', 200)
    btc_data = add_indicators(btc_data, 50, 200)
    btc_market = compute_market_bias(btc_data, 50, 200)
    
    print(f"📊 BTC Market Filter создан: {len(btc_market)} записей")
    print(f"📊 Последние 5 записей BTC gate:")
    for i, row in btc_market.tail().iterrows():
        print(f"   {i}: timestamp={row['timestamp']}, mkt_long_ok={row['mkt_long_ok']}, mkt_short_ok={row['mkt_short_ok']}")
    
    print()
    
    # Проверить конкретную пару
    symbol = 'ADA_USDT'
    print(f"🔍 ПРОВЕРКА BTC GATE ДЛЯ {symbol}...")
    print("-" * 60)
    
    # Получить 15m данные
    df_15m = fetch_ohlcv_live_style(exchange, symbol, '15m', 400)
    print(f"📊 15m данных получено: {len(df_15m)} баров")
    print(f"📊 Последние 5 timestamp 15m:")
    for i, row in df_15m.tail().iterrows():
        print(f"   {i}: timestamp={row['timestamp']}, close={row['close']}")
    
    print()
    
    # Создать 15m gate как в live системе
    print("📊 Создание 15m gate как в live системе...")
    gate_15m_data = []
    for ts in df_15m['timestamp'].values:
        mask = btc_market['timestamp'] <= ts
        if mask.any():
            idx = mask.idxmax()
            gate_15m_data.append({
                'timestamp': ts,
                'mkt_long_ok': btc_market.iloc[idx]['mkt_long_ok'],
                'mkt_short_ok': btc_market.iloc[idx]['mkt_short_ok']
            })
        else:
            gate_15m_data.append({'timestamp': ts, 'mkt_long_ok': False, 'mkt_short_ok': False})
    gate_15m = pd.DataFrame(gate_15m_data)
    
    print(f"📊 15m gate создан: {len(gate_15m)} записей")
    print(f"📊 Последние 5 записей 15m gate:")
    for i, row in gate_15m.tail().iterrows():
        print(f"   {i}: timestamp={row['timestamp']}, mkt_long_ok={row['mkt_long_ok']}, mkt_short_ok={row['mkt_short_ok']}")
    
    print()
    
    # Проверить соответствие timestamp
    print("📊 ПРОВЕРКА СООТВЕТСТВИЯ TIMESTAMP:")
    print(f"   BTC gate последний timestamp: {btc_market.iloc[-1]['timestamp']}")
    print(f"   15m данные последний timestamp: {df_15m.iloc[-1]['timestamp']}")
    print(f"   15m gate последний timestamp: {gate_15m.iloc[-1]['timestamp']}")
    
    # Проверить, есть ли проблемы с соответствием
    btc_last_ts = btc_market.iloc[-1]['timestamp']
    df_15m_last_ts = df_15m.iloc[-1]['timestamp']
    gate_15m_last_ts = gate_15m.iloc[-1]['timestamp']
    
    print(f"   Разница BTC vs 15m: {df_15m_last_ts - btc_last_ts} секунд")
    print(f"   Разница 15m vs gate: {gate_15m_last_ts - df_15m_last_ts} секунд")
    
    # Проверить последние значения mkt_long_ok
    print(f"   BTC gate последний mkt_long_ok: {btc_market.iloc[-1]['mkt_long_ok']}")
    print(f"   15m gate последний mkt_long_ok: {gate_15m.iloc[-1]['mkt_long_ok']}")
    
    print()
    
    # Проверить, есть ли False значения в 15m gate
    false_long_count = (gate_15m['mkt_long_ok'] == False).sum()
    true_long_count = (gate_15m['mkt_long_ok'] == True).sum()
    
    print(f"📊 СТАТИСТИКА 15m GATE:")
    print(f"   mkt_long_ok = True: {true_long_count}")
    print(f"   mkt_long_ok = False: {false_long_count}")
    
    if false_long_count > 0:
        print(f"   ⚠️ НАЙДЕНЫ False значения в 15m gate!")
        false_indices = gate_15m[gate_15m['mkt_long_ok'] == False].index
        print(f"   Индексы с False: {false_indices.tolist()}")
        
        # Показать несколько примеров
        print(f"   Примеры False значений:")
        for idx in false_indices[:5]:
            row = gate_15m.iloc[idx]
            print(f"     {idx}: timestamp={row['timestamp']}, mkt_long_ok={row['mkt_long_ok']}")
    
    print()
    
    # Проверить, что происходит с последними записями
    print("📊 АНАЛИЗ ПОСЛЕДНИХ ЗАПИСЕЙ:")
    last_10_btc = btc_market.tail(10)
    last_10_15m = df_15m.tail(10)
    last_10_gate = gate_15m.tail(10)
    
    print("   BTC gate (последние 10):")
    for i, row in last_10_btc.iterrows():
        print(f"     {i}: ts={row['timestamp']}, long={row['mkt_long_ok']}")
    
    print("   15m данные (последние 10):")
    for i, row in last_10_15m.iterrows():
        print(f"     {i}: ts={row['timestamp']}, close={row['close']}")
    
    print("   15m gate (последние 10):")
    for i, row in last_10_gate.iterrows():
        print(f"     {i}: ts={row['timestamp']}, long={row['mkt_long_ok']}")
    
    print()
    
    # Проверить логику сопоставления
    print("📊 ПРОВЕРКА ЛОГИКИ СОПОСТАВЛЕНИЯ:")
    test_ts = df_15m.iloc[-1]['timestamp']
    print(f"   Тестовый timestamp: {test_ts}")
    
    mask = btc_market['timestamp'] <= test_ts
    print(f"   Маска btc_market['timestamp'] <= {test_ts}:")
    print(f"     True значений: {mask.sum()}")
    print(f"     False значений: {(~mask).sum()}")
    
    if mask.any():
        idx = mask.idxmax()
        print(f"   Индекс максимального True: {idx}")
        print(f"   Соответствующая запись BTC:")
        btc_row = btc_market.iloc[idx]
        print(f"     timestamp: {btc_row['timestamp']}")
        print(f"     mkt_long_ok: {btc_row['mkt_long_ok']}")
        print(f"     mkt_short_ok: {btc_row['mkt_short_ok']}")
    else:
        print(f"   ❌ НЕТ СООТВЕТСТВУЮЩИХ ЗАПИСЕЙ BTC!")

if __name__ == "__main__":
    debug_btc_gate()
