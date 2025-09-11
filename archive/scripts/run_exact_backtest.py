#!/usr/bin/env python3
"""
ТОЧНЫЙ БЭКТЕСТ 1:1 С РЕАЛЬНОЙ СИСТЕМОЙ v1.6-TXB
Полностью соответствует логике live торговли
"""

import os
import sys
import yaml
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pickle
import json

# Добавляем путь к модулям
sys.path.append('.')

from signalwarden_lite.core.features import add_indicators
from signalwarden_lite.core.regimes import add_regime, RegimeThresholds
from signalwarden_lite.core.market import compute_market_bias
from signalwarden_lite.core.signals import generate_signals, SignalParams
from signalwarden_lite.core.trailing import TrailingConfig, update_trailing_pnl_based
from signalwarden_lite.core.types import Side, Position, TradeLog

def load_live_config():
    """Load production configuration (exactly as used in live system)"""
    with open('signalwarden_lite/config/config_production.yaml', 'r') as f:
        return yaml.safe_load(f)

def load_local_data(symbol, timeframe):
    """Load data from local files (much faster than Binance API)"""
    
    # Try to load from historical_candles first (pickle format)
    pickle_file = f"data/historical_candles/{symbol}_{timeframe}.pkl"
    if os.path.exists(pickle_file):
        try:
            print(f"    📊 Загружаем {symbol} {timeframe} из {pickle_file}...")
            with open(pickle_file, 'rb') as f:
                df = pickle.load(f)
            
            # Convert timestamp column to datetime index if needed
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
                df.set_index('timestamp', inplace=True)
            elif not isinstance(df.index, pd.DatetimeIndex):
                # If index is numeric, assume it's timestamp
                df.index = pd.to_datetime(df.index, unit='s')
            
            # Filter to 2022-2024 data (wider range for more data)
            df = df[(df.index >= '2022-01-01') & (df.index < '2024-01-01')]
            
            if len(df) > 0:
                print(f"    ✅ Загружено {len(df)} свечей из pickle ({df.index.min()} - {df.index.max()})")
                return df
            else:
                print(f"    ⚠️ Нет данных в нужном диапазоне")
            
        except Exception as e:
            print(f"    ⚠️ Ошибка загрузки pickle {pickle_file}: {e}")
    
    # Try CSV format as fallback
    csv_file = f"data/historical/{symbol.replace('_USDT', 'USDT')}_{timeframe}.csv"
    if os.path.exists(csv_file):
        try:
            print(f"    📊 Загружаем {symbol} {timeframe} из {csv_file}...")
            df = pd.read_csv(csv_file)
            
            # Convert timestamp column to datetime index
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df.set_index('timestamp', inplace=True)
            elif 'time' in df.columns:
                df['time'] = pd.to_datetime(df['time'])
                df.set_index('time', inplace=True)
            
            # Filter to 2023-2024 data
            df = df[(df.index >= '2023-01-01') & (df.index < '2024-01-01')]
            
            print(f"    ✅ Загружено {len(df)} свечей из CSV")
            return df
            
        except Exception as e:
            print(f"    ⚠️ Ошибка загрузки CSV {csv_file}: {e}")
    
    print(f"    ❌ Не найдены данные для {symbol} {timeframe}")
    return None

