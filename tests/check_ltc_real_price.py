#!/usr/bin/env python3
"""
Проверка реальной цены LTC и обновления Peak PnL
"""

import os
import sys
import json
import ccxt
from dotenv import load_dotenv

# Добавляем путь к модулям
sys.path.append('.')
load_dotenv()

def check_ltc_real_price():
    """Проверка реальной цены LTC"""
    
    print("📊 ПРОВЕРКА РЕАЛЬНОЙ ЦЕНЫ LTC")
    print("=" * 80)
    
    # Загрузить состояние системы
    try:
        with open('trading_state_v1_6_TXB.json', 'r') as f:
            state = json.load(f)
    except Exception as e:
        print(f"❌ Не удалось прочитать состояние системы: {e}")
        return
    
    # Подключиться к бирже
    try:
        api_key = os.getenv('BINANCE_API_KEY')
        secret = os.getenv('BINANCE_SECRET')
        
        exchange = ccxt.binanceusdm({
            'apiKey': api_key,
            'secret': secret,
            'enableRateLimit': True,
            'timeout': 30000,
            'options': {'defaultType': 'future'}
        })
        
        # Live mode
        exchange.set_sandbox_mode(False)
        exchange.load_markets()
        
        print("✅ Подключение к Binance установлено (LIVE режим)")
    except Exception as e:
        print(f"❌ Не удалось подключиться к Binance: {e}")
        return
    
    # Найти позицию LTC
    ltc_data = state.get('symbols', {}).get('LTC_USDT', {})
    active_pos = ltc_data.get('active_position')
    
    if not active_pos:
        print("❌ Позиция LTC не найдена!")
        return
    
    entry = active_pos.get('entry', 0)
    side = active_pos.get('side', 'UNKNOWN')
    qty = active_pos.get('qty', 0)
    sl_current = active_pos.get('sl_current', 0)
    peak_pnl = active_pos.get('peak_pnl_usdt', 0)
    
    print(f"📊 ПОЗИЦИЯ LTC ИЗ СИСТЕМЫ:")
    print(f"   Entry: ${entry:.6f}")
    print(f"   Side: {side}")
    print(f"   Quantity: {qty:.6f}")
    print(f"   SL Current: ${sl_current:.6f}")
    print(f"   Peak PnL: {peak_pnl:.4f} USDT")
    print()
    
    try:
        # Получить текущую цену
        ticker = exchange.fetch_ticker('LTC/USDT')
        current_price = float(ticker['last'])
        
        print(f"💰 РЕАЛЬНАЯ ЦЕНА LTC: ${current_price:.6f}")
        print()
        
        # Рассчитать текущий PnL
        if side == 'LONG':
            current_pnl = (current_price - entry) * qty
        else:
            current_pnl = (entry - current_price) * qty
        
        print(f"🧮 РАСЧЕТ PNL:")
        print(f"   Current Price: ${current_price:.6f}")
        print(f"   Entry Price: ${entry:.6f}")
        print(f"   Price Diff: ${current_price - entry:.6f}")
        print(f"   Quantity: {qty:.6f}")
        print(f"   Current PnL: {current_pnl:.4f} USDT")
        print()
        
        # Проверить, должен ли обновиться Peak PnL
        if current_pnl > peak_pnl:
            print(f"🚨 ПРОБЛЕМА ОБНАРУЖЕНА:")
            print(f"   Current PnL ({current_pnl:.4f}) > Peak PnL ({peak_pnl:.4f})")
            print(f"   Peak PnL ДОЛЖЕН ОБНОВИТЬСЯ!")
            print()
            
            print(f"❌ СИСТЕМА НЕ ОБНОВЛЯЕТ PEAK PNL!")
            print(f"   Это означает, что трейлинг НЕ РАБОТАЕТ")
            print(f"   Нужно найти и исправить проблему в коде")
        else:
            print(f"✅ Peak PnL корректен (не нужно обновлять)")
        
        print()
        
        # Проверить активацию трейлинга
        activate_threshold = 0.10  # из конфига
        
        if current_pnl >= activate_threshold:
            print(f"✅ ТРЕЙЛИНГ ДОЛЖЕН БЫТЬ АКТИВЕН:")
            print(f"   Current PnL ({current_pnl:.4f}) >= Threshold ({activate_threshold})")
            print()
            
            # Определить уровень
            if current_pnl >= 0.40:
                level = 4
                keep_pct = 0.80
                level_threshold = 0.40
            elif current_pnl >= 0.30:
                level = 3
                keep_pct = 0.70
                level_threshold = 0.30
            elif current_pnl >= 0.20:
                level = 2
                keep_pct = 0.60
                level_threshold = 0.20
            elif current_pnl >= 0.10:
                level = 1
                keep_pct = 0.50
                level_threshold = 0.10
            
            target_profit = level_threshold * keep_pct
            
            print(f"📊 ПРАВИЛЬНЫЙ ТРЕЙЛИНГ:")
            print(f"   Уровень: {level}")
            print(f"   Сохранить: {keep_pct*100}% от {level_threshold} USDT")
            print(f"   Целевая прибыль: {target_profit:.4f} USDT")
            
            # Правильный SL
            correct_sl = entry + (target_profit / qty)
            print(f"   Правильный SL: ${correct_sl:.6f}")
            print(f"   Текущий SL: ${sl_current:.6f}")
            
            if correct_sl > sl_current:
                improvement = correct_sl - sl_current
                print(f"   🚨 SL НУЖНО УЛУЧШИТЬ на ${improvement:.6f}!")
            else:
                print(f"   ✅ SL корректен")
        else:
            print(f"❌ ТРЕЙЛИНГ НЕ АКТИВЕН:")
            print(f"   Current PnL ({current_pnl:.4f}) < Threshold ({activate_threshold})")
        
        print()
        print("🔍 ДИАГНОСТИКА ПРОБЛЕМЫ:")
        print("-" * 60)
        
        if current_pnl > peak_pnl:
            print("❌ ПРОБЛЕМА: Peak PnL не обновляется!")
            print("   ВОЗМОЖНЫЕ ПРИЧИНЫ:")
            print("   1. Трейлинг поток не работает")
            print("   2. Ошибка в функции update_trailing_stops")
            print("   3. Проблема с получением цен с биржи")
            print("   4. Ошибка в функции update_trailing_pnl_based")
            print("   5. Peak PnL не сохраняется в JSON файл")
        
        if current_pnl >= activate_threshold and sl_current == active_pos.get('sl_initial', 0):
            print("❌ ПРОБЛЕМА: SL не обновляется трейлингом!")
            print("   ВОЗМОЖНЫЕ ПРИЧИНЫ:")
            print("   1. update_sliding_stop_loss не вызывается")
            print("   2. Ошибка при создании ордеров на бирже")
            print("   3. Конфликт между разными системами SL")
        
    except Exception as e:
        print(f"❌ Ошибка при получении данных с биржи: {e}")

if __name__ == "__main__":
    check_ltc_real_price()
