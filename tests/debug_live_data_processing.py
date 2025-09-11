#!/usr/bin/env python3
"""
Отладка обработки данных в live системе - точная имитация
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

def prepare_data_live_style(df: pd.DataFrame, btc_gate: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """Prepare data exactly like live system"""
    # Add indicators
    df = add_indicators(df)
    
    # Add regime
    regime_thresholds = RegimeThresholds(
        ultra_calm=0.5,
        calm=1.0,
        high=2.0
    )
    df = add_regime(df, regime_thresholds)
    
    # Generate signals
    signal_params = SignalParams(
        setup_breakout=True,
        setup_inside=True,
        setup_trend_cont=True,
        setup_squeeze=True,
        lookback_calm=24,
        lookback_normal=16,
        lookback_high=10,
        long_cushion_calm=0.30,
        long_cushion_normal=0.12,
        long_cushion_high=0.08,
        short_cushion_calm=0.34,
        short_cushion_normal=0.16,
        short_cushion_high=0.12,
        ltf_thinbar_k=0.25
    )
    
    if btc_gate is not None:
        signals = generate_signals(df, signal_params, btc_gate)
    else:
        # Create dummy BTC gate
        dummy_btc = pd.DataFrame({
            'timestamp': df['timestamp'],
            'mkt_long_ok': [True] * len(df),
            'mkt_short_ok': [False] * len(df)
        })
        signals = generate_signals(df, signal_params, dummy_btc)
    
    return signals

def debug_live_data_processing():
    """Отладка обработки данных в live системе"""
    
    print("🔍 ОТЛАДКА ОБРАБОТКИ ДАННЫХ В LIVE СИСТЕМЕ")
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
    latest_btc = btc_market.iloc[-1]
    
    print(f"🟢 BTC Market Filter: {'BULL' if latest_btc['mkt_long_ok'] else 'BEAR'}")
    print(f"   Longs: {latest_btc['mkt_long_ok']}, Shorts: {latest_btc['mkt_short_ok']}")
    print()
    
    # Проверить конкретные пары
    pairs_to_check = [
        ('ADA_USDT', 'ADA/USDT:USDT'),
        ('PNUT_USDT', 'PNUT/USDT:USDT')
    ]
    
    for symbol, binance_symbol in pairs_to_check:
        print(f"🔍 ДЕТАЛЬНАЯ ПРОВЕРКА {symbol}...")
        print("-" * 60)
        
        try:
            # Получить данные 1h как в live системе
            print("   📊 Получение 1h данных...")
            df_1h = fetch_ohlcv_live_style(exchange, symbol, '1h', 200)
            print(f"   📊 1h данных получено: {len(df_1h)} баров")
            print(f"   📊 Последний timestamp: {df_1h.iloc[-1]['timestamp']}")
            print(f"   📊 Последняя цена: {df_1h.iloc[-1]['close']}")
            
            # Подготовить 1h данные
            sig_1h = prepare_data_live_style(df_1h, btc_market)
            latest_1h = sig_1h.iloc[-1]
            
            print(f"   📊 1h после обработки:")
            print(f"      Regime: {latest_1h['regime']}")
            print(f"      RSI: {latest_1h['rsi']:.1f}")
            print(f"      NATR: {latest_1h['natr']:.1f}%")
            print(f"      Allow Long: {latest_1h.get('allow_long', False)}")
            print(f"      Allow Short: {latest_1h.get('allow_short', False)}")
            print(f"      sig_long_breakout: {latest_1h.get('sig_long_breakout', False)}")
            print(f"      sig_short_breakout: {latest_1h.get('sig_short_breakout', False)}")
            
            # Получить данные 15m как в live системе
            print("   📊 Получение 15m данных...")
            df_15m = fetch_ohlcv_live_style(exchange, symbol, '15m', 400)
            print(f"   📊 15m данных получено: {len(df_15m)} баров")
            print(f"   📊 Последний timestamp: {df_15m.iloc[-1]['timestamp']}")
            print(f"   📊 Последняя цена: {df_15m.iloc[-1]['close']}")
            
            # Создать 15m gate как в live системе (ИСПРАВЛЕННАЯ ЛОГИКА)
            print("   📊 Создание 15m gate...")
            gate_15m_data = []
            for ts in df_15m['timestamp'].values:
                mask = btc_market['timestamp'] <= ts
                if mask.any():
                    # ИСПРАВЛЕНИЕ: Найти последний True индекс вместо idxmax()
                    true_indices = mask[mask].index
                    idx = true_indices[-1]  # Последний True индекс
                    gate_15m_data.append({
                        'timestamp': ts,
                        'mkt_long_ok': btc_market.iloc[idx]['mkt_long_ok'],
                        'mkt_short_ok': btc_market.iloc[idx]['mkt_short_ok']
                    })
                else:
                    gate_15m_data.append({'timestamp': ts, 'mkt_long_ok': False, 'mkt_short_ok': False})
            gate_15m = pd.DataFrame(gate_15m_data)
            print(f"   📊 15m gate создан: {len(gate_15m)} записей")
            
            # Подготовить 15m данные
            sig_15m = prepare_data_live_style(df_15m, gate_15m)
            latest_15m = sig_15m.iloc[-1]
            
            print(f"   📊 15m после обработки:")
            print(f"      Regime: {latest_15m['regime']}")
            print(f"      RSI: {latest_15m['rsi']:.1f}")
            print(f"      NATR: {latest_15m['natr']:.1f}%")
            print(f"      Allow Long: {latest_15m.get('allow_long', False)}")
            print(f"      Allow Short: {latest_15m.get('allow_short', False)}")
            print(f"      sig_long_inside: {latest_15m.get('sig_long_inside', False)}")
            print(f"      sig_long_tc: {latest_15m.get('sig_long_tc', False)}")
            print(f"      sig_long_sq: {latest_15m.get('sig_long_sq', False)}")
            print(f"      sig_short_inside: {latest_15m.get('sig_short_inside', False)}")
            print(f"      sig_short_tc: {latest_15m.get('sig_short_tc', False)}")
            print(f"      sig_short_sq: {latest_15m.get('sig_short_sq', False)}")
            
            # Проверить условия входа точно как в live системе
            print(f"   🎯 ПРОВЕРКА УСЛОВИЙ ВХОДА (как в live системе):")
            
            signals_found = []
            
            # 1h breakout signals
            if latest_1h.get('sig_long_breakout', False) and latest_1h.get('allow_long', False):
                signals_found.append("1h LONG breakout")
                print(f"      ✅ 1h LONG breakout сигнал!")
                if 'long_entry_final' in latest_1h:
                    print(f"         Entry: {latest_1h['long_entry_final']:.6f}")
                
            if latest_1h.get('sig_short_breakout', False) and latest_1h.get('allow_short', False):
                signals_found.append("1h SHORT breakout")
                print(f"      ✅ 1h SHORT breakout сигнал!")
                if 'short_entry_final' in latest_1h:
                    print(f"         Entry: {latest_1h['short_entry_final']:.6f}")
            
            # 15m LTF signals (точно как в live коде)
            ltf_setups = ['inside', 'tc', 'sq']
            for setup in ltf_setups:
                # Long signals
                if (latest_15m.get(f'sig_long_{setup}', False) and 
                    latest_15m.get('allow_long', False)):
                    signals_found.append(f"15m LONG {setup}")
                    print(f"      ✅ 15m LONG {setup} сигнал!")
                    if 'long_entry_final' in latest_15m:
                        print(f"         Entry: {latest_15m['long_entry_final']:.6f}")
                        print(f"         ATR: {latest_15m['atr']:.6f}")
                        print(f"         Regime: {latest_15m['regime']}")
                    break  # Only one signal per side (как в live коде)
                
                # Short signals  
                if (latest_15m.get(f'sig_short_{setup}', False) and 
                    latest_15m.get('allow_short', False)):
                    signals_found.append(f"15m SHORT {setup}")
                    print(f"      ✅ 15m SHORT {setup} сигнал!")
                    if 'short_entry_final' in latest_15m:
                        print(f"         Entry: {latest_15m['short_entry_final']:.6f}")
                        print(f"         ATR: {latest_15m['atr']:.6f}")
                        print(f"         Regime: {latest_15m['regime']}")
                    break  # Only one signal per side (как в live коде)
            
            if not signals_found:
                print(f"      ❌ НЕТ СИГНАЛОВ для входа")
                print(f"      Причины:")
                print(f"        - 1h allow_long: {latest_1h.get('allow_long', False)}, sig_long_breakout: {latest_1h.get('sig_long_breakout', False)}")
                print(f"        - 15m allow_long: {latest_15m.get('allow_long', False)}")
                print(f"        - 15m сигналы: inside={latest_15m.get('sig_long_inside', False)}, tc={latest_15m.get('sig_long_tc', False)}, sq={latest_15m.get('sig_long_sq', False)}")
            else:
                print(f"      🎯 НАЙДЕНО СИГНАЛОВ: {len(signals_found)}")
                for sig in signals_found:
                    print(f"         - {sig}")
            
            print()
            
        except Exception as e:
            print(f"❌ Ошибка обработки {symbol}: {e}")
            import traceback
            traceback.print_exc()
            print()

if __name__ == "__main__":
    debug_live_data_processing()
