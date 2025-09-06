import time
from dataclasses import dataclass
from typing import Dict, Any
from .types import OrderPlan, Side
from ..utils.logger import get_logger

logger = get_logger(__name__)

@dataclass
class ExecConfig:
    maker_first: bool = True
    ttl_seconds: int = 8
    fallback_market: bool = True
    manage_stop: bool = True  # Управление стоп-ордерами

class PaperExecutor:
    def __init__(self, cfg: ExecConfig):
        self.cfg = cfg
        self.open_stops = {}  # key: (symbol, side) -> order_id

    def place_entry(self, symbol: str, side: str, price: float, qty: float) -> Dict[str, Any]:
        """Place entry order in paper mode"""
        logger.info(f"Paper mode: placing {side} entry for {symbol} @ {price:.6f}, qty={qty:.6f}")
        return {
            "status": "filled", 
            "symbol": symbol, 
            "side": side, 
            "qty": qty, 
            "entry": price,
            "filled_price": price
        }
    
    def ensure_stop(self, symbol: str, side: str, stop_price: float, qty: float):
        """Ensure stop order exists at correct price (paper mode)"""
        if not self.cfg.manage_stop:
            return
        
        key = (symbol, side)
        logger.info(f"Paper mode: managing stop for {symbol} {side} @ {stop_price:.6f}")
        self.open_stops[key] = f"paper_stop_{symbol}_{side}"

class CCXTBinanceUSDMExecutor:
    def __init__(self, exchange, cfg: ExecConfig):
        self.exchange = exchange
        self.cfg = cfg
        self.open_stops = {}  # key: (symbol, side) -> order_id

    @staticmethod
    def _symbol_to_ccxt(symbol: str) -> str:
        """Convert our symbol format to CCXT format"""
        base, quote = symbol.split('_')
        return f"{base}/{quote}:{quote}"

    def place_entry(self, symbol: str, side: str, price: float, qty: float) -> Dict[str, Any]:
        """Place entry order with maker-first logic"""
        ccxt_symbol = self._symbol_to_ccxt(symbol)
        
        try:
            market = self.exchange.market(ccxt_symbol)
            amount = max(qty, market['limits']['amount']['min'] or 0.0)
            
            # Set position side for hedge mode
            params = {
                'positionSide': 'LONG' if side == 'LONG' else 'SHORT'
            }
            
            if self.cfg.maker_first:
                # Try maker-first with TTL
                params['timeInForce'] = 'GTX'  # Good Till Crossing (Post Only)
                
                try:
                    order = self.exchange.create_order(
                        ccxt_symbol, 
                        'limit', 
                        'buy' if side == 'LONG' else 'sell', 
                        amount, 
                        price, 
                        params
                    )
                    
                    # Wait for fill with TTL
                    created_time = time.time()
                    while time.time() - created_time < self.cfg.ttl_seconds:
                        fetched = self.exchange.fetch_order(order['id'], ccxt_symbol)
                        if fetched.get('status') in ('closed', 'filled'):
                            logger.info(f"Maker order filled: {symbol} {side} @ {fetched.get('average', price)}")
                            return {
                                "status": "filled",
                                "symbol": symbol,
                                "side": side,
                                "qty": amount,
                                "entry": price,
                                "filled_price": fetched.get('average', price),
                                "order_id": order['id']
                            }
                        time.sleep(0.5)
                    
                    # Cancel unfilled maker order
                    try:
                        self.exchange.cancel_order(order['id'], ccxt_symbol)
                        logger.info(f"Cancelled unfilled maker order: {symbol}")
                    except Exception as e:
                        logger.warning(f"Failed to cancel maker order: {e}")
                    
                except Exception as e:
                    logger.warning(f"Maker order failed: {e}")
            
            # Fallback to market order if configured
            if self.cfg.fallback_market:
                logger.info(f"Using market order fallback: {symbol} {side}")
                params.pop('timeInForce', None)  # Remove GTX for market order
                
                market_order = self.exchange.create_order(
                    ccxt_symbol, 
                    'market', 
                    'buy' if side == 'LONG' else 'sell', 
                    amount,
                    None,  # No price for market order
                    params
                )
                
                # Fetch the filled order to get actual price
                filled_order = self.exchange.fetch_order(market_order['id'], ccxt_symbol)
                filled_price = filled_order.get('average', price)
                
                logger.info(f"Market order filled: {symbol} {side} @ {filled_price}")
                return {
                    "status": "filled",
                    "symbol": symbol,
                    "side": side,
                    "qty": amount,
                    "entry": price,
                    "filled_price": filled_price,
                    "order_id": market_order['id']
                }
            
            return {"status": "cancelled_ttl", "symbol": symbol}
            
        except Exception as e:
            logger.error(f"Entry order failed for {symbol}: {e}")
            return {"status": "error", "error": str(e), "symbol": symbol}

    def ensure_stop(self, symbol: str, side: str, stop_price: float, qty: float):
        """Create or update stop-market order"""
        if not self.cfg.manage_stop:
            return
        
        ccxt_symbol = self._symbol_to_ccxt(symbol)
        key = (symbol, side)
        
        try:
            # Cancel existing stop if it exists
            existing_order_id = self.open_stops.get(key)
            if existing_order_id:
                try:
                    self.exchange.cancel_order(existing_order_id, ccxt_symbol)
                    logger.info(f"Cancelled existing stop order: {symbol} {side}")
                    time.sleep(0.1)  # Small delay
                except Exception as e:
                    logger.warning(f"Failed to cancel existing stop: {e}")
            
            # Create new stop order
            market = self.exchange.market(ccxt_symbol)
            amount = max(qty, market['limits']['amount']['min'] or 0.0)
            
            params = {
                'stopPrice': stop_price,
                'positionSide': 'LONG' if side == 'LONG' else 'SHORT',
                'closePosition': False,  # Don't close entire position
                'reduceOnly': True,      # Only reduce position
                'type': 'STOP_MARKET'
            }
            
            stop_order = self.exchange.create_order(
                ccxt_symbol,
                'STOP_MARKET',
                'sell' if side == 'LONG' else 'buy',  # Opposite side to close
                amount,
                None,  # No limit price for stop market
                params
            )
            
            self.open_stops[key] = stop_order['id']
            logger.info(f"Created stop order: {symbol} {side} @ {stop_price:.6f}, order_id={stop_order['id']}")
            
        except Exception as e:
            logger.error(f"Failed to manage stop order for {symbol} {side}: {e}")
            # Don't raise - continue trading, just log the error

    def place(self, symbol: str, plan: OrderPlan, qty: float) -> Dict[str, Any]:
        """Legacy method for compatibility"""
        return self.place_entry(symbol, plan.side.value, plan.entry, qty)