#!/usr/bin/env python3
"""
Оптимизированный бектест на годовых данных для быстрого сравнения
Текущая система vs Оригинальная система
"""

import argparse, yaml, pandas as pd
import numpy as np
from datetime import datetime
import sys
import os
import time

# Add the project root to Python path
sys.path.append('.')

from signalwarden_lite.core.data_loader import load_candles_pkl
from signalwarden_lite.core.features import add_indicators
from signalwarden_lite.core.regimes import add_regime, RegimeThresholds
from signalwarden_lite.core.market import compute_market_bias
from signalwarden_lite.core.signals import generate_signals, SignalParams
from signalwarden_lite.core.trailing import TrailingConfig
from signalwarden_lite.backtest.engine import run_backtest_one, FeesCfg

def _metrics(tr):
    """Быстрые метрики для сравнения"""
    if tr.empty: 
        return {'trades':0,'winrate':0.0,'pnl':0.0,'pf':0.0,'longs':0,'shorts':0,'avg_fee':0.0}
    
    wins, losses = tr[tr['pnl_abs']>0], tr[tr['pnl_abs']<=0]
    gw = wins['pnl_abs'].sum() if not wins.empty else 0.0
    gl = abs(losses['pnl_abs'].sum()) if not losses.empty else 0.0
    longs = len(tr[tr['side']=='LONG'])
    shorts = len(tr[tr['side']=='SHORT'])
    avg_fee = tr['fees'].mean() if 'fees' in tr.columns else 0.0
    
    return {
        'trades':len(tr), 'winrate':len(wins)/len(tr), 'pnl':tr['pnl_abs'].sum(), 
        'pf':(gw/gl) if gl>0 else float('inf'), 'longs':longs, 'shorts':shorts, 'avg_fee':avg_fee
    }

def _clip_period(df, start_ts, end_ts):
    """Обрезка данных по периоду"""
    if start_ts is None and end_ts is None:
        return df
    if start_ts is not None:
        df = df[df['timestamp'] >= start_ts]
    if end_ts is not None:
        df = df[df['timestamp'] <= end_ts]
    return df

def _prep_signals(df, cfg, gate):
    """Подготовка сигналов (оптимизированная версия)"""
    # Добавляем только необходимые индикаторы
    df = add_indicators(df, ema_fast=50, ema_slow=200, atr_p=cfg['regime']['natr_period'], 
                       rsi_p=cfg['short_guard'].get('rsi_period', 14))
    df = add_regime(df, RegimeThresholds(**cfg['regime']['calm_thresholds']))
    
    # Параметры сигналов
    s, st = cfg['signals'], cfg['signals']['setups']
    sp = SignalParams(
        lookback_calm=s['dynamic_lookback']['calm'], 
        lookback_normal=s['dynamic_lookback']['normal'], 
        lookback_high=s['dynamic_lookback']['high'],
        ltf_thinbar_k=s['ltf_thinbar_k'],
        long_cushion_calm=s['atr_cushion_long']['calm'], 
        long_cushion_normal=s['atr_cushion_long']['normal'], 
        long_cushion_high=s['atr_cushion_long']['high'],
        short_cushion_calm=s['atr_cushion_short']['calm'], 
        short_cushion_normal=s['atr_cushion_short']['normal'], 
        short_cushion_high=s['atr_cushion_short']['high'],
        setup_breakout=st['breakout']['enabled'], 
        setup_inside=st['inside_bar']['enabled'],
        setup_trend_cont=st['trend_continuation']['enabled'], 
        setup_squeeze=st['squeeze_breakout']['enabled'],
        ib_min_prev_range_k_atr=st['inside_bar']['min_prev_range_k_atr'],
        tc_min_body_k_range=st['trend_continuation']['min_body_k_range'], 
        tc_confirm_close_k_body=st['trend_continuation']['confirm_close_k_body'],
        bb_period=st['squeeze_breakout']['bb_period'], 
        bb_k=st['squeeze_breakout']['bb_k'], 
        width_k_perc=st['squeeze_breakout']['width_k_perc'],
        sg_rsi_bear_max=cfg['short_guard']['rsi_bear_max'], 
        sg_rsi_bullcorr_max=cfg['short_guard']['rsi_bullcorr_max'],
        sg_min_natr_bear=cfg['short_guard']['min_natr_bear'], 
        sg_min_natr_bullcorr=cfg['short_guard']['min_natr_bullcorr'],
        sg_require_close_below_ema20_bullcorr=cfg['short_guard']['require_close_below_ema20_bullcorr'],
        sg_slope_lookback=cfg['short_guard']['slope_lookback'],
        lg_rsi_long_min=52.0
    )
    return generate_signals(df, sp, market_gate=gate)

