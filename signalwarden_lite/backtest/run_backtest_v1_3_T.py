import argparse
import yaml
import pandas as pd
from pathlib import Path

from ..core.data_loader import load_candles_pkl
from ..core.features import add_indicators
from ..core.regimes import add_regime, RegimeThresholds
from ..core.market import compute_market_bias
from ..core.signals import generate_signals, SignalParams
from ..core.trailing import TrailingConfig
from .engine import run_backtest_one, FeesCfg

def compute_metrics(trades: pd.DataFrame) -> dict:
    """Compute key performance metrics from trades"""
    if trades.empty:
        return {
            'trades': 0,
            'winrate': 0.0,
            'pnl': 0.0,
            'pf': 0.0,
            'avg_win': 0.0,
            'avg_loss': 0.0,
            'max_win': 0.0,
            'max_loss': 0.0,
            'avg_R': 0.0,
            'max_R': 0.0,
            'min_R': 0.0,
            'breakout_trades': 0,
            'micro_trades': 0,
            'trend_trades': 0,
            'squeeze_trades': 0,
            'sl_init_exits': 0,
            'trail_exits': 0,
            'be_exits': 0
        }
    
    wins = trades[trades['pnl_abs'] > 0]
    losses = trades[trades['pnl_abs'] <= 0]
    
    total_pnl = trades['pnl_abs'].sum()
    gross_win = wins['pnl_abs'].sum() if not wins.empty else 0.0
    gross_loss = abs(losses['pnl_abs'].sum()) if not losses.empty else 0.0
    
    profit_factor = (gross_win / gross_loss) if gross_loss > 0 else float('inf')
    winrate = len(wins) / len(trades)
    
    avg_win = wins['pnl_abs'].mean() if not wins.empty else 0.0
    avg_loss = losses['pnl_abs'].mean() if not losses.empty else 0.0
    max_win = wins['pnl_abs'].max() if not wins.empty else 0.0
    max_loss = losses['pnl_abs'].min() if not losses.empty else 0.0
    
    # R-multiple stats
    avg_R = trades['pnl_R'].mean()
    max_R = trades['pnl_R'].max()
    min_R = trades['pnl_R'].min()
    
    # Setup breakdown
    breakout_trades = len(trades[trades['entry_reason'] == 'breakout'])
    micro_trades = len(trades[trades['entry_reason'] == 'micro_breakout'])
    trend_trades = len(trades[trades['entry_reason'] == 'trend_continuation'])
    squeeze_trades = len(trades[trades['entry_reason'] == 'squeeze_breakout'])
    
    # Exit reason breakdown
    sl_init_exits = len(trades[trades['reason'] == 'SL_INIT'])
    trail_exits = len(trades[trades['reason'] == 'TRAIL'])
    be_exits = len(trades[trades['reason'] == 'BE'])
    
    return {
        'trades': len(trades),
        'winrate': winrate,
        'pnl': total_pnl,
        'pf': profit_factor,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'max_win': max_win,
        'max_loss': max_loss,
        'avg_R': avg_R,
        'max_R': max_R,
        'min_R': min_R,
        'breakout_trades': breakout_trades,
        'micro_trades': micro_trades,
        'trend_trades': trend_trades,
        'squeeze_trades': squeeze_trades,
        'sl_init_exits': sl_init_exits,
        'trail_exits': trail_exits,
        'be_exits': be_exits
    }

