import argparse
import yaml
import pandas as pd
from pathlib import Path

from ..core.data_loader import load_candles_pkl
from ..core.features import add_indicators
from ..core.regimes import add_regime, RegimeThresholds
from ..core.signals import generate_signals, SignalParams
from ..core.risk import RiskConfig, build_partials
from ..core.trailing import TrailingConfig
from .engine import run_backtest_one, FeesCfg, CutLossCfg

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
            'pullback_trades': 0,
            'inside_trades': 0,
            'early_cuts': 0
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
    pullback_trades = len(trades[trades['entry_reason'] == 'pullback'])
    inside_trades = len(trades[trades['entry_reason'] == 'inside'])
    early_cuts = len(trades[trades['reason'] == 'EARLY_CUT'])
    
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
        'pullback_trades': pullback_trades,
        'inside_trades': inside_trades,
        'early_cuts': early_cuts
    }

def prep_data(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
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
    signal_params = SignalParams(
        lookback_calm=s['dynamic_lookback']['calm'],
        lookback_normal=s['dynamic_lookback']['normal'],
        lookback_high=s['dynamic_lookback']['high'],
        atr_cushion_calm=s['atr_cushion']['calm'],
        atr_cushion_normal=s['atr_cushion']['normal'],
        atr_cushion_high=s['atr_cushion']['high'],
        ltf_thinbar_k=s['ltf_thinbar_k'],
        setup_breakout=s['setups']['breakout']['enabled'],
        setup_pullback=s['setups']['pullback']['enabled'],
        setup_inside=s['setups']['inside_bar']['enabled'],
        pb_ema_fast=s['setups']['pullback']['ema_fast'],
        pb_ema_slow=s['setups']['pullback']['ema_slow'],
        pb_retrace_band_k_atr=s['setups']['pullback']['retrace_band_k_atr'],
        ib_min_prev_range_k_atr=s['setups']['inside_bar']['min_prev_range_k_atr'],
    )
    
    # Generate signals
    df = generate_signals(df, signal_params)
    
    return df

def main():
    parser = argparse.ArgumentParser(description='Run SignalWarden Lite v1.1 Backtest')
    parser.add_argument('--data-dir', required=True, help='Directory containing pickle files')
    parser.add_argument('--config', required=True, help='Config YAML file path')
    parser.add_argument('--output-dir', default='.', help='Output directory for results')
    
    args = parser.parse_args()
    
    # Load configuration
    with open(args.config, 'r') as f:
        cfg = yaml.safe_load(f)
    
    # Setup components
    fees = FeesCfg(
        maker_bps=cfg['fees']['maker_bps'], 
        taker_bps=cfg['fees']['taker_bps']
    )
    
    risk = RiskConfig(
        mode=cfg['risk']['mode'],
        notional_usdt=cfg['risk']['notional_usdt'],
        sl_atr_mult=cfg['risk']['sl_atr_mult'],
        cutloss_early_enabled=cfg['risk']['cutloss_early']['enabled'],
        cutloss_early_bars=cfg['risk']['cutloss_early']['bars'],
        cutloss_early_threshold_R=cfg['risk']['cutloss_early']['threshold_R']
    )
    
    partials = build_partials(cfg['partials'])
    trailing = TrailingConfig(**cfg['trailing'])
    cutloss = CutLossCfg(
        enabled=cfg['risk']['cutloss_early']['enabled'],
        bars=cfg['risk']['cutloss_early']['bars'],
        threshold_R=cfg['risk']['cutloss_early']['threshold_R']
    )
    
    # Run backtest for each symbol
    results = []
    all_trades = []
    
    print("=== SignalWarden Lite v1.1 Backtest ===")
    print(f"Setups: Breakout={cfg['signals']['setups']['breakout']['enabled']}, "
          f"Pullback={cfg['signals']['setups']['pullback']['enabled']}, "
          f"Inside={cfg['signals']['setups']['inside_bar']['enabled']}")
    print(f"Early cut-loss: {cutloss.enabled} (bars={cutloss.bars}, threshold={cutloss.threshold_R}R)")
    print()
    
    for symbol in cfg['symbols']:
        print(f"Running backtest for {symbol}...")
        
        try:
            # Load data
            df = load_candles_pkl(args.data_dir, symbol, '1h')
            
            # Prepare data with indicators and signals
            df_prepared = prep_data(df, cfg)
            
            # Run backtest
            trades = run_backtest_one(
                df_prepared, symbol, partials, risk.notional_usdt, 
                risk.sl_atr_mult, trailing, fees, cutloss
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
                  f"Pullback={metrics['pullback_trades']}, "
                  f"Inside={metrics['inside_trades']}, "
                  f"EarlyCuts={metrics['early_cuts']}")
                  
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
    report_path = output_dir / 'backtest_report_v1.1.csv'
    report_df.to_csv(report_path, index=False)
    print(f"\nReport saved to: {report_path}")
    
    # All trades
    if all_trades:
        all_trades_df = pd.concat(all_trades, ignore_index=True)
        trades_path = output_dir / 'backtest_trades_v1.1.csv'
        all_trades_df.to_csv(trades_path, index=False)
        print(f"Trades saved to: {trades_path}")
    
    # Print summary
    print("\n=== BACKTEST SUMMARY v1.1 ===")
    print(report_df.to_string(index=False))
    
    # Overall metrics
    if all_trades:
        overall_metrics = compute_metrics(all_trades_df)
        print(f"\n=== OVERALL PERFORMANCE v1.1 ===")
        print(f"Total trades: {overall_metrics['trades']}")
        print(f"Win rate: {overall_metrics['winrate']:.1%}")
        print(f"Profit Factor: {overall_metrics['pf']:.2f}")
        print(f"Total PnL: {overall_metrics['pnl']:.2f} USDT")
        print(f"Average R: {overall_metrics['avg_R']:.2f}")
        print(f"Max R: {overall_metrics['max_R']:.2f}")
        print(f"Min R: {overall_metrics['min_R']:.2f}")
        print(f"\nSetup Breakdown:")
        print(f"  Breakout trades: {overall_metrics['breakout_trades']} ({overall_metrics['breakout_trades']/overall_metrics['trades']*100:.1f}%)")
        print(f"  Pullback trades: {overall_metrics['pullback_trades']} ({overall_metrics['pullback_trades']/overall_metrics['trades']*100:.1f}%)")
        print(f"  Inside trades: {overall_metrics['inside_trades']} ({overall_metrics['inside_trades']/overall_metrics['trades']*100:.1f}%)")
        print(f"  Early cuts: {overall_metrics['early_cuts']} ({overall_metrics['early_cuts']/overall_metrics['trades']*100:.1f}%)")

if __name__ == '__main__':
    main()