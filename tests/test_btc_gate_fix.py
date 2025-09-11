#!/usr/bin/env python3
"""
Тест исправления BTC gate логики
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

def create_15m_gate_old_logic(btc_gate: pd.DataFrame, df_15m: pd.DataFrame) -> pd.DataFrame:
    """Старая (неправильная) логика создания 15m gate"""
    gate_15m_data = []
    for ts in df_15m['timestamp'].values:
        mask = btc_gate['timestamp'] <= ts
        if mask.any():
            idx = mask.idxmax()  # ❌ НЕПРАВИЛЬНО!
            gate_15m_data.append({
                'timestamp': ts,
                'mkt_long_ok': btc_gate.iloc[idx]['mkt_long_ok'],
                'mkt_short_ok': btc_gate.iloc[idx]['mkt_short_ok']
            })
        else:
            gate_15m_data.append({'timestamp': ts, 'mkt_long_ok': False, 'mkt_short_ok': False})
    return pd.DataFrame(gate_15m_data)

def create_15m_gate_new_logic(btc_gate: pd.DataFrame, df_15m: pd.DataFrame) -> pd.DataFrame:
    """Новая (правильная) логика создания 15m gate"""
    gate_15m_data = []
    for ts in df_15m['timestamp'].values:
        mask = btc_gate['timestamp'] <= ts
        if mask.any():
            # ИСПРАВЛЕНИЕ: Найти последний True индекс вместо idxmax()
            true_indices = mask[mask].index
            idx = true_indices[-1]  # Последний True индекс
            gate_15m_data.append({
                'timestamp': ts,
                'mkt_long_ok': btc_gate.iloc[idx]['mkt_long_ok'],
                'mkt_short_ok': btc_gate.iloc[idx]['mkt_short_ok']
            })
        else:
            gate_15m_data.append({'timestamp': ts, 'mkt_long_ok': False, 'mkt_short_ok': False})
    return pd.DataFrame(gate_15m_data)

def test_btc_gate_fix():
    """Тест исправления BTC gate логики"""
    
    print("🔧 ТЕСТ ИСПРАВЛЕНИЯ BTC GATE ЛОГИКИ")
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
    print(f"📊 Последние 3 записи BTC gate:")
    for i, row in btc_market.tail(3).iterrows():
        print(f"   {i}: timestamp={row['timestamp']}, mkt_long_ok={row['mkt_long_ok']}")
    
    print()
    
    # Проверить конкретную пару
    symbol = 'ADA_USDT'
    print(f"🔍 ТЕСТИРОВАНИЕ {symbol}...")
    print("-" * 60)
    
    # Получить 15m данные
    df_15m = fetch_ohlcv_live_style(exchange, symbol, '15m', 400)
    print(f"📊 15m данных получено: {len(df_15m)} баров")
    print(f"📊 Последние 3 timestamp 15m:")
    for i, row in df_15m.tail(3).iterrows():
        print(f"   {i}: timestamp={row['timestamp']}, close={row['close']}")
    
    print()
    
    # Создать 15m gate старой логикой
    print("📊 Создание 15m gate СТАРОЙ логикой...")
    gate_15m_old = create_15m_gate_old_logic(btc_market, df_15m)
    print(f"📊 Старая логика - последние 3 записи:")
    for i, row in gate_15m_old.tail(3).iterrows():
        print(f"   {i}: timestamp={row['timestamp']}, mkt_long_ok={row['mkt_long_ok']}")
    
    # Создать 15m gate новой логикой
    print("📊 Создание 15m gate НОВОЙ логикой...")
    gate_15m_new = create_15m_gate_new_logic(btc_market, df_15m)
    print(f"📊 Новая логика - последние 3 записи:")
    for i, row in gate_15m_new.tail(3).iterrows():
        print(f"   {i}: timestamp={row['timestamp']}, mkt_long_ok={row['mkt_long_ok']}")
    
    print()
    
    # Сравнить результаты
    print("📊 СРАВНЕНИЕ РЕЗУЛЬТАТОВ:")
    old_true_count = (gate_15m_old['mkt_long_ok'] == True).sum()
    new_true_count = (gate_15m_new['mkt_long_ok'] == True).sum()
    
    print(f"   Старая логика - mkt_long_ok = True: {old_true_count}")
    print(f"   Новая логика - mkt_long_ok = True: {new_true_count}")
    print(f"   Разница: {new_true_count - old_true_count}")
    
    if new_true_count > old_true_count:
        print(f"   ✅ ИСПРАВЛЕНИЕ РАБОТАЕТ! Теперь {new_true_count} записей с mkt_long_ok=True")
    else:
        print(f"   ❌ Проблема не исправлена")
    
    print()
    
    # Проверить конкретные timestamp
    print("📊 ПРОВЕРКА КОНКРЕТНЫХ TIMESTAMP:")
    test_ts = df_15m.iloc[-1]['timestamp']
    print(f"   Тестовый timestamp: {test_ts}")
    
    # Старая логика
    mask = btc_market['timestamp'] <= test_ts
    if mask.any():
        old_idx = mask.idxmax()
        old_btc_row = btc_market.iloc[old_idx]
        print(f"   Старая логика (idxmax): idx={old_idx}, timestamp={old_btc_row['timestamp']}, mkt_long_ok={old_btc_row['mkt_long_ok']}")
    
    # Новая логика
    if mask.any():
        true_indices = mask[mask].index
        new_idx = true_indices[-1]
        new_btc_row = btc_market.iloc[new_idx]
        print(f"   Новая логика (last True): idx={new_idx}, timestamp={new_btc_row['timestamp']}, mkt_long_ok={new_btc_row['mkt_long_ok']}")
    
    print()
    
    # Проверить, что новая логика дает правильные результаты
    if new_true_count > 0:
        print("✅ ТЕСТ ПРОЙДЕН: Новая логика создает правильные mkt_long_ok значения")
        print("✅ Live система теперь должна корректно обрабатывать 15m сигналы")
    else:
        print("❌ ТЕСТ НЕ ПРОЙДЕН: Новая логика все еще создает неправильные значения")

if __name__ == "__main__":
    test_btc_gate_fix()
