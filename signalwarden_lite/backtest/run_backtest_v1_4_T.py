# signalwarden_lite/backtest/run_backtest_v1_4_T.py
import argparse, yaml, pandas as pd
from ..core.data_loader import load_candles_pkl
from ..core.features import add_indicators
from ..core.regimes import add_regime, RegimeThresholds
from ..core.market import compute_market_bias
from ..core.signals import generate_signals, SignalParams
from ..core.trailing import TrailingConfig
from .engine import run_backtest_one, FeesCfg

def metrics(tr: pd.DataFrame):
    if tr.empty: return {'trades':0,'winrate':0.0,'pnl':0.0,'pf':0.0}
    wins = tr[tr['pnl_abs']>0]; losses = tr[tr['pnl_abs']<=0]
    gw = wins['pnl_abs'].sum() if not wins.empty else 0.0
    gl = abs(losses['pnl_abs'].sum()) if not losses.empty else 0.0
    return {'trades':len(tr),'winrate':len(wins)/len(tr),'pnl':tr['pnl_abs'].sum(),'pf':(gw/gl) if gl>0 else float('inf')}

def prep(df, cfg, gate):
    df = add_indicators(df, ema_fast=50, ema_slow=200, atr_p=cfg['regime']['natr_period'])
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
        sg_min_natr_perc=cfg['short_guard']['min_natr_perc'],
        sg_need_close_below_ema20=cfg['short_guard']['need_close_below_ema20'],
        sg_slope_lookback=cfg['short_guard']['slope_lookback'],
    )
    return generate_signals(df, sp, market_gate=gate, directions_cfg=cfg.get('directions',{}))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data-dir', required=True)
    ap.add_argument('--config', required=True)
    args = ap.parse_args()

    with open(args.config,'r') as f: cfg = yaml.safe_load(f)

    # BTC gate
    gate = None
    try:
        btc = load_candles_pkl(args.data_dir, cfg['market_filter']['symbol'], '1h')
        gate = compute_market_bias(btc, cfg['market_filter']['ema_fast'], cfg['market_filter']['ema_slow'])
        print(f"✅ BTC market filter loaded: {len(gate)} bars")
    except Exception as e:
        print(f"⚠️ BTC market filter failed: {e}")
        pass

    fees = FeesCfg(maker_bps=cfg['fees']['maker_bps'], taker_bps=cfg['fees']['taker_bps'])
    trailing = TrailingConfig(**cfg['trailing'])

    rows, all_tr = [], []
    directions = cfg.get('directions', {})
    sym_over = directions.get('symbol_overrides', {})

    for sym in cfg['symbols']:
        if sym_over.get(sym, {}).get('enabled') is False:  # на всякий случай
            continue
        try:
            df  = load_candles_pkl(args.data_dir, sym, '1h')
            sig = prep(df, cfg, gate)

            # применим маски направлений постфактум (страховка)
            default = directions.get('default', {'allow_long':True,'allow_short':True})
            allow_long_default  = default.get('allow_long', True)
            allow_short_default = default.get('allow_short',True)
            over = sym_over.get(sym, {})
            allow_long  = over.get('allow_long',  allow_long_default)
            allow_short = over.get('allow_short', allow_short_default)
            if not allow_long:  sig['allow_long']  = False
            if not allow_short: sig['allow_short'] = False

            tr = run_backtest_one(sig, sym, margin_usdt=cfg['risk']['margin_usdt'],
                                  leverage=cfg['risk']['leverage'], sl_atr_mult=cfg['risk']['sl_atr_mult'],
                                  trailing=trailing, fees=fees)
            m = metrics(tr); m['symbol']=sym; rows.append(m)
            if not tr.empty: all_tr.append(tr)
            print(f"✅ {sym}: {m['trades']} trades, WR={m['winrate']:.1%}, PnL=${m['pnl']:.1f}, PF={m['pf']:.2f}")
        except Exception as e:
            print(f"❌ {sym}: {e}")
            continue

    rep = pd.DataFrame(rows).sort_values('pf', ascending=False)
    rep.to_csv('backtest_report_v1_4_T.csv', index=False)
    if all_tr: 
        all_trades = pd.concat(all_tr)
        all_trades.to_csv('backtest_trades_v1_4_T.csv', index=False)
        
    print("\n" + "="*60)
    print("📊 BACKTEST REPORT v1.4-T (profit-first)")
    print("="*60)
    print(rep.round(2))
    
    if not rep.empty:
        total_pnl = rep['pnl'].sum()
        total_trades = rep['trades'].sum()
        avg_wr = rep['winrate'].mean()
        avg_pf = rep['pf'].replace([np.inf, -np.inf], np.nan).mean()
        print(f"\n🎯 SUMMARY:")
        print(f"   Total PnL: ${total_pnl:.1f}")
        print(f"   Total Trades: {total_trades}")
        print(f"   Avg WR: {avg_wr:.1%}")
        print(f"   Avg PF: {avg_pf:.2f}")

if __name__ == '__main__':
    import numpy as np
    main()
