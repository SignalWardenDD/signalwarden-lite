# signalwarden_lite/core/signals.py
from dataclasses import dataclass
import numpy as np, pandas as pd

@dataclass
class SignalParams:
    lookback_calm:int=24; lookback_normal:int=16; lookback_high:int=10
    ltf_thinbar_k:float=0.25
    # ATR cushions (ассиметричные)
    long_cushion_calm:float=0.30; long_cushion_normal:float=0.12; long_cushion_high:float=0.08
    short_cushion_calm:float=0.32; short_cushion_normal:float=0.14; short_cushion_high:float=0.10
    # включатели
    setup_breakout:bool=True
    setup_inside:bool=True
    setup_trend_cont:bool=True
    setup_squeeze:bool=True
    # inside-bar
    ib_min_prev_range_k_atr:float=0.5
    # trend-continuation
    tc_min_body_k_range:float=0.50
    tc_confirm_close_k_body:float=0.20
    # squeeze
    bb_period:int=20; bb_k:float=2.0; width_k_perc:float=9.0
    # short guard
    sg_min_natr_perc:float=1.2
    sg_need_close_below_ema20:bool=True
    sg_slope_lookback:int=3

def _cushion(regime:str, side:str, p:SignalParams)->float:
    if side=='long':
        return p.long_cushion_high if regime=='high' else (p.long_cushion_normal if regime=='normal' else p.long_cushion_calm)
    else:
        return p.short_cushion_high if regime=='high' else (p.short_cushion_normal if regime=='normal' else p.short_cushion_calm)

def _roll_max(s,n): return s.shift(1).rolling(n).max()
def _roll_min(s,n): return s.shift(1).rolling(n).min()

