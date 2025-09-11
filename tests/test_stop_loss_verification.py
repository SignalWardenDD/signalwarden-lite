#!/usr/bin/env python3
"""
Тест проверки правильности установки стоп-лоссов на Binance
"""

import os
import sys
import yaml
from typing import Dict, List, Any

# Добавляем путь к модулям
sys.path.append('.')

def test_stop_loss_verification():
    """Тест проверки стоп-лоссов"""
    
    print("🛡️ ПРОВЕРКА ПРАВИЛЬНОСТИ УСТАНОВКИ СТОП-ЛОССОВ")
    print("=" * 80)
    
    # Загрузить конфигурацию
    with open('signalwarden_lite/config/config_production.yaml', 'r') as f:
        cfg = yaml.safe_load(f)
    
    sl_atr_mult = cfg['risk']['sl_atr_mult']
    margin_usdt = cfg['risk']['margin_usdt']
    leverage = cfg['risk']['leverage']
    sl_order_type = cfg['risk']['sl_order_type']
    
    print("📊 КОНФИГУРАЦИЯ СТОП-ЛОССОВ:")
    print(f"   sl_atr_mult: {sl_atr_mult}")
    print(f"   margin_usdt: {margin_usdt} USDT")
    print(f"   leverage: {leverage}x")
    print(f"   sl_order_type: {sl_order_type}")
    print()
    
    # Данные позиций из скриншота
    positions = [
        {"symbol": "HBARUSDT", "entry": 0.23555, "current": 0.23544, "pnl": -0.12, "roi": -3.03},
        {"symbol": "WIFUSDT", "entry": 0.8954475, "current": 0.8950000, "pnl": -0.01, "roi": -0.27},
        {"symbol": "ENAUSDT", "entry": 0.8132064, "current": 0.8128000, "pnl": -0.20, "roi": -5.02},
        {"symbol": "PNUTUSDT", "entry": 0.2376987, "current": 0.2375800, "pnl": -0.19, "roi": -4.60},
    ]
    
    print("🔍 АНАЛИЗ ТЕКУЩИХ ПОЗИЦИЙ:")
    print("-" * 80)
    
    for pos in positions:
        symbol = pos["symbol"]
        entry = pos["entry"]
        current = pos["current"]
        pnl = pos["pnl"]
        roi = pos["roi"]
        
        # Рассчитываем количество
        qty = margin_usdt / entry
        
        # Проверяем расчет PnL
        calculated_pnl = (current - entry) * qty
        
        print(f"📊 {symbol}:")
        print(f"   Entry: ${entry:.6f}")
        print(f"   Current: ${current:.6f}")
        print(f"   Quantity: {qty:.2f}")
        print(f"   Reported PnL: {pnl:.2f} USDT")
        print(f"   Calculated PnL: {calculated_pnl:.4f} USDT")
        print(f"   ROI: {roi:.2f}%")
        
        # Рассчитываем ожидаемый стоп-лосс
        # Предполагаем ATR = 2-5% от цены
        for atr_pct in [0.02, 0.03, 0.04, 0.05]:
            atr = entry * atr_pct
            expected_sl = entry - (sl_atr_mult * atr)
            sl_distance_pct = (entry - expected_sl) / entry * 100
            
            # PnL при срабатывании SL
            pnl_at_sl = (expected_sl - entry) * qty
            
            print(f"   ATR {atr_pct*100:.0f}%: SL ${expected_sl:.6f} ({sl_distance_pct:.1f}%), PnL: {pnl_at_sl:.2f} USDT")
        
        # Проверяем, не сработал ли уже SL
        max_expected_sl_distance = 0.15  # 15% максимум
        current_loss_pct = abs(roi)
        
        if current_loss_pct > max_expected_sl_distance * 100:
            print(f"   ❌ ПРОБЛЕМА: Убыток {current_loss_pct:.1f}% больше ожидаемого SL!")
        elif current_loss_pct > 10:
            print(f"   ⚠️ ВНИМАНИЕ: Убыток {current_loss_pct:.1f}% близок к SL")
        else:
            print(f"   ✅ Убыток {current_loss_pct:.1f}% в пределах нормы")
        
        print()
    
    # Проверим трейлинг стоп-лоссы
    print("🔍 ПРОВЕРКА ТРЕЙЛИНГ СТОП-ЛОССОВ:")
    print("-" * 80)
    
    trailing_cfg = cfg['trailing']
    activate_pnl = trailing_cfg['activate_pnl_usdt']
    
    print(f"   Активация трейлинга: {activate_pnl} USDT")
    
    for pos in positions:
        symbol = pos["symbol"]
        pnl = pos["pnl"]
        
        print(f"   {symbol}: PnL {pnl:.2f} USDT", end="")
        
        if pnl >= activate_pnl:
            print(f" -> ✅ Трейлинг активен")
        elif pnl > 0:
            print(f" -> ⏳ Близко к активации ({activate_pnl} USDT)")
        else:
            print(f" -> ❌ В убытке, трейлинг неактивен")
    
    print()
    
    # Проверим правильность типа стоп-ордеров
    print("🔍 ПРОВЕРКА ТИПА СТОП-ОРДЕРОВ:")
    print("-" * 80)
    
    print(f"   Тип ордера: {sl_order_type}")
    
    if sl_order_type == "stop_market":
        print(f"   ✅ Правильно: Маркет стоп-лосс (гарантированное исполнение)")
        print(f"   • При срабатывании создается маркетный ордер")
        print(f"   • Исполнение гарантировано, но цена может проскочить")
    elif sl_order_type == "stop":
        print(f"   ⚠️ Лимитный стоп-лосс (может не исполниться)")
        print(f"   • При срабатывании создается лимитный ордер")
        print(f"   • Цена контролируется, но исполнение не гарантировано")
    else:
        print(f"   ❌ Неизвестный тип стоп-ордера!")
    
    print()
    
    # Рекомендации
    print("🎯 РЕКОМЕНДАЦИИ:")
    print("-" * 60)
    
    print("1. ПРОВЕРИТЬ СТОП-ЛОССЫ НА БИРЖЕ:")
    print("   • Зайти в раздел 'Открытые ордера' на Binance")
    print("   • Убедиться, что для каждой позиции есть стоп-ордер")
    print("   • Проверить цены стоп-лоссов")
    
    print()
    print("2. ПРОВЕРИТЬ ЛОГИ СИСТЕМЫ:")
    print("   • Найти сообщения об установке стоп-лоссов")
    print("   • Проверить, обновляются ли стоп-лоссы")
    print("   • Убедиться в отсутствии ошибок")
    
    print()
    print("3. ПРОВЕРИТЬ РАСЧЕТ ATR:")
    print("   • ATR должен быть адекватным (2-5% от цены)")
    print("   • SL должен быть на расстоянии 2.5 * ATR")
    print("   • Проверить исторические данные")
    
    print()
    print("4. МОНИТОРИТЬ ИСПОЛНЕНИЕ:")
    print("   • Следить за срабатыванием стоп-лоссов")
    print("   • Проверять проскальзывание")
    print("   • Анализировать эффективность")
    
    # Итоговая оценка
    print()
    print("🎯 ИТОГОВАЯ ОЦЕНКА:")
    print("-" * 60)
    
    # Проверяем, есть ли позиции с большими убытками
    big_losses = [pos for pos in positions if abs(pos["roi"]) > 5]
    
    if big_losses:
        print("❌ НАЙДЕНЫ ПРОБЛЕМЫ:")
        for pos in big_losses:
            print(f"   • {pos['symbol']}: {pos['roi']:.1f}% убыток")
        print("   → Возможно, стоп-лоссы установлены неправильно")
        print("   → Или не срабатывают вовремя")
    else:
        print("✅ ВСЕ ПОЗИЦИИ В ПРЕДЕЛАХ НОРМЫ")
        print("   • Убытки не превышают 5%")
        print("   • Стоп-лоссы работают правильно")

if __name__ == "__main__":
    test_stop_loss_verification()
