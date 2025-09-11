#!/usr/bin/env python3
"""
Тест стоп-лоссов в live системе
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

def test_stop_losses():
    """Тест стоп-лоссов в live системе"""
    
    print("🛡️ ТЕСТ СТОП-ЛОССОВ В LIVE СИСТЕМЕ")
    print("=" * 80)
    
    # Загрузить конфигурацию
    with open('signalwarden_lite/config/config_production.yaml', 'r') as f:
        cfg = yaml.safe_load(f)
    
    print("📊 КОНФИГУРАЦИЯ СТОП-ЛОССОВ:")
    print(f"   sl_atr_mult: {cfg['risk']['sl_atr_mult']}")
    print(f"   sl_order_type: {cfg['risk']['sl_order_type']}")
    print(f"   margin_usdt: {cfg['risk']['margin_usdt']}")
    print(f"   leverage: {cfg['risk']['leverage']}")
    print()
    
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
    
    print(f"🟢 BTC Market Filter: {'BULL' if btc_market.iloc[-1]['mkt_long_ok'] else 'BEAR'}")
    print()
    
    # Проверить конкретные пары
    pairs_to_check = [
        ('ADA_USDT', 'ADA/USDT:USDT'),
        ('PNUT_USDT', 'PNUT/USDT:USDT')
    ]
    
    for symbol, binance_symbol in pairs_to_check:
        print(f"🔍 ТЕСТ СТОП-ЛОССОВ ДЛЯ {symbol}...")
        print("-" * 60)
        
        try:
            # Получить данные 1h
            df_1h = fetch_ohlcv_live_style(exchange, symbol, '1h', 200)
            df_1h = add_indicators(df_1h)
            regime_thresholds = RegimeThresholds(
                ultra_calm=0.8,
                calm=1.2,
                high=2.5
            )
            df_1h = add_regime(df_1h, regime_thresholds)
            
            # Получить данные 15m
            df_15m = fetch_ohlcv_live_style(exchange, symbol, '15m', 400)
            df_15m = add_indicators(df_15m)
            df_15m = add_regime(df_15m, regime_thresholds)
            
            # Создать 15m gate
            gate_15m_data = []
            for ts in df_15m['timestamp'].values:
                mask = btc_market['timestamp'] <= ts
                if mask.any():
                    true_indices = mask[mask].index
                    idx = true_indices[-1]
                    gate_15m_data.append({
                        'timestamp': ts,
                        'mkt_long_ok': btc_market.iloc[idx]['mkt_long_ok'],
                        'mkt_short_ok': btc_market.iloc[idx]['mkt_short_ok']
                    })
                else:
                    gate_15m_data.append({'timestamp': ts, 'mkt_long_ok': False, 'mkt_short_ok': False})
            gate_15m = pd.DataFrame(gate_15m_data)
            
            # Генерировать сигналы
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
            
            sig_1h = generate_signals(df_1h, signal_params, btc_market)
            sig_15m = generate_signals(df_15m, signal_params, gate_15m)
            
            latest_1h = sig_1h.iloc[-1]
            latest_15m = sig_15m.iloc[-1]
            
            print(f"   📊 1h данные:")
            print(f"      Regime: {latest_1h['regime']}")
            print(f"      ATR: {latest_1h['atr']:.6f}")
            print(f"      Price: {latest_1h['close']:.6f}")
            print(f"      Allow Long: {latest_1h.get('allow_long', False)}")
            print(f"      sig_long_breakout: {latest_1h.get('sig_long_breakout', False)}")
            
            print(f"   📊 15m данные:")
            print(f"      Regime: {latest_15m['regime']}")
            print(f"      ATR: {latest_15m['atr']:.6f}")
            print(f"      Price: {latest_15m['close']:.6f}")
            print(f"      Allow Long: {latest_15m.get('allow_long', False)}")
            print(f"      sig_long_tc: {latest_15m.get('sig_long_tc', False)}")
            print(f"      sig_long_sq: {latest_15m.get('sig_long_sq', False)}")
            
            # Проверить стоп-лоссы для разных сигналов
            print(f"   🛡️ РАСЧЕТ СТОП-ЛОССОВ:")
            
            # 1h breakout сигнал
            if latest_1h.get('sig_long_breakout', False) and latest_1h.get('allow_long', False):
                entry = latest_1h['long_entry_final']
                atr = latest_1h['atr']
                sl_price = entry - (cfg['risk']['sl_atr_mult'] * atr)
                sl_distance = entry - sl_price
                sl_percent = (sl_distance / entry) * 100
                
                print(f"      ✅ 1h LONG breakout:")
                print(f"         Entry: {entry:.6f}")
                print(f"         ATR: {atr:.6f}")
                print(f"         SL Price: {sl_price:.6f}")
                print(f"         SL Distance: {sl_distance:.6f} ({sl_percent:.2f}%)")
                print(f"         SL Multiplier: {cfg['risk']['sl_atr_mult']}x ATR")
            
            # 15m LTF сигналы
            ltf_setups = ['tc', 'sq']
            for setup in ltf_setups:
                if (latest_15m.get(f'sig_long_{setup}', False) and 
                    latest_15m.get('allow_long', False)):
                    entry = latest_15m['long_entry_final']
                    atr = latest_15m['atr']
                    sl_price = entry - (cfg['risk']['sl_atr_mult'] * atr)
                    sl_distance = entry - sl_price
                    sl_percent = (sl_distance / entry) * 100
                    
                    print(f"      ✅ 15m LONG {setup}:")
                    print(f"         Entry: {entry:.6f}")
                    print(f"         ATR: {atr:.6f}")
                    print(f"         SL Price: {sl_price:.6f}")
                    print(f"         SL Distance: {sl_distance:.6f} ({sl_percent:.2f}%)")
                    print(f"         SL Multiplier: {cfg['risk']['sl_atr_mult']}x ATR")
                    break
            
            # Проверить, есть ли сигналы
            signals_found = []
            if latest_1h.get('sig_long_breakout', False) and latest_1h.get('allow_long', False):
                signals_found.append("1h LONG breakout")
            for setup in ltf_setups:
                if (latest_15m.get(f'sig_long_{setup}', False) and 
                    latest_15m.get('allow_long', False)):
                    signals_found.append(f"15m LONG {setup}")
                    break
            
            if not signals_found:
                print(f"      ❌ НЕТ СИГНАЛОВ для тестирования стоп-лоссов")
            else:
                print(f"      🎯 НАЙДЕНО СИГНАЛОВ: {len(signals_found)}")
                for sig in signals_found:
                    print(f"         - {sig}")
            
            print()
            
        except Exception as e:
            print(f"❌ Ошибка тестирования {symbol}: {e}")
            import traceback
            traceback.print_exc()
            print()
    
    # Проверить конфигурацию стоп-лоссов
    print("🔍 АНАЛИЗ КОНФИГУРАЦИИ СТОП-ЛОССОВ:")
    print("-" * 60)
    
    sl_atr_mult = cfg['risk']['sl_atr_mult']
    sl_order_type = cfg['risk']['sl_order_type']
    
    print(f"📊 Параметры стоп-лоссов:")
    print(f"   sl_atr_mult: {sl_atr_mult}")
    print(f"   sl_order_type: {sl_order_type}")
    
    if sl_atr_mult == 2.5:
        print(f"   ✅ sl_atr_mult = 2.5 - консервативное расстояние (хорошо для live)")
    elif sl_atr_mult < 2.0:
        print(f"   ⚠️ sl_atr_mult = {sl_atr_mult} - может быть слишком близко (риск ложных срабатываний)")
    elif sl_atr_mult > 3.0:
        print(f"   ⚠️ sl_atr_mult = {sl_atr_mult} - может быть слишком далеко (большие потери)")
    else:
        print(f"   ✅ sl_atr_mult = {sl_atr_mult} - разумное расстояние")
    
    if sl_order_type == 'stop_market':
        print(f"   ✅ sl_order_type = 'stop_market' - маркет стоп-лосс (гарантированное исполнение)")
    elif sl_order_type == 'stop':
        print(f"   ⚠️ sl_order_type = 'stop' - лимитный стоп-лосс (может не исполниться)")
    else:
        print(f"   ❌ sl_order_type = '{sl_order_type}' - неизвестный тип")
    
    print()
    
    # Проверить расчет позиции
    print("🔍 АНАЛИЗ РАСЧЕТА ПОЗИЦИИ:")
    print("-" * 60)
    
    margin_usdt = cfg['risk']['margin_usdt']
    leverage = cfg['risk']['leverage']
    notional_value = margin_usdt * leverage
    
    print(f"📊 Параметры позиции:")
    print(f"   margin_usdt: {margin_usdt} USDT")
    print(f"   leverage: {leverage}x")
    print(f"   notional_value: {notional_value} USDT")
    
    if margin_usdt == 21:
        print(f"   ✅ margin_usdt = 21 USDT - консервативный размер позиции")
    elif margin_usdt < 10:
        print(f"   ⚠️ margin_usdt = {margin_usdt} USDT - очень маленькая позиция")
    elif margin_usdt > 50:
        print(f"   ⚠️ margin_usdt = {margin_usdt} USDT - большая позиция (высокий риск)")
    else:
        print(f"   ✅ margin_usdt = {margin_usdt} USDT - разумный размер позиции")
    
    if leverage == 5:
        print(f"   ✅ leverage = 5x - умеренное плечо (хорошо для live)")
    elif leverage < 3:
        print(f"   ⚠️ leverage = {leverage}x - низкое плечо (малая прибыль)")
    elif leverage > 10:
        print(f"   ⚠️ leverage = {leverage}x - высокое плечо (высокий риск)")
    else:
        print(f"   ✅ leverage = {leverage}x - разумное плечо")
    
    print()
    
    # Итоговая оценка
    print("🎯 ИТОГОВАЯ ОЦЕНКА СТОП-ЛОССОВ:")
    print("-" * 60)
    
    issues = []
    if sl_atr_mult < 2.0 or sl_atr_mult > 3.0:
        issues.append(f"sl_atr_mult = {sl_atr_mult} (рекомендуется 2.0-3.0)")
    if sl_order_type != 'stop_market':
        issues.append(f"sl_order_type = '{sl_order_type}' (рекомендуется 'stop_market')")
    if margin_usdt < 10 or margin_usdt > 50:
        issues.append(f"margin_usdt = {margin_usdt} (рекомендуется 10-50)")
    if leverage < 3 or leverage > 10:
        issues.append(f"leverage = {leverage} (рекомендуется 3-10)")
    
    if not issues:
        print("✅ ВСЕ ПАРАМЕТРЫ СТОП-ЛОССОВ НАСТРОЕНЫ ПРАВИЛЬНО!")
        print("✅ Система готова к безопасной торговле")
    else:
        print("⚠️ НАЙДЕНЫ ПРОБЛЕМЫ В КОНФИГУРАЦИИ:")
        for issue in issues:
            print(f"   - {issue}")
        print("⚠️ Рекомендуется исправить перед live торговлей")

if __name__ == "__main__":
    test_stop_losses()
