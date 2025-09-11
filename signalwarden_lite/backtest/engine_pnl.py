from dataclasses import dataclass
from typing import List, Tuple
import pandas as pd
from ..core.types import Side, Position, TradeLog
from ..core.trailing import TrailingConfig, update_trailing_pnl_based

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

def _entry_fees(notional_usdt: float, cfg: FeesCfg) -> float:
    """Calculate entry fees"""
    if cfg.entry_liquidity == 'taker':
        return _fees(notional_usdt, cfg.taker_bps)
    else:
        return _fees(notional_usdt, cfg.maker_bps)

def _exit_fees(notional_usdt: float, cfg: FeesCfg) -> float:
    """Calculate exit fees (always taker for stop-loss)"""
    return _fees(notional_usdt, cfg.taker_bps)

def backtest_single_symbol(
    df: pd.DataFrame,
    signals: pd.DataFrame,
    notional_usdt: float,
    sl_atr_mult: float,
    trailing: TrailingConfig,
    fees: FeesCfg,
    symbol: str
) -> List[TradeLog]:
    """
    Backtest single symbol with PnL-based trailing system (matching production)
    """
    trades = []
    pos = None
    
    for i, (timestamp, current_row) in enumerate(df.iterrows()):
        signal_row = signals.loc[timestamp]
        
        # Если нет позиции, ищем сигнал входа
        if pos is None:
            if signal_row['allow_long'] and signal_row['signal_long']:
                # Вход в лонг
                entry_price = current_row['close']
                qty = _qty(notional_usdt, entry_price)
                entry_fees_usdt = _entry_fees(notional_usdt, fees)
                
                # Рассчитываем SL
                atr = current_row['atr']
                sl_price = entry_price - (sl_atr_mult * atr)
                
                pos = Position(
                    side=Side.LONG,
                    entry=entry_price,
                    qty=qty,
                    sl_initial=sl_price,
                    sl=sl_price,
                    entry_fees_usdt=entry_fees_usdt,
                    bars_open=0,
                    peak_pnl_usdt=0.0,
                    remaining_qty=qty
                )
                
            elif signal_row['allow_short'] and signal_row['signal_short']:
                # Вход в шорт
                entry_price = current_row['close']
                qty = _qty(notional_usdt, entry_price)
                entry_fees_usdt = _entry_fees(notional_usdt, fees)
                
                # Рассчитываем SL
                atr = current_row['atr']
                sl_price = entry_price + (sl_atr_mult * atr)
                
                pos = Position(
                    side=Side.SHORT,
                    entry=entry_price,
                    qty=qty,
                    sl_initial=sl_price,
                    sl=sl_price,
                    entry_fees_usdt=entry_fees_usdt,
                    bars_open=0,
                    peak_pnl_usdt=0.0,
                    remaining_qty=qty
                )
        
        # Если есть позиция
        else:
            pos.bars_open += 1
            
            # Обновляем трейлинг стоп (PnL-based система как в production)
            pos = update_trailing_pnl_based(pos, current_row['close'], trailing)

            # Проверяем выход по SL (только один способ выхода)
            exited = False
            if pos.side == Side.LONG and current_row['low'] <= pos.sl:
                price = pos.sl
                exit_fees_usdt = _exit_fees(price * pos.qty, fees)
                pnl_before_fees = (price - pos.entry) * pos.qty
                pnl_usdt = pnl_before_fees - pos.entry_fees_usdt - exit_fees_usdt
                exited = True
                
            elif pos.side == Side.SHORT and current_row['high'] >= pos.sl:
                price = pos.sl
                exit_fees_usdt = _exit_fees(price * pos.qty, fees)
                pnl_before_fees = (pos.entry - price) * pos.qty
                pnl_usdt = pnl_before_fees - pos.entry_fees_usdt - exit_fees_usdt
                exited = True
            
            if exited:
                # Логируем сделку
                trade = TradeLog(
                    symbol=symbol,
                    timestamp=timestamp,
                    side=pos.side.value,
                    entry=pos.entry,
                    exit=price,
                    qty=pos.qty,
                    pnl_usdt=pnl_usdt,
                    entry_fees_usdt=pos.entry_fees_usdt,
                    exit_fees_usdt=exit_fees_usdt,
                    bars_held=pos.bars_open,
                    sl_initial=pos.sl_initial,
                    sl_final=pos.sl,
                    peak_pnl_usdt=pos.peak_pnl_usdt
                )
                trades.append(trade)
                pos = None
    
    return trades

def run_backtest_pnl_based(
    data_dict: dict,
    signals_dict: dict,
    notional_usdt: float,
    sl_atr_mult: float,
    trailing: TrailingConfig,
    fees: FeesCfg
) -> List[TradeLog]:
    """
    Run backtest with PnL-based trailing system (matching production exactly)
    """
    all_trades = []
    
    for symbol in data_dict.keys():
        if symbol in signals_dict:
            print(f"Backtesting {symbol} with PnL-based trailing...")
            trades = backtest_single_symbol(
                data_dict[symbol],
                signals_dict[symbol],
                notional_usdt,
                sl_atr_mult,
                trailing,
                fees,
                symbol
            )
            all_trades.extend(trades)
            print(f"  {symbol}: {len(trades)} trades")
    
    return all_trades
