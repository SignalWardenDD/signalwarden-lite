#!/usr/bin/env python3
"""
Тест выполнения сигналов - имитация live системы
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
        
        return df
        
    except Exception as e:
        print(f"❌ Ошибка получения данных для {symbol}: {e}")
        return None

def simulate_live_execution():
    """Имитация выполнения сигналов как в live системе"""
    
    print("🎯 ТЕСТ ВЫПОЛНЕНИЯ СИГНАЛОВ")
    print("=" * 80)
    
    # Загрузить конфигурацию
    with open('signalwarden_lite/config/config_production.yaml', 'r') as f:
        cfg = yaml.safe_load(f)
    
    # Параметры
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
    
    # Получить BTC данные
    print("📊 Получение BTC данных...")
    btc_data = fetch_binance_data('BTC/USDT:USDT', '1h', 200)
    if btc_data is None:
        print("❌ Не удалось получить BTC данные")
        return
    
    btc_data = add_indicators(btc_data, cfg['market_filter']['ema_fast'], cfg['market_filter']['ema_slow'])
    btc_market = compute_market_bias(btc_data, cfg['market_filter']['ema_fast'], cfg['market_filter']['ema_slow'])
    latest_btc = btc_market.iloc[-1]
    
    print(f"🟢 BTC Market Filter: {'BULL' if latest_btc['mkt_long_ok'] else 'BEAR'}")
    print()
    
    # Проверить пары с сигналами
    pairs_to_check = [
        ('ADA_USDT', 'ADA/USDT:USDT'),
        ('PNUT_USDT', 'PNUT/USDT:USDT')
    ]
    
    total_signals = 0
    
    for symbol, binance_symbol in pairs_to_check:
        print(f"🎯 ОБРАБОТКА {symbol}...")
        print("-" * 60)
        
        try:
            # Получить данные как в live системе
            df_1h = fetch_binance_data(binance_symbol, '1h', 200)
            if df_1h is None:
                continue
                
            df_15m = fetch_binance_data(binance_symbol, '15m', 200)
            if df_15m is None:
                continue
            
            # Подготовить данные
            df_1h = add_indicators(df_1h)
            df_15m = add_indicators(df_15m)
            df_1h = add_regime(df_1h, regime_thresholds)
            df_15m = add_regime(df_15m, regime_thresholds)
            
            # Создать 15m gate
            gate_15m_data = []
            for _, row_15m in df_15m.iterrows():
                ts_15m = row_15m['timestamp']
                closest_idx = None
                min_diff = float('inf')
                for idx, btc_row in btc_market.iterrows():
                    diff = abs((ts_15m - btc_row['timestamp']).total_seconds())
                    if diff < min_diff:
                        min_diff = diff
                        closest_idx = idx
                
                if closest_idx is not None and min_diff < 3600:
                    gate_15m_data.append({
                        'timestamp': ts_15m,
                        'mkt_long_ok': btc_market.iloc[closest_idx]['mkt_long_ok'],
                        'mkt_short_ok': btc_market.iloc[closest_idx]['mkt_short_ok']
                    })
                else:
                    gate_15m_data.append({'timestamp': ts_15m, 'mkt_long_ok': False, 'mkt_short_ok': False})
            
            gate_15m = pd.DataFrame(gate_15m_data)
            
            # Генерировать сигналы
            signals_1h = generate_signals(df_1h, signal_params, btc_market)
            signals_15m = generate_signals(df_15m, signal_params, gate_15m)
            
            latest_1h = signals_1h.iloc[-1]
            latest_15m = signals_15m.iloc[-1]
            
            # Проверить сигналы как в live системе
            signals_found = []
            
            # 1h breakout signals
            if latest_1h.get('sig_long_breakout', False) and latest_1h.get('allow_long', False):
                signals_found.append({
                    'timeframe': '1h',
                    'side': 'LONG',
                    'setup': 'breakout',
                    'entry': float(latest_1h['long_entry_final']),
                    'reason': latest_1h.get('long_reason', 'breakout'),
                    'atr': float(latest_1h['atr']),
                    'regime': latest_1h.get('regime', 'unknown'),
                    'confidence': 'HIGH'
                })
                
            if latest_1h.get('sig_short_breakout', False) and latest_1h.get('allow_short', False):
                signals_found.append({
                    'timeframe': '1h',
                    'side': 'SHORT',
                    'setup': 'breakout',
                    'entry': float(latest_1h['short_entry_final']),
                    'reason': latest_1h.get('short_reason', 'breakout'),
                    'atr': float(latest_1h['atr']),
                    'regime': latest_1h.get('regime', 'unknown'),
                    'confidence': 'HIGH'
                })
            
            # 15m LTF signals
            ltf_setups = ['inside', 'tc', 'sq']
            for setup in ltf_setups:
                # Long signals
                if (latest_15m.get(f'sig_long_{setup}', False) and 
                    latest_15m.get('allow_long', False)):
                    signals_found.append({
                        'timeframe': '15m',
                        'side': 'LONG',
                        'setup': setup,
                        'entry': float(latest_15m['long_entry_final']),
                        'reason': latest_15m.get('long_reason', setup),
                        'atr': float(latest_15m['atr']),
                        'regime': latest_15m.get('regime', 'unknown'),
                        'confidence': 'MEDIUM'
                    })
                    break  # Only one signal per side
                
                # Short signals  
                if (latest_15m.get(f'sig_short_{setup}', False) and 
                    latest_15m.get('allow_short', False)):
                    signals_found.append({
                        'timeframe': '15m',
                        'side': 'SHORT',
                        'setup': setup,
                        'entry': float(latest_15m['short_entry_final']),
                        'reason': latest_15m.get('short_reason', setup),
                        'atr': float(latest_15m['atr']),
                        'regime': latest_15m.get('regime', 'unknown'),
                        'confidence': 'MEDIUM'
                    })
                    break  # Only one signal per side
            
            # Показать результаты
            if signals_found:
                print(f"✅ НАЙДЕНО СИГНАЛОВ: {len(signals_found)}")
                for signal in signals_found:
                    total_signals += 1
                    print(f"   🎯 {signal['confidence']} {signal['timeframe']} {signal['side']} {signal['setup']} @ {signal['entry']:.6f}")
                    print(f"      ATR: {signal['atr']:.6f}, Regime: {signal['regime']}")
                    
                    # Имитация выполнения
                    print(f"   📈 ИМИТАЦИЯ ВЫПОЛНЕНИЯ:")
                    
                    # Рассчитать параметры позиции
                    margin_usdt = cfg['risk']['margin_usdt']
                    leverage = cfg['risk']['leverage']
                    sl_atr_mult = cfg['risk']['sl_atr_mult']
                    
                    entry_price = signal['entry']
                    atr = signal['atr']
                    position_value_usdt = margin_usdt
                    qty = position_value_usdt / entry_price
                    
                    if signal['side'] == 'LONG':
                        sl_price = entry_price - (sl_atr_mult * atr)
                    else:
                        sl_price = entry_price + (sl_atr_mult * atr)
                    
                    print(f"      Entry: {entry_price:.6f}")
                    print(f"      Quantity: {qty:.6f}")
                    print(f"      Stop Loss: {sl_price:.6f}")
                    print(f"      Position Value: {position_value_usdt} USDT")
                    print(f"      Actual Margin: {position_value_usdt/leverage:.2f} USDT")
                    
                    print(f"   ✅ СИГНАЛ ГОТОВ К ВЫПОЛНЕНИЮ!")
            else:
                print(f"❌ Нет сигналов для {symbol}")
                print(f"   1h: allow_long={latest_1h.get('allow_long', False)}, sig_long_breakout={latest_1h.get('sig_long_breakout', False)}")
                print(f"   15m: allow_long={latest_15m.get('allow_long', False)}")
                print(f"   15m сигналы: inside={latest_15m.get('sig_long_inside', False)}, tc={latest_15m.get('sig_long_tc', False)}, sq={latest_15m.get('sig_long_sq', False)}")
            
            print()
            
        except Exception as e:
            print(f"❌ Ошибка обработки {symbol}: {e}")
            print()
    
    print("=" * 80)
    print(f"🎯 ИТОГО НАЙДЕНО СИГНАЛОВ: {total_signals}")
    
    if total_signals > 0:
        print("✅ СИСТЕМА ДОЛЖНА ВЫПОЛНЯТЬ СИГНАЛЫ!")
        print("🚨 Если live система не выполняет сигналы, проверьте:")
        print("   1. Режим paper_mode в live системе")
        print("   2. Логи live системы на наличие ошибок")
        print("   3. Активные позиции в trading_state")
        print("   4. Баланс USDT на бирже")
    else:
        print("❌ Нет сигналов для выполнения")

if __name__ == "__main__":
    load_dotenv()
    simulate_live_execution()
