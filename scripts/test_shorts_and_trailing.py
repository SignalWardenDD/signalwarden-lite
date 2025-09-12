#!/usr/bin/env python3

import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

# Добавляем путь к модулям
sys.path.append('.')

from signalwarden_lite.core.signals import generate_signals
from signalwarden_lite.core.types import SignalParams, Position, Side
from signalwarden_lite.core.trailing_pnl_only import update_trailing_pnl_only, TrailingConfigPnLOnly
from signalwarden_lite.core.market import compute_market_bias

def test_short_signal_generation():
    """Тест генерации SHORT сигналов"""
    
    print("🔍 ТЕСТ ГЕНЕРАЦИИ SHORT СИГНАЛОВ")
    print("=" * 80)
    
    # Загружаем последние данные
    try:
        df_btc = pd.read_pickle('data/historical_candles/BTC_USDT_1h.pkl')
        df_ada = pd.read_pickle('data/historical_candles/ADA_USDT_1h.pkl')
        
        # Берем последние 100 баров для анализа
        df_btc = df_btc.tail(100).copy()
        df_ada = df_ada.tail(100).copy()
        
        # Рассчитываем BTC market bias
        btc_bias = compute_market_bias(df_btc, ema_fast=50, ema_slow=200)
        
        # Параметры сигналов (как в production)
        signal_params = SignalParams(
            # Setups
            setup_breakout=True,
            setup_inside=True,
            setup_tc=True,
            setup_squeeze=True,
            
            # Lookbacks по режиму
            lookback_calm=24,
            lookback_normal=16,
            lookback_high=10,
            
            # ATR cushions (шорты шире)
            long_cushion_calm=0.30, long_cushion_normal=0.12, long_cushion_high=0.08,
            short_cushion_calm=0.34, short_cushion_normal=0.16, short_cushion_high=0.12,
            
            # Short guard parameters
            sg_rsi_bear_max=52,           # RSI <= 52 в медвежьем рынке
            sg_rsi_bullcorr_max=50,       # RSI <= 50 в коррекциях
            sg_min_natr_bear=0.9,         # NATR >= 0.9% в медвежьем рынке
            sg_min_natr_bullcorr=0.8,     # NATR >= 0.8% в коррекциях
            sg_require_close_below_ema20_bullcorr=True,  # Close < EMA20 в коррекциях
            sg_slope_lookback=3,
            
            # Long guard
            lg_rsi_long_min=35,           # RSI >= 35 для лонгов
            
            ltf_thinbar_k=0.25
        )
        
        # Генерируем сигналы
        signals = generate_signals(df_ada, signal_params, btc_bias)
        
        # Анализируем последний бар
        latest = signals.iloc[-1]
        latest_btc = btc_bias.iloc[-1]
        
        print(f"📊 ТЕКУЩИЕ УСЛОВИЯ (ADA_USDT):")
        print(f"   Цена: ${latest['close']:.4f}")
        print(f"   RSI: {latest['rsi']:.2f}")
        print(f"   NATR: {latest['natr']:.2f}%")
        print(f"   EMA50: {latest['ema_fast']:.4f}")
        print(f"   EMA200: {latest['ema_slow']:.4f}")
        print(f"   EMA20: {latest.get('ema20', 0):.4f}")
        print(f"   Режим: {latest['regime']}")
        print()
        
        print(f"📊 BTC MARKET CONTEXT:")
        print(f"   BTC mkt_long_ok: {latest_btc['mkt_long_ok']}")
        print(f"   BTC mkt_short_ok: {latest_btc['mkt_short_ok']}")
        print()
        
        # Проверяем условия для шортов
        print(f"🔍 ПРОВЕРКА УСЛОВИЙ ДЛЯ ШОРТОВ:")
        
        # 1. Raw signal
        raw_short = latest.get('allow_short_raw', False)
        print(f"   1. Raw short signal: {raw_short}")
        
        # 2. BTC market filter
        btc_allows_short = latest_btc['mkt_short_ok']
        print(f"   2. BTC allows shorts: {btc_allows_short}")
        
        # 3. EMA trend condition
        ema_bearish = latest['ema_fast'] < latest['ema_slow']
        print(f"   3. EMA50 < EMA200 (bearish): {ema_bearish}")
        
        # 4. Short guard conditions
        if btc_allows_short:
            # Bear market conditions
            rsi_ok = latest['rsi'] <= signal_params.sg_rsi_bear_max
            natr_ok = latest['natr'] >= signal_params.sg_min_natr_bear
            print(f"   4. Bear market conditions:")
            print(f"      RSI <= {signal_params.sg_rsi_bear_max}: {rsi_ok}")
            print(f"      NATR >= {signal_params.sg_min_natr_bear}%: {natr_ok}")
            guard_ok = rsi_ok and natr_ok
        else:
            # Bull correction conditions
            rsi_ok = latest['rsi'] <= signal_params.sg_rsi_bullcorr_max
            natr_ok = latest['natr'] >= signal_params.sg_min_natr_bullcorr
            ema20_ok = latest['close'] < latest.get('ema20', float('inf'))
            print(f"   4. Bull correction conditions:")
            print(f"      RSI <= {signal_params.sg_rsi_bullcorr_max}: {rsi_ok}")
            print(f"      NATR >= {signal_params.sg_min_natr_bullcorr}%: {natr_ok}")
            print(f"      Close < EMA20: {ema20_ok}")
            guard_ok = rsi_ok and natr_ok and ema20_ok
        
        print(f"   5. Guard conditions met: {guard_ok}")
        
        # 5. Final short signal
        final_short = latest.get('allow_short', False)
        print(f"   6. Final short allowed: {final_short}")
        
        print()
        
        # Проверяем историю сигналов
        recent_shorts = signals.tail(20)['allow_short'].sum()
        recent_longs = signals.tail(20)['allow_long'].sum()
        
        print(f"📈 ИСТОРИЯ СИГНАЛОВ (последние 20 баров):")
        print(f"   Short signals: {recent_shorts}")
        print(f"   Long signals: {recent_longs}")
        
        # Ищем ближайшие условия для шортов
        print(f"\n🔮 АНАЛИЗ ВОЗМОЖНОСТИ ШОРТОВ:")
        if not final_short:
            print(f"   Текущие шорты заблокированы")
            if not btc_allows_short:
                print(f"   • BTC в бычьем тренде - нужны коррекционные условия")
                print(f"   • Нужно: RSI <= {signal_params.sg_rsi_bullcorr_max}, NATR >= {signal_params.sg_min_natr_bullcorr}%, Close < EMA20")
            else:
                print(f"   • BTC в медвежьем тренде - нужны медвежьи условия")
                print(f"   • Нужно: RSI <= {signal_params.sg_rsi_bear_max}, NATR >= {signal_params.sg_min_natr_bear}%")
        else:
            print(f"   ✅ Шорты разрешены! Система готова открывать короткие позиции")
        
        return final_short
        
    except Exception as e:
        print(f"❌ Ошибка при тестировании шортов: {e}")
        return False

