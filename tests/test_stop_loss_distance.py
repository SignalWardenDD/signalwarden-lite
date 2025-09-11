#!/usr/bin/env python3
"""
Тест расстояния стоп-лоссов по умолчанию
"""

import os
import sys
import yaml
import pandas as pd
import numpy as np
from typing import Dict, List, Any

# Добавляем путь к модулям
sys.path.append('.')

def calculate_atr(df: pd.DataFrame, period: int = 14) -> float:
    """Рассчитать ATR"""
    df['hl'] = df['high'] - df['low']
    df['hc'] = abs(df['high'] - df['close'].shift())
    df['lc'] = abs(df['low'] - df['close'].shift())
    df['tr'] = df[['hl', 'hc', 'lc']].max(axis=1)
    return df['tr'].rolling(window=period).mean().iloc[-1]

def test_stop_loss_distance():
    """Тест расстояния стоп-лоссов по умолчанию"""
    
    print("🛡️ ТЕСТ РАССТОЯНИЯ СТОП-ЛОССОВ ПО УМОЛЧАНИЮ")
    print("=" * 80)
    
    # Загрузить конфигурацию
    with open('signalwarden_lite/config/config_production.yaml', 'r') as f:
        cfg = yaml.safe_load(f)
    
    sl_atr_mult = cfg['risk']['sl_atr_mult']
    margin_usdt = cfg['risk']['margin_usdt']
    leverage = cfg['risk']['leverage']
    
    print("📊 КОНФИГУРАЦИЯ:")
    print(f"   sl_atr_mult: {sl_atr_mult}")
    print(f"   margin_usdt: {margin_usdt} USDT")
    print(f"   leverage: {leverage}x")
    print()
    
    # Тестовые сценарии
    scenarios = [
        {"symbol": "BTCUSDT", "price": 50000.0, "atr_pct": 0.02, "desc": "BTC - 2% ATR"},
        {"symbol": "ETHUSDT", "price": 3000.0, "atr_pct": 0.03, "desc": "ETH - 3% ATR"},
        {"symbol": "ADAUSDT", "price": 0.5, "atr_pct": 0.05, "desc": "ADA - 5% ATR"},
        {"symbol": "DOGEUSDT", "price": 0.08, "atr_pct": 0.08, "desc": "DOGE - 8% ATR"},
        {"symbol": "ENAUSDT", "price": 0.8, "atr_pct": 0.04, "desc": "ENA - 4% ATR"},
    ]
    
    print("🧮 РАСЧЕТ СТОП-ЛОССОВ:")
    print("-" * 80)
    
    for scenario in scenarios:
        symbol = scenario["symbol"]
        price = scenario["price"]
        atr_pct = scenario["atr_pct"]
        desc = scenario["desc"]
        
        # Рассчитать ATR в абсолютных единицах
        atr_absolute = price * atr_pct
        
        # Рассчитать стоп-лосс
        sl_distance = sl_atr_mult * atr_absolute
        sl_price_long = price - sl_distance
        sl_price_short = price + sl_distance
        
        # Рассчитать PnL при срабатывании стоп-лосса
        position_size = margin_usdt  # 21 USDT
        qty = position_size / price
        
        pnl_long = (sl_price_long - price) * qty
        pnl_short = (price - sl_price_short) * qty
        
        print(f"📊 {symbol} ({desc}):")
        print(f"   Price: ${price:.6f}")
        print(f"   ATR: {atr_absolute:.6f} ({atr_pct*100:.1f}%)")
        print(f"   SL Distance: {sl_distance:.6f} ({sl_distance/price*100:.2f}%)")
        print(f"   Long SL: ${sl_price_long:.6f}")
        print(f"   Short SL: ${sl_price_short:.6f}")
        print(f"   Long PnL: {pnl_long:.4f} USDT")
        print(f"   Short PnL: {pnl_short:.4f} USDT")
        print()
    
    # Проверим конкретный случай ENAUSDT
    print("🔍 ДЕТАЛЬНЫЙ АНАЛИЗ ENAUSDT:")
    print("-" * 80)
    
    ena_price = 0.8
    ena_atr_pct = 0.04
    ena_atr = ena_price * ena_atr_pct
    ena_sl_distance = sl_atr_mult * ena_atr
    ena_sl_price = ena_price - ena_sl_distance
    
    position_size = margin_usdt
    qty = position_size / ena_price
    
    pnl_at_sl = (ena_sl_price - ena_price) * qty
    
    print(f"   Entry Price: ${ena_price:.6f}")
    print(f"   ATR: {ena_atr:.6f} ({ena_atr_pct*100:.1f}%)")
    print(f"   SL Distance: {ena_sl_distance:.6f} ({ena_sl_distance/ena_price*100:.2f}%)")
    print(f"   SL Price: ${ena_sl_price:.6f}")
    print(f"   Position Size: {position_size} USDT")
    print(f"   Quantity: {qty:.2f} ENA")
    print(f"   PnL at SL: {pnl_at_sl:.4f} USDT")
    print()
    
    # Проверим, что PnL при стоп-лоссе больше -0.04 USDT
    print("🎯 ПРОВЕРКА ЗАЩИТЫ ОТ УБЫТКОВ:")
    print("-" * 80)
    
    if pnl_at_sl > -0.04:
        print(f"   ✅ PnL при SL ({pnl_at_sl:.4f} USDT) > -0.04 USDT")
        print(f"   ✅ Стоп-лосс защищает от больших убытков")
    else:
        print(f"   ❌ PnL при SL ({pnl_at_sl:.4f} USDT) <= -0.04 USDT")
        print(f"   ❌ Стоп-лосс может привести к большим убыткам")
    
    print()
    
    # Итоговая оценка
    print("🎯 ИТОГОВАЯ ОЦЕНКА:")
    print("-" * 80)
    
    if pnl_at_sl > -0.04:
        print("✅ СТОП-ЛОССЫ НАСТРОЕНЫ ПРАВИЛЬНО:")
        print("   • Расстояние SL достаточное для защиты от убытков")
        print("   • PnL при срабатывании SL больше -0.04 USDT")
        print("   • Система защищена от больших потерь")
    else:
        print("❌ СТОП-ЛОССЫ ТРЕБУЮТ НАСТРОЙКИ:")
        print("   • Расстояние SL слишком маленькое")
        print("   • PnL при срабатывании SL может быть меньше -0.04 USDT")
        print("   • Требуется увеличить sl_atr_mult")
    
    print()
    print("📋 СВОДКА:")
    print(f"   • sl_atr_mult: {sl_atr_mult}")
    print(f"   • Position Size: {margin_usdt} USDT")
    print(f"   • ENA SL Distance: {ena_sl_distance/ena_price*100:.2f}%")
    print(f"   • ENA PnL at SL: {pnl_at_sl:.4f} USDT")

if __name__ == "__main__":
    test_stop_loss_distance()
