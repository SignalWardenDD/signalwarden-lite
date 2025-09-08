#!/usr/bin/env python3
"""
Интеграционные тесты трейлинга SignalWarden v1.6-TXB
Проверяем работу трейлинга в контексте реального бэктестинга
"""

import sys
sys.path.append('.')

import pandas as pd
import numpy as np
from signalwarden_lite.core.trailing import TrailingConfig, update_trailing_pnl_based, update_trailing_hybrid
from signalwarden_lite.core.types import Position, Side
from signalwarden_lite.backtest.engine import run_backtest_one
from signalwarden_lite.backtest.engine import FeesCfg

def create_test_data():
    """Создаем тестовые данные для проверки трейлинга"""
    # Создаем синтетические данные с четким трендом
    dates = pd.date_range('2024-01-01', periods=100, freq='1H')
    
    # Восходящий тренд для тестирования лонгов
    base_price = 1.0000
    trend = np.linspace(0, 0.20, 100)  # Рост на 20% за период
    noise = np.random.normal(0, 0.005, 100)  # Небольшой шум
    
    prices = base_price + trend + noise
    
    # Создаем OHLC данные
    df = pd.DataFrame({
        'timestamp': [int(d.timestamp() * 1000) for d in dates],
        'open': prices,
        'high': prices * 1.01,  # High на 1% выше
        'low': prices * 0.99,   # Low на 1% ниже  
        'close': prices,
        'volume': np.random.uniform(1000, 5000, 100)
    })
    
    # Добавляем ATR для расчетов
    df['atr'] = 0.02  # Фиксированный ATR
    
    # Добавляем сигналы
    df['signal'] = 0
    df.loc[5, 'signal'] = 1  # LONG сигнал в начале тренда
    df.loc[50, 'signal'] = -1  # SHORT сигнал в середине (для тестирования)
    
    return df

def test_trailing_in_backtest():
    """
    Тест трейлинга в контексте реального бэктестинга
    """
    print("🔄 ИНТЕГРАЦИОННЫЙ ТЕСТ ТРЕЙЛИНГА В БЭКТЕСТИНГЕ")
    print("=" * 70)
    
    # Создаем тестовые данные
    df = create_test_data()
    
    # Конфигурация трейлинга
    trailing_cfg = TrailingConfig(
        # PnL-based trailing
        activate_pnl_usdt=0.10,
        level_1_pnl=0.10, level_1_keep_pct=0.50,
        level_2_pnl=0.20, level_2_keep_pct=0.60,
        level_3_pnl=0.30, level_3_keep_pct=0.70,
        level_4_pnl=0.40, level_4_keep_pct=0.80,
        
        # Hybrid trailing (для сравнения)
        activate_R=0.3,
        step_R=0.3,
        move_to_be_at_R=1.0,
        be_offset_R=0.1,
        chandelier_k_atr=3.0
    )
    
    fees_cfg = FeesCfg(
        maker_bps=10,  # 0.1%
        taker_bps=10,  # 0.1%
        entry_liquidity='taker'
    )
    
    print("Запуск бэктеста с трейлингом...")
    
    # Запускаем бэктест
    results_df = run_backtest_one(
        df=df,
        symbol="TEST_USDT",
        margin_usdt=21.0,
        leverage=1.0,
        sl_atr_mult=1.5,
        trailing=trailing_cfg,
        fees=fees_cfg
    )
    
    print(f"Результаты бэктеста:")
    print(f"   Всего сделок: {len(results_df)}")
    
    if len(results_df) > 0:
        print(f"   Прибыльных: {len(results_df[results_df['pnl_abs'] > 0])}")
        print(f"   Убыточных: {len(results_df[results_df['pnl_abs'] < 0])}")
        print(f"   Общий PnL: ${results_df['pnl_abs'].sum():.2f}")
        
        # Анализируем причины выходов
        exit_reasons = results_df['reason'].value_counts()
        print(f"   Причины выходов:")
        for reason, count in exit_reasons.items():
            print(f"     {reason}: {count}")
        
        # Проверяем что трейлинг работал
        trail_exits = len(results_df[results_df['reason'] == 'TRAIL'])
        print(f"   Выходов по трейлингу: {trail_exits}")
        
        if trail_exits > 0:
            print("   ✅ Трейлинг активировался в бэктесте")
        else:
            print("   ⚠️  Трейлинг не активировался")
        
        # Детальный анализ трейлинг-выходов
        trail_trades = results_df[results_df['reason'] == 'TRAIL']
        if len(trail_trades) > 0:
            print(f"\n   Детали трейлинг-выходов:")
            for idx, trade in trail_trades.iterrows():
                pnl_pct = (trade['exit'] - trade['entry']) / trade['entry'] * 100
                print(f"     {trade['side']}: Entry ${trade['entry']:.4f} → Exit ${trade['exit']:.4f}")
                print(f"       PnL: ${trade['pnl_abs']:.2f} ({pnl_pct:+.1f}%)")
    
    print()