def run_system_backtest(cfg, data_dir, start_ts, end_ts, system_name, trailing_config, risk_config):
    """Запуск бектеста для конкретной системы"""
    print(f"\n🔍 {system_name}")
    print("=" * 60)
    
    # Загрузка BTC фильтра
    gate_1h = None
    try:
        btc_1h = load_candles_pkl(data_dir, cfg['market_filter']['symbol'], '1h')
        btc_1h = _clip_period(btc_1h, start_ts, end_ts)
        gate_1h = compute_market_bias(btc_1h, cfg['market_filter']['ema_fast'], cfg['market_filter']['ema_slow'])
        print(f"✅ BTC фильтр: {len(gate_1h)} баров")
    except Exception as e:
        print(f"⚠️ BTC фильтр: {e}")

    # Настройка комиссий
    fees = FeesCfg(
        maker_bps=cfg['fees']['maker_bps'], 
        taker_bps=cfg['fees']['taker_bps'],
        entry_liquidity=cfg['fees'].get('entry_liquidity', 'taker')
    )
    trailing = TrailingConfig(**trailing_config)
    
    # Обработка символов
    rows, all_tr = [], []
    symbols_to_process = cfg['symbols']  # Все символы для полного сравнения
    
    for sym in symbols_to_process:
        print(f"📊 {sym}...", end=" ")
        
        try:
            # 1h breakout trades
            df_1h = load_candles_pkl(data_dir, sym, '1h')
            df_1h = _clip_period(df_1h, start_ts, end_ts)
            sig_1h = _prep_signals(df_1h, cfg, gate_1h)
            
            # Только breakout сигналы
            sig_1h['allow_long']  = sig_1h.get('sig_long_breakout', False) & sig_1h.get('allow_long', False)
            sig_1h['allow_short'] = sig_1h.get('sig_short_breakout', False) & sig_1h.get('allow_short', False)
            
            tr_1h = run_backtest_one(sig_1h, sym, risk_config['margin_usdt'], 
                                   risk_config['leverage'], risk_config['sl_atr_mult'], 
                                   trailing, fees)
            
            # 15m LTF trades (для всех символов)
            tr_15m = pd.DataFrame()
            try:
                df_15m = load_candles_pkl(data_dir, sym, '15m')
                df_15m = _clip_period(df_15m, start_ts, end_ts)
                
                # Forward fill BTC gate to 15m
                gate_15m = None
                if gate_1h is not None and not gate_1h.empty:
                    gate_15m_data = []
                    for ts in df_15m['timestamp'].values:
                        mask = gate_1h['timestamp'] <= ts
                        if mask.any():
                            idx = mask.idxmax()
                            gate_15m_data.append({
                                'timestamp': ts,
                                'mkt_long_ok': gate_1h.iloc[idx]['mkt_long_ok'],
                                'mkt_short_ok': gate_1h.iloc[idx]['mkt_short_ok']
                            })
                        else:
                            gate_15m_data.append({'timestamp': ts, 'mkt_long_ok': False, 'mkt_short_ok': False})
                    gate_15m = pd.DataFrame(gate_15m_data)
                
                sig_15m = _prep_signals(df_15m, cfg, gate_15m)
                
                # LTF setups only
                ltf_long = sig_15m[['sig_long_inside', 'sig_long_tc', 'sig_long_sq']].any(axis=1)
                ltf_short = sig_15m[['sig_short_inside', 'sig_short_tc', 'sig_short_sq']].any(axis=1)
                
                sig_15m['allow_long'] = ltf_long & sig_15m.get('allow_long', False)
                sig_15m['allow_short'] = ltf_short & sig_15m.get('allow_short', False)
                
                tr_15m = run_backtest_one(sig_15m, sym, risk_config['margin_usdt'], 
                                        risk_config['leverage'], risk_config['sl_atr_mult'], 
                                        trailing, fees)
            except Exception as e:
                pass  # Игнорируем ошибки 15m для скорости

            # Объединяем результаты
            if not tr_1h.empty and not tr_15m.empty:
                tr = pd.concat([tr_1h, tr_15m]).sort_values('open_ts').reset_index(drop=True)
            elif not tr_1h.empty:
                tr = tr_1h
            elif not tr_15m.empty:
                tr = tr_15m
            else:
                tr = pd.DataFrame()
            
            # Метрики
            m = _metrics(tr)
            m['symbol'] = sym
            rows.append(m)
            
            if not tr.empty:
                all_tr.append(tr)
            
            print(f"{m['trades']} сделок, WR={m['winrate']:.1%}, PnL=${m['pnl']:.1f}")
            
        except Exception as e:
            print(f"❌ {e}")
            rows.append({'trades':0,'winrate':0.0,'pnl':0.0,'pf':0.0,'longs':0,'shorts':0,'avg_fee':0.0,'symbol':sym})

    # Результаты
    rep = pd.DataFrame(rows)
    if not rep.empty:
        rep = rep.sort_values('pf', ascending=False)
    
    if all_tr:
        all_trades = pd.concat(all_tr, ignore_index=True)
    else:
        all_trades = pd.DataFrame()
    
    return rep, all_trades

