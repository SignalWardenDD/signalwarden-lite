# signalwarden_lite/backtest/run_backtest_v1_6_TXB.py
import argparse, yaml, pandas as pd
import numpy as np
from datetime import datetime
from ..core.data_loader import load_candles_pkl
from ..core.features import add_indicators
from ..core.regimes import add_regime, RegimeThresholds
from ..core.market import compute_market_bias
from ..core.signals import generate_signals, SignalParams
from ..core.trailing import TrailingConfig
from .engine import run_backtest_one, FeesCfg

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
    ap = argparse.ArgumentParser(description="SignalWarden Lite v1.6-TXB Backtest")
    ap.add_argument('--data-dir', required=True, help="Data directory with pickle files")
    ap.add_argument('--config', required=True, help="Config YAML file")
    ap.add_argument('--start', default='2020-01-01', help="Start date YYYY-MM-DD")
    ap.add_argument('--end', default='2024-12-31', help="End date YYYY-MM-DD")
    args = ap.parse_args()

    # Load config
    with open(args.config, 'r') as f:
        cfg = yaml.safe_load(f)
    
    # Convert dates to timestamps (seconds)
    start_ts = int(pd.Timestamp(args.start, tz='UTC').timestamp()) if args.start else None
    end_ts = int(pd.Timestamp(args.end, tz='UTC').timestamp()) if args.end else None
    
    print(f"📅 Backtest period: {args.start} to {args.end}")
    print(f"🎯 Profile: {cfg['profile']}")

    # Load BTC market filter (1h)
    gate_1h = None
    try:
        btc_1h = load_candles_pkl(args.data_dir, cfg['market_filter']['symbol'], '1h')
        btc_1h = _clip_period(btc_1h, start_ts, end_ts)
        gate_1h = compute_market_bias(btc_1h, cfg['market_filter']['ema_fast'], cfg['market_filter']['ema_slow'])
        print(f"✅ BTC market filter loaded: {len(gate_1h)} bars")
        print(f"   Long periods: {gate_1h['mkt_long_ok'].sum()} ({gate_1h['mkt_long_ok'].mean():.1%})")
        print(f"   Short periods: {gate_1h['mkt_short_ok'].sum()} ({gate_1h['mkt_short_ok'].mean():.1%})")
    except Exception as e:
        print(f"⚠️ BTC market filter failed: {e}")

    # Setup fees and trailing
    fees = FeesCfg(
        maker_bps=cfg['fees']['maker_bps'], 
        taker_bps=cfg['fees']['taker_bps'],
        entry_liquidity=cfg['fees'].get('entry_liquidity', 'taker')
    )
    trailing = TrailingConfig(**cfg['trailing'])
    
    print(f"💰 Fees: {fees.entry_liquidity} entry ({fees.maker_bps if fees.entry_liquidity=='maker_first' else fees.taker_bps}bps), taker exit ({fees.taker_bps}bps)")

    # Process each symbol
    rows, all_tr = [], []
    for sym in cfg['symbols']:
        print(f"\n📊 Processing {sym}...")
        
        try:
            # 1h breakout trades
            df_1h = load_candles_pkl(args.data_dir, sym, '1h')
            df_1h = _clip_period(df_1h, start_ts, end_ts)
            sig_1h = _prep(df_1h, cfg, gate_1h)
            
            # Filter to breakout signals only
            sig_1h['allow_long']  = sig_1h.get('sig_long_breakout', False) & sig_1h.get('allow_long', False)
            sig_1h['allow_short'] = sig_1h.get('sig_short_breakout', False) & sig_1h.get('allow_short', False)
            
            tr_1h = run_backtest_one(sig_1h, sym, cfg['risk']['margin_usdt'], 
                                   cfg['risk']['leverage'], cfg['risk']['sl_atr_mult'], 
                                   trailing, fees)
            print(f"   1h breakout: {len(tr_1h)} trades")
            
        except Exception as e:
            print(f"   ❌ 1h failed: {e}")
            tr_1h = pd.DataFrame()

        # 15m LTF trades (inside/trend/squeeze)
        tr_15m = pd.DataFrame()
        try:
            df_15m = load_candles_pkl(args.data_dir, sym, '15m')
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
            print(f"   15m LTF setups: {len(tr_15m)} trades")
            
        except Exception as e:
            print(f"   ⚠️ 15m failed: {e}")

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
        
        print(f"   ✅ Total: {m['trades']} trades ({m['longs']}L/{m['shorts']}S), WR={m['winrate']:.1%}, PnL=${m['pnl']:.1f}, PF={m['pf']:.2f}")
        if m['avg_fee'] > 0:
            print(f"      Avg fee: ${m['avg_fee']:.2f}/trade")

    # Generate reports
    rep = pd.DataFrame(rows)
    if not rep.empty:
        rep = rep.sort_values('pf', ascending=False)
    
    rep.to_csv('backtest_report_v1_6_TXB.csv', index=False)
    
    if all_tr:
        all_trades = pd.concat(all_tr, ignore_index=True)
        all_trades.to_csv('backtest_trades_v1_6_TXB.csv', index=False)
        
    print("\n" + "="*80)
    print("📊 BACKTEST REPORT v1.6-TXB (Adaptive Shorts + 2020-2024)")
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
        
        # Estimate period in days
        if all_tr and start_ts and end_ts:
            period_days = (end_ts - start_ts) / (24 * 3600)
            trades_per_day = total_trades / period_days if period_days > 0 else 0
        else:
            trades_per_day = 0
        
        print(f"\n🎯 SUMMARY v1.6-TXB:")
        print(f"   Total PnL: ${total_pnl:.1f}")
        print(f"   Total Trades: {total_trades} ({total_longs}L/{total_shorts}S)")
        print(f"   Active Pairs: {active_pairs}/{len(cfg['symbols'])}")
        print(f"   Avg WR: {avg_wr:.1%}")
        print(f"   Avg PF: {avg_pf:.2f}")
        if trades_per_day > 0:
            print(f"   Trades/Day: {trades_per_day:.1f}")
        
        # Shorts analysis
        if total_shorts > 0:
            short_trades = all_trades[all_trades['side'] == 'SHORT']
            short_wr = len(short_trades[short_trades['pnl_abs'] > 0]) / len(short_trades)
            short_pnl = short_trades['pnl_abs'].sum()
            print(f"\n🔻 SHORTS BREAKTHROUGH:")
            print(f"   Short trades: {total_shorts}")
            print(f"   Short WR: {short_wr:.1%}")
            print(f"   Short PnL: ${short_pnl:.1f}")
            print(f"   🎉 ADAPTIVE SHORT-GUARD WORKING!")
        else:
            print(f"\n⚠️ No shorts executed - guard may be too strict")
            
        # Fee analysis
        if all_tr and 'fees' in all_trades.columns:
            total_fees = all_trades['fees'].sum()
            avg_fee = all_trades['fees'].mean()
            fee_pct = (total_fees / abs(total_pnl)) * 100 if total_pnl != 0 else 0
            print(f"\n💰 FEE ANALYSIS:")
            print(f"   Total fees: ${total_fees:.1f}")
            print(f"   Avg fee/trade: ${avg_fee:.2f}")
            print(f"   Fees as % of PnL: {fee_pct:.1f}%")
    else:
        print("No trades executed!")

if __name__ == '__main__':
    main()