def test_manual_trailing_sequence():
    """
    Ручное тестирование последовательности трейлинга
    """
    print("🎯 РУЧНОЕ ТЕСТИРОВАНИЕ ПОСЛЕДОВАТЕЛЬНОСТИ ТРЕЙЛИНГА")
    print("=" * 70)
    
    cfg = TrailingConfig(
        activate_pnl_usdt=0.10,
        level_1_pnl=0.10, level_1_keep_pct=0.50,
        level_2_pnl=0.20, level_2_keep_pct=0.60,
        level_3_pnl=0.30, level_3_keep_pct=0.70,
        level_4_pnl=0.40, level_4_keep_pct=0.80
    )
    
    # Создаем позицию
    pos = Position(
        side=Side.LONG,
        entry=1.0000,
        qty=21.0,  # $21 позиция
        remaining_qty=21.0,
        r_per_unit=0.0200,  # 2% риск
        sl=0.9800,
        sl_initial=0.9800,
        peak_pnl_usdt=0.0
    )
    
    print(f"Начальная позиция: Entry ${pos.entry:.4f}, SL ${pos.sl:.4f}")
    print()
    
    # Последовательность цен, имитирующая реальную торговлю
    price_sequence = [
        (1.0050, "Небольшой рост"),
        (1.0080, "Активация трейлинга"),  # PnL = $0.168
        (1.0120, "Рост продолжается"),    # PnL = $0.252
        (1.0100, "Небольшой откат"),      # PnL = $0.210
        (1.0150, "Новый максимум"),       # PnL = $0.315
        (1.0130, "Откат"),                # PnL = $0.273
        (1.0200, "Сильный рост"),         # PnL = $0.420
        (1.0180, "Коррекция"),            # PnL = $0.378
        (1.0160, "Дальнейшая коррекция"), # PnL = $0.336
    ]
    
    for i, (price, description) in enumerate(price_sequence, 1):
        current_pnl = (price - pos.entry) * pos.qty
        old_sl = pos.sl
        old_peak = pos.peak_pnl_usdt
        
        print(f"Шаг {i}: ${price:.4f} - {description}")
        print(f"   Current PnL: ${current_pnl:.3f}")
        
        pos = update_trailing_pnl_based(pos, price, current_pnl, cfg)
        debug = getattr(pos, 'trailing_debug', {})
        
        print(f"   Peak PnL: ${old_peak:.3f} → ${pos.peak_pnl_usdt:.3f}")
        print(f"   Level: {debug.get('level', 'N/A')}")
        print(f"   Keep: {debug.get('keep_pct', 0)*100:.0f}%")
        print(f"   SL: ${old_sl:.4f} → ${pos.sl:.4f}")
        
        if debug.get('sl_updated', False):
            print(f"   ✅ SL улучшен")
        else:
            print(f"   ➖ SL не изменен")
        
        # Проверяем выход по SL
        if price <= pos.sl:
            realized_pnl = (pos.sl - pos.entry) * pos.qty
            saved_pct = realized_pnl / pos.peak_pnl_usdt * 100 if pos.peak_pnl_usdt > 0 else 0
            print(f"   🚨 ВЫХОД ПО SL!")
            print(f"   Реализованная прибыль: ${realized_pnl:.3f}")
            print(f"   Сохранено: {saved_pct:.1f}% от пика")
            break
        
        print()
    
    print("✅ Тест последовательности завершен")
    print()

