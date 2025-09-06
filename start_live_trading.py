#!/usr/bin/env python3
"""
Quick start script for SignalWarden Lite v1.6-TXB Live Trading
Provides safety checks and easy mode switching
"""

import os
import sys
import argparse
import yaml
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from signalwarden_lite.live.run_live_v1_6_TXB import SignalWardenLive
from signalwarden_lite.utils.logger import get_logger

logger = get_logger(__name__)

def check_environment():
    """Check environment and API credentials"""
    logger.info("🔍 Checking environment...")
    
    # Check .env file
    if not os.path.exists('.env'):
        logger.error("❌ .env file not found! Create it with your Binance API credentials.")
        return False
        
    # Check API credentials
    api_key = os.getenv('BINANCE_API_KEY')
    secret = os.getenv('BINANCE_SECRET')
    
    if not api_key or not secret:
        logger.error("❌ Missing BINANCE_API_KEY or BINANCE_SECRET in .env file")
        return False
        
    logger.info(f"✅ API Key: {api_key[:8]}...{api_key[-8:]}")
    logger.info("✅ API Secret: [HIDDEN]")
    
    return True

def check_config(config_path: str, live_mode: bool):
    """Check and validate configuration"""
    logger.info(f"🔍 Checking configuration: {config_path}")
    
    if not os.path.exists(config_path):
        logger.error(f"❌ Config file not found: {config_path}")
        return False
        
    try:
        with open(config_path, 'r') as f:
            cfg = yaml.safe_load(f)
            
        # Check testnet setting
        testnet = cfg.get('exchange', {}).get('testnet', True)
        
        if live_mode and testnet:
            logger.error("❌ DANGER: You specified --live but config has testnet: true")
            logger.error("   Set testnet: false in config for live trading!")
            return False
            
        if not live_mode and not testnet:
            logger.warning("⚠️ Config has testnet: false but you're not using --live flag")
            logger.warning("   This will trade on LIVE exchange!")
            
        # Log key settings
        profile = cfg.get('profile', 'unknown')
        symbols = cfg.get('symbols', [])
        margin = cfg.get('risk', {}).get('margin_usdt', 0)
        leverage = cfg.get('risk', {}).get('leverage', 1)
        
        logger.info(f"📊 Profile: {profile}")
        logger.info(f"💰 Risk: {margin} USDT margin × {leverage} = {margin * leverage} USDT notional")
        logger.info(f"🎯 Symbols: {len(symbols)} pairs")
        logger.info(f"🧪 Mode: {'LIVE TRADING' if not testnet else 'TESTNET'}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Config validation failed: {e}")
        return False

def confirm_live_trading():
    """Confirm live trading with user"""
    logger.warning("🚨 LIVE TRADING MODE CONFIRMATION REQUIRED 🚨")
    logger.warning("You are about to start LIVE TRADING with REAL MONEY!")
    logger.warning("This will place REAL ORDERS on Binance USDM Futures!")
    
    print()
    print("Type 'I UNDERSTAND THE RISKS' to continue:")
    confirmation = input("> ").strip()
    
    if confirmation != "I UNDERSTAND THE RISKS":
        logger.info("❌ Live trading cancelled by user")
        return False
        
    print()
    print("Type 'START LIVE TRADING' to begin:")
    final_confirm = input("> ").strip()
    
    if final_confirm != "START LIVE TRADING":
        logger.info("❌ Live trading cancelled by user")
        return False
        
    logger.info("✅ Live trading confirmed by user")
    return True

def main():
    parser = argparse.ArgumentParser(description='Start SignalWarden v1.6-TXB Live Trading')
    parser.add_argument('--config', default='./signalwarden_lite/config/config_production.yaml', 
                       help='Config file path')
    parser.add_argument('--paper', action='store_true', 
                       help='Force paper trading mode (no real orders)')
    parser.add_argument('--live', action='store_true', 
                       help='Enable live trading mode (REAL MONEY)')
    parser.add_argument('--no-confirm', action='store_true', 
                       help='Skip live trading confirmation (DANGEROUS)')
    
    args = parser.parse_args()
    
    # Print banner
    print("=" * 80)
    print("🚀 SignalWarden Lite v1.6-TXB - Live Trading System")
    print("   Adaptive Shorts + MTF Strategy + Profit-First Trailing")
    print("=" * 80)
    
    # Check environment
    if not check_environment():
        return 1
        
    # Check configuration
    if not check_config(args.config, args.live):
        return 1
        
    # Determine mode
    if args.paper:
        paper_mode = True
        logger.info("📝 Paper trading mode selected")
    elif args.live:
        paper_mode = False
        logger.warning("🔴 Live trading mode selected")
        
        # Require confirmation unless --no-confirm
        if not args.no_confirm:
            if not confirm_live_trading():
                return 1
    else:
        # Auto-detect from config
        with open(args.config, 'r') as f:
            cfg = yaml.safe_load(f)
        testnet = cfg.get('exchange', {}).get('testnet', True)
        paper_mode = testnet
        
        if paper_mode:
            logger.info("🧪 Testnet mode (from config)")
        else:
            logger.warning("🔴 Live mode detected from config")
            if not args.no_confirm:
                if not confirm_live_trading():
                    return 1
    
    # Start trading system
    try:
        logger.info("🚀 Initializing SignalWarden v1.6-TXB...")
        trader = SignalWardenLive(args.config, paper_mode=paper_mode)
        
        logger.info("✅ System initialized successfully!")
        logger.info("🎯 Starting live trading loop...")
        logger.info("   Press Ctrl+C to stop")
        
        # Run the trading system
        trader.run()
        
    except KeyboardInterrupt:
        logger.info("🛑 Trading stopped by user")
        return 0
    except Exception as e:
        logger.error(f"💥 Trading system error: {e}")
        return 1

if __name__ == '__main__':
    sys.exit(main())
