# signalwarden_lite/backtest/run_backtest_v1_5_TX.py
import argparse, yaml, pandas as pd
import numpy as np
from ..core.data_loader import load_candles_pkl
from ..core.features import add_indicators
from ..core.regimes import add_regime, RegimeThresholds
from ..core.market import compute_market_bias
from ..core.signals import generate_signals, SignalParams
from ..core.trailing import TrailingConfig
from .engine import run_backtest_one, FeesCfg

def _metrics(tr):
    if tr.empty: return {'trades':0,'winrate':0.0,'pnl':0.0,'pf':0.0,'longs':0,'shorts':0}
    wins, losses = tr[tr['pnl_abs']>0], tr[tr['pnl_abs']<=0]
    gw = wins['pnl_abs'].sum() if not wins.empty else 0.0
    gl = abs(losses['pnl_abs'].sum()) if not losses.empty else 0.0
    longs = len(tr[tr['side']=='LONG'])
    shorts = len(tr[tr['side']=='SHORT'])
    return {'trades':len(tr),'winrate':len(wins)/len(tr),'pnl':tr['pnl_abs'].sum(),'pf':(gw/gl) if gl>0 else float('inf'), 'longs':longs, 'shorts':shorts}

def _prep(df, cfg, gate, rsi_p=14):
    df = add_indicators(df, ema_fast=50, ema_slow=200, atr_p=cfg['regime']['natr_period'], rsi_p=rsi_p)
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
        sg_rsi_short_max=cfg['short_guard']['rsi_short_max'],
        sg_need_close_below_ema20=cfg['short_guard']['need_close_below_ema20'],
        sg_slope_lookback=cfg['short_guard']['slope_lookback'],
        lg_rsi_long_min=52.0
    )
    return generate_signals(df, sp, market_gate=gate)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data-dir', required=True)
    ap.add_argument('--config', required=True)
    args = ap.parse_args()

    with open(args.config,'r') as f: cfg = yaml.safe_load(f)
    fees = FeesCfg(**cfg['fees'])
    trailing = TrailingConfig(**cfg['trailing'])

    # BTC gate на 1h
    gate_1h = None
    try:
        btc_1h = load_candles_pkl(args.data_dir, cfg['market_filter']['symbol'], '1h')
        gate_1h = compute_market_bias(btc_1h, cfg['market_filter']['ema_fast'], cfg['market_filter']['ema_slow'])
        print(f"✅ BTC market filter loaded: {len(gate_1h)} bars")
    except Exception as e:
        print(f"⚠️ BTC market filter failed: {e}")
        pass

    rows, all_tr = [], []
    for sym in cfg['symbols']:
        print(f"\n📊 Processing {sym}...")
        
        # 1h блок (breakout only)
        try:
            df_1h = load_candles_pkl(args.data_dir, sym, '1h')
            sig_1h = _prep(df_1h, cfg, gate_1h)
            # оставляем только breakout-сигналы на 1h
            sig_1h['allow_long']  = sig_1h['sig_long_breakout']  & sig_1h['allow_long']
            sig_1h['allow_short'] = sig_1h['sig_short_breakout'] & sig_1h['allow_short']
            tr_1h = run_backtest_one(sig_1h, sym, cfg['risk']['margin_usdt'], cfg['risk']['leverage'], cfg['risk']['sl_atr_mult'], trailing, fees)
            print(f"   1h breakout: {len(tr_1h)} trades")
        except Exception as e:
            print(f"   ❌ 1h failed: {e}")
            tr_1h = pd.DataFrame()

        # 15m блок (inside/trend/squeeze)
        tr_15m = pd.DataFrame()
        try:
            df_15m = load_candles_pkl(args.data_dir, sym, '15m')
            
            # Создаем 15m BTC gate путем forward fill
            if gate_1h is not None:
                # Создаем временные метки для 15m
                ts_15m = df_15m['timestamp'].values
                ts_1h = gate_1h['timestamp'].values
                
                # Для каждой 15m метки найдем ближайшую 1h метку (не позже)
                gate_15m_data = []
                for ts in ts_15m:
                    # Найдем последнюю 1h метку до или равную текущей 15m метке
                    mask = ts_1h <= ts
                    if mask.any():
                        idx = np.where(mask)[0][-1]  # последний True индекс
                        gate_15m_data.append({
                            'timestamp': ts,
                            'mkt_long_ok': gate_1h.iloc[idx]['mkt_long_ok'],
                            'mkt_short_ok': gate_1h.iloc[idx]['mkt_short_ok']
                        })
                    else:
                        gate_15m_data.append({
                            'timestamp': ts,
                            'mkt_long_ok': False,
                            'mkt_short_ok': False
                        })
                gate_15m = pd.DataFrame(gate_15m_data)
            else:
                gate_15m = None
            
            sig_15m = _prep(df_15m, cfg, gate_15m)
            # убираем breakout, оставляем три LTF-сетапа
            sig_15m['allow_long']  = (sig_15m[['sig_long_inside','sig_long_tc','sig_long_sq']].any(axis=1)) & sig_15m['allow_long']
            sig_15m['allow_short'] = (sig_15m[['sig_short_inside','sig_short_tc','sig_short_sq']].any(axis=1)) & sig_15m['allow_short']
            tr_15m = run_backtest_one(sig_15m, sym, cfg['risk']['margin_usdt'], cfg['risk']['leverage'], cfg['risk']['sl_atr_mult'], trailing, fees)
            print(f"   15m LTF setups: {len(tr_15m)} trades")
        except Exception as e:
            print(f"   ⚠️ 15m failed: {e}")

        # Объединяем результаты
        tr = pd.concat([tr_1h, tr_15m]).sort_values('open_ts') if not tr_15m.empty else tr_1h
        
        m = _metrics(tr); m['symbol']=sym; rows.append(m)
        if not tr.empty: 
            all_tr.append(tr)
        
        print(f"   ✅ Total: {m['trades']} trades, WR={m['winrate']:.1%}, PnL=${m['pnl']:.1f}, PF={m['pf']:.2f}, L/S={m['longs']}/{m['shorts']}")

    # Сводка
    rep = pd.DataFrame(rows).sort_values('pf', ascending=False)
    rep.to_csv('backtest_report_v1_5_TX.csv', index=False)
    if all_tr: 
        all_trades = pd.concat(all_tr)
        all_trades.to_csv('backtest_trades_v1_5_TX.csv', index=False)
        
    print("\n" + "="*80)
    print("📊 BACKTEST REPORT v1.5-TX (MTF profit-first)")
    print("="*80)
    print(rep.round(2))
    
    if not rep.empty:
        total_pnl = rep['pnl'].sum()
        total_trades = rep['trades'].sum()
        total_longs = rep['longs'].sum()
        total_shorts = rep['shorts'].sum()
        avg_wr = rep['winrate'].mean()
        avg_pf = rep['pf'].replace([np.inf, -np.inf], np.nan).mean()
        active_pairs = len(rep[rep['trades'] > 0])
        
        print(f"\n🎯 SUMMARY v1.5-TX:")
        print(f"   Total PnL: ${total_pnl:.1f}")
        print(f"   Total Trades: {total_trades} ({total_longs}L/{total_shorts}S)")
        print(f"   Active Pairs: {active_pairs}/{len(cfg['symbols'])}")
        print(f"   Avg WR: {avg_wr:.1%}")
        print(f"   Avg PF: {avg_pf:.2f}")
        print(f"   Trades/Day: {total_trades/200*24:.1f} (assuming 200 bars = ~8.3 days)")
        
        # Анализ шортов
        if total_shorts > 0:
            short_trades = all_trades[all_trades['side'] == 'SHORT']
            short_wr = len(short_trades[short_trades['pnl_abs'] > 0]) / len(short_trades)
            short_pnl = short_trades['pnl_abs'].sum()
            print(f"\n🔻 SHORT Analysis:")
            print(f"   Short trades: {total_shorts}")
            print(f"   Short WR: {short_wr:.1%}")
            print(f"   Short PnL: ${short_pnl:.1f}")

if __name__ == '__main__':
    main()