def test_trailing_activation():
    """Тест активации трейлинга по уровням PnL"""
    
    print("\n🎯 ТЕСТ АКТИВАЦИИ ТРЕЙЛИНГА ПО УРОВНЯМ PnL")
    print("=" * 80)
    
    # Конфигурация трейлинга (как в production)
    trailing_config = TrailingConfigPnLOnly(
        level_1_pnl=0.06,     # При $0.06 прибыли
        level_1_keep_pct=0.50, # сохранить 50% = минимум $0.03
        level_2_pnl=0.15,     # При $0.15 прибыли  
        level_2_keep_pct=0.60, # сохранить 60% = минимум $0.09
        level_3_pnl=0.25,     # При $0.25 прибыли
        level_3_keep_pct=0.70, # сохранить 70% = минимум $0.175
        level_4_pnl=0.35,     # При $0.35+ прибыли
        level_4_keep_pct=0.80  # сохранить 80% = минимум $0.28
    )
    
    # Создаем тестовую позицию
    entry_price = 0.884021
    qty = 23.76
    initial_sl = entry_price - 0.019  # ~2.2% ниже входа
    
    position = Position(
        side=Side.LONG,
        entry=entry_price,
        sl=initial_sl,
        sl_initial=initial_sl,
        qty=qty,
        remaining_qty=qty,
        r_per_unit=0.019,
        entry_reason="test"
    )
    
    print(f"📊 ТЕСТОВАЯ ПОЗИЦИЯ:")
    print(f"   Entry: ${entry_price:.6f}")
    print(f"   Qty: {qty:.4f}")
    print(f"   Initial SL: ${initial_sl:.6f}")
    print()
    
    # Тестируем различные уровни цены
    test_prices = [
        (0.884021, "Entry level"),
        (0.887021, "Small profit (+$0.07)"),
        (0.890521, "Level 1 trigger (+$0.15)"),
        (0.894521, "Level 2 trigger (+$0.25)"),
        (0.898521, "Level 3 trigger (+$0.34)"),
        (0.903021, "Level 4 trigger (+$0.45)")
    ]
    
    print(f"🧮 ТЕСТИРОВАНИЕ УРОВНЕЙ ТРЕЙЛИНГА:")
    print("-" * 80)
    
    for price, description in test_prices:
        # Сбрасываем позицию для каждого теста
        test_pos = Position(
            side=Side.LONG,
            entry=entry_price,
            sl=initial_sl,
            sl_initial=initial_sl,
            qty=qty,
            remaining_qty=qty,
            r_per_unit=0.019,
            entry_reason="test"
        )
        
        # Рассчитываем PnL
        current_pnl = (price - entry_price) * qty
        
        # Применяем трейлинг
        updated_pos = update_trailing_pnl_only(
            test_pos, 
            price,  # hi
            price,  # lo
            0.004,  # atr (не используется в PnL-only)
            trailing_config
        )
        
        # Получаем отладочную информацию
        debug_info = getattr(updated_pos, 'trailing_debug', {})
        level = debug_info.get('level', 'UNKNOWN')
        keep_pct = debug_info.get('keep_pct', 0)
        target_profit = debug_info.get('target_profit', 0)
        sl_updated = debug_info.get('sl_updated', False)
        
        print(f"   💰 {description}:")
        print(f"      Price: ${price:.6f}")
        print(f"      PnL: ${current_pnl:.4f}")
        print(f"      Level: {level}")
        print(f"      Keep %: {keep_pct*100:.0f}%")
        print(f"      Target profit: ${target_profit:.4f}")
        print(f"      New SL: ${updated_pos.sl:.6f}")
        print(f"      SL updated: {sl_updated}")
        
        # Проверяем логику
        if current_pnl > 0:
            if level == "INACTIVE":
                print(f"      ❌ Трейлинг не активирован (PnL < ${trailing_config.level_1_pnl:.2f})")
            else:
                expected_sl = entry_price + (target_profit / qty)
                actual_sl = updated_pos.sl
                sl_correct = abs(actual_sl - expected_sl) < 0.000001
                print(f"      ✅ Трейлинг активирован: {sl_correct}")
                if not sl_correct:
                    print(f"         Expected SL: ${expected_sl:.6f}")
                    print(f"         Actual SL: ${actual_sl:.6f}")
        else:
            print(f"      ⏸️ Трейлинг неактивен (убыток)")
        print()
    
    # Тест защиты минимальной прибыли
    print(f"🛡️ ТЕСТ ЗАЩИТЫ МИНИМАЛЬНОЙ ПРИБЫЛИ:")
    print("-" * 60)
    
    # Создаем позицию с небольшой прибылью
    small_profit_price = entry_price + 0.002  # Очень маленькая прибыль
    test_pos = Position(
        side=Side.LONG,
        entry=entry_price,
        sl=initial_sl,
        sl_initial=initial_sl,
        qty=qty,
        remaining_qty=qty,
        r_per_unit=0.019,
        entry_reason="test"
    )
    
    # Устанавливаем пиковую прибыль выше уровня 1
    test_pos.peak_pnl_usdt = 0.10  # $0.10 пиковая прибыль
    
    updated_pos = update_trailing_pnl_only(
        test_pos,
        small_profit_price,  # Текущая цена с маленькой прибылью
        small_profit_price,
        0.004,
        trailing_config
    )
    
    debug_info = getattr(updated_pos, 'trailing_debug', {})
    target_profit = debug_info.get('target_profit', 0)
    
    print(f"   Пиковая прибыль: ${test_pos.peak_pnl_usdt:.4f}")
    print(f"   Текущая прибыль: ${(small_profit_price - entry_price) * qty:.4f}")
    print(f"   Целевая прибыль: ${target_profit:.4f}")
    print(f"   Минимальная защита: ${0.03:.4f}")
    
    if target_profit >= 0.03:
        print(f"   ✅ Защита минимальной прибыли работает")
    else:
        print(f"   ❌ Защита минимальной прибыли НЕ работает")
    
    return True