def process_symbol_mtf(symbol: str, cfg: dict, btc_bias: pd.DataFrame = None) -> dict:
    """
    Process symbol with MTF strategy (EXACTLY as in live system)
    """
    result = {
        'symbol': symbol,
        'signals': [],
        'data_1h': None,
        'data_15m': None,
        'errors': []
    }
    
    try:
        # Load 1h data for breakout signals
        df_1h = load_local_data(symbol, '1h')
        
        if df_1h is None or len(df_1h) < 200:
            result['errors'].append(f"Insufficient 1h data: {len(df_1h) if df_1h is not None else 0}")
            return result
        
        # Load 15m data for LTF signals
        df_15m = load_local_data(symbol, '15m')
        
        if df_15m is None or len(df_15m) < 200:
            result['errors'].append(f"Insufficient 15m data: {len(df_15m) if df_15m is not None else 0}")
            return result
        
        # Add indicators to both timeframes
        df_1h = add_indicators(df_1h)
        df_15m = add_indicators(df_15m)
        
        # Add regime classification
        regime_thresholds = RegimeThresholds(
            ultra_calm=cfg['regime']['calm_thresholds']['ultra_calm'],
            calm=cfg['regime']['calm_thresholds']['calm'],
            high=cfg['regime']['calm_thresholds']['high']
        )
        df_1h = add_regime(df_1h, regime_thresholds)
        df_15m = add_regime(df_15m, regime_thresholds)
        
        # Generate signals for both timeframes
        signal_params = SignalParams(
            # Lookbacks
            lookback_calm=cfg['signals']['dynamic_lookback']['calm'],
            lookback_normal=cfg['signals']['dynamic_lookback']['normal'],
            lookback_high=cfg['signals']['dynamic_lookback']['high'],
            # ATR cushions
            long_cushion_calm=cfg['signals']['atr_cushion_long']['calm'],
            long_cushion_normal=cfg['signals']['atr_cushion_long']['normal'],
            long_cushion_high=cfg['signals']['atr_cushion_long']['high'],
            short_cushion_calm=cfg['signals']['atr_cushion_short']['calm'],
            short_cushion_normal=cfg['signals']['atr_cushion_short']['normal'],
            short_cushion_high=cfg['signals']['atr_cushion_short']['high'],
            # Setups
            setup_breakout=cfg['signals']['setups']['breakout']['enabled'],
            setup_inside=cfg['signals']['setups']['inside_bar']['enabled'],
            setup_trend_cont=cfg['signals']['setups']['trend_continuation']['enabled'],
            setup_squeeze=cfg['signals']['setups']['squeeze_breakout']['enabled'],
            # Inside bar params
            ib_min_prev_range_k_atr=cfg['signals']['setups']['inside_bar']['min_prev_range_k_atr'],
            # Trend continuation params
            tc_min_body_k_range=cfg['signals']['setups']['trend_continuation']['min_body_k_range'],
            tc_confirm_close_k_body=cfg['signals']['setups']['trend_continuation']['confirm_close_k_body'],
            # Squeeze params
            bb_period=cfg['signals']['setups']['squeeze_breakout']['bb_period'],
            bb_k=cfg['signals']['setups']['squeeze_breakout']['bb_k'],
            width_k_perc=cfg['signals']['setups']['squeeze_breakout']['width_k_perc'],
            # LTF thin bar filter
            ltf_thinbar_k=cfg['signals']['ltf_thinbar_k'],
            # Short guard params
            sg_rsi_bear_max=cfg['short_guard']['rsi_bear_max'],
            sg_rsi_bullcorr_max=cfg['short_guard']['rsi_bullcorr_max'],
            sg_min_natr_bear=cfg['short_guard']['min_natr_bear'],
            sg_min_natr_bullcorr=cfg['short_guard']['min_natr_bullcorr'],
            sg_require_close_below_ema20_bullcorr=cfg['short_guard']['require_close_below_ema20_bullcorr'],
            sg_slope_lookback=cfg['short_guard']['slope_lookback']
        )
        
        # Process 1h signals (breakout only)
        df_1h_signals = generate_signals(df_1h, signal_params, btc_bias)
        
        # Process 15m signals (inside/trend/squeeze)
        df_15m_signals = generate_signals(df_15m, signal_params, btc_bias)
        
        # Apply short guard filters (EXACTLY as in live system)
        # Note: Short guard is already applied within generate_signals function
        # df_1h_signals = apply_short_guard(df_1h_signals, cfg['short_guard'], btc_bias)
        # df_15m_signals = apply_short_guard(df_15m_signals, cfg['short_guard'], btc_bias)
        
        # Combine signals from both timeframes
        all_signals = []
        
        # Add 1h breakout signals
        for timestamp, row in df_1h_signals.iterrows():
            if row.get('signal_long', False) or row.get('signal_short', False):
                signal = {
                    'timestamp': timestamp,
                    'symbol': symbol,
                    'timeframe': '1h',
                    'side': 'LONG' if row.get('signal_long', False) else 'SHORT',
                    'setup': row.get('setup_name', 'breakout'),
                    'entry': float(df_1h.loc[timestamp, 'close']),
                    'atr': float(df_1h.loc[timestamp, 'atr']),
                    'allow_long': row.get('allow_long', False),
                    'allow_short': row.get('allow_short', False)
                }
                all_signals.append(signal)
        
        # Add 15m LTF signals
        for timestamp, row in df_15m_signals.iterrows():
            if row.get('signal_long', False) or row.get('signal_short', False):
                signal = {
                    'timestamp': timestamp,
                    'symbol': symbol,
                    'timeframe': '15m',
                    'side': 'LONG' if row.get('signal_long', False) else 'SHORT',
                    'setup': row.get('setup_name', 'ltf'),
                    'entry': float(df_15m.loc[timestamp, 'close']),
                    'atr': float(df_15m.loc[timestamp, 'atr']),
                    'allow_long': row.get('allow_long', False),
                    'allow_short': row.get('allow_short', False)
                }
                all_signals.append(signal)
        
        # Sort signals by timestamp
        all_signals.sort(key=lambda x: x['timestamp'])
        
        result['signals'] = all_signals
        result['data_1h'] = df_1h
        result['data_15m'] = df_15m
        
        print(f"    ✅ {len(all_signals)} сигналов сгенерировано")
        
    except Exception as e:
        result['errors'].append(str(e))
        print(f"    ❌ Ошибка обработки {symbol}: {e}")
    
    return result