def prep_data(df: pd.DataFrame, cfg: dict, market_gate: pd.DataFrame = None) -> pd.DataFrame:
    """Prepare data with all indicators and signals"""
    # Add technical indicators
    df = add_indicators(
        df, 
        ema_fast=50, 
        ema_slow=200, 
        atr_p=cfg['regime']['natr_period']
    )
    
    # Add regime classification
    regime_thresholds = RegimeThresholds(**cfg['regime']['calm_thresholds'])
    df = add_regime(df, regime_thresholds)
    
    # Create signal parameters from config
    s = cfg['signals']
    setups = s['setups']
    signal_params = SignalParams(
        lookback_calm=s['dynamic_lookback']['calm'],
        lookback_normal=s['dynamic_lookback']['normal'],
        lookback_high=s['dynamic_lookback']['high'],
        atr_cushion_calm=s['atr_cushion']['calm'],
        atr_cushion_normal=s['atr_cushion']['normal'],
        atr_cushion_high=s['atr_cushion']['high'],
        ltf_thinbar_k=s['ltf_thinbar_k'],
        setup_breakout=setups['breakout']['enabled'],
        setup_micro_breakout=setups['micro_breakout']['enabled'],
        setup_trend_cont=setups['trend_continuation']['enabled'],
        setup_squeeze=setups['squeeze_breakout']['enabled'],
        micro_lb_normal=setups['micro_breakout']['lookback']['normal'],
        micro_lb_high=setups['micro_breakout']['lookback']['high'],
        micro_cushion_normal=setups['micro_breakout']['cushion_k_atr']['normal'],
        micro_cushion_high=setups['micro_breakout']['cushion_k_atr']['high'],
        tc_min_body_k_range=setups['trend_continuation']['min_body_k_range'],
        tc_confirm_close_k_body=setups['trend_continuation']['confirm_close_k_body'],
        bb_period=setups['squeeze_breakout']['bb_period'],
        bb_k=setups['squeeze_breakout']['bb_k'],
        width_k_perc=setups['squeeze_breakout']['width_k_perc'],
    )
    
    # Generate signals
    df = generate_signals(df, signal_params, market_gate)
    
    return df