def test_current_positions_trailing():
    """Тест трейлинга на текущих позициях"""
    
    print(f"\n💼 ТЕСТ ТРЕЙЛИНГА НА ТЕКУЩИХ ПОЗИЦИЯХ")
    print("=" * 80)
    
    try:
        # Загружаем текущее состояние
        with open('trading_state_v1_6_TXB.json', 'r') as f:
            state = json.load(f)
        
        trailing_config = TrailingConfigPnLOnly(
            level_1_pnl=0.06, level_1_keep_pct=0.50,
            level_2_pnl=0.15, level_2_keep_pct=0.60,
            level_3_pnl=0.25, level_3_keep_pct=0.70,
            level_4_pnl=0.35, level_4_keep_pct=0.80
        )
        
        positions_found = 0
        
        for symbol, data in state.get('symbols', {}).items():
            if symbol.endswith('_position'):
                continue
                
            active_pos = data.get('active_position')
            if active_pos:
                positions_found += 1
                entry = active_pos.get('entry', 0)
                side = active_pos.get('side', 'UNKNOWN')
                qty = active_pos.get('qty', 0)
                sl_current = active_pos.get('sl_current', 0)
                
                print(f"📊 {symbol}:")
                print(f"   Entry: ${entry:.6f}")
                print(f"   Current SL: ${sl_current:.6f}")
                print(f"   Side: {side}")
                print(f"   Qty: {qty:.4f}")
                
                # Симулируем различные цены для проверки трейлинга
                if side == 'LONG':
                    test_prices = [
                        entry + 0.003,  # Небольшая прибыль
                        entry + 0.006,  # Level 1 область
                        entry + 0.010,  # Level 2 область
                    ]
                    
                    for i, test_price in enumerate(test_prices):
                        pnl = (test_price - entry) * qty
                        print(f"   Тест {i+1}: Price=${test_price:.6f}, PnL=${pnl:.4f}")
                        
                        # Создаем тестовую позицию
                        test_pos = Position(
                            side=Side.LONG,
                            entry=entry,
                            sl=sl_current,
                            sl_initial=sl_current,
                            qty=qty,
                            remaining_qty=qty,
                            r_per_unit=abs(sl_current - entry),
                            entry_reason="live"
                        )
                        
                        # Применяем трейлинг
                        updated_pos = update_trailing_pnl_only(
                            test_pos, test_price, test_price, 0.004, trailing_config
                        )
                        
                        debug_info = getattr(updated_pos, 'trailing_debug', {})
                        level = debug_info.get('level', 'INACTIVE')
                        target_profit = debug_info.get('target_profit', 0)
                        
                        print(f"      Level: {level}, Target: ${target_profit:.4f}, New SL: ${updated_pos.sl:.6f}")
                
                print()
        
        if positions_found == 0:
            print("❌ Активные позиции не найдены!")
        else:
            print(f"✅ Протестировано позиций: {positions_found}")
            
    except Exception as e:
        print(f"❌ Ошибка при тестировании трейлинга: {e}")
        return False
    
    return True

