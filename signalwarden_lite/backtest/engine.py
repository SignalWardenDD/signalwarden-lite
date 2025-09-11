from dataclasses import dataclass
from typing import List, Tuple
import pandas as pd
from ..core.types import Side, Position, TradeLog
from ..core.trailing import TrailingConfig, update_trailing_hybrid
from ..core.trailing_pnl_only import TrailingConfigPnLOnly, update_trailing_pnl_only

@dataclass
class FeesCfg:
    maker_bps: float = 2.0
    taker_bps: float = 5.0
    entry_liquidity: str = 'taker'  # 'taker' | 'maker_first'

def _qty(notional_usdt: float, price: float) -> float:
    """Calculate quantity based on notional value"""
    return notional_usdt / price

def _fees(amount_quote: float, bps: float) -> float:
    """Calculate fees based on quote amount and basis points"""
    return amount_quote * (bps / 10000.0)

def _entry_fill_price(is_long: bool, entry: float, bar_open: float, bar_high: float, bar_low: float) -> Tuple[bool, float]:
    """Check if entry was hit during bar and return fill price"""
    if is_long and bar_high >= entry:
        return True, max(entry, bar_open)
    elif (not is_long) and bar_low <= entry:
        return True, min(entry, bar_open)
    return False, 0.0

def run_backtest_one(df: pd.DataFrame, symbol: str,
                     margin_usdt: float, leverage: float, sl_atr_mult: float,
                     trailing: TrailingConfig, fees: FeesCfg) -> pd.DataFrame:
    """
    Run backtest for single symbol with hybrid trailing (no partials)
    Fixed margin size with leverage
    """
    
    trades: List[TradeLog] = []
    pos: Position = None
    base_notional = margin_usdt * leverage  # 15 × 5 = 75 USDT

    for i in range(1, len(df)):
        current_row = df.iloc[i]
        prev_row = df.iloc[i-1]

        # вход в позицию
        if pos is None:
            if current_row.get('allow_long', False):
                entry = float(current_row.get('long_entry_final', current_row.get('long_entry_breakout', float('nan'))))
                reason = current_row.get('long_reason', 'breakout')
                filled, price = _entry_fill_price(True, entry, current_row['open'], current_row['high'], current_row['low'])
                
                if filled and not pd.isna(entry):
                    r_unit = sl_atr_mult * current_row['atr']
                    qty = _qty(base_notional, price)
                    sl = entry - r_unit
                    pos = Position(
                        side=Side.LONG,
                        entry=price,
                        sl=sl,
                        sl_initial=sl,  # запоминаем исходный SL
                        qty=qty,
                        remaining_qty=qty,
                        r_per_unit=r_unit,
                        entry_reason=reason
                    )
                    pos.bars_open = 0

            elif current_row.get('allow_short', False):
                entry = float(current_row.get('short_entry_final', current_row.get('short_entry_breakout', float('nan'))))
                reason = current_row.get('short_reason', 'breakout')
                filled, price = _entry_fill_price(False, entry, current_row['open'], current_row['high'], current_row['low'])
                
                if filled and not pd.isna(entry):
                    r_unit = sl_atr_mult * current_row['atr']
                    qty = _qty(base_notional, price)
                    sl = entry + r_unit
                    pos = Position(
                        side=Side.SHORT,
                        entry=price,
                        sl=sl,
                        sl_initial=sl,  # запоминаем исходный SL
                        qty=qty,
                        remaining_qty=qty,
                        r_per_unit=r_unit,
                        entry_reason=reason
                    )
                    pos.bars_open = 0

        # сопровождение позиции
        else:
            pos.bars_open += 1
            
            # Обновляем трейлинг стоп
            pos = update_trailing_hybrid(pos, current_row['high'], current_row['low'], current_row['atr'], trailing)

            # Проверяем выход по SL (только один способ выхода)
            exited = False
            if pos.side == Side.LONG and current_row['low'] <= pos.sl:
                price = pos.sl
                pnl = (price - pos.entry) * pos.qty
                
                # Определяем причину выхода
                if pos.sl > pos.sl_initial:
                    reason = 'TRAIL'  # Трейлинг сработал
                elif pos.be_applied:
                    reason = 'BE'     # Break-even
                else:
                    reason = 'SL_INIT'  # Исходный стоп
                
                # Entry fee: maker_first or taker, Exit fee: always taker (stop market)
                entry_fee_bps = fees.maker_bps if fees.entry_liquidity == 'maker_first' else fees.taker_bps
                fee = _fees(pos.entry*pos.qty, entry_fee_bps) + _fees(price*pos.qty, fees.taker_bps)
                trades.append(TradeLog(
                    symbol=symbol,
                    open_ts=int(prev_row['timestamp']),
                    close_ts=int(current_row['timestamp']),
                    side=pos.side,
                    entry=pos.entry,
                    exit=price,
                    pnl_abs=pnl-fee,
                    pnl_R=(pnl/(pos.r_per_unit*pos.qty)),
                    reason=reason,
                    entry_reason=pos.entry_reason,
                    fees=fee
                ))
                pos = None
                exited = True

            elif pos and pos.side == Side.SHORT and current_row['high'] >= pos.sl:
                price = pos.sl
                pnl = -(price - pos.entry) * pos.qty
                
                # Определяем причину выхода
                if pos.sl < pos.sl_initial:
                    reason = 'TRAIL'  # Трейлинг сработал
                elif pos.be_applied:
                    reason = 'BE'     # Break-even
                else:
                    reason = 'SL_INIT'  # Исходный стоп
                
                # Entry fee: maker_first or taker, Exit fee: always taker (stop market)
                entry_fee_bps = fees.maker_bps if fees.entry_liquidity == 'maker_first' else fees.taker_bps
                fee = _fees(pos.entry*pos.qty, entry_fee_bps) + _fees(price*pos.qty, fees.taker_bps)
                trades.append(TradeLog(
                    symbol=symbol,
                    open_ts=int(prev_row['timestamp']),
                    close_ts=int(current_row['timestamp']),
                    side=pos.side,
                    entry=pos.entry,
                    exit=price,
                    pnl_abs=pnl-fee,
                    pnl_R=(pnl/(pos.r_per_unit*pos.qty)),
                    reason=reason,
                    entry_reason=pos.entry_reason,
                    fees=fee
                ))
                pos = None
                exited = True

    # Convert trades to DataFrame
    if trades:
        trades_df = pd.DataFrame([t.__dict__ for t in trades])
    else:
        trades_df = pd.DataFrame(columns=[
            'symbol', 'open_ts', 'close_ts', 'side', 'entry', 'exit', 
            'pnl_abs', 'pnl_R', 'reason', 'entry_reason', 'fees'
        ])
    
    return trades_df