def main():
    parser = argparse.ArgumentParser(description='Run SignalWarden Lite v1.3-T Backtest')
    parser.add_argument('--data-dir', required=True, help='Directory containing pickle files')
    parser.add_argument('--config', required=True, help='Config YAML file path')
    parser.add_argument('--output-dir', default='.', help='Output directory for results')
    
    args = parser.parse_args()
    
    # Load configuration
    with open(args.config, 'r') as f:
        cfg = yaml.safe_load(f)
    
    # Load BTC market filter
    market_gate = None
    try:
        btc_data = load_candles_pkl(args.data_dir, cfg['market_filter']['symbol'], '1h')
        market_gate = compute_market_bias(
            btc_data, 
            cfg['market_filter']['ema_fast'], 
            cfg['market_filter']['ema_slow']
        )
        print(f"✅ BTC market filter loaded: {len(market_gate)} bars")
    except Exception as e:
        print(f"⚠️ BTC market filter failed, continuing without: {e}")
        market_gate = None
    
    # Setup components
    fees = FeesCfg(
        maker_bps=cfg['fees']['maker_bps'], 
        taker_bps=cfg['fees']['taker_bps']
    )
    
    trailing = TrailingConfig(**cfg['trailing'])
    
    # Run backtest for each symbol
    results = []
    all_trades = []
    
    print("=== SignalWarden Lite v1.3-T Backtest ===")
    print(f"Fixed margin: {cfg['risk']['margin_usdt']} USDT × {cfg['risk']['leverage']} leverage = {cfg['risk']['margin_usdt'] * cfg['risk']['leverage']} USDT nominal")
    print(f"Setups: Breakout={cfg['signals']['setups']['breakout']['enabled']}, "
          f"Micro={cfg['signals']['setups']['micro_breakout']['enabled']}, "
          f"Trend={cfg['signals']['setups']['trend_continuation']['enabled']}, "
          f"Squeeze={cfg['signals']['setups']['squeeze_breakout']['enabled']}")
    print(f"Trailing: activate_R={trailing.activate_R}, step_R={trailing.step_R}, move_to_be_at_R={trailing.move_to_be_at_R}")
    print(f"BTC filter: {'✅ Active' if market_gate is not None else '❌ Disabled'}")
    print()
    
    for symbol in cfg['symbols']:
        print(f"Running backtest for {symbol}...")
        
        try:
            # Load data
            df = load_candles_pkl(args.data_dir, symbol, '1h')
            
            # Prepare data with indicators and signals
            df_prepared = prep_data(df, cfg, market_gate)
            
            # Run backtest
            trades = run_backtest_one(
                df_prepared, symbol, 
                cfg['risk']['margin_usdt'], 
                cfg['risk']['leverage'],
                cfg['risk']['sl_atr_mult'], 
                trailing, fees
            )
            
            # Compute metrics
            metrics = compute_metrics(trades)
            metrics['symbol'] = symbol
            results.append(metrics)
            
            if not trades.empty:
                all_trades.append(trades)
                
            print(f"  {symbol}: {metrics['trades']} trades, "
                  f"PF={metrics['pf']:.2f}, WR={metrics['winrate']:.1%}, "
                  f"PnL={metrics['pnl']:.2f} USDT")
            print(f"    Setups: Breakout={metrics['breakout_trades']}, "
                  f"Micro={metrics['micro_trades']}, "
                  f"Trend={metrics['trend_trades']}, "
                  f"Squeeze={metrics['squeeze_trades']}")
            print(f"    Exits: SL_INIT={metrics['sl_init_exits']}, "
                  f"TRAIL={metrics['trail_exits']}, "
                  f"BE={metrics['be_exits']}")
                  
        except Exception as e:
            print(f"  Error processing {symbol}: {e}")
            # Add empty result
            empty_metrics = compute_metrics(pd.DataFrame())
            empty_metrics['symbol'] = symbol
            results.append(empty_metrics)
    
    # Save results
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)
    
    # Summary report
    report_df = pd.DataFrame(results).sort_values('pf', ascending=False)
    report_path = output_dir / 'backtest_report_v1_3_T.csv'
    report_df.to_csv(report_path, index=False)
    print(f"\nReport saved to: {report_path}")
    
    # All trades
    if all_trades:
        all_trades_df = pd.concat(all_trades, ignore_index=True)
        trades_path = output_dir / 'backtest_trades_v1_3_T.csv'
        all_trades_df.to_csv(trades_path, index=False)
        print(f"Trades saved to: {trades_path}")
    
    # Print summary
    print("\n=== BACKTEST SUMMARY v1.3-T ===")
    print(report_df.to_string(index=False))
    
    # Overall metrics
    if all_trades:
        overall_metrics = compute_metrics(all_trades_df)
        print(f"\n=== OVERALL PERFORMANCE v1.3-T ===")
        print(f"Total trades: {overall_metrics['trades']}")
        print(f"Win rate: {overall_metrics['winrate']:.1%}")
        print(f"Profit Factor: {overall_metrics['pf']:.2f}")
        print(f"Total PnL: {overall_metrics['pnl']:.2f} USDT")
        print(f"Average R: {overall_metrics['avg_R']:.2f}")
        print(f"Max R: {overall_metrics['max_R']:.2f}")
        print(f"Min R: {overall_metrics['min_R']:.2f}")
        print(f"\nSetup Breakdown:")
        print(f"  Breakout trades: {overall_metrics['breakout_trades']} ({overall_metrics['breakout_trades']/overall_metrics['trades']*100:.1f}%)")
        print(f"  Micro-breakout trades: {overall_metrics['micro_trades']} ({overall_metrics['micro_trades']/overall_metrics['trades']*100:.1f}%)")
        print(f"  Trend-continuation trades: {overall_metrics['trend_trades']} ({overall_metrics['trend_trades']/overall_metrics['trades']*100:.1f}%)")
        print(f"  Squeeze-breakout trades: {overall_metrics['squeeze_trades']} ({overall_metrics['squeeze_trades']/overall_metrics['trades']*100:.1f}%)")
        print(f"\nExit Breakdown:")
        print(f"  Initial SL exits: {overall_metrics['sl_init_exits']} ({overall_metrics['sl_init_exits']/overall_metrics['trades']*100:.1f}%)")
        print(f"  Trailing exits: {overall_metrics['trail_exits']} ({overall_metrics['trail_exits']/overall_metrics['trades']*100:.1f}%)")
        print(f"  Break-even exits: {overall_metrics['be_exits']} ({overall_metrics['be_exits']/overall_metrics['trades']*100:.1f}%)")

if __name__ == '__main__':
    main()