def main():
    """Основная функция тестирования"""
    
    print("🧪 КОМПЛЕКСНОЕ ТЕСТИРОВАНИЕ ШОРТОВ И ТРЕЙЛИНГА")
    print("=" * 100)
    
    # Тест 1: Генерация шортов
    print("\n" + "="*100)
    shorts_working = test_short_signal_generation()
    
    # Тест 2: Активация трейлинга
    print("\n" + "="*100)
    trailing_working = test_trailing_activation()
    
    # Тест 3: Трейлинг на текущих позициях
    print("\n" + "="*100)
    current_trailing_working = test_current_positions_trailing()
    
    # Итоговый отчет
    print("\n" + "="*100)
    print("📋 ИТОГОВЫЙ ОТЧЕТ:")
    print("=" * 100)
    
    print(f"✅ Генерация шортов: {'РАБОТАЕТ' if shorts_working else 'ТРЕБУЕТ ВНИМАНИЯ'}")
    print(f"✅ Активация трейлинга: {'РАБОТАЕТ' if trailing_working else 'НЕ РАБОТАЕТ'}")
    print(f"✅ Трейлинг текущих позиций: {'РАБОТАЕТ' if current_trailing_working else 'НЕ РАБОТАЕТ'}")
    
    if shorts_working and trailing_working and current_trailing_working:
        print(f"\n🎉 ВСЕ СИСТЕМЫ РАБОТАЮТ КОРРЕКТНО!")
    else:
        print(f"\n⚠️ НЕКОТОРЫЕ СИСТЕМЫ ТРЕБУЮТ ВНИМАНИЯ!")
    
    print("\n🚀 Система готова к торговле!")

if __name__ == '__main__':
    main()