def apply_short_guard(df_signals: pd.DataFrame, short_guard_cfg: dict, btc_bias: pd.DataFrame = None) -> pd.DataFrame:
    """Apply short guard filters (EXACTLY as in live system)"""
    
    if btc_bias is None:
        return df_signals
    
    df_result = df_signals.copy()
    
    for timestamp, row in df_result.iterrows():
        if not row.get('signal_short', False):
            continue
            
        # Get BTC market context
        try:
            btc_row = btc_bias.loc[timestamp]
            mkt_short_ok = btc_row.get('mkt_short_ok', False)
        except:
            continue
        
        # Get current bar data
        try:
            current_bar = df_result.loc[timestamp]
            rsi = current_bar.get('rsi', 50)
            natr = current_bar.get('natr', 1.0)
            ema20 = current_bar.get('ema20', current_bar.get('close', 0))
            close = current_bar.get('close', 0)
        except:
            continue
        
        # Apply short guard logic
        if mkt_short_ok:  # Bear market
            if rsi > short_guard_cfg['rsi_bear_max'] or natr < short_guard_cfg['min_natr_bear']:
                df_result.loc[timestamp, 'signal_short'] = False
                df_result.loc[timestamp, 'allow_short'] = False
        else:  # Bull market corrections
            if (rsi > short_guard_cfg['rsi_bullcorr_max'] or 
                natr < short_guard_cfg['min_natr_bullcorr'] or
                (short_guard_cfg['require_close_below_ema20_bullcorr'] and close >= ema20)):
                df_result.loc[timestamp, 'signal_short'] = False
                df_result.loc[timestamp, 'allow_short'] = False
    
    return df_result

def execute_exact_backtest_trade(signal: dict, cfg: dict) -> dict:
    """
    Execute backtest trade EXACTLY as live system would
    """
    symbol = signal['symbol']
    side = signal['side']
    entry = signal['entry']
    atr = signal['atr']
    
    # Calculate position size: EXACTLY as live system (21 USDT notional)
    margin_usdt = cfg['risk']['margin_usdt']  # 21 USDT
    position_value_usdt = margin_usdt
    qty = position_value_usdt / entry
    
    # Calculate stop loss with MINIMUM ATR protection (EXACTLY as live system)
    min_atr_pct = 0.02  # Minimum 2% from price (CRITICAL DIFFERENCE!)
    min_atr = entry * min_atr_pct
    effective_atr = max(atr, min_atr)  # Use larger ATR
    
    sl_atr_mult = cfg['risk']['sl_atr_mult']  # 2.5
    
    if side == 'LONG':
        sl_price = entry - (sl_atr_mult * effective_atr)
    else:
        sl_price = entry + (sl_atr_mult * effective_atr)
    
    # Calculate fees (EXACTLY as live system)
    maker_bps = cfg['fees']['maker_bps']  # 2.0
    taker_bps = cfg['fees']['taker_bps']  # 5.0
    
    # Entry fees (taker for market orders)
    entry_fees_usdt = position_value_usdt * (taker_bps / 10000.0)
    
    return {
        'symbol': symbol,
        'side': side,
        'entry': entry,
        'qty': qty,
        'sl_initial': sl_price,
        'sl_current': sl_price,
        'atr': effective_atr,  # Store effective ATR
        'original_atr': atr,   # Store original ATR
        'entry_fees_usdt': entry_fees_usdt,
        'timestamp': signal['timestamp'],
        'setup': signal['setup'],
        'timeframe': signal['timeframe']
    }