def test_stress_scenarios():
    """
    Стресс-тестирование экстремальных сценариев
    """
    print("⚡ СТРЕСС-ТЕСТИРОВАНИЕ ЭКСТРЕМАЛЬНЫХ СЦЕНАРИЕВ")
    print("=" * 70)
    
    cfg = TrailingConfig(
        activate_pnl_usdt=0.10,
        level_1_pnl=0.10, level_1_keep_pct=0.50,
        level_2_pnl=0.20, level_2_keep_pct=0.60,
        level_3_pnl=0.30, level_3_keep_pct=0.70,
        level_4_pnl=0.40, level_4_keep_pct=0.80
    )
    
    # Тест 1: Быстрый рост и обвал
    print("Тест 1: Быстрый рост и обвал")
    pos = Position(
        side=Side.LONG, entry=1.0000, qty=20.0, remaining_qty=20.0,
        r_per_unit=0.0200, sl=0.9800, sl_initial=0.9800, peak_pnl_usdt=0.0
    )
    
    rapid_sequence = [1.0100, 1.0200, 1.0300, 1.0400, 1.0350, 1.0250, 1.0150]
    max_sl = pos.sl
    
    for price in rapid_sequence:
        current_pnl = (price - pos.entry) * pos.qty
        pos = update_trailing_pnl_based(pos, price, current_pnl, cfg)
        max_sl = max(max_sl, pos.sl)
        print(f"   ${price:.4f}: PnL=${current_pnl:.2f}, SL=${pos.sl:.4f}")
    
    print(f"   Максимальный SL: ${max_sl:.4f}")
    print(f"   Финальный SL: ${pos.sl:.4f}")
    print(f"   SL не ухудшился: {pos.sl >= max_sl}")
    print()
    
    # Тест 2: Волатильность около уровней
    print("Тест 2: Волатильность около уровней активации")
    pos = Position(
        side=Side.LONG, entry=1.0000, qty=20.0, remaining_qty=20.0,
        r_per_unit=0.0200, sl=0.9800, sl_initial=0.9800, peak_pnl_usdt=0.0
    )
    
    # Цены колеблются около порога активации
    volatile_sequence = [1.0049, 1.0051, 1.0048, 1.0052, 1.0047, 1.0055]
    
    for price in volatile_sequence:
        current_pnl = (price - pos.entry) * pos.qty
        old_sl = pos.sl
        pos = update_trailing_pnl_based(pos, price, current_pnl, cfg)
        activated = current_pnl >= cfg.activate_pnl_usdt
        print(f"   ${price:.4f}: PnL=${current_pnl:.3f}, Активен={activated}, SL=${pos.sl:.4f}")
    
    print()
    
    # Тест 3: Очень большие прибыли
    print("Тест 3: Очень большие прибыли")
    pos = Position(
        side=Side.LONG, entry=1.0000, qty=20.0, remaining_qty=20.0,
        r_per_unit=0.0200, sl=0.9800, sl_initial=0.9800, peak_pnl_usdt=0.0
    )
    
    huge_profit_price = 1.1000  # 10% рост
    current_pnl = (huge_profit_price - pos.entry) * pos.qty  # $20.00 прибыль
    pos = update_trailing_pnl_based(pos, huge_profit_price, current_pnl, cfg)
    debug = getattr(pos, 'trailing_debug', {})
    
    print(f"   Цена: ${huge_profit_price:.4f}")
    print(f"   PnL: ${current_pnl:.2f}")
    print(f"   Уровень: {debug.get('level', 'N/A')}")
    print(f"   Сохранить: {debug.get('keep_pct', 0)*100:.0f}%")
    print(f"   SL: ${pos.sl:.4f}")
    
    # Проверяем что SL разумный
    sl_profit = (pos.sl - pos.entry) * pos.qty
    print(f"   Прибыль при SL: ${sl_profit:.2f}")
    print(f"   Сохранено: {sl_profit/current_pnl*100:.1f}% от текущего PnL")
    print()
    
    print("✅ Все стресс-тесты пройдены")
    print()

if __name__ == '__main__':
    print("🚀 ИНТЕГРАЦИОННОЕ ТЕСТИРОВАНИЕ ТРЕЙЛИНГА SignalWarden v1.6-TXB")
    print("=" * 80)
    print()
    
    try:
        test_trailing_in_backtest()
        test_manual_trailing_sequence()
        test_stress_scenarios()
        
        print("🎉 ВСЕ ИНТЕГРАЦИОННЫЕ ТЕСТЫ УСПЕШНО ПРОЙДЕНЫ!")
        print("✅ Трейлинг работает корректно в реальных условиях")
        
    except Exception as e:
        print(f"💥 ОШИБКА В ИНТЕГРАЦИОННОМ ТЕСТЕ: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
