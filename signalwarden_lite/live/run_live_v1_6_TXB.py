# signalwarden_lite/live/run_live_v1_6_TXB.py
"""
SignalWarden Lite v1.6-TXB Live Trading
- Adaptive Shorts with BTC market filter
- MTF strategy (1h + 15m)  
- Production-ready architecture
- Real maker/taker fees
"""

import os
import time
import yaml
import json
import argparse
import threading
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
import ccxt
import pandas as pd
import numpy as np
from typing import Optional, Dict, Any

from ..core.features import add_indicators
from ..core.regimes import add_regime, RegimeThresholds
from ..core.market import compute_market_bias
from ..core.signals import generate_signals, SignalParams
from ..core.trailing import TrailingConfig, update_trailing_hybrid
from ..core.trailing_pnl_only import TrailingConfigPnLOnly, update_trailing_pnl_only
from ..core.storage import JSONStore
from ..core.state_validator import StateValidator
from ..core.auto_fixer import AutoFixer
from ..core.types import Side
from ..utils.logger import get_logger

logger = get_logger(__name__)

class SignalWardenLive:
    """Production-ready live trading system v1.6-TXB"""
    
    def __init__(self, config_path: str, paper_mode: bool = False):
        self.config_path = config_path
        self.paper_mode = paper_mode
        self.load_config()
        self.setup_exchange()
        self.setup_components()
        
        # State tracking with cache management
        self.last_1h_fetch = {}  # symbol -> timestamp
        self.last_15m_fetch = {}  # symbol -> timestamp  
        self.btc_gate_cache = None
        self.btc_gate_timestamp = int(time.time())  # ИСПРАВЛЕНО: Правильная инициализация времени
        self.data_cache = {}  # symbol_timeframe -> (data, timestamp)
        self.cache_ttl = 60  # Cache TTL: 60 seconds
        
        logger.info(f"🚀 SignalWarden v1.6-TXB initialized ({'Paper' if paper_mode else 'LIVE'} mode)")
    
    def clear_stale_cache(self):
        """Clear stale cache entries to prevent trading on outdated data"""
        current_time = time.time()
        stale_keys = []
        
        for key, (data, timestamp) in self.data_cache.items():
            if current_time - timestamp > self.cache_ttl:
                stale_keys.append(key)
        
        for key in stale_keys:
            del self.data_cache[key]
            logger.debug(f"🧹 Cleared stale cache for {key}")
        
        # Clear BTC gate cache if stale
        if self.btc_gate_cache is not None and current_time - self.btc_gate_timestamp > self.cache_ttl:
            self.btc_gate_cache = None
            self.btc_gate_timestamp = 0
            logger.debug("🧹 Cleared stale BTC gate cache")
        
    def load_config(self):
        """Load and validate configuration"""
        with open(self.config_path, 'r') as f:
            self.cfg = yaml.safe_load(f)
            
        # Validate v1.6-TXB config structure
        required_sections = ['signals', 'short_guard', 'market_filter', 'timeframes']
        for section in required_sections:
            if section not in self.cfg:
                raise ValueError(f"Missing required config section: {section}")
                
        logger.info(f"✅ Config loaded: {self.cfg['profile']}")
        logger.info(f"📊 Symbols: {self.cfg['symbols']}")
        logger.info(f"⏰ Timeframes: {self.cfg['timeframes']}")
        
    def setup_exchange(self):
        """Setup CCXT exchange connection"""
        if self.paper_mode:
            self.exchange = None
            logger.info("📝 Paper trading mode - no exchange connection")
            return
            
        load_dotenv()
        
        api_key = os.getenv('BINANCE_API_KEY')
        secret = os.getenv('BINANCE_SECRET')
        
        if not api_key or not secret:
            raise ValueError("❌ Missing BINANCE_API_KEY or BINANCE_SECRET in .env file")
        
        self.exchange = ccxt.binanceusdm({
            'apiKey': api_key,
            'secret': secret,
            'enableRateLimit': self.cfg['exchange'].get('rate_limit', True),
            'timeout': 30000,
            'options': {'defaultType': 'future'}
        })
        
        # Set sandbox/live mode
        testnet_mode = self.cfg['exchange'].get('testnet', True)
        if testnet_mode:
            self.exchange.set_sandbox_mode(True)
            logger.info("🧪 TESTNET mode enabled")
        else:
            logger.warning("🔴 LIVE TRADING mode enabled!")
            
        try:
            self.exchange.load_markets()
            balance = self.exchange.fetch_balance()
            logger.info(f"💰 Connected to Binance USDM. USDT balance: {balance.get('USDT', {}).get('total', 0):.2f}")
        except Exception as e:
            logger.error(f"❌ Exchange connection failed: {e}")
            raise
            
    def setup_components(self):
        """Setup trading components"""
        # Signal parameters for v1.6-TXB
        s, st = self.cfg['signals'], self.cfg['signals']['setups']
        self.signal_params = SignalParams(
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
            sg_rsi_bear_max=self.cfg['short_guard']['rsi_bear_max'],
            sg_rsi_bullcorr_max=self.cfg['short_guard']['rsi_bullcorr_max'],
            sg_min_natr_bear=self.cfg['short_guard']['min_natr_bear'],
            sg_min_natr_bullcorr=self.cfg['short_guard']['min_natr_bullcorr'],
            sg_require_close_below_ema20_bullcorr=self.cfg['short_guard']['require_close_below_ema20_bullcorr'],
            sg_slope_lookback=self.cfg['short_guard']['slope_lookback'],
            lg_rsi_long_min=52.0
        )
        
        # Regime thresholds
        self.regime_thresholds = RegimeThresholds(**self.cfg['regime']['calm_thresholds'])
        
        # Trailing config - ЧИСТО PnL-BASED ТРЕЙЛИНГ ПО УРОВНЯМ
        # Простая и понятная система только по прибыли в долларах
        trailing_cfg = self.cfg.get('trailing', {})
        self.trailing = TrailingConfigPnLOnly(
            level_1_pnl=trailing_cfg.get('level_1_pnl', 0.06),
            level_1_keep_pct=trailing_cfg.get('level_1_keep_pct', 0.50),
            level_2_pnl=trailing_cfg.get('level_2_pnl', 0.15),
            level_2_keep_pct=trailing_cfg.get('level_2_keep_pct', 0.60),
            level_3_pnl=trailing_cfg.get('level_3_pnl', 0.25),
            level_3_keep_pct=trailing_cfg.get('level_3_keep_pct', 0.70),
            level_4_pnl=trailing_cfg.get('level_4_pnl', 0.35),
            level_4_keep_pct=trailing_cfg.get('level_4_keep_pct', 0.80)
        )
        
        # Storage
        self.storage = JSONStore('trading_state_v1_6_TXB.json')
        
        # Risk parameters - FIXED: margin_usdt is NOTIONAL size, not actual margin
        self.margin_usdt = self.cfg['risk']['margin_usdt']  # 21 USDT notional per trade
        self.leverage = self.cfg['risk']['leverage']  # 5x leverage
        self.sl_atr_mult = self.cfg['risk']['sl_atr_mult']  # 1.5x ATR for SL
        self.sl_order_type = self.cfg['risk'].get('sl_order_type', 'stop_market')  # Default to market stop loss
        
        # Active positions tracking (1 position per symbol max)
        self.active_positions = {}  # symbol -> position_info
        
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Загрузить позиции из торгового состояния
        self.load_positions_from_state()
        
        # Initialize validation and auto-fix components
        self.setup_validation_and_fixes()
        
        # Sync positions from exchange on startup
        self.sync_positions_from_exchange()
        
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Принудительная очистка несуществующих позиций
        self.force_cleanup_nonexistent_positions()
        
        # Trailing thread control
        self.trailing_thread = None
        self.trailing_stop_event = threading.Event()
        
        logger.info(f"⚙️ Risk per trade: {self.margin_usdt} USDT notional ({self.margin_usdt/self.leverage:.1f} USDT actual margin)")
        logger.info(f"🛡️ Stop-loss type: {self.sl_order_type} ({'маркет стоп-лосс (рыночный)' if self.sl_order_type == 'stop_market' else 'лимитный стоп-лосс'})")
    
    def load_positions_from_state(self):
        """КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Загрузить активные позиции из торгового состояния"""
        try:
            state_data = self.storage.read()
            symbols_data = state_data.get('symbols', {})
            
            loaded_count = 0
            for symbol, data in symbols_data.items():
                if symbol.endswith('_position'):
                    continue
                
                active_pos = data.get('active_position')
                if active_pos and active_pos.get('entry', 0) > 0:
                    # Инициализируем недостающие поля для трейлинга
                    if 'peak_pnl_usdt' not in active_pos:
                        active_pos['peak_pnl_usdt'] = 0.0
                    if 'trailing_active' not in active_pos:
                        active_pos['trailing_active'] = False
                    if 'trailing_level' not in active_pos:
                        active_pos['trailing_level'] = 'INACTIVE'
                    
                    # Загружаем позицию в память
                    self.active_positions[symbol] = active_pos
                    loaded_count += 1
                    
                    logger.info(f"🔄 Загружена позиция {symbol}: {active_pos['side']} {active_pos['qty']:.4f} @ ${active_pos['entry']:.6f}")
                    logger.info(f"   Peak PnL: ${active_pos['peak_pnl_usdt']:.4f}, Trailing: {active_pos['trailing_active']}")
            
            if loaded_count > 0:
                logger.info(f"✅ Загружено позиций из состояния: {loaded_count}")
            else:
                logger.info("ℹ️ Активные позиции в состоянии не найдены")
                
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки позиций из состояния: {e}")
        
    def setup_validation_and_fixes(self):
        """Настроить валидацию и автоисправление"""
        try:
            # Инициализировать валидатор и автоисправитель
            self.state_validator = StateValidator('trading_state_v1_6_TXB.json', self.exchange)
            self.auto_fixer = AutoFixer('trading_state_v1_6_TXB.json', self.exchange)
            
            # Запустить автоматическое исправление при старте
            logger.info("🔧 Запуск автоматического исправления при старте...")
            fix_result = self.auto_fixer.run_auto_fix(self.cfg['symbols'])
            
            if fix_result['success']:
                if fix_result['fixes_applied']:
                    logger.info(f"✅ Автоисправление завершено. Применено исправлений: {len(fix_result['fixes_applied'])}")
                    for fix in fix_result['fixes_applied']:
                        logger.info(f"   - {fix['type']}: {fix.get('symbols', fix.get('positions', 'N/A'))}")
                else:
                    logger.info("✅ Проблем не найдено, автоисправление не требуется")
            else:
                logger.warning(f"⚠️ Автоисправление завершено с ошибками: {fix_result['errors']}")
                
            # Запустить валидацию
            validation_result = self.state_validator.run_full_validation(self.cfg['symbols'])
            if not validation_result['overall_valid']:
                logger.warning(f"⚠️ Найдены проблемы валидации: {validation_result['total_errors']}")
            else:
                logger.info("✅ Валидация состояния пройдена успешно")
                
        except Exception as e:
            logger.error(f"❌ Ошибка настройки валидации и автоисправления: {e}")
            
    def run_periodic_validation(self):
        """Запустить периодическую валидацию"""
        try:
            logger.info("🔍 Периодическая валидация состояния...")
            
            # Быстрая валидация консистентности
            validation_result = self.state_validator.run_full_validation(self.cfg['symbols'])
            
            if not validation_result['overall_valid']:
                logger.warning(f"⚠️ Найдены проблемы валидации: {validation_result['total_errors']}")
                
                # Попытаться исправить автоматически
                fix_result = self.auto_fixer.run_auto_fix(self.cfg['symbols'])
                if fix_result['success'] and fix_result['fixes_applied']:
                    logger.info(f"✅ Автоматически исправлено: {len(fix_result['fixes_applied'])} проблем")
                else:
                    logger.warning("⚠️ Не удалось автоматически исправить проблемы")
            else:
                logger.debug("✅ Периодическая валидация пройдена успешно")
                
        except Exception as e:
            logger.error(f"❌ Ошибка периодической валидации: {e}")
        
    def sync_positions_from_exchange(self):
        """Sync positions from Binance exchange"""
        if self.paper_mode:
            return
            
        try:
            positions = self.exchange.fetch_positions()
            logger.info(f"📊 Syncing positions from exchange...")
            
            synced_count = 0
            for pos in positions:
                if float(pos['contracts']) == 0:  # No position
                    continue
                    
                symbol_ccxt = pos['symbol']  # ADA/USDT:USDT format
                if ':USDT' not in symbol_ccxt:
                    continue
                    
                # Convert to our format: ADA/USDT:USDT -> ADA_USDT
                base_quote = symbol_ccxt.split(':')[0]  # ADA/USDT
                symbol = base_quote.replace('/', '_')   # ADA_USDT
                
                if symbol not in self.cfg['symbols']:
                    continue
                    
                # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: НЕ ПЕРЕЗАПИСЫВАЕМ ТРЕЙЛИНГ SL!
                # Проверяем, есть ли уже активная позиция с трейлингом
                existing_pos = self.active_positions.get(symbol)
                if existing_pos and existing_pos.get('trailing_active', False):
                    # Позиция уже в трейлинге - НЕ ТРОГАЕМ SL!
                    logger.warning(f"🔒 {symbol}: Позиция в трейлинге - пропускаем пересчет SL при синхронизации")
                    logger.warning(f"🔒 {symbol}: Текущий трейлинг SL: {existing_pos.get('sl_current', 'N/A')}")
                    
                    # Просто обновляем данные позиции без изменения SL
                    entry_price = float(pos['entryPrice'])
                    side = 'LONG' if pos['side'] == 'long' else 'SHORT'
                    
                    # Используем существующий SL из трейлинга
                    sl_price = existing_pos['sl_current']
                    
                    # Получаем ATR для сохранения в позиции
                    try:
                        df = self.fetch_recent_data(symbol, '1h', 100)
                        if df is not None and len(df) > 0:
                            from signalwarden_lite.core.features import add_indicators
                            df = add_indicators(df, atr_p=14)
                            atr = float(df.iloc[-1]['atr'])
                        else:
                            atr = entry_price * 0.01  # Fallback ATR
                    except:
                        atr = entry_price * 0.01  # Fallback ATR
                        
                else:
                    # Новая позиция или позиция без трейлинга - рассчитываем SL
                    try:
                        # Get recent data to calculate ATR
                        df = self.fetch_recent_data(symbol, '1h', 100)
                        
                        if df is not None and len(df) > 0:
                            # ИСПРАВЛЕНО: Используем правильный расчет ATR через add_indicators
                            from signalwarden_lite.core.features import add_indicators
                            df = add_indicators(df, atr_p=14)
                            atr = float(df.iloc[-1]['atr'])
                            
                            # Calculate stop loss with minimum ATR protection
                            entry_price = float(pos['entryPrice'])
                            side = 'LONG' if pos['side'] == 'long' else 'SHORT'
                            
                            # Используем чистый ATR (как в стратегии)
                            effective_atr = atr
                            
                            if side == 'LONG':
                                sl_price = entry_price - (self.sl_atr_mult * effective_atr)
                            else:
                                sl_price = entry_price + (self.sl_atr_mult * effective_atr)
                                
                            # Логирование SL для диагностики
                            sl_distance = abs(sl_price - entry_price)
                            sl_distance_pct = (sl_distance / entry_price) * 100
                            logger.info(f"🔍 {symbol} {side} SYNC SL: Entry {entry_price:.6f}, SL {sl_price:.6f}, Distance {sl_distance:.6f} ({sl_distance_pct:.2f}%)")
                            
                            # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Создаем stop-market ордер только для новых позиций
                            try:
                                ccxt_sym = self.ccxt_symbol(symbol)
                                sl_side = 'sell' if side == 'LONG' else 'buy'
                                
                                # Отменяем старые SL ордера
                                try:
                                    open_orders = self.exchange.fetch_open_orders(ccxt_sym)
                                    for order in open_orders:
                                        if order['type'] in ['stop_market', 'stop'] and order['info'].get('reduceOnly'):
                                            self.exchange.cancel_order(order['id'], ccxt_sym)
                                            logger.info(f"🗑️ {symbol}: Отменен старый SL ордер {order['id']}")
                                except Exception as e:
                                    logger.warning(f"⚠️ {symbol}: Не удалось отменить старые ордера: {e}")
                                
                                # Создаем новый stop-market ордер
                                new_sl_order = self.exchange.create_order(
                                    ccxt_sym,
                                    'stop_market',
                                    sl_side,
                                    pos['contracts'],
                                    None,  # Нет цены исполнения для stop_market
                                    params={
                                        'stopPrice': sl_price,
                                        'reduceOnly': True,
                                        'timeInForce': 'GTC'
                                    }
                                )
                                logger.info(f"✅ {symbol}: Создан новый stop-market ордер {new_sl_order['id']} @ {sl_price:.6f}")
                                
                            except Exception as e:
                                logger.error(f"❌ {symbol}: Ошибка создания stop-market ордера: {e}")
                            
                            # Обновляем ATR на эффективное значение
                            atr = effective_atr
                        else:
                            # Fallback: use 2% stop loss if no data
                            entry_price = float(pos['entryPrice'])
                            side = 'LONG' if pos['side'] == 'long' else 'SHORT'
                            
                            if side == 'LONG':
                                sl_price = entry_price * 0.98
                            else:
                                sl_price = entry_price * 1.02
                            atr = entry_price * 0.02  # 2% fallback
                    except Exception as e:
                        logger.error(f"❌ {symbol}: Ошибка синхронизации позиции: {e}")
                        continue
                
                # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Очищаем старые данные перед синхронизацией
                # Но только если локальная и биржевая позиции не совпадают
                if symbol in self.active_positions:
                    local_pos = self.active_positions[symbol]
                    # Проверяем совпадение с биржевой позицией
                    local_side = local_pos.get('side', '')
                    local_qty = abs(local_pos.get('qty', 0))
                    exchange_side = 'LONG' if pos['side'] == 'long' else 'SHORT'
                    exchange_qty = abs(float(pos['contracts']))
                    
                    # Если позиции кардинально различаются - очищаем
                    if local_side != exchange_side or abs(local_qty - exchange_qty) > 0.1:
                        logger.warning(f"🧹 {symbol}: Локальная и биржевая позиции не совпадают")
                        logger.warning(f"🧹 {symbol}: Локальная: {local_side} {local_qty}, Биржа: {exchange_side} {exchange_qty}")
                        del self.active_positions[symbol]
                        self.cleanup_position_state(symbol)
                    else:
                        logger.info(f"✅ {symbol}: Локальная позиция совпадает с биржевой, пропускаем синхронизацию")
                        continue  # Пропускаем синхронизацию для этой позиции
                
                # Create position info from exchange data (ЧИСТЫЕ данные!)
                position_info = {
                    'symbol': symbol,
                    'side': 'LONG' if pos['side'] == 'long' else 'SHORT',
                    'entry': float(pos['entryPrice']),
                    'qty': abs(float(pos['contracts'])),
                    'sl_initial': sl_price,
                    'sl_current': sl_price,
                    'last_updated_sl': sl_price,  # КРИТИЧНО: устанавливаем чтобы избежать спама
                    'atr': atr,
                    'timestamp': time.time(),
                    'order_id': None,
                    'trailing_active': False,  # НОВАЯ позиция - трейлинг НЕАКТИВЕН
                    'unrealized_pnl': float(pos['unrealizedPnl']),
                    'peak_pnl_usdt': max(0.0, float(pos['unrealizedPnl'])),  # Начинаем с текущего PnL
                    'synced_from_exchange': True
                }
                
                self.active_positions[symbol] = position_info
                logger.info(f"✅ {symbol}: Позиция синхронизирована с чистыми данными трейлинга")
                synced_count += 1
                
                # Place stop loss order for synced position
                try:
                    self.update_sliding_stop_loss(symbol, position_info)
                    logger.info(f"📍 Synced {symbol}: {position_info['side']} @ {position_info['entry']:.6f}, "
                              f"Qty: {position_info['qty']:.6f}, SL: {sl_price:.6f}, PnL: {position_info['unrealized_pnl']:.2f} USDT")
                except Exception as sl_error:
                    logger.warning(f"⚠️ Could not place SL order for synced position {symbol}: {sl_error}")
                    logger.info(f"📍 Synced {symbol}: {position_info['side']} @ {position_info['entry']:.6f}, "
                              f"Qty: {position_info['qty']:.6f}, SL: {sl_price:.6f} (NO SL ORDER), PnL: {position_info['unrealized_pnl']:.2f} USDT")
                          
            logger.info(f"✅ Synced {synced_count} positions from exchange")
            
        except Exception as e:
            logger.error(f"❌ Failed to sync positions from exchange: {e}")
    
    def force_cleanup_nonexistent_positions(self):
        """Принудительная очистка позиций, которые не существуют на бирже"""
        if self.paper_mode:
            return
            
        logger.info("🧹 Принудительная очистка несуществующих позиций...")
        
        positions_to_remove = []
        
        for symbol in list(self.active_positions.keys()):
            try:
                ccxt_sym = self.ccxt_symbol(symbol)
                exchange_positions = self.exchange.fetch_positions([ccxt_sym])
                
                position_exists = False
                for exchange_pos in exchange_positions:
                    if float(exchange_pos['contracts']) != 0:
                        position_exists = True
                        break
                
                if not position_exists:
                    positions_to_remove.append(symbol)
                    logger.warning(f"🧹 {symbol}: Позиция не существует на бирже, помечена к удалению")
                    
            except Exception as e:
                logger.warning(f"⚠️ {symbol}: Не удалось проверить позицию на бирже: {e}")
        
        # Удаляем несуществующие позиции
        for symbol in positions_to_remove:
            if symbol in self.active_positions:
                del self.active_positions[symbol]
                self.cleanup_position_state(symbol)  # ИСПРАВЛЕНО: используем правильную функцию
                logger.info(f"🗑️ {symbol}: Позиция удалена из локального трекинга")
        
        if positions_to_remove:
            logger.info(f"✅ Очищено {len(positions_to_remove)} несуществующих позиций")
        else:
            logger.info("✅ Все позиции синхронизированы с биржей")
    
    def has_open_position(self, symbol: str) -> bool:
        """Check if symbol has an open position (both locally and on exchange)"""
        # Сначала проверяем локально
        if symbol not in self.active_positions:
            return False
            
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Проверяем существование позиции на бирже
        if not self.paper_mode:
            try:
                ccxt_sym = self.ccxt_symbol(symbol)
                exchange_positions = self.exchange.fetch_positions([ccxt_sym])
                
                for exchange_pos in exchange_positions:
                    if float(exchange_pos['contracts']) != 0:
                        # Позиция существует на бирже
                        return True
                
                # Позиция НЕ существует на бирже - очищаем локально
                logger.warning(f"🧹 {symbol}: Позиция не существует на бирже, очищаем локально")
                if symbol in self.active_positions:
                    del self.active_positions[symbol]
                    self.cleanup_position_state(symbol)  # ИСПРАВЛЕНО: используем правильную функцию
                return False
                
            except Exception as e:
                logger.warning(f"⚠️ {symbol}: Не удалось проверить позицию на бирже: {e}")
                # В случае ошибки возвращаем локальное состояние
                return True
        
        # В paper mode используем только локальное состояние
        return True
    
    def can_open_new_position(self) -> bool:
        """Check if we have enough balance for a new position"""
        if self.paper_mode:
            return len(self.active_positions) < len(self.cfg['symbols'])
            
        try:
            # Get current balance
            balance = self.exchange.fetch_balance()
            free_usdt = balance.get('USDT', {}).get('free', 0)
            
            # With 5x leverage, margin_usdt is NOTIONAL, actual margin = notional/leverage
            # Small buffer for fees (~0.1% entry + 0.1% exit = 0.2% total)  
            actual_margin_per_position = self.margin_usdt / self.leverage  # Real margin needed
            required_margin = actual_margin_per_position * 1.05  # 5% buffer for fees
            
            if free_usdt < required_margin:
                logger.debug(f"Insufficient balance: {free_usdt:.2f} USDT free, need {required_margin:.2f} USDT")
                return False
                
            # Also check we don't exceed max positions per symbol limit
            current_positions = len(self.active_positions)  # Use tracked positions
            max_total_positions = len(self.cfg['symbols'])  # 1 position per symbol
            
            if current_positions >= max_total_positions:
                logger.debug(f"Max positions reached: {current_positions}/{max_total_positions}")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Error checking balance for new position: {e}")
            return False  # Conservative: don't open on error
        
    def get_position_pnl_from_exchange(self, symbol: str) -> float:
        """Get real-time PnL from exchange"""
        if self.paper_mode:
            logger.debug(f"📊 {symbol}: Paper mode - возвращаем PnL=0.0")
            return 0.0
            
        try:
            ccxt_sym = self.ccxt_symbol(symbol)
            positions = self.exchange.fetch_positions([ccxt_sym])
            
            logger.debug(f"📊 {symbol}: Получено позиций с биржи: {len(positions)}")
            
            for pos in positions:
                contracts = float(pos['contracts'])
                if contracts != 0:
                    pnl = float(pos['unrealizedPnl'])
                    logger.debug(f"📊 {symbol}: Найдена позиция - Contracts: {contracts}, PnL: {pnl:.4f}")
                    return pnl
            
            logger.debug(f"📊 {symbol}: Позиция не найдена на бирже (contracts=0)")
            return 0.0
            
        except Exception as e:
            logger.warning(f"⚠️ {symbol}: Ошибка получения PnL с биржи: {e}")
            return 0.0
        
    def start_trailing_thread(self):
        """Start fast trailing updates in separate thread"""
        if self.trailing_thread and self.trailing_thread.is_alive():
            return
            
        self.trailing_stop_event.clear()
        self.trailing_thread = threading.Thread(target=self._fast_trailing_loop, daemon=True)
        self.trailing_thread.start()
        logger.info("🔄 Fast trailing thread started (2-second updates)")
        
    def stop_trailing_thread(self):
        """Stop trailing thread"""
        if self.trailing_thread and self.trailing_thread.is_alive():
            self.trailing_stop_event.set()
            self.trailing_thread.join(timeout=5)
            logger.info("⏹️ Fast trailing thread stopped")
            
    def check_and_sync_missing_positions(self):
        """Check for positions on exchange that are missing from our state and sync them"""
        if self.paper_mode:
            return
            
        try:
            # Get all positions from exchange
            exchange_positions = self.exchange.fetch_positions()
            active_exchange_positions = [p for p in exchange_positions if float(p['contracts']) > 0]
            
            for pos in active_exchange_positions:
                symbol = pos['symbol']
                # Convert CCXT symbol to our format
                symbol_key = symbol.replace('/', '_').replace(':USDT', '')
                
                # Check if position is missing from our state
                if symbol_key not in self.active_positions:
                    logger.warning(f"🚨 НАЙДЕНА ОТСУТСТВУЮЩАЯ ПОЗИЦИЯ: {symbol} (PnL: {float(pos['unrealizedPnl']):.4f} USDT)")
                    
                    # Sync this position
                    try:
                        entry_price = float(pos['entryPrice'])
                        side = 'LONG' if pos['side'] == 'long' else 'SHORT'
                        
                        # Try to get proper ATR
                        try:
                            df = self.fetch_ohlcv(symbol_key, '1h', 50)
                            if not df.empty:
                                df = add_indicators(df, atr_p=14)
                                atr = float(df.iloc[-1]['atr'])
                                # Используем чистый ATR (как в стратегии)
                                effective_atr = atr
                                sl_price = entry_price - (self.sl_atr_mult * effective_atr) if side == 'LONG' else entry_price + (self.sl_atr_mult * effective_atr)
                            else:
                                raise Exception("Empty dataframe")
                        except Exception as e:
                            logger.warning(f"⚠️ Could not get ATR for {symbol_key}: {e}, using 2% fallback")
                            atr = entry_price * 0.02
                            sl_price = entry_price * 0.98 if side == 'LONG' else entry_price * 1.02
                        
                        # Create position info
                        position_info = {
                            'symbol': symbol_key,
                            'side': side,
                            'entry': entry_price,
                            'qty': abs(float(pos['contracts'])),
                            'sl_initial': sl_price,
                            'sl_current': sl_price,
                            'last_updated_sl': sl_price,  # КРИТИЧНО: устанавливаем чтобы избежать спама
                            'atr': atr,
                            'timestamp': time.time(),
                            'order_id': None,
                            'trailing_active': False,
                            'unrealized_pnl': float(pos['unrealizedPnl']),
                            'peak_pnl_usdt': max(0.0, float(pos['unrealizedPnl'])),
                            'synced_from_exchange': True
                        }
                        
                        self.active_positions[symbol_key] = position_info
                        self.save_position_state(symbol_key, position_info)
                        
                        logger.info(f"✅ СИНХРОНИЗИРОВАНА ПОЗИЦИЯ {symbol_key}: {side} {position_info['qty']:.1f} @ {entry_price:.6f}")
                        
                        # Immediately update stop loss if needed
                        current_pnl = float(pos['unrealizedPnl'])
                        if current_pnl > 0:
                            logger.info(f"🔄 НЕМЕДЛЕННАЯ АКТИВАЦИЯ ТРЕЙЛИНГА для {symbol_key} (PnL: {current_pnl:.4f})")
                            
                    except Exception as e:
                        logger.error(f"❌ Ошибка синхронизации {symbol}: {e}")
                        
        except Exception as e:
            logger.error(f"❌ Ошибка проверки отсутствующих позиций: {e}")
            
    def _fast_trailing_loop(self):
        """Fast trailing updates every 2 seconds"""
        while not self.trailing_stop_event.is_set():
            try:
                self.update_trailing_stops()
                self.trailing_stop_event.wait(2)  # 2-second updates
            except Exception as e:
                logger.error(f"❌ Fast trailing error: {e}")
                self.trailing_stop_event.wait(2)
    
    def update_trailing_stops(self):
        """Update trailing stops for all open positions with real PnL from Binance"""
        # ИСПРАВЛЕНО: Синхронизируем реже чтобы избежать спама
        # Проверяем отсутствующие позиции каждый раз, но полную синхронизацию - реже
        self.check_and_sync_missing_positions()
        
        if not self.active_positions:
            logger.debug("📊 Нет активных позиций для трейлинга")
            return
        
        # КРИТИЧЕСКАЯ ПРОВЕРКА БЕЗОПАСНОСТИ: Проверяем реже (каждые 30 секунд)
        if not hasattr(self, '_last_protection_check'):
            self._last_protection_check = 0
        
        current_time = time.time()
        if current_time - self._last_protection_check > 30:  # Каждые 30 секунд
            # СНАЧАЛА очищаем orphaned ордера, ПОТОМ проверяем защиту
            self.cleanup_orphaned_orders()
            self.verify_all_positions_have_sl_protection()
            self._last_protection_check = current_time
            
        for symbol, pos in list(self.active_positions.items()):
            try:
                # Get current price and PnL from exchange
                df = self.fetch_ohlcv(symbol, '1m', 5)
                if df.empty:
                    continue
                    
                current_price = float(df.iloc[-1]['close'])
                real_pnl = self.get_position_pnl_from_exchange(symbol)
                
                # ПРОВЕРКА СИНХРОНИЗАЦИИ: сравниваем расчетный PnL с биржевым
                calculated_pnl = (current_price - pos['entry']) * pos['qty'] if pos['side'] == 'LONG' else (pos['entry'] - current_price) * pos['qty']
                pnl_diff = abs(real_pnl - calculated_pnl)
                
                # УЛУЧШЕННАЯ ПРОВЕРКА: Проверяем реальное наличие позиции на бирже
                # Получаем актуальные позиции с биржи
                try:
                    ccxt_sym = self.ccxt_symbol(symbol)
                    exchange_positions = self.exchange.fetch_positions([ccxt_sym])
                    position_exists = False
                    
                    for ex_pos in exchange_positions:
                        if float(ex_pos['contracts']) != 0:
                            position_exists = True
                            break
                    
                    # Если позиции нет на бирже, но есть локально - удаляем
                    if not position_exists:
                        logger.warning(f"🚨 {symbol}: Позиция НЕ СУЩЕСТВУЕТ на бирже! Удаляем из локального трекинга")
                        logger.info(f"🗑️ {symbol}: Удаляем закрытую позицию из локального трекинга")
                        # Помечаем позицию для удаления
                        pos['_to_remove'] = True
                        continue
                        
                except Exception as pos_check_error:
                    logger.warning(f"⚠️ {symbol}: Ошибка проверки существования позиции: {pos_check_error}")
                    # Если не можем проверить - продолжаем обычную логику
                
                if pnl_diff > 0.50:  # Разница больше 0.50 USDT
                    logger.warning(f"⚠️ {symbol}: PnL рассинхронизация! Биржа: {real_pnl:.4f}, Расчет: {calculated_pnl:.4f}, Разница: {pnl_diff:.4f}")
                    # Используем биржевый PnL как более точный
                elif pnl_diff > 0.10:  # Небольшая разница
                    logger.debug(f"📊 {symbol}: Небольшая PnL разница: {pnl_diff:.4f} USDT")
                
                # Update position with real PnL
                pos['unrealized_pnl'] = real_pnl
                
                # Calculate ATR if missing (for synced positions)
                if pos['atr'] is None:
                    df_atr = self.fetch_ohlcv(symbol, '1h', 50)
                    if not df_atr.empty:
                        df_atr = add_indicators(df_atr, atr_p=14)
                        calculated_atr = float(df_atr.iloc[-1]['atr'])
                        # Защита от микроубытков: минимальный ATR
                        min_atr = pos['entry'] * 0.008  # 0.8% от цены
                        pos['atr'] = max(calculated_atr, min_atr)
                        
                        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: НЕ сбрасываем sl_current если он уже установлен!
                        # Это уничтожает весь трейлинг!
                        if 'sl_initial' not in pos or pos['sl_initial'] is None:
                            pos['sl_initial'] = pos['entry'] - (self.sl_atr_mult * pos['atr']) if pos['side'] == 'LONG' else pos['entry'] + (self.sl_atr_mult * pos['atr'])
                        
                        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Сохраняем текущий SL если он лучше начального
                        if 'sl_current' not in pos or pos['sl_current'] is None:
                            pos['sl_current'] = pos['sl_initial']
                        else:
                            # Проверяем, что текущий SL не хуже начального
                            if pos['side'] == 'LONG':
                                # Для лонгов: sl_current должен быть >= sl_initial (выше = лучше)
                                if pos['sl_current'] < pos['sl_initial']:
                                    logger.warning(f"⚠️ {symbol}: Текущий SL хуже начального, восстанавливаем: {pos['sl_current']:.6f} → {pos['sl_initial']:.6f}")
                                    pos['sl_current'] = pos['sl_initial']
                            else:  # SHORT
                                # Для шортов: sl_current должен быть <= sl_initial (ниже = лучше)
                                if pos['sl_current'] > pos['sl_initial']:
                                    logger.warning(f"⚠️ {symbol}: Текущий SL хуже начального, восстанавливаем: {pos['sl_current']:.6f} → {pos['sl_initial']:.6f}")
                                    pos['sl_current'] = pos['sl_initial']
                        
                        logger.debug(f"📊 {symbol}: ATR установлен {pos['atr']:.6f}, SL initial: {pos['sl_initial']:.6f}, current: {pos['sl_current']:.6f}")
                
                if pos['atr'] is None:  # Still None, skip
                    continue
                
                # Update trailing logic using PnL-ONLY system (простая система по уровням!)
                from ..core.trailing_pnl_only import update_trailing_pnl_only
                from ..core.types import Position, Side
                
                # Convert to Position object
                position = Position(
                    side=Side.LONG if pos['side'] == 'LONG' else Side.SHORT,
                    entry=pos['entry'],
                    sl=pos['sl_current'] if pos['sl_current'] else pos['sl_initial'],
                    qty=pos['qty'],
                    remaining_qty=pos['qty'],
                    r_per_unit=pos['atr'] * self.sl_atr_mult,
                    atr=pos['atr'] if pos['atr'] else 0.0,
                    sl_initial=pos['sl_initial']
                )
                
                # Add peak_pnl_usdt tracking to Position object
                position.peak_pnl_usdt = pos.get('peak_pnl_usdt', 0.0)
                
                # Используем только реальный PnL с биржи (надежно)
                effective_pnl = real_pnl
                
                # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Обновляем peak_pnl_usdt при ЛЮБОМ положительном PnL
                # Если peak_pnl_usdt был сброшен в 0, а текущий PnL > 0.06 - трейлинг должен активироваться!
                if effective_pnl > 0:
                    if position.peak_pnl_usdt == 0.0 and effective_pnl >= self.trailing.level_1_pnl:
                        # Экстренная активация трейлинга для позиций выше порога
                        position.peak_pnl_usdt = effective_pnl
                        pos['peak_pnl_usdt'] = effective_pnl
                        logger.warning(f"🚨 {symbol}: ЭКСТРЕННАЯ АКТИВАЦИЯ трейлинга! PnL ${effective_pnl:.4f} >= ${self.trailing.level_1_pnl} (peak был 0)")
                    elif effective_pnl > position.peak_pnl_usdt:
                        # Обычное обновление пика
                        position.peak_pnl_usdt = effective_pnl
                        pos['peak_pnl_usdt'] = effective_pnl
                        logger.debug(f"📈 {symbol}: Новый пик PnL: ${effective_pnl:.4f}")
                
                # Трейлинг работает даже при небольшом убытке для защиты минимальной прибыли
                logger.debug(f"📊 {symbol}: Трейлинг PnL check - Real: {real_pnl:.4f}, Calculated: {calculated_pnl:.4f}, Effective: {effective_pnl:.4f}")
                
                # R-based трейлинг имеет свою логику активации внутри функции
                
                # Use PnL-ONLY trailing system (простая система по уровням!)
                updated_pos = update_trailing_pnl_only(
                    position,
                    current_price,  # hi
                    current_price,  # lo (используем текущую цену для обеих)
                    pos['atr'],     # ATR (не используется в PnL-only, но нужен для совместимости)
                    self.trailing   # TrailingConfigPnLOnly с PnL-уровнями
                )
                
                # УЛУЧШЕННОЕ ЛОГИРОВАНИЕ для диагностики PnL-ONLY трейлинга
                debug_info = getattr(updated_pos, 'trailing_debug', {})
                level = debug_info.get('level', 'unknown')
                keep_pct = debug_info.get('keep_pct', 0)
                
                if level == 'INACTIVE':
                    logger.debug(f"📊 {symbol}: PnL-трейлинг не активен (PnL: {real_pnl:.4f} < ${self.trailing.level_1_pnl})")
                elif debug_info.get('sl_updated', False):
                    peak_pnl = debug_info.get('peak_pnl', 0)
                    target_profit = debug_info.get('target_profit', 0)
                    protection_applied = debug_info.get('protection_applied', False)
                    protected_sl = debug_info.get('protected_sl', 0)
                    pnl_sl = debug_info.get('pnl_sl', 0)
                    
                    if level == 'INACTIVE' and protection_applied:
                        logger.info(f"🛡️ {symbol}: БАЗОВАЯ ЗАЩИТА активирована! SL: ${old_sl:.6f} → ${protected_sl:.6f} (мин. $0.03)")
                    elif protection_applied:
                        logger.info(f"🛡️ {symbol}: PnL-трейлинг с ЗАЩИТОЙ - Уровень: {level}, Peak PnL: ${peak_pnl:.4f}, Сохранить: {keep_pct*100:.0f}% (${target_profit:.4f})")
                        logger.info(f"🛡️ {symbol}: Защита активирована! SL: ${pnl_sl:.6f} → ${protected_sl:.6f} (мин. $0.03)")
                    else:
                        logger.info(f"📊 {symbol}: PnL-трейлинг активен - Уровень: {level}, Peak PnL: ${peak_pnl:.4f}, Сохранить: {keep_pct*100:.0f}% (${target_profit:.4f})")
                elif real_pnl > 0:
                    logger.debug(f"📊 {symbol}: PnL-трейлинг PnL=${real_pnl:.4f}, SL без изменений")
                
                # КРИТИЧЕСКОЕ ПРАВИЛО: Стоп-лоссы могут ТОЛЬКО УЛУЧШАТЬСЯ!
                # Никаких обновлений без реального улучшения
                should_update = False
                old_sl = pos['sl_current']
                new_sl = updated_pos.sl
                
                # Минимальное улучшение для обновления (0.0001% от entry цены)
                min_improvement = pos['entry'] * 0.000001
                
                if pos['side'] == 'LONG':
                    # Для лонгов: новый SL должен быть ЗНАЧИТЕЛЬНО выше (лучше)
                    improvement = new_sl - old_sl
                    if improvement > min_improvement:
                        should_update = True
                        projected_pnl = (new_sl - pos['entry']) * pos['qty']
                        logger.info(f"✅ {symbol}: SL УЛУЧШЕНИЕ для LONG: {old_sl:.6f} → {new_sl:.6f} (+{improvement:.6f}, прибыль: ${projected_pnl:.3f})")
                    elif improvement < -min_improvement:
                        logger.error(f"❌ {symbol}: КРИТИЧНО - Трейлинг пытается УХУДШИТЬ SL для LONG: {old_sl:.6f} → {new_sl:.6f} ({improvement:.6f})!")
                    else:
                        logger.debug(f"📊 {symbol}: SL изменение для LONG слишком мало: {improvement:.8f}, пропускаем")
                        
                elif pos['side'] == 'SHORT':
                    # Для шортов: новый SL должен быть ЗНАЧИТЕЛЬНО ниже (лучше)
                    improvement = old_sl - new_sl  # Для шортов улучшение = уменьшение SL
                    if improvement > min_improvement:
                        should_update = True
                        projected_pnl = (pos['entry'] - new_sl) * pos['qty']
                        logger.info(f"✅ {symbol}: SL УЛУЧШЕНИЕ для SHORT: {old_sl:.6f} → {new_sl:.6f} (-{improvement:.6f}, прибыль: ${projected_pnl:.3f})")
                    elif improvement < -min_improvement:
                        logger.error(f"❌ {symbol}: КРИТИЧНО - Трейлинг пытается УХУДШИТЬ SL для SHORT: {old_sl:.6f} → {new_sl:.6f} (+{-improvement:.6f})!")
                    else:
                        logger.debug(f"📊 {symbol}: SL изменение для SHORT слишком мало: {-improvement:.8f}, пропускаем")
                    
                if should_update:
                    old_sl = pos['sl_current']
                    
                    # КРИТИЧЕСКАЯ ЗАЩИТА: SL может ТОЛЬКО УЛУЧШАТЬСЯ!
                    new_sl = updated_pos.sl
                    if pos['side'] == 'LONG':
                        # Для лонгов: новый SL должен быть ВЫШЕ (лучше)
                        if new_sl > old_sl:
                            pos['sl_current'] = new_sl
                        else:
                            logger.warning(f"⚠️ {symbol}: Попытка ухудшить LONG SL! {old_sl:.6f} → {new_sl:.6f}, блокируем!")
                            continue  # Не обновляем SL
                    else:  # SHORT
                        # Для шортов: новый SL должен быть НИЖЕ (лучше)
                        if new_sl < old_sl:
                            pos['sl_current'] = new_sl
                        else:
                            logger.warning(f"⚠️ {symbol}: Попытка ухудшить SHORT SL! {old_sl:.6f} → {new_sl:.6f}, блокируем!")
                            continue  # Не обновляем SL
                    
                    pos['trailing_active'] = True
                    
                    # Save updated peak PnL
                    pos['peak_pnl_usdt'] = updated_pos.peak_pnl_usdt
                    
                    # Save position state to persistent storage
                    self.save_position_state(symbol, pos)
                    
                    # Update sliding market stop loss on exchange
                    self.update_sliding_stop_loss(symbol, pos)
                    
                    # Log trailing update with detailed debug info
                    direction = "🟢" if pos['side'] == 'LONG' else "🔴"
                    
                    # Get debug info from trailing function
                    debug_info = getattr(updated_pos, 'trailing_debug', {})
                    level_info = f" ({debug_info.get('level', 'L?')}: {debug_info.get('keep_pct', 0)*100:.0f}%)"
                    
                    logger.info(f"{direction} {symbol}: PnL-Trailing SL {old_sl:.6f} → {updated_pos.sl:.6f}, PnL: {real_pnl:.2f} USDT{level_info}")
                    
                    # Additional debug logging
                    if debug_info:
                        logger.debug(f"📊 {symbol} Trailing Debug: Peak={debug_info.get('peak_pnl', 0):.2f}, Target={debug_info.get('target_profit', 0):.2f}, Updated={debug_info.get('sl_updated', False)}")
                else:
                    # Always save peak PnL even if SL doesn't update
                    if updated_pos.peak_pnl_usdt > pos.get('peak_pnl_usdt', 0.0):
                        pos['peak_pnl_usdt'] = updated_pos.peak_pnl_usdt
                        self.save_position_state(symbol, pos)
                        
                        # Log peak PnL update
                        logger.debug(f"📊 {symbol}: Peak PnL updated to ${updated_pos.peak_pnl_usdt:.3f} (SL unchanged)")
                
                # Check if current SL hit (use CURRENT sl_current, not updated_pos.sl)
                sl_hit = False
                if pos['side'] == 'LONG' and current_price <= pos['sl_current']:
                    sl_hit = True
                elif pos['side'] == 'SHORT' and current_price >= pos['sl_current']:
                    sl_hit = True
                    
                if sl_hit:
                    logger.info(f"🚨 {symbol}: SL hit at {current_price:.6f}, closing position")
                    self.close_position(symbol, current_price, "Trailing SL Hit")
            except Exception as e:
                logger.error(f"❌ Trailing update failed for {symbol}: {e}")
        
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Удаляем позиции помеченные как закрытые на бирже
        positions_to_remove = []
        for symbol, pos in self.active_positions.items():
            if pos.get('_to_remove', False):
                positions_to_remove.append(symbol)
        
        for symbol in positions_to_remove:
            logger.info(f"🗑️ {symbol}: Удаляем закрытую позицию из трекинга")
            self.close_position(symbol, 0.0, "Position closed on exchange")
                
    def close_position(self, symbol: str, exit_price: float, reason: str):
        """Close position and clean up"""
        if symbol not in self.active_positions:
            return
            
        try:
            pos = self.active_positions[symbol]
            
            # Check if position still exists on exchange first
            ccxt_sym = self.ccxt_symbol(symbol)
            
            if not self.paper_mode:
                try:
                    exchange_positions = self.exchange.fetch_positions([ccxt_sym])
                    position_exists = False
                    
                    for exchange_pos in exchange_positions:
                        if float(exchange_pos['contracts']) != 0:
                            position_exists = True
                            break
                    
                    if not position_exists:
                        logger.info(f"📊 {symbol}: Position already closed on exchange")
                        # Remove from tracking
                        del self.active_positions[symbol]
                        # Clean up saved position state
                        self.cleanup_position_state(symbol)
                        self.storage.update_symbol(symbol, {'active_position': None})
                        return
                except Exception as pos_check_error:
                    logger.warning(f"⚠️ Could not check position status for {symbol}: {pos_check_error}")
            
            # Place market order to close
            close_side = 'sell' if pos['side'] == 'LONG' else 'buy'
            
            close_order = self.exchange.create_market_order(
                ccxt_sym,
                close_side,
                pos['qty'],
                exit_price,
                params={'reduceOnly': True}
            )
            
            # Calculate PnL (including commissions)
            if pos['side'] == 'LONG':
                pnl_before_fees = (exit_price - pos['entry']) * pos['qty']
            else:
                pnl_before_fees = (pos['entry'] - exit_price) * pos['qty']
            
            # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Улучшенный расчет комиссий
            # Проверяем реальные комиссии с биржи если возможно
            try:
                # Получаем реальную информацию о комиссиях из ордера
                actual_commission = 0.0
                if 'fee' in close_order and close_order['fee']:
                    actual_commission += float(close_order['fee']['cost'] or 0)
                    logger.debug(f"💰 {symbol}: Реальная комиссия закрытия: {actual_commission:.6f} USDT")
                
                # Оценка комиссии входа (обычно maker с меньшей комиссией)
                entry_value = pos['entry'] * pos['qty']
                estimated_entry_fee = entry_value * 0.0002  # 0.02% maker fee (меньше чем taker)
                
                # Общая комиссия
                total_commission = actual_commission + estimated_entry_fee
                
                logger.debug(f"💰 {symbol}: Оценка комиссии входа: {estimated_entry_fee:.6f} USDT")
                
            except Exception as fee_error:
                logger.warning(f"⚠️ {symbol}: Не удалось получить реальные комиссии: {fee_error}")
                # Fallback к старой логике с улучшенными коэффициентами
                position_value = pos['entry'] * pos['qty']
                # Используем смешанную комиссию: maker (0.02%) + taker (0.05%)
                mixed_fee = (0.0002 + 0.0005) / 2  # Средняя между maker и taker
                total_commission = position_value * mixed_fee * 2  # entry + exit
            
            # PnL after commissions
            pnl_usdt = pnl_before_fees - total_commission
            
            logger.info(f"💰 {symbol}: PnL before fees: {pnl_before_fees:.6f} USDT, Commission: {total_commission:.6f} USDT, Net PnL: {pnl_usdt:.6f} USDT")
                
            logger.info(f"🔚 {symbol}: Position closed @ {exit_price:.6f} ({reason}), PnL: {pnl_usdt:.2f} USDT")
            
            # Remove from tracking
            del self.active_positions[symbol]
            
            # Clean up saved position state
            self.cleanup_position_state(symbol)
            
            # Update storage
            self.storage.update_symbol(symbol, {
                'active_position': None,
                'last_close_time': time.time(),
                'last_pnl': pnl_usdt
            })
            
        except Exception as e:
            logger.error(f"❌ Failed to close position {symbol}: {e}")
    
    def check_active_positions(self):
        """Check all active positions for stop loss triggers and sync with exchange"""
        if not self.active_positions:
            return
            
        logger.debug(f"🔍 Checking {len(self.active_positions)} active positions...")
        
        # ТОЛЬКО МОНИТОРИНГ - закрытие происходит через stop_market ордера на бирже
        positions_to_close = []  # Список позиций для удаления из трекинга
        
        for symbol, pos in list(self.active_positions.items()):
            try:
                # Get current market price
                ccxt_sym = self.ccxt_symbol(symbol)
                
                if not self.paper_mode:
                    # Verify position still exists on exchange
                    try:
                        exchange_positions = self.exchange.fetch_positions([ccxt_sym])
                        position_exists = False
                        
                        for exchange_pos in exchange_positions:
                            if float(exchange_pos['contracts']) != 0:
                                position_exists = True
                                break
                        
                        if not position_exists:
                            logger.info(f"📊 {symbol}: Position no longer exists on exchange, removing from tracking")
                            positions_to_close.append(symbol)
                            continue
                            
                    except Exception as e:
                        logger.warning(f"⚠️ Could not verify {symbol} position on exchange: {e}")
                        continue
                
                # Get current price
                ticker = self.exchange.fetch_ticker(ccxt_sym)
                current_price = ticker['last']
                
                # Check stop loss trigger
                sl_price = pos.get('sl_current') or pos.get('sl_initial')
                if not sl_price:
                    logger.warning(f"⚠️ {symbol}: No stop loss price set!")
                    continue
                
                # ТОЛЬКО МОНИТОРИНГ - НЕТ ПРОГРАММНОГО ЗАКРЫТИЯ!
                # Полагаемся исключительно на stop_market ордера на бирже
                
                sl_distance_pct = 0
                if pos['side'] == 'LONG':
                    sl_distance_pct = ((current_price - sl_price) / current_price) * 100
                    if current_price <= sl_price:
                        logger.warning(f"🚨 {symbol} LONG SL ZONE: Price ${current_price:.6f} <= SL ${sl_price:.6f} - ожидаем исполнения stop_market ордера")
                else:
                    sl_distance_pct = ((sl_price - current_price) / current_price) * 100  
                    if current_price >= sl_price:
                        logger.warning(f"🚨 {symbol} SHORT SL ZONE: Price ${current_price:.6f} >= SL ${sl_price:.6f} - ожидаем исполнения stop_market ордера")
                
                # Log position status
                pnl = pos.get('unrealized_pnl', 0)
                direction = "🟢" if pos['side'] == 'LONG' else "🔴"
                logger.debug(f"{direction} {symbol}: Price ${current_price:.6f}, SL ${sl_price:.6f} ({sl_distance_pct:+.2f}%), PnL: {pnl:.2f} USDT")
                    
            except Exception as e:
                logger.error(f"❌ Failed to check position {symbol}: {e}")
        
        # Очистка закрытых позиций из трекинга
        for symbol in positions_to_close:
            if symbol in self.active_positions:
                logger.info(f"🗑️ Removing closed position {symbol} from tracking")
                self.cleanup_position_state(symbol)
        
        # Позиции закрываются только через stop_market ордера на бирже
    
    def update_sliding_stop_loss(self, symbol: str, pos: Dict[str, Any]):
        """Update sliding market stop loss order on exchange"""
        if self.paper_mode:
            return
        
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: СТРОГАЯ проверка необходимости обновления SL
        # Обновляем ТОЛЬКО если SL действительно УЛУЧШАЕТСЯ
        current_sl = pos['sl_current']
        last_updated_sl = pos.get('last_updated_sl', 0)
        
        # Проверяем минимальное изменение SL (0.0001% от цены)
        min_sl_change = pos['entry'] * 0.000001  # 0.0001% от entry цены
        sl_change = abs(current_sl - last_updated_sl)
        
        if sl_change < min_sl_change:
            logger.debug(f"📊 {symbol}: SL изменение слишком мало ({sl_change:.8f} < {min_sl_change:.8f}), пропускаем обновление")
            return
        
        # СТРОГАЯ ПРОВЕРКА: SL должен только УЛУЧШАТЬСЯ, никогда не ухудшаться
        if last_updated_sl != 0:  # Если есть предыдущий SL
            if pos['side'] == 'LONG':
                # Для лонгов: новый SL должен быть ВЫШЕ (лучше)
                if current_sl <= last_updated_sl:
                    logger.debug(f"📊 {symbol}: SL не улучшился для LONG ({current_sl:.6f} <= {last_updated_sl:.6f}), пропускаем")
                    return
            else:  # SHORT
                # Для шортов: новый SL должен быть НИЖЕ (лучше)
                if current_sl >= last_updated_sl:
                    logger.debug(f"📊 {symbol}: SL не улучшился для SHORT ({current_sl:.6f} >= {last_updated_sl:.6f}), пропускаем")
                    return
        
        # ДОПОЛНИТЕЛЬНАЯ ЗАЩИТА: Если SL точно такой же как last_updated_sl - НЕ ОБНОВЛЯТЬ
        if abs(current_sl - last_updated_sl) < 0.000001:
            logger.debug(f"📊 {symbol}: SL идентичен предыдущему ({current_sl:.6f} = {last_updated_sl:.6f}), пропускаем")
            return
        
        # Дополнительная проверка против начального SL
        sl_initial = pos.get('sl_initial', 0)
        if sl_initial != 0:
            if pos['side'] == 'LONG':
                # Для лонгов: текущий SL должен быть >= начального
                if current_sl < sl_initial:
                    logger.warning(f"⚠️ {symbol}: SL хуже начального для LONG! {current_sl:.6f} < {sl_initial:.6f}, блокируем обновление")
                    return
            else:  # SHORT
                # Для шортов: текущий SL должен быть <= начального  
                if current_sl > sl_initial:
                    logger.warning(f"⚠️ {symbol}: SL хуже начального для SHORT! {current_sl:.6f} > {sl_initial:.6f}, блокируем обновление")
                    return
            
        logger.info(f"🔄 {symbol}: УЛУЧШАЕМ SL ордер: {last_updated_sl:.6f} → {current_sl:.6f} (✅ подтверждено улучшение)")
            
        try:
            ccxt_sym = self.ccxt_symbol(symbol)
            
            # First, check if position still exists
            try:
                exchange_positions = self.exchange.fetch_positions([ccxt_sym])
                position_exists = False
                
                for exchange_pos in exchange_positions:
                    if float(exchange_pos['contracts']) != 0:
                        position_exists = True
                        break
                
                if not position_exists:
                    logger.debug(f"📊 {symbol}: No position on exchange, skipping SL update")
                    return
            except Exception as pos_check_error:
                logger.warning(f"⚠️ Could not verify position for SL update {symbol}: {pos_check_error}")
                return
            
            # CRITICAL FIX: Cancel old SL orders FIRST, then create new one
            # This prevents race condition where old SL triggers before new one is active
            
            import time
            
            # Get existing stop loss orders first
            old_sl_orders = []
            try:
                open_orders = self.exchange.fetch_open_orders(ccxt_sym)
                for order in open_orders:
                    if order['type'] in ['stop_market', 'stop'] and order['info'].get('reduceOnly'):
                        old_sl_orders.append(order)
                        logger.debug(f"📊 {symbol}: Found existing SL order {order['id']} @ {order.get('stopPrice', order.get('price'))}")
            except Exception as orders_error:
                logger.warning(f"⚠️ Could not fetch open orders for {symbol}: {orders_error}")
            
            # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: БЕЗОПАСНАЯ ЗАМЕНА SL ОРДЕРА
            # НИКОГДА НЕ ОСТАВЛЯЕМ ПОЗИЦИЮ БЕЗ ЗАЩИТЫ!
            
            # STEP 1: Проверяем, что новый SL не сработает немедленно
            current_price = None
            try:
                ticker = self.exchange.fetch_ticker(ccxt_sym)
                current_price = float(ticker['last'])
            except Exception as price_error:
                logger.warning(f"⚠️ {symbol}: Could not fetch current price for SL validation: {price_error}")
                return  # Не обновляем SL если не можем получить цену
            
            # Проверяем безопасность нового SL уровня
            new_sl_price = pos['sl_current']
            old_sl_price = pos.get('last_updated_sl', 0)
            
            # УМНАЯ ПРОВЕРКА: разные буферы для разных ситуаций
            is_trailing_update = old_sl_price > 0 and abs(new_sl_price - old_sl_price) > 0.000001
            
            if is_trailing_update:
                # Для трейлинга: маленький буфер 0.05% (чтобы не блокировать трейлинг)
                price_buffer = current_price * 0.0005
                buffer_name = "trailing"
            else:
                # Для первого SL и emergency: большой буфер 0.2%
                price_buffer = current_price * 0.002
                buffer_name = "initial/emergency"
            
            is_sl_safe = True
            if pos['side'] == 'LONG':
                # Для лонгов: SL должен быть ниже текущей цены с буфером
                if new_sl_price >= (current_price - price_buffer):
                    is_sl_safe = False
            else:  # SHORT
                # Для шортов: SL должен быть выше текущей цены с буфером
                if new_sl_price <= (current_price + price_buffer):
                    is_sl_safe = False
            
            if not is_sl_safe and not is_trailing_update:
                # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Блокируем только ПЕРВОНАЧАЛЬНЫЕ SL, НЕ трейлинг обновления
                # Трейлинг должен ВСЕГДА обновляться для защиты минимальной прибыли!
                logger.warning(f"⚠️ {symbol}: NEW INITIAL SL TOO CLOSE TO CURRENT PRICE! SL: {new_sl_price:.6f}, Price: {current_price:.6f}, Buffer: {price_buffer:.6f}")
                logger.warning(f"⚠️ {symbol}: Skipping INITIAL SL update to prevent immediate trigger")
                return
            elif not is_sl_safe and is_trailing_update:
                # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Для трейлинга НИКОГДА НЕ БЛОКИРУЕМ!
                # Защита минимальной прибыли важнее риска немедленного срабатывания!
                logger.warning(f"🚨 {symbol}: TRAILING SL CLOSE TO PRICE! SL: {new_sl_price:.6f}, Price: {current_price:.6f} - PROCEEDING (profit protection priority)")
                logger.warning(f"🚨 {symbol}: Это защита минимальной прибыли $0.03 - КРИТИЧЕСКИ ВАЖНО!")
            
            # STEP 2: Создаем НОВЫЙ SL ордер ПЕРВЫМ (позиция остается защищенной)
            sl_side = 'sell' if pos['side'] == 'LONG' else 'buy'
            new_sl_created = False
            new_sl_order = None
            
            max_retries = 3  # Уменьшили количество попыток
            for attempt in range(max_retries):
                try:
                    # Determine order parameters based on type
                    if self.sl_order_type == 'stop_market':
                        # Маркет стоп-лосс (рыночный ордер после триггера) - по умолчанию
                        new_sl_order = self.exchange.create_order(
                            ccxt_sym,
                            'stop_market',
                            sl_side,
                            pos['qty'],
                            None,  # Нет цены исполнения для stop_market
                            params={
                                'stopPrice': new_sl_price,
                                'reduceOnly': True,
                                'timeInForce': 'GTC'
                            }
                        )
                    else:
                        # Лимитный стоп-лосс (лимитный ордер после триггера)
                        new_sl_order = self.exchange.create_order(
                            ccxt_sym,
                            self.sl_order_type,  # Используем из конфигурации!
                            sl_side,
                            pos['qty'],
                            new_sl_price if self.sl_order_type == 'stop' else None,  # Цена только для лимитного
                            params={
                                'stopPrice': new_sl_price,
                                'reduceOnly': True,
                                'timeInForce': 'GTC'
                            }
                        )
                    new_sl_created = True
                    logger.info(f"✅ {symbol}: New SL order created @ {new_sl_price:.6f} (ID: {new_sl_order['id']})")
                    break
                except Exception as e:
                    error_msg = str(e).lower()
                    if "order would immediately trigger" in error_msg or "-2021" in str(e):
                        if is_trailing_update:
                            # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Для трейлинга НЕ прерываем!
                            # Это может быть защита минимальной прибыли - попробуем еще раз!
                            logger.warning(f"🚨 {symbol}: TRAILING SL WOULD TRIGGER IMMEDIATELY! Current: {current_price:.6f}, New SL: {new_sl_price:.6f}")
                            logger.warning(f"🚨 {symbol}: Это может быть защита минимальной прибыли - продолжаем попытки!")
                            if attempt < max_retries - 1:
                                time.sleep(0.5)  # Пауза перед повтором
                                continue
                            else:
                                logger.error(f"❌ {symbol}: КРИТИЧНО - не удалось создать TRAILING SL после всех попыток!")
                                logger.error(f"❌ {symbol}: Позиция может остаться без защиты минимальной прибыли!")
                                break
                        else:
                            logger.error(f"❌ {symbol}: NEW INITIAL SL WOULD TRIGGER IMMEDIATELY! Current: {current_price:.6f}, New SL: {new_sl_price:.6f}")
                            logger.error(f"❌ {symbol}: This should not happen after our price checks! Aborting SL update.")
                            return  # Прерываем обновление только для начальных SL
                    else:
                        logger.warning(f"⚠️ {symbol}: SL creation attempt {attempt+1}/{max_retries} failed: {e}")
                        if attempt < max_retries - 1:
                            time.sleep(0.3)  # Короткая пауза
            
            # Если не удалось создать новый SL - НЕ ТРОГАЕМ СТАРЫЕ!
            if not new_sl_created:
                logger.error(f"❌ {symbol}: CRITICAL - Could not create new SL order after {max_retries} attempts!")
                logger.error(f"❌ {symbol}: KEEPING OLD SL ORDERS FOR PROTECTION! Manual intervention may be required.")
                return  # Оставляем старые SL ордера для защиты
            
            # STEP 3: ТОЛЬКО ПОСЛЕ успешного создания нового SL - отменяем старые
            cancelled_orders = []
            if old_sl_orders:
                logger.info(f"🚫 {symbol}: Cancelling {len(old_sl_orders)} old SL orders (new SL is active)")
                for old_order in old_sl_orders:
                    try:
                        self.exchange.cancel_order(old_order['id'], ccxt_sym)
                        cancelled_orders.append(old_order)
                        logger.debug(f"🚫 {symbol}: Cancelled old SL order {old_order['id']} @ {old_order.get('stopPrice')}")
                        time.sleep(0.05)  # Small delay between cancellations
                    except Exception as cancel_error:
                        logger.warning(f"⚠️ {symbol}: Could not cancel old SL order {old_order['id']}: {cancel_error}")
                        # Не критично - у нас есть новый SL
            
            # STEP 4: Финализируем обновление
            pos['last_updated_sl'] = new_sl_price
            pos['sl_order_id'] = new_sl_order['id'] if new_sl_order else None
            
            logger.info(f"🛡️ {symbol}: SL SAFELY UPDATED! Old cancelled: {len(cancelled_orders)}, New active: {new_sl_order['id']}")
            
        except Exception as e:
            logger.error(f"❌ Failed to update sliding SL for {symbol}: {e}")
    
    def cleanup_orphaned_orders(self):
        """Очистка orphaned (лишних) stop-loss ордеров на бирже"""
        if self.paper_mode:
            return
            
        try:
            # Получаем все позиции с биржи
            exchange_positions = self.exchange.fetch_positions()
            active_symbols = set(self.active_positions.keys())
            
            # Проверяем каждый символ из наших активных позиций
            for symbol in active_symbols:
                try:
                    ccxt_sym = self.ccxt_symbol(symbol)
                    open_orders = self.exchange.fetch_open_orders(ccxt_sym)
                    
                    # Найти все SL ордера для этого символа
                    sl_orders = []
                    for order in open_orders:
                        if (order['type'] in ['stop_market', 'stop'] and 
                            order['info'].get('reduceOnly') and
                            order['status'] == 'open'):
                            sl_orders.append(order)
                    
                    # КРИТИЧЕСКАЯ ПРОВЕРКА: должен быть только ОДИН SL ордер на позицию
                    if len(sl_orders) > 1:
                        logger.warning(f"🧹 {symbol}: Найдено {len(sl_orders)} SL ордеров, должен быть только 1!")
                        
                        # Сортируем по времени создания (новейший первый)
                        sl_orders.sort(key=lambda x: x['timestamp'], reverse=True)
                        
                        # Оставляем только новейший ордер
                        newest_order = sl_orders[0]
                        orders_to_cancel = sl_orders[1:]
                        
                        logger.info(f"🧹 {symbol}: Оставляем новейший SL ордер ID: {newest_order['id']} @ {newest_order['stopPrice']}")
                        
                        # Отменяем старые ордера
                        for old_order in orders_to_cancel:
                            try:
                                self.exchange.cancel_order(old_order['id'], ccxt_sym)
                                logger.info(f"🧹 {symbol}: Отменен старый SL ордер ID: {old_order['id']}")
                                time.sleep(0.1)  # Небольшая задержка между отменами
                            except Exception as cancel_error:
                                logger.warning(f"⚠️ {symbol}: Не удалось отменить старый SL {old_order['id']}: {cancel_error}")
                        
                        # Обновляем локальную информацию о SL ордере
                        if symbol in self.active_positions:
                            self.active_positions[symbol]['sl_order_id'] = newest_order['id']
                            self.active_positions[symbol]['last_updated_sl'] = float(newest_order['stopPrice'])
                    
                    elif len(sl_orders) == 1:
                        # Все в порядке - один SL ордер
                        sl_order = sl_orders[0]
                        logger.debug(f"✅ {symbol}: Корректный SL ордер ID: {sl_order['id']} @ {sl_order['stopPrice']}")
                        
                        # Убеждаемся что локальная информация актуальна
                        if symbol in self.active_positions:
                            self.active_positions[symbol]['sl_order_id'] = sl_order['id']
                            if 'last_updated_sl' not in self.active_positions[symbol]:
                                self.active_positions[symbol]['last_updated_sl'] = float(sl_order['stopPrice'])
                    
                    elif len(sl_orders) == 0:
                        # Нет SL ордеров - это проблема, но она решается в verify_all_positions_have_sl_protection
                        logger.debug(f"⚠️ {symbol}: Нет SL ордеров (будет создан в verify_all_positions_have_sl_protection)")
                        
                except Exception as symbol_error:
                    logger.warning(f"⚠️ Ошибка очистки ордеров для {symbol}: {symbol_error}")
            
            # ДОПОЛНИТЕЛЬНАЯ ОЧИСТКА: Ищем orphaned ордера для символов, которых нет в наших активных позициях
            # ИСПРАВЛЕНО: Получаем ВСЕ открытые ордера, а не только для активных символов
            try:
                # Получаем все открытые ордера без фильтрации по символам
                all_open_orders = self.exchange.fetch_open_orders()
                
                # Ищем SL ордера для символов, которых нет в active_positions
                for order in all_open_orders:
                    if (order['type'] in ['stop_market', 'stop'] and 
                        order['info'].get('reduceOnly') and
                        order['status'] == 'open'):
                        
                        # Конвертируем символ обратно к нашему формату
                        ccxt_symbol = order['symbol']
                        our_symbol = ccxt_symbol.replace('/', '_').replace(':USDT', '')
                        
                        if our_symbol not in active_symbols:
                            logger.warning(f"🧹 Найден orphaned SL ордер для {our_symbol} (ID: {order['id']}) - позиции нет в active_positions")
                            try:
                                self.exchange.cancel_order(order['id'], ccxt_symbol)
                                logger.info(f"🧹 Отменен orphaned SL ордер {our_symbol} ID: {order['id']}")
                            except Exception as cancel_error:
                                logger.warning(f"⚠️ Не удалось отменить orphaned ордер {order['id']}: {cancel_error}")
                
            except Exception as global_cleanup_error:
                logger.warning(f"⚠️ Ошибка глобальной очистки ордеров: {global_cleanup_error}")
                
        except Exception as e:
            logger.error(f"❌ Критическая ошибка очистки orphaned ордеров: {e}")

    def verify_all_positions_have_sl_protection(self):
        """Критическая проверка: все позиции должны иметь активные SL ордера"""
        if self.paper_mode:
            return
        
        unprotected_positions = []
        
        for symbol, pos in self.active_positions.items():
            try:
                ccxt_sym = self.ccxt_symbol(symbol)
                
                # Проверяем наличие SL ордеров на бирже
                open_orders = self.exchange.fetch_open_orders(ccxt_sym)
                sl_orders = []
                
                for order in open_orders:
                    if (order['type'] in ['stop_market', 'stop'] and 
                        order['info'].get('reduceOnly') and
                        order['status'] == 'open'):
                        sl_orders.append(order)
                
                if len(sl_orders) == 0:
                    unprotected_positions.append(symbol)
                    entry_price = pos.get('entry_price', pos.get('entry', 0))
                    current_sl = pos.get('last_updated_sl', pos.get('sl_current', 'N/A'))
                    logger.error(f"❌ {symbol}: CRITICAL - ПОЗИЦИЯ БЕЗ SL ОРДЕРА! Entry: {entry_price:.6f}, Current SL: {current_sl}")
                    
                    # Пытаемся создать экстренный SL
                    try:
                        side = pos.get('side', 'long').lower()
                        sl_side = 'sell' if side == 'long' else 'buy'
                        quantity = pos.get('quantity', pos.get('qty', 0))
                        
                        # Рассчитываем emergency SL цену
                        emergency_sl = pos.get('last_updated_sl')
                        if not emergency_sl:
                            emergency_sl = pos.get('sl_current', pos.get('sl_initial'))
                        if not emergency_sl:
                            # Используем 3% от входной цены как emergency SL
                            emergency_sl = entry_price * (0.97 if side == 'long' else 1.03)
                        
                        emergency_order = self.exchange.create_order(
                            ccxt_sym,
                            'stop_market',
                            sl_side,
                            quantity,
                            None,
                            params={
                                'stopPrice': emergency_sl,
                                'reduceOnly': True,
                                'timeInForce': 'GTC'
                            }
                        )
                        
                        pos['sl_order_id'] = str(emergency_order['id'])
                        pos['last_updated_sl'] = emergency_sl
                        logger.warning(f"🛡️ {symbol}: EMERGENCY SL создан @ {emergency_sl:.6f} (ID: {emergency_order['id']})")
                        
                    except Exception as emergency_error:
                        logger.error(f"❌ {symbol}: НЕ УДАЛОСЬ СОЗДАТЬ EMERGENCY SL: {emergency_error}")
                        logger.error(f"❌ {symbol}: ПОЗИЦИЯ ОСТАЕТСЯ ПОЛНОСТЬЮ НЕЗАЩИЩЕННОЙ!")
                
                elif len(sl_orders) > 1:
                    logger.warning(f"⚠️ {symbol}: Найдено {len(sl_orders)} SL ордеров, должен быть только 1! (Будет исправлено в cleanup_orphaned_orders)")
                        
            except Exception as check_error:
                logger.warning(f"⚠️ Ошибка проверки SL для {symbol}: {check_error}")
        
        if unprotected_positions:
            logger.error(f"❌ КРИТИЧНО: {len(unprotected_positions)} позиций без SL защиты: {unprotected_positions}")
        else:
            logger.debug(f"✅ Все {len(self.active_positions)} позиций имеют SL защиту")
        
    def ccxt_symbol(self, symbol: str) -> str:
        """Convert symbol format: ADA_USDT -> ADA/USDT:USDT"""
        # If already in CCXT format, return as-is
        if '/' in symbol and ':' in symbol:
            return symbol
            
        # If contains underscore, convert from our format
        if '_' in symbol:
            parts = symbol.split('_')
            if len(parts) == 2:
                base, quote = parts
                return f"{base}/{quote}:{quote}"
            else:
                logger.error(f"❌ Invalid symbol format: {symbol}")
                return symbol
        
        # If no underscore, assume it's already in some other format
        logger.warning(f"⚠️ Unexpected symbol format: {symbol}")
        return symbol
        
    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 500) -> pd.DataFrame:
        """Fetch OHLCV data from exchange"""
        if self.paper_mode:
            # In paper mode, return empty DataFrame
            return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
        try:
            ccxt_sym = self.ccxt_symbol(symbol)
            ohlcv = self.exchange.fetch_ohlcv(ccxt_sym, timeframe=timeframe, limit=limit)
            
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = (df['timestamp'] // 1000).astype(int)  # Convert to seconds
            
            return df.sort_values('timestamp').reset_index(drop=True)
            
        except Exception as e:
            logger.error(f"❌ Failed to fetch {symbol} {timeframe}: {e}")
            return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    
    def fetch_recent_data(self, symbol: str, timeframe: str = '1h', limit: int = 600) -> pd.DataFrame:
        """Fetch recent OHLCV data from exchange (compatible with old API)"""
        return self.fetch_ohlcv(symbol, timeframe, limit)
            
    def get_btc_market_bias(self, force_refresh: bool = False) -> Optional[pd.DataFrame]:
        """Get BTC market filter - ВСЕГДА получает свежие данные с Binance"""
        current_time = int(time.time())
        
        # ИСПРАВЛЕНО: Убираем кеширование для BTC данных - всегда получаем свежие данные
        # Актуальность BTC тренда критически важна для правильной торговли
        logger.debug("📊 Получение актуальных BTC данных с Binance...")
            
        try:
            # Всегда получаем свежие данные BTC с биржи
            btc_1h = self.fetch_ohlcv('BTC/USDT:USDT', '1h', 200)
            if btc_1h.empty:
                logger.warning("⚠️ No BTC data - market filter disabled")
                return None
                
            btc_bias = compute_market_bias(
                btc_1h, 
                self.cfg['market_filter']['ema_fast'], 
                self.cfg['market_filter']['ema_slow']
            )
            
            # Log current market state and detect changes
            latest = btc_bias.iloc[-1]
            long_ok = latest['mkt_long_ok']
            short_ok = latest['mkt_short_ok']
            
            # Detect trend changes (только если есть старый кеш)
            old_cache = self.btc_gate_cache
            trend_changed = False
            if old_cache is not None and not old_cache.empty:
                old_latest = old_cache.iloc[-1]
                old_long_ok = old_latest['mkt_long_ok']
                old_short_ok = old_latest['mkt_short_ok']
                
                if (long_ok != old_long_ok) or (short_ok != old_short_ok):
                    trend_changed = True
                    logger.warning(f"🔄 BTC TREND CHANGE DETECTED! "
                                 f"Long: {old_long_ok}→{long_ok}, "
                                 f"Short: {old_short_ok}→{short_ok}")
            
            if long_ok and short_ok:
                market_state = "🟡 NEUTRAL"
            elif long_ok:
                market_state = "🟢 BULL (longs favored)"
            elif short_ok:
                market_state = "🔴 BEAR (shorts favored)"
            else:
                market_state = "⚫ SIDEWAYS"
                
            logger.info(f"📊 BTC Market Filter: {market_state}"
                       f" {'🔄 CHANGED!' if trend_changed else ''}")
            
            # Сохраняем для сравнения (но не используем для кеширования)
            self.btc_gate_cache = btc_bias
            self.btc_gate_timestamp = current_time
            
            return btc_bias
            
        except Exception as e:
            logger.error(f"❌ BTC market filter failed: {e}")
            return None
    
    def force_refresh_btc_cache(self):
        """Принудительно обновить кеш BTC фильтра"""
        logger.info("🔄 Принудительное обновление BTC кеша...")
        self.btc_gate_cache = None
        self.btc_gate_timestamp = 0
        return self.get_btc_market_bias(force_refresh=True)
    
    def clear_all_caches(self):
        """Очистить все кеши системы"""
        logger.warning("🧹 Очистка всех кешей системы...")
        self.btc_gate_cache = None
        self.btc_gate_timestamp = 0
        # Добавить другие кеши при необходимости
        logger.info("✅ Все кеши очищены")
    
    def check_cache_control_signals(self):
        """Проверить файл сигналов управления кешем"""
        try:
            signal_file = Path("cache_control_signal.json")
            if not signal_file.exists():
                return
            
            # Проверяем только раз в 10 секунд
            current_time = time.time()
            if current_time - self.last_signal_check < 10:
                return
            
            self.last_signal_check = current_time
            
            with open(signal_file, 'r') as f:
                signal = json.load(f)
            
            action = signal.get('action')
            timestamp = signal.get('timestamp', 0)
            
            # Игнорируем старые сигналы (>5 минут)
            if current_time - timestamp > 300:
                return
            
            logger.info(f"📨 Получен сигнал управления: {action}")
            
            if action == "clear_btc_cache":
                self.force_refresh_btc_cache()
            elif action == "force_position_sync":
                self.check_and_sync_missing_positions()
            elif action == "clear_all_caches":
                self.clear_all_caches()
                self.check_and_sync_missing_positions()
            
            # Удаляем обработанный сигнал
            signal_file.unlink()
            logger.info("✅ Сигнал обработан и удален")
            
        except Exception as e:
            logger.error(f"❌ Ошибка обработки сигнала: {e}")
            
    def prepare_data(self, df: pd.DataFrame, gate: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """Prepare data with indicators and signals"""
        if df.empty:
            return df
            
        # Add indicators
        df = add_indicators(
            df, 
            ema_fast=50, 
            ema_slow=200, 
            atr_p=self.cfg['regime']['natr_period'],
            rsi_p=self.cfg['short_guard'].get('rsi_period', 14)
        )
        
        # Add regime
        df = add_regime(df, self.regime_thresholds)
        
        # Generate signals
        df = generate_signals(df, self.signal_params, market_gate=gate)
        
        return df
        
    def process_symbol_mtf(self, symbol: str) -> Dict[str, Any]:
        """Process symbol with MTF logic (1h + 15m)"""
        result = {
            'symbol': symbol,
            'signals': [],
            'current_state': {},
            'errors': []
        }
        
        try:
            # ИСПРАВЛЕНО: Всегда получаем актуальные BTC данные без проверки возраста кеша
            # Актуальность BTC тренда критически важна для правильной торговли
            btc_gate = self.get_btc_market_bias()
            
            # Fetch 1h data for breakout signals
            df_1h = self.fetch_ohlcv(symbol, '1h', 200)
            if df_1h.empty:
                result['errors'].append("No 1h data")
                return result
                
            sig_1h = self.prepare_data(df_1h, btc_gate)
            latest_1h = sig_1h.iloc[-1]
            
            # Check 1h breakout signals
            if latest_1h.get('sig_long_breakout', False) and latest_1h.get('allow_long', False):
                result['signals'].append({
                    'timeframe': '1h',
                    'side': 'LONG',
                    'setup': 'breakout',
                    'entry': float(latest_1h['long_entry_final']),
                    'reason': latest_1h.get('long_reason', 'breakout'),
                    'atr': float(latest_1h['atr']),
                    'regime': latest_1h.get('regime', 'unknown'),
                    'confidence': 'HIGH'
                })
                
            if latest_1h.get('sig_short_breakout', False) and latest_1h.get('allow_short', False):
                result['signals'].append({
                    'timeframe': '1h',
                    'side': 'SHORT', 
                    'setup': 'breakout',
                    'entry': float(latest_1h['short_entry_final']),
                    'reason': latest_1h.get('short_reason', 'breakout'),
                    'atr': float(latest_1h['atr']),
                    'regime': latest_1h.get('regime', 'unknown'),
                    'confidence': 'HIGH'
                })
            
            # Fetch 15m data for LTF signals
            df_15m = self.fetch_ohlcv(symbol, '15m', 400)
            if not df_15m.empty:
                # Forward fill BTC gate to 15m
                gate_15m = None
                if btc_gate is not None:
                    gate_15m_data = []
                    for ts in df_15m['timestamp'].values:
                        mask = btc_gate['timestamp'] <= ts
                        if mask.any():
                            # ИСПРАВЛЕНИЕ: Найти последний True индекс вместо idxmax()
                            true_indices = mask[mask].index
                            idx = true_indices[-1]  # Последний True индекс
                            gate_15m_data.append({
                                'timestamp': ts,
                                'mkt_long_ok': btc_gate.iloc[idx]['mkt_long_ok'],
                                'mkt_short_ok': btc_gate.iloc[idx]['mkt_short_ok']
                            })
                        else:
                            gate_15m_data.append({'timestamp': ts, 'mkt_long_ok': False, 'mkt_short_ok': False})
                    gate_15m = pd.DataFrame(gate_15m_data)
                
                sig_15m = self.prepare_data(df_15m, gate_15m)
                latest_15m = sig_15m.iloc[-1]
                
                # Check 15m LTF signals (inside/trend/squeeze)
                ltf_setups = ['inside', 'tc', 'sq']
                for setup in ltf_setups:
                    # Long signals
                    if (latest_15m.get(f'sig_long_{setup}', False) and 
                        latest_15m.get('allow_long', False)):
                        result['signals'].append({
                            'timeframe': '15m',
                            'side': 'LONG',
                            'setup': setup,
                            'entry': float(latest_15m['long_entry_final']),
                            'reason': latest_15m.get('long_reason', setup),
                            'atr': float(latest_15m['atr']),
                            'regime': latest_15m.get('regime', 'unknown'),
                            'confidence': 'MEDIUM'
                        })
                        break  # Only one signal per side
                    
                    # Short signals  
                    if (latest_15m.get(f'sig_short_{setup}', False) and 
                        latest_15m.get('allow_short', False)):
                        result['signals'].append({
                            'timeframe': '15m',
                            'side': 'SHORT',
                            'setup': setup,
                            'entry': float(latest_15m['short_entry_final']),
                            'reason': latest_15m.get('short_reason', setup),
                            'atr': float(latest_15m['atr']),
                            'regime': latest_15m.get('regime', 'unknown'),
                            'confidence': 'MEDIUM'
                        })
                        break  # Only one signal per side
                        
            # Current state for monitoring
            # Get BTC market filter status from the gate data
            btc_long_ok = True
            btc_short_ok = True
            if btc_gate is not None and not btc_gate.empty:
                btc_latest = btc_gate.iloc[-1]
                btc_long_ok = bool(btc_latest.get('mkt_long_ok', True))
                btc_short_ok = bool(btc_latest.get('mkt_short_ok', True))
            
            result['current_state'] = {
                'regime_1h': latest_1h.get('regime', 'unknown'),
                'trend_long_1h': bool(latest_1h.get('trend_long', False)),
                'trend_short_1h': bool(latest_1h.get('trend_short', False)),
                'natr_1h': float(latest_1h.get('natr', 0)),
                'rsi_1h': float(latest_1h.get('rsi', 50)),
                'btc_long_ok': btc_long_ok,
                'btc_short_ok': btc_short_ok,
                'price': float(latest_1h['close'])
            }
            
        except Exception as e:
            logger.error(f"❌ Error processing {symbol}: {e}")
            result['errors'].append(str(e))
            
        return result
        
    def execute_signal(self, signal: Dict[str, Any]) -> str:
        """Execute trading signal"""
        if self.paper_mode:
            return f"PAPER: {signal['side']} {signal['setup']} @ {signal['entry']:.6f}"
            
        try:
            symbol = signal['symbol']
            side = signal['side']
            entry = signal['entry']
            
            # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Принудительно пересчитываем ATR
            try:
                df = self.fetch_ohlcv(symbol, '1h', 50)
                if not df.empty:
                    from signalwarden_lite.core.features import add_indicators
                    df = add_indicators(df, atr_p=14)
                    atr = float(df.iloc[-1]['atr'])
                    logger.info(f"🔄 {symbol}: ATR пересчитан: {atr:.6f} USDT")
                else:
                    atr = signal['atr']  # Fallback к сигналу
                    logger.warning(f"⚠️ {symbol}: Нет данных для пересчета ATR, используем из сигнала: {atr:.6f}")
            except Exception as e:
                atr = signal['atr']  # Fallback к сигналу
                logger.warning(f"⚠️ {symbol}: Ошибка пересчета ATR: {e}, используем из сигнала: {atr:.6f}")
            
            # Check if position already exists for this symbol
            if self.has_open_position(symbol):
                error_msg = f"❌ Position already open for {symbol} - skipping"
                logger.warning(f"⚠️ {symbol}: {error_msg}")
                return error_msg
            
            # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Очищаем старые данные ТОЛЬКО если позиция закрыта
            # has_open_position уже очистил данные если позиция не существует на бирже
            # Но на всякий случай проверяем локальные остатки
            if symbol in self.active_positions:
                logger.warning(f"🧹 {symbol}: Обнаружены локальные остатки данных, очищаем")
                del self.active_positions[symbol]
                self.cleanup_position_state(symbol)
            
            # Check if we have enough balance for new position (considering 5x leverage)
            if not self.can_open_new_position():
                error_msg = f"❌ Insufficient balance for new position - need {self.margin_usdt/self.leverage:.1f} USDT margin"
                logger.warning(f"⚠️ {symbol}: {error_msg}")
                return error_msg
            
            # Calculate position size: FIXED margin_usdt positions (21 USDT notional with 5x leverage)
            # This ensures we trade with exactly margin_usdt notional value
            position_value_usdt = self.margin_usdt  # 21 USDT notional exactly
            qty = position_value_usdt / entry
            
            # Используем чистый ATR (как в стратегии)
            effective_atr = atr
            
            if side == 'LONG':
                sl_price = entry - (self.sl_atr_mult * effective_atr)
            else:
                sl_price = entry + (self.sl_atr_mult * effective_atr)
            
            # ПОДРОБНОЕ ЛОГИРОВАНИЕ для диагностики (анти-дрейф)
            original_atr = atr
            sl_distance_usdt = abs(sl_price - entry) * qty
            sl_distance_pct = (abs(sl_price - entry) / entry) * 100
            
            # Логирование SL расстояния
            logger.info(f"🔍 {symbol}: ATR {effective_atr:.6f}, SL distance {sl_distance_pct:.2f}%")
            
            logger.info(f"🎯 {symbol} {side} ENTRY ANALYSIS:")
            logger.info(f"   📊 Entry: {entry:.6f}, Qty: {qty:.4f} ({position_value_usdt} USDT)")
            logger.info(f"   📏 ATR: {atr:.6f} (ЧИСТЫЙ - как в успешном бэктесте!)")
            logger.info(f"   🛡️ SL: {sl_price:.6f} (Distance: ${sl_distance_usdt:.4f})")
            
            # КРИТИЧЕСКОЕ ЛОГИРОВАНИЕ для диагностики
            sl_distance_pct = (abs(sl_price - entry) / entry) * 100
            logger.warning(f"🚨 {symbol}: КРИТИЧЕСКАЯ ДИАГНОСТИКА:")
            logger.warning(f"   • Оригинальный ATR: {original_atr:.6f} USDT")
            logger.warning(f"   • Эффективный ATR: {effective_atr:.6f} USDT")
            logger.warning(f"   • SL distance: {sl_distance_pct:.2f}% от цены")
            logger.warning(f"   • SL distance USDT: ${sl_distance_usdt:.4f}")
            logger.warning(f"   • Ожидаемый минимум: 1.2% = ${entry * 0.012:.4f}")
            
            if sl_distance_pct < 1.0:
                logger.error(f"❌ {symbol}: SL СЛИШКОМ БЛИЗКО! {sl_distance_pct:.2f}% < 1.0%")
            elif sl_distance_pct < 1.5:
                logger.warning(f"⚠️ {symbol}: SL близко к минимуму: {sl_distance_pct:.2f}%")
            else:
                logger.info(f"✅ {symbol}: SL нормальный: {sl_distance_pct:.2f}%")
            logger.info(f"   💸 Entry Fee: maker_first (низкие комиссии)")
            
            ccxt_sym = self.ccxt_symbol(symbol)
            
            # Place market order
            order_side = 'buy' if side == 'LONG' else 'sell'
            order = self.exchange.create_market_order(
                ccxt_sym, 
                order_side, 
                qty,
                entry,  # price for logging
                params={'reduceOnly': False}
            )
            
            # Create initial stop loss order immediately
            sl_side = 'sell' if side == 'LONG' else 'buy'
            try:
                # Determine order parameters based on type
                if self.sl_order_type == 'stop_market':
                    # Маркет стоп-лосс (рыночный ордер после триггера) - по умолчанию
                    sl_order = self.exchange.create_order(
                        ccxt_sym,
                        'stop_market',
                        sl_side,
                        qty,
                        None,  # Нет цены исполнения для stop_market
                        params={
                            'stopPrice': sl_price,
                            'reduceOnly': True,
                            'timeInForce': 'GTC'
                        }
                    )
                else:
                    # Лимитный стоп-лосс (лимитный ордер после триггера)
                    sl_order = self.exchange.create_order(
                        ccxt_sym,
                        self.sl_order_type,  # Используем из конфигурации!
                        sl_side,
                        qty,
                        sl_price if self.sl_order_type == 'stop' else None,  # Цена только для лимитного
                        params={
                            'stopPrice': sl_price,
                            'reduceOnly': True,
                            'timeInForce': 'GTC'
                        }
                    )
                sl_order_id = sl_order['id']
                logger.info(f"🛡️ {symbol}: Stop-loss created @ {sl_price:.6f} (Order ID: {sl_order_id})")
                
                # КРИТИЧЕСКОЕ ЛОГИРОВАНИЕ stop-market ордера
                logger.warning(f"🚨 {symbol}: STOP-MARKET ОРДЕР СОЗДАН:")
                logger.warning(f"   • Order ID: {sl_order_id}")
                logger.warning(f"   • Stop Price: {sl_price:.6f} USDT")
                logger.warning(f"   • Entry Price: {entry:.6f} USDT")
                logger.warning(f"   • SL Distance: {abs(sl_price - entry):.6f} USDT")
                logger.warning(f"   • SL Distance %: {abs(sl_price - entry)/entry*100:.2f}%")
                logger.warning(f"   • Qty: {qty:.4f}")
                logger.warning(f"   • Side: {sl_side}")
                logger.warning(f"   • Type: {self.sl_order_type}")
            except Exception as e:
                logger.error(f"❌ {symbol}: Failed to create stop-loss: {e}")
                sl_order_id = None
            
            # КРИТИЧЕСКАЯ ПРОВЕРКА: Позиция НЕ добавляется без SL ордера!
            if sl_order_id is None:
                logger.error(f"❌ {symbol}: КРИТИЧНО - НЕ УДАЛОСЬ СОЗДАТЬ SL ОРДЕР!")
                logger.error(f"❌ {symbol}: ПОЗИЦИЯ НЕ БУДЕТ ДОБАВЛЕНА В ТРЕЙЛИНГ!")
                
                # Пытаемся закрыть позицию на бирже чтобы не оставлять ее без защиты
                try:
                    close_side = 'sell' if side == 'LONG' else 'buy'
                    close_order = self.exchange.create_market_order(
                        ccxt_sym,
                        close_side,
                        qty,
                        None,
                        params={'reduceOnly': True}
                    )
                    logger.warning(f"🛡️ {symbol}: Позиция закрыта для безопасности (ID: {close_order['id']})")
                    return f"❌ {symbol}: Позиция закрыта - не удалось создать SL"
                except Exception as close_error:
                    logger.error(f"❌ {symbol}: Не удалось закрыть незащищенную позицию: {close_error}")
                    logger.error(f"❌ {symbol}: ПОЗИЦИЯ ОСТАЛАСЬ НЕЗАЩИЩЕННОЙ НА БИРЖЕ!")
                    return f"❌ {symbol}: КРИТИЧНО - позиция без SL осталась на бирже!"
            
            # Track position
            position_info = {
                'symbol': symbol,
                'side': side,
                'entry': entry,
                'qty': qty,
                'sl_initial': sl_price,
                'sl_current': sl_price,
                'atr': atr,
                'timestamp': time.time(),
                'order_id': order['id'],
                'sl_order_id': sl_order_id,
                'trailing_active': False,
                'peak_pnl_usdt': 0.0,  # Initialize peak PnL tracking
                'last_updated_sl': sl_price  # Для предотвращения спама обновлений
            }
            
            self.active_positions[symbol] = position_info
            logger.info(f"✅ {symbol}: Позиция добавлена в активные с SL защитой")
            
            # Save state
            self.storage.update_symbol(symbol, {
                'active_position': position_info,
                'last_signal_time': time.time()
            })
            
            result = f"✅ {side} {signal['setup']} @ {entry:.6f}, SL @ {sl_price:.6f}, Qty: {qty:.6f}"
            logger.info(f"🎯 {symbol}: {result}")
            
            return result
            
        except Exception as e:
            error_msg = f"❌ Execution failed: {e}"
            logger.error(f"💥 {symbol}: {error_msg}")
            return error_msg
            
    def run_trading_cycle(self):
        """Run one complete trading cycle"""
        cycle_start = time.time()
        logger.info("=" * 80)
        logger.info(f"🔄 TRADING CYCLE START: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
        
        # Проверяем сигналы управления кешем
        self.check_cache_control_signals()
        
        total_signals = 0
        executed_trades = 0
        
        # CRITICAL: First check and manage active positions
        self.check_active_positions()
        
        # Periodic validation (every 10 cycles)
        if hasattr(self, '_cycle_count'):
            self._cycle_count += 1
        else:
            self._cycle_count = 1
            
        if self._cycle_count % 10 == 0:
            self.run_periodic_validation()
        
        # Trailing is now handled by separate thread, no need to update here
        
        for symbol in self.cfg['symbols']:
            try:
                logger.info(f"📊 Processing {symbol}...")
                
                # Process with MTF logic
                result = self.process_symbol_mtf(symbol)
                
                # Log current state
                state = result['current_state']
                if state:
                    logger.info(f"   State: {state['regime_1h']} regime, "
                              f"Price: ${state['price']:.6f}, "
                              f"NATR: {state['natr_1h']:.1f}%, "
                              f"RSI: {state['rsi_1h']:.0f}, "
                              f"BTC: {'🟢L' if state['btc_long_ok'] else '❌L'}"
                              f"{'🔴S' if state['btc_short_ok'] else '❌S'}")
                
                # Process signals
                if result['signals']:
                    for signal in result['signals']:
                        total_signals += 1
                        signal['symbol'] = symbol
                        
                        logger.info(f"🎯 {symbol}: {signal['confidence']} {signal['timeframe']} "
                                  f"{signal['side']} {signal['setup']} @ {signal['entry']:.6f}")
                        
                        # Execute signal
                        exec_result = self.execute_signal(signal)
                        
                        if "✅" in exec_result:
                            executed_trades += 1
                            
                        # Store signal in history
                        self.storage.add_signal(symbol, {
                            'timestamp': int(time.time()),
                            'signal': signal,
                            'result': exec_result
                        })
                        
                else:
                    logger.info(f"   No signals detected")
                    
                # Log errors
                if result['errors']:
                    for error in result['errors']:
                        logger.warning(f"   ⚠️ {error}")
                        
            except Exception as e:
                logger.error(f"💥 Failed to process {symbol}: {e}")
                continue
                
        # Cycle summary
        cycle_time = time.time() - cycle_start
        logger.info(f"📈 CYCLE COMPLETE: {total_signals} signals, {executed_trades} trades executed in {cycle_time:.1f}s")
        logger.info("=" * 80)
        
        return total_signals, executed_trades
        
    def run(self):
        """Main trading loop"""
        logger.info("🚀 Starting SignalWarden v1.6-TXB live trading...")
        logger.info(f"📊 Monitoring {len(self.cfg['symbols'])} symbols")
        logger.info(f"💰 Risk per trade: {self.margin_usdt} USDT notional ({self.margin_usdt/self.leverage:.1f} USDT margin)")
        logger.info(f"⚙️ MTF Strategy: 1h breakout + 15m LTF setups")
        logger.info(f"🛡️ Adaptive shorts with BTC filter enabled")
        logger.info(f"🔄 PnL-only trailing: ${self.trailing.level_1_pnl}→{self.trailing.level_1_keep_pct*100:.0f}%, ${self.trailing.level_2_pnl}→{self.trailing.level_2_keep_pct*100:.0f}%, ${self.trailing.level_3_pnl}→{self.trailing.level_3_keep_pct*100:.0f}%, ${self.trailing.level_4_pnl}→{self.trailing.level_4_keep_pct*100:.0f}%")
        
        # Load saved position states
        self.load_position_states()
        
        # Initialize cache control
        self.last_signal_check = 0
        
        # Start fast trailing thread
        self.start_trailing_thread()
        
        cycle_count = 0
        
        try:
            while True:
                cycle_count += 1
                
                try:
                    # Clear stale cache to prevent trading on outdated data
                    self.clear_stale_cache()
                    
                    # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Синхронизация каждый цикл
                    logger.info("🔄 Синхронизация с биржей каждый цикл...")
                    self.force_cleanup_nonexistent_positions()
                    
                    signals, trades = self.run_trading_cycle()
                    
                    # Sleep for 2 minutes between cycles
                    logger.info(f"😴 Cycle {cycle_count} complete. Sleeping 120 seconds...")
                    time.sleep(120)
                    
                except KeyboardInterrupt:
                    logger.info("🛑 Received interrupt signal, shutting down...")
                    self.stop_trailing_thread()
                    break
                    
                except Exception as e:
                    logger.error(f"💥 Cycle error: {e}")
                    logger.info("⏰ Sleeping 60 seconds before retry...")
                    time.sleep(60)
                    
        except KeyboardInterrupt:
            logger.info("🛑 Shutdown complete")
            
        logger.info(f"📊 Total cycles completed: {cycle_count}")
    
    def save_position_state(self, symbol: str, pos: dict):
        """Save position state to persistent storage"""
        try:
            position_state = {
                'symbol': symbol,
                'side': pos['side'],
                'entry': pos['entry'],
                'qty': pos['qty'],
                'sl_current': pos['sl_current'],
                'sl_initial': pos['sl_initial'],
                'peak_pnl_usdt': pos['peak_pnl_usdt'],
                'trailing_active': pos['trailing_active'],
                'timestamp': time.time()
            }
            
            # Save to storage
            self.storage.update_symbol(f"{symbol}_position", position_state)
            
        except Exception as e:
            logger.error(f"❌ Error saving position state for {symbol}: {e}")
    
    def load_position_states(self):
        """Load saved position states from persistent storage"""
        try:
            for symbol in self.cfg['symbols']:
                ccxt_symbol = self.ccxt_symbol(symbol)
                
                # Skip if position already exists in memory
                if symbol in self.active_positions:
                    # Load saved peak_pnl_usdt if available
                    saved_state = self.storage.get_symbol(f"{symbol}_position")
                    if saved_state and 'peak_pnl_usdt' in saved_state:
                        self.active_positions[symbol]['peak_pnl_usdt'] = max(
                            self.active_positions[symbol]['peak_pnl_usdt'],
                            saved_state['peak_pnl_usdt']
                        )
                        logger.info(f"🔄 {symbol}: Restored peak PnL {saved_state['peak_pnl_usdt']:.3f} USDT")
                    continue
                    
        except Exception as e:
            logger.error(f"❌ Error loading position states: {e}")
    
    def cleanup_position_state(self, symbol: str):
        """Clean up saved position state when position is closed"""
        try:
            # Remove from storage
            db = self.storage.read()
            position_key = f"{symbol}_position"
            if 'symbols' in db and position_key in db['symbols']:
                del db['symbols'][position_key]
                self.storage.write(db)
                logger.debug(f"🧹 Cleaned up saved state for {symbol}")
                
        except Exception as e:
            logger.error(f"❌ Error cleaning up position state for {symbol}: {e}")

def main():
    parser = argparse.ArgumentParser(description='SignalWarden Lite v1.6-TXB Live Trading')
    parser.add_argument('--config', required=True, help='Config YAML file path')
    parser.add_argument('--paper', action='store_true', help='Run in paper trading mode')
    
    args = parser.parse_args()
    
    # Create and run trading system
    trader = SignalWardenLive(args.config, paper_mode=args.paper)
    trader.run()

if __name__ == '__main__':
    main()
