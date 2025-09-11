# Бэктест ТЕКУЩЕЙ системы (оригинальная стратегия + улучшенный R-based трейлинг)
import argparse, yaml, pandas as pd
import numpy as np
from datetime import datetime
import sys
import os

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
    if tr.empty: return {'trades':0,'winrate':0.0,'pnl':0.0,'pf':0.0,'longs':0,'shorts':0,'avg_fee':0.0}
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
    if start_ts is None and end_ts is None:
        return df
    if start_ts is not None:
        df = df[df['timestamp'] >= start_ts]
    if end_ts is not None:
        df = df[df['timestamp'] <= end_ts]
    return df

def _prep(df, cfg, gate):
    df = add_indicators(df, ema_fast=50, ema_slow=200, atr_p=cfg['regime']['natr_period'], 
                       rsi_p=cfg['short_guard'].get('rsi_period', 14))
    df = add_regime(df, RegimeThresholds(**cfg['regime']['calm_thresholds']))
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

def main():
    print("🔍 ТЕКУЩИЙ БЭКТЕСТ v1.6-TXB (с улучшенным R-трейлингом)")
    print("=" * 60)
    
    # Fixed parameters for current system
    data_dir = 'data/historical_candles'
    config_file = 'signalwarden_lite/config/config_production.yaml'
    start_date = '2022-01-01'
    end_date = '2024-01-01'
    
    # Load config
    with open(config_file, 'r') as f:
        cfg = yaml.safe_load(f)
    
    print("🔧 НАСТРОЙКИ ТЕКУЩЕЙ СИСТЕМЫ:")
    print(f"   💰 Размер позиции: ${cfg['risk']['margin_usdt']} USDT")
    print(f"   🛡️ SL множитель: {cfg['risk']['sl_atr_mult']}x ATR")
    print(f"   📊 R-трейлинг: активация {cfg['trailing']['activate_R']}R, шаг {cfg['trailing']['step_R']}R")
    print(f"   🔒 Минимум: {cfg['trailing']['min_keep_R']}R (общий)")
    print("   🛡️ ИНДИВИДУАЛЬНЫЕ ПОРОГИ:")
    for symbol, min_keep in cfg['trailing']['symbol_min_keep'].items():
        print(f"      {symbol}: {min_keep}R минимум")
    print()
    
    # Convert dates to timestamps (seconds)
    start_ts = int(pd.Timestamp(start_date, tz='UTC').timestamp())
    end_ts = int(pd.Timestamp(end_date, tz='UTC').timestamp())
    
    print(f"📅 Период: {start_date} to {end_date}")
    print(f"🎯 Профиль: {cfg['profile']}")

    # Load BTC market filter (1h)
    gate_1h = None
    try:
        btc_1h = load_candles_pkl(data_dir, cfg['market_filter']['symbol'], '1h')
        btc_1h = _clip_period(btc_1h, start_ts, end_ts)
        gate_1h = compute_market_bias(btc_1h, cfg['market_filter']['ema_fast'], cfg['market_filter']['ema_slow'])
        print(f"✅ BTC фильтр загружен: {len(gate_1h)} баров")
        print(f"   Лонг периоды: {gate_1h['mkt_long_ok'].sum()} ({gate_1h['mkt_long_ok'].mean():.1%})")
        print(f"   Шорт периоды: {gate_1h['mkt_short_ok'].sum()} ({gate_1h['mkt_short_ok'].mean():.1%})")
    except Exception as e:
        print(f"⚠️ BTC фильтр не загружен: {e}")

    # Setup fees and trailing (используем текущие настройки)
    fees = FeesCfg(
        maker_bps=cfg['fees']['maker_bps'], 
        taker_bps=cfg['fees']['taker_bps'],
        entry_liquidity=cfg['fees'].get('entry_liquidity', 'taker')
    )
    trailing = TrailingConfig(**cfg['trailing'])
    
    print(f"💰 Комиссии: {fees.entry_liquidity} вход, taker выход")

    # Process each symbol
    rows, all_tr = [], []
    for sym in cfg['symbols']:
        print(f"\n📊 Обработка {sym}...")
        
        try:
            # 1h breakout trades
            df_1h = load_candles_pkl(data_dir, sym, '1h')
            df_1h = _clip_period(df_1h, start_ts, end_ts)
            sig_1h = _prep(df_1h, cfg, gate_1h)
            
            # Filter to breakout signals only
            sig_1h['allow_long']  = sig_1h.get('sig_long_breakout', False) & sig_1h.get('allow_long', False)
            sig_1h['allow_short'] = sig_1h.get('sig_short_breakout', False) & sig_1h.get('allow_short', False)
            
            tr_1h = run_backtest_one(sig_1h, sym, cfg['risk']['margin_usdt'], 
                                   cfg['risk']['leverage'], cfg['risk']['sl_atr_mult'], 
                                   trailing, fees)
            print(f"   1h breakout: {len(tr_1h)} сделок")
            
        except Exception as e:
            print(f"   ❌ 1h ошибка: {e}")
            tr_1h = pd.DataFrame()

        # 15m LTF trades (inside/trend/squeeze)
        tr_15m = pd.DataFrame()
        try:
            df_15m = load_candles_pkl(data_dir, sym, '15m')
            df_15m = _clip_period(df_15m, start_ts, end_ts)
            
            # Create 15m BTC gate by forward fill from 1h
            gate_15m = None
            if gate_1h is not None and not gate_1h.empty:
                # Forward fill BTC gate to 15m timeframe
                gate_15m_data = []
                for ts in df_15m['timestamp'].values:
                    # Find the latest 1h gate entry <= current 15m timestamp
                    mask = gate_1h['timestamp'] <= ts
                    if mask.any():
                        idx = mask.idxmax()  # последний True индекс
                        gate_15m_data.append({
                            'timestamp': ts,
                            'mkt_long_ok': gate_1h.iloc[idx]['mkt_long_ok'],
                            'mkt_short_ok': gate_1h.iloc[idx]['mkt_short_ok']
                        })
                    else:
                        gate_15m_data.append({'timestamp': ts, 'mkt_long_ok': False, 'mkt_short_ok': False})
                gate_15m = pd.DataFrame(gate_15m_data)
            
            sig_15m = _prep(df_15m, cfg, gate_15m)
            
            # Filter to LTF setups only (exclude breakout)
            ltf_long = sig_15m[['sig_long_inside', 'sig_long_tc', 'sig_long_sq']].any(axis=1)
            ltf_short = sig_15m[['sig_short_inside', 'sig_short_tc', 'sig_short_sq']].any(axis=1)
            
            sig_15m['allow_long'] = ltf_long & sig_15m.get('allow_long', False)
            sig_15m['allow_short'] = ltf_short & sig_15m.get('allow_short', False)
            
            tr_15m = run_backtest_one(sig_15m, sym, cfg['risk']['margin_usdt'], 
                                    cfg['risk']['leverage'], cfg['risk']['sl_atr_mult'], 
                                    trailing, fees)
            print(f"   15m LTF setups: {len(tr_15m)} сделок")
            
        except Exception as e:
            print(f"   ⚠️ 15m ошибка: {e}")

        # Combine results
        if not tr_1h.empty and not tr_15m.empty:
            tr = pd.concat([tr_1h, tr_15m]).sort_values('open_ts').reset_index(drop=True)
        elif not tr_1h.empty:
            tr = tr_1h
        elif not tr_15m.empty:
            tr = tr_15m
        else:
            tr = pd.DataFrame()
        
        # Calculate metrics
        m = _metrics(tr)
        m['symbol'] = sym
        rows.append(m)
        
        if not tr.empty:
            all_tr.append(tr)
        
        print(f"   ✅ Итого: {m['trades']} сделок ({m['longs']}L/{m['shorts']}S), WR={m['winrate']:.1%}, PnL=${m['pnl']:.1f}, PF={m['pf']:.2f}")

    # Generate reports
    rep = pd.DataFrame(rows)
    if not rep.empty:
        rep = rep.sort_values('pf', ascending=False)
    
    rep.to_csv('backtest_report_CURRENT_v1_6_TXB.csv', index=False)
    
    if all_tr:
        all_trades = pd.concat(all_tr, ignore_index=True)
        all_trades.to_csv('backtest_trades_CURRENT_v1_6_TXB.csv', index=False)
        
    print("\n" + "="*80)
    print("📊 ТЕКУЩИЙ БЭКТЕСТ v1.6-TXB (с улучшенным R-трейлингом)")
    print("="*80)
    if not rep.empty:
        print(rep.round(2))
        
        # Summary statistics
        total_pnl = rep['pnl'].sum()
        total_trades = rep['trades'].sum()
        total_longs = rep['longs'].sum()
        total_shorts = rep['shorts'].sum()
        active_pairs = len(rep[rep['trades'] > 0])
        avg_wr = rep[rep['trades'] > 0]['winrate'].mean() if active_pairs > 0 else 0
        avg_pf = rep[rep['trades'] > 0]['pf'].replace([np.inf, -np.inf], np.nan).mean() if active_pairs > 0 else 0
        
        print(f"\n🎯 ИТОГОВЫЕ РЕЗУЛЬТАТЫ ТЕКУЩЕЙ СИСТЕМЫ:")
        print(f"   💰 Общая прибыль: ${total_pnl:.1f}")
        print(f"   📈 Всего сделок: {total_trades} ({total_longs}L/{total_shorts}S)")
        print(f"   🎯 Активные пары: {active_pairs}/{len(cfg['symbols'])}")
        print(f"   ✅ Средний WR: {avg_wr:.1%}")
        print(f"   ⚖️ Средний PF: {avg_pf:.2f}")
        print(f"   📊 Средняя сделка: ${total_pnl/total_trades:.3f}" if total_trades > 0 else "")
        
        # Shorts analysis
        if total_shorts > 0:
            short_trades = all_trades[all_trades['side'] == 'SHORT']
            short_wr = len(short_trades[short_trades['pnl_abs'] > 0]) / len(short_trades)
            short_pnl = short_trades['pnl_abs'].sum()
            print(f"\n🔻 АНАЛИЗ ШОРТОВ:")
            print(f"   Шорт сделки: {total_shorts}")
            print(f"   Шорт WR: {short_wr:.1%}")
            print(f"   Шорт PnL: ${short_pnl:.1f}")
            
        # Fee analysis
        if all_tr and 'fees' in all_trades.columns:
            total_fees = all_trades['fees'].sum()
            avg_fee = all_trades['fees'].mean()
            fee_pct = (total_fees / abs(total_pnl)) * 100 if total_pnl != 0 else 0
            print(f"\n💰 АНАЛИЗ КОМИССИЙ:")
            print(f"   Общие комиссии: ${total_fees:.1f}")
            print(f"   Средняя комиссия: ${avg_fee:.2f}")
            print(f"   Комиссии от PnL: {fee_pct:.1f}%")
            
        # Защита от микроприбылей - анализ
        if all_tr:
            microprofit_trades = all_trades[(all_trades['pnl_abs'] > 0) & (all_trades['pnl_abs'] < 0.05)]
            if len(microprofit_trades) > 0:
                print(f"\n🛡️ АНАЛИЗ ЗАЩИТЫ ОТ МИКРОПРИБЫЛЕЙ:")
                print(f"   Микроприбыли (<$0.05): {len(microprofit_trades)} сделок")
                print(f"   Средняя микроприбыль: ${microprofit_trades['pnl_abs'].mean():.3f}")
                print(f"   Защита работает: {len(microprofit_trades) < total_trades * 0.1}")
    else:
        print("Сделки не выполнены!")

if __name__ == '__main__':
    main()