def run_backtest_one_pnl_only(df: pd.DataFrame, symbol: str,
                              margin_usdt: float, leverage: float, sl_atr_mult: float,
                              trailing: TrailingConfigPnLOnly, fees: FeesCfg) -> pd.DataFrame:
    """
    Run backtest for single symbol with PnL-only trailing (no partials)
    Fixed margin size with leverage
    """
    
    trades: List[TradeLog] = []
    pos: Position = None
    base_notional = margin_usdt * leverage  # 21 × 5 = 105 USDT

    for i in range(1, len(df)):
        current_row = df.iloc[i]
        prev_row = df.iloc[i-1]

        # вход в позицию
        if pos is None:
            if current_row.get('allow_long', False):
                entry = float(current_row.get('long_entry_final', current_row.get('long_entry_breakout', float('nan'))))
                reason = current_row.get('long_reason', 'breakout')
                filled, price = _entry_fill_price(True, entry, current_row['open'], current_row['high'], current_row['low'])
                
                if filled and not pd.isna(entry):
                    r_unit = sl_atr_mult * current_row['atr']
                    qty = _qty(base_notional, price)
                    sl = entry - r_unit
                    pos = Position(
                        side=Side.LONG,
                        entry=price,
                        sl=sl,
                        sl_initial=sl,  # запоминаем исходный SL
                        qty=qty,
                        remaining_qty=qty,
                        r_per_unit=r_unit,
                        entry_reason=reason
                    )
                    pos.bars_open = 0

            elif current_row.get('allow_short', False):
                entry = float(current_row.get('short_entry_final', current_row.get('short_entry_breakout', float('nan'))))
                reason = current_row.get('short_reason', 'breakout')
                filled, price = _entry_fill_price(False, entry, current_row['open'], current_row['high'], current_row['low'])
                
                if filled and not pd.isna(entry):
                    r_unit = sl_atr_mult * current_row['atr']
                    qty = _qty(base_notional, price)
                    sl = entry + r_unit
                    pos = Position(
                        side=Side.SHORT,
                        entry=price,
                        sl=sl,
                        sl_initial=sl,  # запоминаем исходный SL
                        qty=qty,
                        remaining_qty=qty,
                        r_per_unit=r_unit,
                        entry_reason=reason
                    )
                    pos.bars_open = 0

        # обновление позиции
        if pos is not None:
            pos.bars_open += 1
            
            # PnL-only трейлинг
            pos = update_trailing_pnl_only(pos, current_row['high'], current_row['low'], current_row['atr'], trailing)
            
            # проверка SL
            sl_hit = False
            if pos.side == Side.LONG and current_row['low'] <= pos.sl:
                sl_hit = True
                exit_price = pos.sl
            elif pos.side == Side.SHORT and current_row['high'] >= pos.sl:
                sl_hit = True
                exit_price = pos.sl
            
            if sl_hit:
                # расчет PnL
                if pos.side == Side.LONG:
                    pnl_abs = (exit_price - pos.entry) * pos.qty
                else:
                    pnl_abs = (pos.entry - exit_price) * pos.qty
                
                # комиссии
                entry_fee = _fees(pos.entry * pos.qty, fees.taker_bps if fees.entry_liquidity == 'taker' else fees.maker_bps)
                exit_fee = _fees(exit_price * pos.qty, fees.taker_bps)
                total_fees = entry_fee + exit_fee
                
                pnl_net = pnl_abs - total_fees
                pnl_R = pnl_net / (pos.r_per_unit * pos.qty) if pos.r_per_unit > 0 else 0
                
                # логируем сделку
                trade = TradeLog(
                    symbol=symbol,
                    open_ts=int(prev_row['timestamp']),
                    close_ts=int(current_row['timestamp']),
                    side=pos.side.value,
                    entry=pos.entry,
                    exit=exit_price,
                    pnl_abs=pnl_net,
                    pnl_R=pnl_R,
                    reason='SL',
                    entry_reason=pos.entry_reason,
                    fees=total_fees
                )
                trades.append(trade)
                pos = None

    # Convert trades to DataFrame
    if trades:
        trades_df = pd.DataFrame([t.__dict__ for t in trades])
    else:
        trades_df = pd.DataFrame(columns=[
            'symbol', 'open_ts', 'close_ts', 'side', 'entry', 'exit', 
            'pnl_abs', 'pnl_R', 'reason', 'entry_reason', 'fees'
        ])
    
    return trades_df