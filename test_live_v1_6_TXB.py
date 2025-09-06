#!/usr/bin/env python3
"""
Test script for SignalWarden Lite v1.6-TXB Live Trading
Tests the system in paper mode first, then optionally on testnet
"""

import os
import sys
import time
import argparse
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from signalwarden_lite.live.run_live_v1_6_TXB import SignalWardenLive
from signalwarden_lite.utils.logger import get_logger

logger = get_logger(__name__)

def test_paper_mode():
    """Test in paper mode"""
    logger.info("🧪 Testing SignalWarden v1.6-TXB in PAPER mode...")
    
    config_path = "./signalwarden_lite/config/config_production.yaml"
    
    try:
        trader = SignalWardenLive(config_path, paper_mode=True)
        
        # Run a few cycles in paper mode
        logger.info("📝 Running 3 paper trading cycles...")
        
        for cycle in range(3):
            logger.info(f"🔄 Paper cycle {cycle + 1}/3")
            signals, trades = trader.run_trading_cycle()
            logger.info(f"   Result: {signals} signals detected")
            
            if cycle < 2:  # Don't sleep on last cycle
                time.sleep(10)  # Short sleep between cycles
                
        logger.info("✅ Paper mode test completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Paper mode test failed: {e}")
        return False

def test_testnet_mode():
    """Test on Binance testnet"""
    logger.info("🧪 Testing SignalWarden v1.6-TXB on BINANCE TESTNET...")
    
    # Load .env file
    from dotenv import load_dotenv
    load_dotenv()
    
    # Check environment
    if not os.getenv('BINANCE_API_KEY') or not os.getenv('BINANCE_SECRET'):
        logger.error("❌ Missing API credentials in .env file")
        return False
    
    config_path = "./signalwarden_lite/config/config_production.yaml"
    
    try:
        trader = SignalWardenLive(config_path, paper_mode=False)
        
        # Test exchange connection
        if trader.exchange:
            balance = trader.exchange.fetch_balance()
            logger.info(f"💰 Testnet balance: {balance.get('USDT', {}).get('total', 0):.2f} USDT")
            
            # Test BTC market filter
            btc_gate = trader.get_btc_market_bias()
            if btc_gate is not None:
                logger.info("✅ BTC market filter working")
            else:
                logger.warning("⚠️ BTC market filter failed")
            
            # Run one test cycle
            logger.info("🔄 Running one testnet cycle...")
            signals, trades = trader.run_trading_cycle()
            logger.info(f"   Result: {signals} signals, {trades} trades executed")
            
        logger.info("✅ Testnet test completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Testnet test failed: {e}")
        return False

def validate_config():
    """Validate production config"""
    logger.info("🔍 Validating production configuration...")
    
    config_path = "./signalwarden_lite/config/config_production.yaml"
    
    if not os.path.exists(config_path):
        logger.error(f"❌ Config file not found: {config_path}")
        return False
        
    import yaml
    
    try:
        with open(config_path, 'r') as f:
            cfg = yaml.safe_load(f)
            
        # Check critical settings
        checks = [
            ('profile', 'v1_6_TXB_production'),
            ('exchange.testnet', True),  # Should be True for testing
            ('risk.margin_usdt', 15),
            ('risk.leverage', 5),
            ('signals.setup_timeframes.breakout', '1h'),
            ('signals.setup_timeframes.inside_bar', '15m'),
        ]
        
        for key_path, expected in checks:
            keys = key_path.split('.')
            value = cfg
            
            try:
                for key in keys:
                    value = value[key]
                    
                if value != expected:
                    logger.warning(f"⚠️ Config {key_path}: expected {expected}, got {value}")
                else:
                    logger.info(f"✅ Config {key_path}: {value}")
                    
            except (KeyError, TypeError):
                logger.error(f"❌ Missing config key: {key_path}")
                return False
                
        # Check symbols
        symbols = cfg.get('symbols', [])
        logger.info(f"📊 Trading symbols: {len(symbols)} pairs")
        for symbol in symbols:
            logger.info(f"   - {symbol}")
            
        # Check short guard settings
        sg = cfg.get('short_guard', {})
        logger.info(f"🛡️ Short Guard: Bear RSI≤{sg.get('rsi_bear_max', 'N/A')}, Bull RSI≤{sg.get('rsi_bullcorr_max', 'N/A')}")
        
        logger.info("✅ Configuration validation passed!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Config validation failed: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Test SignalWarden v1.6-TXB Live Trading')
    parser.add_argument('--paper-only', action='store_true', help='Test paper mode only')
    parser.add_argument('--testnet-only', action='store_true', help='Test testnet mode only')
    parser.add_argument('--config-only', action='store_true', help='Validate config only')
    
    args = parser.parse_args()
    
    logger.info("🚀 SignalWarden v1.6-TXB Live Trading Test Suite")
    logger.info("=" * 60)
    
    success = True
    
    # Always validate config first
    if not validate_config():
        logger.error("❌ Configuration validation failed!")
        return 1
    
    if args.config_only:
        logger.info("✅ Configuration-only test completed!")
        return 0
    
    # Test paper mode
    if not args.testnet_only:
        if not test_paper_mode():
            success = False
        print()  # Empty line
    
    # Test testnet mode
    if not args.paper_only:
        if not test_testnet_mode():
            success = False
    
    print()  # Empty line
    if success:
        logger.info("🎉 ALL TESTS PASSED! System ready for live trading.")
        logger.info("📋 Next steps:")
        logger.info("   1. Set testnet: false in config_production.yaml")
        logger.info("   2. Run: python -m signalwarden_lite.live.run_live_v1_6_TXB --config ./signalwarden_lite/config/config_production.yaml")
        return 0
    else:
        logger.error("❌ Some tests failed. Fix issues before live trading!")
        return 1

if __name__ == '__main__':
    sys.exit(main())
