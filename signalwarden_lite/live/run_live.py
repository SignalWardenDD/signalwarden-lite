import os
import time
import yaml
import argparse
from datetime import datetime
from dotenv import load_dotenv
import ccxt
import pandas as pd

from ..core.features import add_indicators
from ..core.regimes import add_regime, RegimeThresholds
from ..core.signals import generate_signals, SignalParams
from ..core.risk import RiskConfig, build_partials, make_order_plan
from ..core.trailing import TrailingConfig
from ..core.execution import CCXTBinanceUSDMExecutor, PaperExecutor, ExecConfig
from ..core.quality import QualityController, QualityConfig
from ..core.storage import JSONStore
from ..core.types import Side
from ..utils.logger import get_logger

logger = get_logger(__name__)

def ccxt_symbol(symbol: str) -> str:
    """Convert our symbol format to CCXT format"""
    base, quote = symbol.split('_')
    return f"{base}/{quote}:{quote}"

def make_exchange(cfg: dict):
    """Create and configure CCXT exchange"""
    load_dotenv()
    
    api_key = os.getenv('BINANCE_API_KEY')
    secret = os.getenv('BINANCE_SECRET')
    
    if not api_key or not secret:
        raise ValueError("Missing BINANCE_API_KEY or BINANCE_SECRET in environment")
    
    exchange = ccxt.binanceusdm({
        'apiKey': api_key,
        'secret': secret,
        'enableRateLimit': cfg['exchange'].get('rate_limit', True),
        'options': {
            'defaultType': 'future'
        }
    })
    
    # Set sandbox mode if configured
    if cfg['exchange'].get('testnet', True):
        exchange.set_sandbox_mode(True)
        logger.info("Using testnet/sandbox mode")
    else:
        logger.warning("Using LIVE trading mode!")
    
    # Load markets
    exchange.load_markets()
    return exchange

