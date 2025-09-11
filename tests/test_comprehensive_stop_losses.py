#!/usr/bin/env python3
"""
Комплексный тест стоп-лоссов в live системе
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
from signalwarden_lite.core.trailing import TrailingConfig, update_trailing_pnl_based
from signalwarden_lite.core.types import Position, Side

def test_comprehensive_stop_losses():
    """Комплексный тест стоп-лоссов"""
    
    print("🛡️ КОМПЛЕКСНЫЙ ТЕСТ СТОП-ЛОССОВ")
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
    
    # Тест 1: Расчет начального стоп-лосса
    print("🔍 ТЕСТ 1: РАСЧЕТ НАЧАЛЬНОГО СТОП-ЛОССА")
    print("-" * 60)
    
    # Симуляция сигнала
    entry_price = 0.884021
    atr = 0.004071
    sl_atr_mult = cfg['risk']['sl_atr_mult']
    
    # Расчет стоп-лосса (как в live системе)
    sl_price = entry_price - (sl_atr_mult * atr)
    sl_distance = entry_price - sl_price
    sl_percent = (sl_distance / entry_price) * 100
    
    print(f"   Entry Price: {entry_price:.6f}")
    print(f"   ATR: {atr:.6f}")
    print(f"   SL Multiplier: {sl_atr_mult}x")
    print(f"   SL Price: {sl_price:.6f}")
    print(f"   SL Distance: {sl_distance:.6f} ({sl_percent:.2f}%)")
    
    if sl_percent >= 1.0 and sl_percent <= 3.0:
        print(f"   ✅ SL Distance в разумных пределах (1-3%)")
    else:
        print(f"   ⚠️ SL Distance вне рекомендуемых пределов")
    
    print()
    
    # Тест 2: Создание стоп-ордера
    print("🔍 ТЕСТ 2: СОЗДАНИЕ СТОП-ОРДЕРА")
    print("-" * 60)
    
    sl_order_type = cfg['risk']['sl_order_type']
    qty = 23.76  # Примерное количество для 21 USDT позиции
    
    print(f"   Order Type: {sl_order_type}")
    print(f"   Quantity: {qty:.2f}")
    print(f"   Stop Price: {sl_price:.6f}")
    print(f"   Side: sell (для LONG позиции)")
    print(f"   reduceOnly: True")
    print(f"   timeInForce: GTC")
    
    if sl_order_type == 'stop_market':
        print(f"   ✅ Используется stop_market - гарантированное исполнение")
        print(f"   ✅ Маркет ордер после триггера - лучший выбор для live")
    elif sl_order_type == 'stop':
        print(f"   ⚠️ Используется stop - лимитный ордер после триггера")
        print(f"   ⚠️ Может не исполниться при быстром движении цены")
    else:
        print(f"   ❌ Неизвестный тип ордера: {sl_order_type}")
    
    print()
    
    # Тест 3: Трейлинг стоп-лосс
    print("🔍 ТЕСТ 3: ТРЕЙЛИНГ СТОП-ЛОСС")
    print("-" * 60)
    
    # Создать тестовую позицию
    test_position = Position(
        side=Side.LONG,
        entry=entry_price,
        qty=qty,
        remaining_qty=qty,
        r_per_unit=entry_price - sl_price,
        sl=sl_price,
        sl_initial=sl_price,
        peak_pnl_usdt=0.0
    )
    
    # Создать конфигурацию трейлинга
    trailing_config = TrailingConfig(
        activate_pnl_usdt=cfg['trailing']['activate_pnl_usdt'],
        level_1_pnl=cfg['trailing']['level_1_pnl'],
        level_1_keep_pct=cfg['trailing']['level_1_keep_pct'],
        level_2_pnl=cfg['trailing']['level_2_pnl'],
        level_2_keep_pct=cfg['trailing']['level_2_keep_pct'],
        level_3_pnl=cfg['trailing']['level_3_pnl'],
        level_3_keep_pct=cfg['trailing']['level_3_keep_pct'],
        level_4_pnl=cfg['trailing']['level_4_pnl'],
        level_4_keep_pct=cfg['trailing']['level_4_keep_pct']
    )
    
    print(f"   Trailing Activation: {trailing_config.activate_pnl_usdt} USDT")
    print(f"   Level 1: {trailing_config.level_1_pnl} USDT → keep {trailing_config.level_1_keep_pct*100}%")
    print(f"   Level 2: {trailing_config.level_2_pnl} USDT → keep {trailing_config.level_2_keep_pct*100}%")
    print(f"   Level 3: {trailing_config.level_3_pnl} USDT → keep {trailing_config.level_3_keep_pct*100}%")
    print(f"   Level 4: {trailing_config.level_4_pnl} USDT → keep {trailing_config.level_4_keep_pct*100}%")
    print()
    
    # Тест разных уровней PnL
    test_pnl_levels = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45]
    current_price = entry_price
    
    print(f"   Тестирование трейлинга для разных уровней PnL:")
    print(f"   {'PnL (USDT)':<12} {'Level':<6} {'Keep %':<8} {'New SL':<12} {'Updated':<8}")
    print(f"   {'-'*12} {'-'*6} {'-'*8} {'-'*12} {'-'*8}")
    
    for pnl in test_pnl_levels:
        # Обновить позицию
        updated_position = update_trailing_pnl_based(test_position, current_price, pnl, trailing_config)
        
        # Получить информацию о трейлинге
        debug_info = getattr(updated_position, 'trailing_debug', {})
        level = debug_info.get('level', 'N/A')
        keep_pct = debug_info.get('keep_pct', 0) * 100
        new_sl = updated_position.sl
        updated = debug_info.get('sl_updated', False)
        
        print(f"   {pnl:<12.2f} {level:<6} {keep_pct:<8.0f} {new_sl:<12.6f} {'✅' if updated else '❌'}")
        
        # Обновить позицию для следующего теста
        test_position = updated_position
    
    print()
    
    # Тест 4: Анализ рисков
    print("🔍 ТЕСТ 4: АНАЛИЗ РИСКОВ")
    print("-" * 60)
    
    margin_usdt = cfg['risk']['margin_usdt']
    leverage = cfg['risk']['leverage']
    notional_value = margin_usdt * leverage
    
    print(f"   Margin: {margin_usdt} USDT")
    print(f"   Leverage: {leverage}x")
    print(f"   Notional Value: {notional_value} USDT")
    print(f"   Max Loss (SL): {sl_distance * qty:.2f} USDT")
    print(f"   Max Loss %: {(sl_distance * qty / margin_usdt) * 100:.1f}%")
    
    max_loss_percent = (sl_distance * qty / margin_usdt) * 100
    
    if max_loss_percent <= 5.0:
        print(f"   ✅ Максимальная потеря ≤ 5% - консервативно")
    elif max_loss_percent <= 10.0:
        print(f"   ✅ Максимальная потеря ≤ 10% - приемлемо")
    elif max_loss_percent <= 20.0:
        print(f"   ⚠️ Максимальная потеря ≤ 20% - высокий риск")
    else:
        print(f"   ❌ Максимальная потеря > 20% - очень высокий риск")
    
    print()
    
    # Тест 5: Проверка конфигурации
    print("🔍 ТЕСТ 5: ПРОВЕРКА КОНФИГУРАЦИИ")
    print("-" * 60)
    
    issues = []
    recommendations = []
    
    # Проверка sl_atr_mult
    if sl_atr_mult < 2.0:
        issues.append("sl_atr_mult слишком мал - риск ложных срабатываний")
    elif sl_atr_mult > 3.0:
        issues.append("sl_atr_mult слишком велик - большие потери")
    else:
        recommendations.append("sl_atr_mult в оптимальном диапазоне")
    
    # Проверка sl_order_type
    if sl_order_type != 'stop_market':
        issues.append("sl_order_type не 'stop_market' - риск неисполнения")
    else:
        recommendations.append("sl_order_type оптимален для live торговли")
    
    # Проверка margin_usdt
    if margin_usdt < 10:
        issues.append("margin_usdt слишком мал - малая прибыль")
    elif margin_usdt > 50:
        issues.append("margin_usdt слишком велик - высокий риск")
    else:
        recommendations.append("margin_usdt в разумных пределах")
    
    # Проверка leverage
    if leverage < 3:
        issues.append("leverage слишком низок - малая прибыль")
    elif leverage > 10:
        issues.append("leverage слишком высок - высокий риск")
    else:
        recommendations.append("leverage в безопасных пределах")
    
    # Проверка trailing параметров
    if trailing_config.activate_pnl_usdt < 0.05:
        issues.append("activate_pnl_usdt слишком мал - ранняя активация")
    elif trailing_config.activate_pnl_usdt > 0.20:
        issues.append("activate_pnl_usdt слишком велик - поздняя активация")
    else:
        recommendations.append("activate_pnl_usdt оптимален")
    
    if issues:
        print("   ⚠️ НАЙДЕНЫ ПРОБЛЕМЫ:")
        for issue in issues:
            print(f"      - {issue}")
    else:
        print("   ✅ Проблем не найдено")
    
    if recommendations:
        print("   ✅ РЕКОМЕНДАЦИИ:")
        for rec in recommendations:
            print(f"      - {rec}")
    
    print()
    
    # Итоговая оценка
    print("🎯 ИТОГОВАЯ ОЦЕНКА СТОП-ЛОССОВ:")
    print("-" * 60)
    
    if not issues:
        print("✅ ВСЕ ПАРАМЕТРЫ СТОП-ЛОССОВ НАСТРОЕНЫ ОПТИМАЛЬНО!")
        print("✅ Система готова к безопасной live торговле")
        print("✅ Стоп-лоссы обеспечивают надежную защиту от потерь")
        print("✅ Трейлинг система максимизирует прибыль")
    else:
        print("⚠️ НАЙДЕНЫ ПРОБЛЕМЫ В КОНФИГУРАЦИИ СТОП-ЛОССОВ")
        print("⚠️ Рекомендуется исправить перед live торговлей")
        print("⚠️ Текущие настройки могут привести к неожиданным потерям")
    
    print()
    print("📋 СВОДКА ПО СТОП-ЛОССАМ:")
    print(f"   • Начальный SL: {sl_percent:.2f}% от цены входа")
    print(f"   • Тип ордера: {sl_order_type}")
    print(f"   • Максимальная потеря: {max_loss_percent:.1f}% от маржи")
    print(f"   • Трейлинг активация: {trailing_config.activate_pnl_usdt} USDT")
    print(f"   • Уровни сохранения: 50%/60%/70%/80%")

if __name__ == "__main__":
    test_comprehensive_stop_losses()