def generate_signals(df: pd.DataFrame, p: SignalParams, market_gate: pd.DataFrame=None,
                     directions_cfg: dict=None) -> pd.DataFrame:
    out = df.copy()
    out['trend_long']  = out['ema_fast'] > out['ema_slow']
    out['trend_short'] = out['ema_fast'] < out['ema_slow']
    out['ema20'] = out['close'].ewm(span=20, adjust=False).mean()

    # BTC-гейты
    if market_gate is not None and {'mkt_long_ok','mkt_short_ok'}.issubset(market_gate.columns):
        out = out.merge(market_gate[['timestamp','mkt_long_ok','mkt_short_ok']], on='timestamp', how='left')
        out[['mkt_long_ok','mkt_short_ok']] = out[['mkt_long_ok','mkt_short_ok']].ffill().fillna(False)
    else:
        out['mkt_long_ok']=True; out['mkt_short_ok']=True

    # динамические свинги
    lbH = _roll_max(out['high'], p.lookback_high);  lbL = _roll_min(out['low'],  p.lookback_high)
    lnH = _roll_max(out['high'], p.lookback_normal);lnL = _roll_min(out['low'],  p.lookback_normal)
    lcH = _roll_max(out['high'], p.lookback_calm);  lcL = _roll_min(out['low'],  p.lookback_calm)
    swingH = lcH.where(out['regime'].isin(['ultra_calm','calm']), lnH).where(out['regime']!='high', lbH)
    swingL = lcL.where(out['regime'].isin(['ultra_calm','calm']), lnL).where(out['regime']!='high', lbL)
    out['swing_high'], out['swing_low'] = swingH, swingL

    # тонкая свеча
    thin_cutoff = p.ltf_thinbar_k * out['atr']
    out['thin_bar'] = (out['high'] - out['low']).abs() < thin_cutoff

    # ATR подушки
    long_cush  = out['regime'].apply(lambda r: _cushion(r,'long',p))
    short_cush = out['regime'].apply(lambda r: _cushion(r,'short',p))

    # A) Breakout
    out['long_entry_breakout']  = out['swing_high'] + long_cush*out['atr']
    out['short_entry_breakout'] = out['swing_low']  - short_cush*out['atr']
    out['sig_long_breakout']  = p.setup_breakout  and out['trend_long']  & (~out['thin_bar']) & (out['high']>=out['long_entry_breakout'])
    out['sig_short_breakout'] = p.setup_breakout  and out['trend_short'] & (~out['thin_bar']) & (out['low'] <=out['short_entry_breakout'])

    # B) Inside-bar (по тренду)
    if p.setup_inside:
        prevH, prevL = out['high'].shift(1), out['low'].shift(1)
        prevR = (prevH - prevL).abs()
        ib = (out['high'] <= prevH) & (out['low'] >= prevL)
        big = prevR >= (p.ib_min_prev_range_k_atr * out['atr'])
        out['long_entry_inside']  = prevH + long_cush*out['atr']
        out['short_entry_inside'] = prevL - short_cush*out['atr']
        out['sig_long_inside']  = ib & big & out['trend_long']  & (~out['thin_bar'])
        out['sig_short_inside'] = ib & big & out['trend_short'] & (~out['thin_bar'])
    else:
        out['sig_long_inside']=False; out['sig_short_inside']=False

    # C) Trend-Continuation (ослаблено)
    if p.setup_trend_cont:
        po, pc = out['open'].shift(1), out['close'].shift(1)
        ph, pl = out['high'].shift(1), out['low'].shift(1)
        body = (pc-po).abs(); rng=(ph-pl).abs()
        strong = body >= p.tc_min_body_k_range * rng
        long_conf  = out['close'] >= (pc - p.tc_confirm_close_k_body * body)
        short_conf = out['close'] <= (pc + p.tc_confirm_close_k_body * body)
        out['long_entry_tc']  = ph + long_cush*out['atr']
        out['short_entry_tc'] = pl - short_cush*out['atr']
        out['sig_long_tc']  = strong & out['trend_long']  & long_conf  & (~out['thin_bar'])
        out['sig_short_tc'] = strong & out['trend_short'] & short_conf & (~out['thin_bar'])
    else:
        out['sig_long_tc']=False; out['sig_short_tc']=False

    # D) Squeeze-Breakout (слегка шире)
    if p.setup_squeeze:
        ma = out['close'].rolling(p.bb_period).mean()
        sd = out['close'].rolling(p.bb_period).std()
        upper, lower = ma + p.bb_k*sd, ma - p.bb_k*sd
        width_perc = (upper - lower) / ma * 100.0
        sq = width_perc <= p.width_k_perc
        out['long_entry_sq']  = out['swing_high'] + long_cush*out['atr']
        out['short_entry_sq'] = out['swing_low']  - short_cush*out['atr']
        out['sig_long_sq']  = sq & out['trend_long']  & (~out['thin_bar'])
        out['sig_short_sq'] = sq & out['trend_short'] & (~out['thin_bar'])
    else:
        out['sig_long_sq']=False; out['sig_short_sq']=False

    # объединяем сигналы
    Lcols = ['sig_long_breakout','sig_long_inside','sig_long_tc','sig_long_sq']
    Scols = ['sig_short_breakout','sig_short_inside','sig_short_tc','sig_short_sq']
    out['allow_long_raw']  = out[Lcols].any(axis=1)
    out['allow_short_raw'] = out[Scols].any(axis=1)

    # BTC-гейт и Short-Guard
    # long final
    out['allow_long'] = out['allow_long_raw'] & out['mkt_long_ok']
    # short guard
    slope = out['ema_slow'] - out['ema_slow'].shift(p.sg_slope_lookback)
    natr_perc = out['natr']  # предполагаем, что add_indicators добавил natr (%)
    guard_short = (out['ema_fast'] < out['ema_slow']) & (slope < 0) \
                  & (natr_perc >= p.sg_min_natr_perc) \
                  & (out['close'] < out['ema20'] if p.sg_need_close_below_ema20 else True)
    out['allow_short'] = out['allow_short_raw'] & out['mkt_short_ok'] & guard_short

    # пер-символьные маски направлений (если переданы)
    if directions_cfg:
        def dir_mask(ts_row):
            return True
        # применим постфактум по символам в run_backtest/live

    # выбор цены и причины (приоритет: breakout > inside > tc > squeeze)
    def _pick_long(r):
        for k, lab in [('sig_long_breakout','breakout'),('sig_long_inside','inside'),('sig_long_tc','trend_cont'),('sig_long_sq','squeeze')]:
            if r[k]: return r.get(f'long_entry_{lab if lab!="breakout" else "breakout"}', np.nan), lab
        return np.nan, ''
    def _pick_short(r):
        for k, lab in [('sig_short_breakout','breakout'),('sig_short_inside','inside'),('sig_short_tc','trend_cont'),('sig_short_sq','squeeze')]:
            if r[k]: return r.get(f'short_entry_{lab if lab!="breakout" else "breakout"}', np.nan), lab
        return np.nan, ''

    cL = out.apply(_pick_long, axis=1, result_type='expand')
    cS = out.apply(_pick_short, axis=1, result_type='expand')
    out['long_entry_final'], out['long_reason'] = cL[0], cL[1]
    out['short_entry_final'], out['short_reason'] = cS[0], cS[1]
    return out