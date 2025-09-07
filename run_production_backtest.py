#!/usr/bin/env python3
"""
Бэктест с production настройками SignalWarden v1.6-TXB
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import yaml
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta

from signalwarden_lite.core.data_loader import load_candles_pkl
from signalwarden_lite.core.features import add_indicators
from signalwarden_lite.core.regimes import add_regime, RegimeThresholds
from signalwarden_lite.core.signals import generate_signals, SignalParams
from signalwarden_lite.core.market import compute_market_bias
from signalwarden_lite.core.trailing import TrailingConfig
from signalwarden_lite.backtest.engine import run_backtest_one, FeesCfg

def main():
    print("🚀 БЭКТЕСТ SignalWarden v1.6-TXB Production Settings")
    print("=" * 70)
    
    # Загружаем production конфиг
    config_path = "signalwarden_lite/config/config_production.yaml"
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    print(f"📊 Настройки:")
    print(f"   Символы: {len(config['symbols'])} пар")
    print(f"   Размер позиции: {config['risk']['margin_usdt']} USDT")
    print(f"   Плечо: {config['risk']['leverage']}x")
    print(f"   SL: {config['risk']['sl_atr_mult']}x ATR")
    print(f"   Трейлинг: {config['trailing']['activate_R']*100}% R")
    print()
    
    # Настройки
    symbols = config['symbols']
    margin_usdt = config['risk']['margin_usdt']
    leverage = config['risk']['leverage']
    sl_atr_mult = config['risk']['sl_atr_mult']
    
    # Трейлинг конфиг
    trailing = TrailingConfig(**config['trailing'])
    
    # Комиссии
    fees = FeesCfg(
        maker_bps=config['fees']['maker_bps'],
        taker_bps=config['fees']['taker_bps'],
        entry_liquidity=config['fees']['entry_liquidity']
    )
    
    # Пороги режимов
    regime_thresholds = RegimeThresholds(**config['regime']['calm_thresholds'])
    
    # Параметры сигналов - создаем вручную из конфига
    signals_cfg = config['signals']
    signal_params = SignalParams(
        # Dynamic lookbacks
        lookback_calm=signals_cfg['dynamic_lookback']['calm'],
        lookback_normal=signals_cfg['dynamic_lookback']['normal'], 
        lookback_high=signals_cfg['dynamic_lookback']['high'],
        # ATR cushions
        long_cushion_calm=signals_cfg['atr_cushion_long']['calm'],
        long_cushion_normal=signals_cfg['atr_cushion_long']['normal'],
        long_cushion_high=signals_cfg['atr_cushion_long']['high'],
        short_cushion_calm=signals_cfg['atr_cushion_short']['calm'],
        short_cushion_normal=signals_cfg['atr_cushion_short']['normal'],
        short_cushion_high=signals_cfg['atr_cushion_short']['high'],
        # Setups
        setup_breakout=signals_cfg['setups']['breakout']['enabled'],
        setup_inside=signals_cfg['setups']['inside_bar']['enabled'],
        setup_trend_cont=signals_cfg['setups']['trend_continuation']['enabled'],
        setup_squeeze=signals_cfg['setups']['squeeze_breakout']['enabled'],
        # LTF thin bar filter
        ltf_thinbar_k=signals_cfg['ltf_thinbar_k'],
        # Inside bar params
        ib_min_prev_range_k_atr=signals_cfg['setups']['inside_bar']['min_prev_range_k_atr'],
        # Trend continuation params
        tc_min_body_k_range=signals_cfg['setups']['trend_continuation']['min_body_k_range'],
        tc_confirm_close_k_body=signals_cfg['setups']['trend_continuation']['confirm_close_k_body'],
        # Squeeze params
        bb_period=signals_cfg['setups']['squeeze_breakout']['bb_period'],
        bb_k=signals_cfg['setups']['squeeze_breakout']['bb_k'],
        width_k_perc=signals_cfg['setups']['squeeze_breakout']['width_k_perc'],
        # Short guard params
        sg_rsi_bear_max=config['short_guard']['rsi_bear_max'],
        sg_rsi_bullcorr_max=config['short_guard']['rsi_bullcorr_max'],
        sg_min_natr_bear=config['short_guard']['min_natr_bear'],
        sg_min_natr_bullcorr=config['short_guard']['min_natr_bullcorr'],
        sg_require_close_below_ema20_bullcorr=config['short_guard']['require_close_below_ema20_bullcorr']
    )
    
    # Результаты по символам
    all_trades = []
    symbol_results = {}
    
    print("🔄 Запуск бэктеста по символам...")
    
    for symbol in symbols:
        print(f"\n📊 Обрабатываю {symbol}...")
        
        try:
            # Загружаем данные
            df = load_candles_pkl('data/historical_candles', symbol, '1h')
            if df is None or df.empty:
                print(f"   ❌ Нет данных для {symbol}")
                continue
                
            # Ограничиваем период (последние 2 года)
            end_date = df.index.max()
            start_date = end_date - pd.Timedelta(days=730)
            df = df[df.index >= start_date].copy()
            
            print(f"   📅 Период: {df.index.min().strftime('%Y-%m-%d')} - {df.index.max().strftime('%Y-%m-%d')}")
            print(f"   📈 Баров: {len(df)}")
            
            if len(df) < 200:
                print(f"   ❌ Недостаточно данных для {symbol}")
                continue
            
            # Добавляем индикаторы
            df = add_indicators(df)
            df = add_regime(df, regime_thresholds)
            
            # Загружаем BTC для market bias
            btc_df = load_candles_pkl('data/historical_candles', 'BTC_USDT', '1h')
            if btc_df is not None:
                btc_df = btc_df[btc_df.index.isin(df.index)].copy()
                btc_df = add_indicators(btc_df)
                
                # Добавляем market bias
                for i in range(len(df)):
                    current_time = df.index[i]
                    btc_slice = btc_df[btc_df.index <= current_time].tail(250)
                    if len(btc_slice) >= 200:
                        bias = compute_market_bias(btc_slice, 50, 200)
                        df.loc[current_time, 'mkt_long_ok'] = bias.get('mkt_long_ok', True)
                        df.loc[current_time, 'mkt_short_ok'] = bias.get('mkt_short_ok', True)
            
            # Заполняем пропуски
            df['mkt_long_ok'] = df['mkt_long_ok'].fillna(True)
            df['mkt_short_ok'] = df['mkt_short_ok'].fillna(True)
            
            # Генерируем сигналы
            signals = generate_signals(df, signal_params, symbol)
            
            if signals.empty:
                print(f"   ❌ Нет сигналов для {symbol}")
                continue
                
            print(f"   🎯 Сигналов: {len(signals)}")
            
            # Запускаем бэктест
            trades = run_backtest_one(
                df, symbol, margin_usdt, leverage, sl_atr_mult,
                trailing, fees, signals
            )
            
            if not trades.empty:
                all_trades.append(trades)
                
                # Статистика по символу
                total_pnl = trades['pnl_abs'].sum()
                wins = len(trades[trades['pnl_abs'] > 0])
                total_trades = len(trades)
                win_rate = wins / total_trades * 100 if total_trades > 0 else 0
                
                symbol_results[symbol] = {
                    'trades': total_trades,
                    'pnl': total_pnl,
                    'win_rate': win_rate
                }
                
                print(f"   ✅ Сделок: {total_trades}, PnL: {total_pnl:+.2f} USDT, WR: {win_rate:.1f}%")
            else:
                print(f"   ❌ Нет сделок для {symbol}")
                
        except Exception as e:
            print(f"   ❌ Ошибка {symbol}: {e}")
            continue
    
    # Общие результаты
    if all_trades:
        combined_trades = pd.concat(all_trades, ignore_index=True)
        
        print("\n" + "="*70)
        print("📈 ИТОГОВЫЕ РЕЗУЛЬТАТЫ")
        print("="*70)
        
        total_pnl = combined_trades['pnl_abs'].sum()
        total_trades = len(combined_trades)
        wins = len(combined_trades[combined_trades['pnl_abs'] > 0])
        win_rate = wins / total_trades * 100 if total_trades > 0 else 0
        
        # Profit Factor
        gross_wins = combined_trades[combined_trades['pnl_abs'] > 0]['pnl_abs'].sum()
        gross_losses = abs(combined_trades[combined_trades['pnl_abs'] <= 0]['pnl_abs'].sum())
        profit_factor = gross_wins / gross_losses if gross_losses > 0 else float('inf')
        
        print(f"💰 Общий PnL: {total_pnl:+.2f} USDT")
        print(f"🔄 Всего сделок: {total_trades}")
        print(f"📊 Win Rate: {win_rate:.1f}%")
        print(f"💎 Profit Factor: {profit_factor:.2f}")
        
        # Результаты по символам
        print(f"\n📊 ПО СИМВОЛАМ:")
        for symbol, result in symbol_results.items():
            print(f"   {symbol}: {result['trades']} сделок, {result['pnl']:+.2f} USDT, {result['win_rate']:.1f}% WR")
        
        # Сохраняем результаты
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"backtest_production_{timestamp}.csv"
        combined_trades.to_csv(filename, index=False)
        print(f"\n💾 Результаты сохранены: {filename}")
        
    else:
        print("\n❌ Нет данных для бэктеста")

if __name__ == "__main__":
    main()