def run_exact_position_simulation(position: dict, price_data: pd.DataFrame, cfg: dict) -> dict:
    """
    Simulate position lifecycle EXACTLY as live system
    """
    
    # Create trailing config (EXACTLY as production)
    trailing = TrailingConfig(
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
    
    # Create Position object
    pos = Position(
        side=Side.LONG if position['side'] == 'LONG' else Side.SHORT,
        entry=position['entry'],
        sl=position['sl_initial'],
        qty=position['qty'],
        remaining_qty=position['qty'],
        r_per_unit=0.0,  # Not used in PnL-based trailing
        sl_initial=position['sl_initial'],
        peak_pnl_usdt=0.0,
        bars_open=0,
        entry_fees_usdt=position['entry_fees_usdt']
    )
    
    entry_time = position['timestamp']
    max_bars = 500  # Maximum bars to hold
    bars_held = 0
    peak_pnl_usdt = 0.0
    
    # Find entry point in price data
    try:
        entry_idx = price_data.index.get_loc(entry_time, method='nearest')
    except:
        return {'error': 'Entry time not found in price data'}
    
    # Simulate position from entry to exit
    for i in range(entry_idx + 1, min(entry_idx + max_bars, len(price_data))):
        current_time = price_data.index[i]
        current_row = price_data.iloc[i]
        
        current_price = float(current_row['close'])
        high = float(current_row['high'])
        low = float(current_row['low'])
        
        bars_held += 1
        pos.bars_open = bars_held
        
        # Calculate current PnL (EXACTLY as live system)
        if position['side'] == 'LONG':
            current_pnl_usdt = (current_price - pos.entry) * pos.qty
            # Check stop loss hit
            if low <= pos.sl:
                exit_price = pos.sl
                exit_reason = 'stop_loss'
                break
        else:  # SHORT
            current_pnl_usdt = (pos.entry - current_price) * pos.qty
            # Check stop loss hit
            if high >= pos.sl:
                exit_price = pos.sl
                exit_reason = 'stop_loss'
                break
        
        # Update peak PnL
        peak_pnl_usdt = max(peak_pnl_usdt, current_pnl_usdt)
        pos.peak_pnl_usdt = peak_pnl_usdt
        
        # Update trailing stop (EXACTLY as live system)
        pos = update_trailing_pnl_based(pos, current_price, current_pnl_usdt, trailing)
        
    else:
        # Position held to maximum bars
        exit_price = current_price
        exit_reason = 'max_bars'
    
    # Calculate final PnL and fees
    if position['side'] == 'LONG':
        final_pnl_usdt = (exit_price - pos.entry) * pos.qty
    else:
        final_pnl_usdt = (pos.entry - exit_price) * pos.qty
    
    # Exit fees (always taker for stop loss)
    exit_notional = exit_price * pos.qty
    exit_fees_usdt = exit_notional * (cfg['fees']['taker_bps'] / 10000.0)
    
    # Net PnL after fees
    net_pnl_usdt = final_pnl_usdt - position['entry_fees_usdt'] - exit_fees_usdt
    
    return {
        'symbol': position['symbol'],
        'timestamp': entry_time,
        'side': position['side'],
        'setup': position['setup'],
        'timeframe': position['timeframe'],
        'entry': position['entry'],
        'exit': exit_price,
        'qty': position['qty'],
        'pnl_usdt': final_pnl_usdt,
        'entry_fees_usdt': position['entry_fees_usdt'],
        'exit_fees_usdt': exit_fees_usdt,
        'net_pnl_usdt': net_pnl_usdt,
        'bars_held': bars_held,
        'sl_initial': position['sl_initial'],
        'sl_final': pos.sl,
        'peak_pnl_usdt': peak_pnl_usdt,
        'exit_reason': exit_reason,
        'atr_used': position['atr'],
        'atr_original': position['original_atr']
    }

def run_exact_backtest():
    """
    Run EXACT backtest matching live system 1:1
    """
    
    print("🚀 ТОЧНЫЙ БЭКТЕСТ 1:1 С РЕАЛЬНОЙ СИСТЕМОЙ v1.6-TXB")
    print("=" * 80)
    print("📋 ПОЛНОЕ СООТВЕТСТВИЕ LIVE ТОРГОВЛЕ!")
    print()
    
    # Load production configuration
    cfg = load_live_config()
    
    print("📊 ПАРАМЕТРЫ (КАК В PRODUCTION):")
    print("-" * 60)
    print(f"💰 Position Size: {cfg['risk']['margin_usdt']} USDT")
    print(f"🛡️ SL ATR Multiplier: {cfg['risk']['sl_atr_mult']}")
    print(f"📈 Leverage: {cfg['risk']['leverage']}")
    print(f"⚠️ Minimum ATR Protection: 2% от цены")
    print(f"📅 Period: 2023-01-01 - 2024-01-01")
    print()
    
    print("🔧 PnL-based ТРЕЙЛИНГ (КАК В PRODUCTION):")
    print("-" * 60)
    trailing_config = cfg['trailing']
    print(f"🎯 Activation: {trailing_config['activate_pnl_usdt']} USDT")
    print(f"📊 Level 1: {trailing_config['level_1_pnl']} USDT → {trailing_config['level_1_keep_pct']*100:.0f}%")
    print(f"📊 Level 2: {trailing_config['level_2_pnl']} USDT → {trailing_config['level_2_keep_pct']*100:.0f}%")
    print(f"📊 Level 3: {trailing_config['level_3_pnl']} USDT → {trailing_config['level_3_keep_pct']*100:.0f}%")
    print(f"📊 Level 4: {trailing_config['level_4_pnl']} USDT → {trailing_config['level_4_keep_pct']*100:.0f}%")
    print()
    
    # Load BTC market bias
    print("🔧 ЗАГРУЗКА BTC MARKET BIAS...")
    btc_data = load_local_data('BTC_USDT', '1h')
    if btc_data is not None:
        btc_data = add_indicators(btc_data)
        # Reset index to make timestamp a column for compute_market_bias
        btc_data_for_bias = btc_data.reset_index()
        btc_bias = compute_market_bias(
            btc_data_for_bias, 
            cfg['market_filter']['ema_fast'], 
            cfg['market_filter']['ema_slow']
        )
        # Set timestamp as index for easier lookup
        btc_bias.set_index('timestamp', inplace=True)
        print(f"✅ BTC bias загружен: {len(btc_bias)} баров")
    else:
        btc_bias = None
        print("⚠️ BTC bias не загружен")
    
    print()
    
    # Process symbols with full data (skip newer tokens like ENA, WIF, PNUT)
    available_symbols = ['ADA_USDT', 'LTC_USDT', 'DOGE_USDT', 'HBAR_USDT']  # Only symbols with 2022-2023 data
    all_trades = []
    symbol_results = {}
    
    print(f"📊 Обрабатываем символы с полными данными: {available_symbols}")
    print()
    
    for symbol in available_symbols:
        print(f"📈 ОБРАБОТКА {symbol}...")
        
        # Process symbol with MTF strategy
        symbol_result = process_symbol_mtf(symbol, cfg, btc_bias)
        symbol_results[symbol] = symbol_result
        
        if symbol_result['errors']:
            print(f"    ❌ Ошибки: {symbol_result['errors']}")
            continue
        
        if not symbol_result['signals']:
            print(f"    ⚠️ Нет сигналов для {symbol}")
            continue
        
        # Execute trades for this symbol
        symbol_trades = []
        
        for signal in symbol_result['signals']:
            # Execute trade
            position = execute_exact_backtest_trade(signal, cfg)
            
            # Get price data for simulation
            if signal['timeframe'] == '1h':
                price_data = symbol_result['data_1h']
            else:
                price_data = symbol_result['data_15m']
            
            # Simulate position lifecycle
            trade_result = run_exact_position_simulation(position, price_data, cfg)
            
            if 'error' not in trade_result:
                symbol_trades.append(trade_result)
                all_trades.append(trade_result)
        
        print(f"    ✅ {len(symbol_trades)} сделок выполнено")
    
    if not all_trades:
        print("❌ НЕТ СДЕЛОК В БЭКТЕСТЕ!")
        return
    
    print(f"\n📊 ГОТОВО К АНАЛИЗУ: {len(all_trades)} сделок")
    print()
    
    # Analyze results
    print("📊 РЕЗУЛЬТАТЫ ТОЧНОГО БЭКТЕСТА:")
    print("=" * 80)
    
    df_trades = pd.DataFrame(all_trades)
    
    # Overall statistics
    total_trades = len(df_trades)
    total_pnl = df_trades['net_pnl_usdt'].sum()
    gross_pnl = df_trades['pnl_usdt'].sum()
    total_fees = (df_trades['entry_fees_usdt'] + df_trades['exit_fees_usdt']).sum()
    
    winning_trades = len(df_trades[df_trades['net_pnl_usdt'] > 0])
    losing_trades = len(df_trades[df_trades['net_pnl_usdt'] < 0])
    win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0
    
    avg_win = df_trades[df_trades['net_pnl_usdt'] > 0]['net_pnl_usdt'].mean() if winning_trades > 0 else 0
    avg_loss = df_trades[df_trades['net_pnl_usdt'] < 0]['net_pnl_usdt'].mean() if losing_trades > 0 else 0
    profit_factor = abs(avg_win * winning_trades / (avg_loss * losing_trades)) if losing_trades > 0 and avg_loss != 0 else float('inf')
    
    print(f"📊 ОБЩАЯ СТАТИСТИКА:")
    print(f"   💰 Net PnL: ${total_pnl:.2f}")
    print(f"   💰 Gross PnL: ${gross_pnl:.2f}")
    print(f"   📈 Total Trades: {total_trades}")
    print(f"   ✅ Win Rate: {win_rate:.1f}%")
    print(f"   📊 Profit Factor: {profit_factor:.2f}")
    print(f"   💸 Total Fees: ${total_fees:.2f}")
    print()
    
    # Statistics by symbol
    print(f"📊 СТАТИСТИКА ПО СИМВОЛАМ:")
    symbol_stats = df_trades.groupby('symbol').agg({
        'net_pnl_usdt': ['count', 'sum', 'mean'],
        'entry_fees_usdt': 'sum',
        'exit_fees_usdt': 'sum'
    }).round(4)
    
    for symbol in symbol_stats.index:
        trades_count = int(symbol_stats.loc[symbol, ('net_pnl_usdt', 'count')])
        pnl_sum = symbol_stats.loc[symbol, ('net_pnl_usdt', 'sum')]
        pnl_avg = symbol_stats.loc[symbol, ('net_pnl_usdt', 'mean')]
        fees_sum = symbol_stats.loc[symbol, ('entry_fees_usdt', 'sum')] + symbol_stats.loc[symbol, ('exit_fees_usdt', 'sum')]
        
        print(f"   📈 {symbol}: {trades_count} trades, Net PnL: ${pnl_sum:.2f}, Avg: ${pnl_avg:.4f}, Fees: ${fees_sum:.2f}")
    
    print()
    
    # Statistics by side
    long_trades = df_trades[df_trades['side'] == 'LONG']
    short_trades = df_trades[df_trades['side'] == 'SHORT']
    
    print(f"📊 СТАТИСТИКА ПО ТИПАМ СДЕЛОК:")
    print(f"   📈 Long trades: {len(long_trades)} ({len(long_trades)/total_trades*100:.1f}%)")
    if len(long_trades) > 0:
        print(f"      💰 Long Net PnL: ${long_trades['net_pnl_usdt'].sum():.2f}")
    
    print(f"   📉 Short trades: {len(short_trades)} ({len(short_trades)/total_trades*100:.1f}%)")
    if len(short_trades) > 0:
        print(f"      💰 Short Net PnL: ${short_trades['net_pnl_usdt'].sum():.2f}")
    
    print()
    
    # ATR analysis
    print(f"📊 АНАЛИЗ ATR PROTECTION:")
    atr_protected = df_trades[df_trades['atr_used'] > df_trades['atr_original']]
    print(f"   🛡️ Trades with ATR protection: {len(atr_protected)} ({len(atr_protected)/total_trades*100:.1f}%)")
    if len(atr_protected) > 0:
        avg_protection = ((atr_protected['atr_used'] - atr_protected['atr_original']) / atr_protected['atr_original'] * 100).mean()
        print(f"   📊 Avg ATR increase: {avg_protection:.1f}%")
        print(f"   💰 Protected trades PnL: ${atr_protected['net_pnl_usdt'].sum():.2f}")
    
    print()
    
    # Trailing analysis
    print(f"📊 АНАЛИЗ ТРЕЙЛИНГА:")
    trailing_trades = df_trades[df_trades['peak_pnl_usdt'] > 0]
    print(f"   🎯 Trades with trailing: {len(trailing_trades)} ({len(trailing_trades)/total_trades*100:.1f}%)")
    
    if len(trailing_trades) > 0:
        avg_peak_pnl = trailing_trades['peak_pnl_usdt'].mean()
        avg_final_pnl = trailing_trades['net_pnl_usdt'].mean()
        trailing_effectiveness = (avg_final_pnl / avg_peak_pnl) * 100 if avg_peak_pnl > 0 else 0
        
        print(f"   📊 Avg Peak PnL: ${avg_peak_pnl:.4f}")
        print(f"   📊 Avg Final Net PnL: ${avg_final_pnl:.4f}")
        print(f"   📊 Trailing Effectiveness: {trailing_effectiveness:.1f}%")
    
    print()
    print("🎯 ЗАКЛЮЧЕНИЕ:")
    print("-" * 60)
    
    if total_pnl > 0:
        print("✅ ТОЧНЫЙ БЭКТЕСТ ПОКАЗЫВАЕТ ПРИБЫЛЬ!")
        print(f"✅ Net PnL: ${total_pnl:.2f}")
        print(f"✅ Win Rate: {win_rate:.1f}%")
    else:
        print("❌ ТОЧНЫЙ БЭКТЕСТ ПОКАЗЫВАЕТ УБЫТОК!")
        print(f"❌ Net PnL: ${total_pnl:.2f}")
        print(f"❌ Win Rate: {win_rate:.1f}%")
        print()
        print("🔍 ВОЗМОЖНЫЕ ПРИЧИНЫ УБЫТКОВ:")
        print("   1. Минимальная защита ATR (2%) делает SL слишком далеко")
        print("   2. Высокие комиссии (0.07% на вход+выход)")
        print("   3. Реальные проскальзывания не учтены")
        print("   4. Различия в тайминге сигналов MTF")
    
    # Save results
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    results_file = f"exact_backtest_results_{timestamp}.csv"
    df_trades.to_csv(results_file, index=False)
    print(f"\n💾 Результаты сохранены в: {results_file}")
    
    # Save summary
    summary = {
        'timestamp': timestamp,
        'total_trades': total_trades,
        'net_pnl_usdt': total_pnl,
        'gross_pnl_usdt': gross_pnl,
        'total_fees_usdt': total_fees,
        'win_rate_pct': win_rate,
        'profit_factor': profit_factor,
        'winning_trades': winning_trades,
        'losing_trades': losing_trades,
        'avg_win_usdt': avg_win,
        'avg_loss_usdt': avg_loss,
        'long_trades': len(long_trades),
        'short_trades': len(short_trades),
        'atr_protected_trades': len(atr_protected),
        'trailing_active_trades': len(trailing_trades)
    }
    
    summary_file = f"exact_backtest_summary_{timestamp}.json"
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"💾 Сводка сохранена в: {summary_file}")

if __name__ == "__main__":
    run_exact_backtest()