def main():
    print("🚀 ОПТИМИЗИРОВАННЫЙ ГОДОВОЙ БЕКТЕСТ")
    print("=" * 80)
    print("Сравнение: Текущая система vs Оригинальная система")
    print("=" * 80)
    
    # Параметры
    data_dir = 'data/historical_candles'
    config_file = 'signalwarden_lite/config/config_production.yaml'
    start_date = '2023-01-01'  # 2 года данных
    end_date = '2024-12-31'
    
    # Загрузка конфигурации
    with open(config_file, 'r') as f:
        cfg = yaml.safe_load(f)
    
    # Конвертация дат
    start_ts = int(pd.Timestamp(start_date, tz='UTC').timestamp())
    end_ts = int(pd.Timestamp(end_date, tz='UTC').timestamp())
    
    print(f"📅 Период: {start_date} to {end_date}")
    print(f"🎯 Профиль: {cfg['profile']}")
    print(f"📊 Символы: {len(cfg['symbols'])} пар")
    
    # Оригинальная система (базовая)
    original_trailing = {
        'activate_R': 0.35,
        'step_R': 0.20,
        'move_to_be_at_R': 0.35,
        'be_offset_R': 0.08,
        'chandelier_k_atr': 3.5,
        'level_1_pnl': 0.06,
        'level_1_keep_pct': 0.50,
        'level_2_pnl': 0.15,
        'level_2_keep_pct': 0.60,
        'level_3_pnl': 0.25,
        'level_3_keep_pct': 0.70,
        'level_4_pnl': 0.35,
        'level_4_keep_pct': 0.80
    }
    
    original_risk = {
        'margin_usdt': 21,
        'leverage': 5,
        'sl_atr_mult': 1.5
    }
    
    # Текущая система (из конфига)
    current_trailing = {
        'activate_R': cfg['trailing']['activate_R'],
        'step_R': cfg['trailing']['step_R'],
        'move_to_be_at_R': cfg['trailing']['move_to_be_at_R'],
        'be_offset_R': cfg['trailing']['be_offset_R'],
        'chandelier_k_atr': cfg['trailing']['chandelier_k_atr'],
        'level_1_pnl': cfg['trailing']['level_1_pnl'],
        'level_1_keep_pct': cfg['trailing']['level_1_keep_pct'],
        'level_2_pnl': cfg['trailing']['level_2_pnl'],
        'level_2_keep_pct': cfg['trailing']['level_2_keep_pct'],
        'level_3_pnl': cfg['trailing']['level_3_pnl'],
        'level_3_keep_pct': cfg['trailing']['level_3_keep_pct'],
        'level_4_pnl': cfg['trailing']['level_4_pnl'],
        'level_4_keep_pct': cfg['trailing']['level_4_keep_pct']
    }
    current_risk = cfg['risk']
    
    print(f"\n🔧 НАСТРОЙКИ СИСТЕМ:")
    print(f"   Оригинал: ${original_risk['margin_usdt']} позиция, {original_risk['sl_atr_mult']}x SL, {original_trailing['activate_R']}R активация")
    print(f"   Текущая: ${current_risk['margin_usdt']} позиция, {current_risk['sl_atr_mult']}x SL, {current_trailing['activate_R']}R активация")
    
    # Запуск бектестов
    start_time = time.time()
    
    # Оригинальная система
    print(f"\n⏱️ Запуск оригинального бектеста...")
    orig_rep, orig_trades = run_system_backtest(
        cfg, data_dir, start_ts, end_ts, 
        "ОРИГИНАЛЬНАЯ СИСТЕМА", original_trailing, original_risk
    )
    
    # Текущая система
    print(f"\n⏱️ Запуск текущего бектеста...")
    curr_rep, curr_trades = run_system_backtest(
        cfg, data_dir, start_ts, end_ts, 
        "ТЕКУЩАЯ СИСТЕМА", current_trailing, current_risk
    )
    
    elapsed = time.time() - start_time
    print(f"\n⏱️ Время выполнения: {elapsed:.1f} секунд")
    
    # Сравнение результатов
    print("\n" + "="*80)
    print("📊 СРАВНЕНИЕ РЕЗУЛЬТАТОВ")
    print("="*80)
    
    if not orig_rep.empty and not curr_rep.empty:
        # Сводная таблица
        comparison_data = []
        
        # Оригинальная система
        orig_total_pnl = orig_rep['pnl'].sum()
        orig_total_trades = orig_rep['trades'].sum()
        orig_active_pairs = len(orig_rep[orig_rep['trades'] > 0])
        orig_avg_wr = orig_rep[orig_rep['trades'] > 0]['winrate'].mean() if orig_active_pairs > 0 else 0
        orig_avg_pf = orig_rep[orig_rep['trades'] > 0]['pf'].replace([np.inf, -np.inf], np.nan).mean() if orig_active_pairs > 0 else 0
        
        # Текущая система
        curr_total_pnl = curr_rep['pnl'].sum()
        curr_total_trades = curr_rep['trades'].sum()
        curr_active_pairs = len(curr_rep[curr_rep['trades'] > 0])
        curr_avg_wr = curr_rep[curr_rep['trades'] > 0]['winrate'].mean() if curr_active_pairs > 0 else 0
        curr_avg_pf = curr_rep[curr_rep['trades'] > 0]['pf'].replace([np.inf, -np.inf], np.nan).mean() if curr_active_pairs > 0 else 0
        
        print(f"🎯 ОРИГИНАЛЬНАЯ СИСТЕМА:")
        print(f"   💰 PnL: ${orig_total_pnl:.1f}")
        print(f"   📈 Сделки: {orig_total_trades}")
        print(f"   🎯 Активные пары: {orig_active_pairs}")
        print(f"   ✅ WR: {orig_avg_wr:.1%}")
        print(f"   ⚖️ PF: {orig_avg_pf:.2f}")
        
        print(f"\n🎯 ТЕКУЩАЯ СИСТЕМА:")
        print(f"   💰 PnL: ${curr_total_pnl:.1f}")
        print(f"   📈 Сделки: {curr_total_trades}")
        print(f"   🎯 Активные пары: {curr_active_pairs}")
        print(f"   ✅ WR: {curr_avg_wr:.1%}")
        print(f"   ⚖️ PF: {curr_avg_pf:.2f}")
        
        # Изменения
        pnl_change = curr_total_pnl - orig_total_pnl
        pnl_change_pct = (pnl_change / abs(orig_total_pnl)) * 100 if orig_total_pnl != 0 else 0
        
        print(f"\n📊 ИЗМЕНЕНИЯ:")
        print(f"   💰 PnL: {pnl_change:+.1f} ({pnl_change_pct:+.1f}%)")
        print(f"   📈 Сделки: {curr_total_trades - orig_total_trades:+d}")
        print(f"   🎯 Активные пары: {curr_active_pairs - orig_active_pairs:+d}")
        print(f"   ✅ WR: {(curr_avg_wr - orig_avg_wr)*100:+.1f}pp")
        print(f"   ⚖️ PF: {curr_avg_pf - orig_avg_pf:+.2f}")
        
        # Вывод
        if pnl_change > 0:
            print(f"\n✅ ТЕКУЩАЯ СИСТЕМА ЛУЧШЕ на ${pnl_change:.1f}")
        elif pnl_change < 0:
            print(f"\n❌ ОРИГИНАЛЬНАЯ СИСТЕМА ЛУЧШЕ на ${abs(pnl_change):.1f}")
        else:
            print(f"\n⚖️ СИСТЕМЫ ПОКАЗАЛИ ОДИНАКОВЫЙ РЕЗУЛЬТАТ")
    
    # Сохранение результатов
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if not orig_rep.empty:
        orig_rep.to_csv(f'backtest_report_ORIGINAL_year_{timestamp}.csv', index=False)
    if not curr_rep.empty:
        curr_rep.to_csv(f'backtest_report_CURRENT_year_{timestamp}.csv', index=False)
    
    if not orig_trades.empty:
        orig_trades.to_csv(f'backtest_trades_ORIGINAL_year_{timestamp}.csv', index=False)
    if not curr_trades.empty:
        curr_trades.to_csv(f'backtest_trades_CURRENT_year_{timestamp}.csv', index=False)
    
    print(f"\n💾 Результаты сохранены с timestamp: {timestamp}")

if __name__ == '__main__':
    main()