def make_signal_params(cfg: dict) -> SignalParams:
    """Create SignalParams from config"""
    s = cfg['signals']
    return SignalParams(
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

def fetch_recent_data(exchange, symbol: str, timeframe: str = '1h', limit: int = 600) -> pd.DataFrame:
    """Fetch recent OHLCV data from exchange"""
    ccxt_sym = ccxt_symbol(symbol)
    ohlcv = exchange.fetch_ohlcv(ccxt_sym, timeframe=timeframe, limit=limit)
    
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = df['timestamp'] // 1000  # Convert to seconds
    
    return df

def prepare_data(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Prepare data with indicators and signals"""
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
    
    # Generate signals
    signal_params = make_signal_params(cfg)
    df = generate_signals(df, signal_params)
    
    return df

def run_live_trading(config_path: str, paper_mode: bool = False):
    """Main live trading loop with v1.1 enhancements"""
    # Load configuration
    with open(config_path, 'r') as f:
        cfg = yaml.safe_load(f)
    
    logger.info(f"Starting SignalWarden Lite v1.1 - {'Paper' if paper_mode else 'Live'} Mode")
    
    # Setup components
    exchange = None if paper_mode else make_exchange(cfg)
    
    exec_config = ExecConfig(**cfg['execution'])
    if paper_mode:
        executor = PaperExecutor(exec_config)
        logger.info("Using paper trading executor")
    else:
        executor = CCXTBinanceUSDMExecutor(exchange, exec_config)
        logger.info("Using live CCXT executor")
    
    # Risk and trading parameters
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
    
    # Quality control
    quality_config = QualityConfig(**cfg['quality'])
    quality_controller = QualityController(quality_config)
    
    # Storage
    storage = JSONStore('trading_state_v1.1.json')
    
    # Log configuration
    logger.info(f"Monitoring {len(cfg['symbols'])} symbols: {cfg['symbols']}")
    logger.info(f"Risk per trade: {risk.notional_usdt} USDT")
    logger.info(f"Setups enabled: Breakout={cfg['signals']['setups']['breakout']['enabled']}, "
               f"Pullback={cfg['signals']['setups']['pullback']['enabled']}, "
               f"Inside={cfg['signals']['setups']['inside_bar']['enabled']}")
    logger.info(f"Early cut-loss: {cfg['risk']['cutloss_early']['enabled']}")
    
    # Main trading loop
    cycle_count = 0
    last_day = None
    
    while True:
        try:
            cycle_count += 1
            current_time = datetime.utcnow()
            current_day = current_time.date()
            
            # Reset daily counters at midnight UTC
            if last_day != current_day:
                if last_day is not None:
                    logger.info(f"New trading day: {current_day}")
                quality_controller.reset_daily_counters()
                last_day = current_day
            
            logger.info(f"=== Trading Cycle {cycle_count} at {current_time.strftime('%Y-%m-%d %H:%M:%S')} UTC ===")
            
            for symbol in cfg['symbols']:
                try:
                    logger.info(f"Processing {symbol}...")
                    
                    # Fetch recent data
                    if paper_mode:
                        # In paper mode, simulate with some dummy data
                        # In real implementation, you might want to use saved data
                        logger.info(f"  Paper mode: skipping {symbol}")
                        continue
                    else:
                        df = fetch_recent_data(exchange, symbol, '1h', 600)
                    
                    # Prepare data with indicators and signals
                    df_prepared = prepare_data(df, cfg)
                    
                    # Get latest bar
                    latest = df_prepared.iloc[-1]
                    
                    # Get current position info from storage
                    symbol_state = storage.get_symbol(symbol)
                    open_positions = len(symbol_state.get('positions', []))
                    trades_today = symbol_state.get('trades_today', 0)
                    
                    # Check if we can trade
                    if not quality_controller.can_trade(symbol, open_positions, trades_today):
                        logger.info(f"  {symbol}: Trading blocked by quality controller")
                        continue
                    
                    # Check for signals
                    if latest.get('allow_long', False):
                        entry = float(latest['long_entry_final'])
                        reason = latest['long_reason']
                        logger.info(f"  {symbol}: LONG signal detected ({reason})")
                        
                        plan = make_order_plan(
                            Side.LONG, 
                            entry, 
                            latest['atr'], 
                            partials, 
                            risk
                        )
                        
                        qty = max(1e-9, risk.notional_usdt / entry)
                        
                        # Execute order
                        result = executor.place(symbol, plan, qty)
                        logger.info(f"  {symbol}: LONG {reason} @ {entry:.6f} → {result}")
                        
                        # Update counters
                        quality_controller.note_trade(symbol)
                        
                        # Update storage
                        symbol_state['trades_today'] = trades_today + 1
                        symbol_state['last_signal'] = {
                            'timestamp': int(latest['timestamp']),
                            'side': 'LONG',
                            'entry': entry,
                            'sl': plan.sl,
                            'reason': reason,
                            'result': result
                        }
                        storage.update_symbol(symbol, symbol_state)
                        
                    elif latest.get('allow_short', False):
                        entry = float(latest['short_entry_final'])
                        reason = latest['short_reason']
                        logger.info(f"  {symbol}: SHORT signal detected ({reason})")
                        
                        plan = make_order_plan(
                            Side.SHORT, 
                            entry, 
                            latest['atr'], 
                            partials, 
                            risk
                        )
                        
                        qty = max(1e-9, risk.notional_usdt / entry)
                        
                        # Execute order
                        result = executor.place(symbol, plan, qty)
                        logger.info(f"  {symbol}: SHORT {reason} @ {entry:.6f} → {result}")
                        
                        # Update counters
                        quality_controller.note_trade(symbol)
                        
                        # Update storage
                        symbol_state['trades_today'] = trades_today + 1
                        symbol_state['last_signal'] = {
                            'timestamp': int(latest['timestamp']),
                            'side': 'SHORT',
                            'entry': entry,
                            'sl': plan.sl,
                            'reason': reason,
                            'result': result
                        }
                        storage.update_symbol(symbol, symbol_state)
                        
                    else:
                        logger.info(f"  {symbol}: No signals (regime={latest.get('regime', 'unknown')}, "
                                  f"trend_long={latest.get('trend_long', False)}, "
                                  f"trend_short={latest.get('trend_short', False)})")
                
                except Exception as e:
                    logger.error(f"Error processing {symbol}: {e}")
                    continue
            
            # Sleep until next cycle (120 seconds = 2 minutes)
            logger.info(f"Cycle {cycle_count} completed. Sleeping for 120 seconds...")
            time.sleep(120)
            
        except KeyboardInterrupt:
            logger.info("Received interrupt signal, shutting down...")
            break
        except Exception as e:
            logger.error(f"Unexpected error in main loop: {e}")
            logger.info("Continuing after 60 seconds...")
            time.sleep(60)

def main():
    parser = argparse.ArgumentParser(description='Run SignalWarden Lite v1.1 Live Trading')
    parser.add_argument('--config', required=True, help='Config YAML file path')
    parser.add_argument('--paper', action='store_true', help='Run in paper trading mode')
    
    args = parser.parse_args()
    
    run_live_trading(args.config, paper_mode=args.paper)

if __name__ == '__main__':
    main()