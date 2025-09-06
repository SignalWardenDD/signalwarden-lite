#!/usr/bin/env python3
"""
REALTIME GATEWAY
Координирующий слой для реалтайм данных с TTL кэшированием и дедупликацией
"""

import time
import asyncio
import threading
from typing import Dict, List, Optional, Any
from collections import defaultdict
import logging
import numpy as np

logger = logging.getLogger(__name__)

class RealtimeGateway:
    """Координирующий слой для реалтайм данных"""
    
    def __init__(self, exchange):
        self.exchange = exchange
        self.logger = logger
        
        # Кэш для дедупликации (БЕЗ TTL - приоритет актуальности)
        self.cache = {
            'ticker': {},      # БЕЗ TTL - всегда свежие данные
            'positions': {},   # БЕЗ TTL - всегда свежие данные
            'orders': {},      # БЕЗ TTL - всегда свежие данные
            'tickers_batch': {}, # БЕЗ TTL - всегда свежие данные
            'returns': {},     # Кэш для ретурнов (TTL=60s)
            'correlations': {} # Кэш для корреляций (TTL=60s)
        }
        
        # TTL настройки (в секундах) - ПРИОРИТЕТ АКТУАЛЬНОСТИ
        self.ttl = {
            'ticker': 0.0,       # БЕЗ КЭШИРОВАНИЯ - всегда свежие данные
            'positions': 0.0,    # БЕЗ КЭШИРОВАНИЯ - всегда свежие данные
            'orders': 0.0,       # БЕЗ КЭШИРОВАНИЯ - всегда свежие данные
            'tickers_batch': 0.0,  # БЕЗ КЭШИРОВАНИЯ - всегда свежие данные
            'returns': 60.0,     # TTL=60s для ретурнов
            'correlations': 60.0 # TTL=60s для корреляций
        }
        
        # Дедупликация запросов
        self.pending_requests = {}
        self.request_locks = defaultdict(threading.Lock)
        
        # Статистика
        self.stats = {
            'requests': 0,
            'cache_hits': 0,
            'api_calls': 0,
            'errors': 0
        }
    
    def _is_cache_valid(self, cache_key: str, data_type: str) -> bool:
        """Проверяет актуальность кэша"""
        if cache_key not in self.cache[data_type]:
            return False
        
        cache_entry = self.cache[data_type][cache_key]
        return time.time() - cache_entry['timestamp'] < self.ttl[data_type]
    
    def _get_cached_data(self, cache_key: str, data_type: str) -> Optional[Dict]:
        """Получает данные из кэша"""
        if self._is_cache_valid(cache_key, data_type):
            self.stats['cache_hits'] += 1
            return self.cache[data_type][cache_key]['data']
        return None
    
    def _set_cached_data(self, cache_key: str, data_type: str, data: Dict):
        """Сохраняет данные в кэш"""
        self.cache[data_type][cache_key] = {
            'data': data,
            'timestamp': time.time()
        }
    
    def _make_api_call(self, method: str, *args, **kwargs) -> Optional[Dict]:
        """Выполняет API вызов с обработкой ошибок"""
        try:
            self.stats['api_calls'] += 1
            if method == 'fetch_ticker':
                return self.exchange.fetch_ticker(*args, **kwargs)
            elif method == 'fetch_positions':
                return self.exchange.fetch_positions(*args, **kwargs)
            elif method == 'fetch_open_orders':
                return self.exchange.fetch_open_orders(*args, **kwargs)
            else:
                raise ValueError(f"Unknown method: {method}")
        except Exception as e:
            self.stats['errors'] += 1
            self.logger.error(f"❌ API call failed {method}: {e}")
            return None
    
    def get_ticker(self, symbol: str) -> Optional[Dict]:
        """
        Получает тикер с приоритетом актуальности и дедупликацией
        
        Args:
            symbol: Торговая пара
            
        Returns:
            Dict с данными тикера или None при ошибке
        """
        self.stats['requests'] += 1
        
        # Проверяем кэш
        cached = self._get_cached_data(symbol, 'ticker')
        if cached:
            return cached
        
        # Дедупликация: если запрос уже выполняется, ждем результат
        with self.request_locks[f"ticker_{symbol}"]:
            # Повторная проверка кэша (возможно, другой поток уже обновил)
            cached = self._get_cached_data(symbol, 'ticker')
            if cached:
                return cached
            
            # Выполняем API запрос
            ticker_data = self._make_api_call('fetch_ticker', symbol)
            if ticker_data:
                self._set_cached_data(symbol, 'ticker', ticker_data)
                return ticker_data
        
        return None
    
    def get_positions(self) -> List[Dict]:
        """
        Получает позиции с TTL кэшированием
        
        Returns:
            List с позициями или пустой список при ошибке
        """
        self.stats['requests'] += 1
        
        # Проверяем кэш
        cached = self._get_cached_data('all', 'positions')
        if cached:
            return cached
        
        # Дедупликация
        with self.request_locks['positions']:
            # Повторная проверка кэша
            cached = self._get_cached_data('all', 'positions')
            if cached:
                return cached
            
            # Выполняем API запрос
            positions_data = self._make_api_call('fetch_positions')
            if positions_data:
                self._set_cached_data('all', 'positions', positions_data)
                return positions_data
        
        return []
    
    def get_open_orders(self, symbol: str) -> List[Dict]:
        """
        Получает открытые ордера для символа с TTL кэшированием
        
        Args:
            symbol: Торговая пара
            
        Returns:
            List с ордерами или пустой список при ошибке
        """
        self.stats['requests'] += 1
        
        # Проверяем кэш
        cached = self._get_cached_data(symbol, 'orders')
        if cached:
            return cached
        
        # Дедупликация
        with self.request_locks[f"orders_{symbol}"]:
            # Повторная проверка кэша
            cached = self._get_cached_data(symbol, 'orders')
            if cached:
                return cached
            
            # Выполняем API запрос
            orders_data = self._make_api_call('fetch_open_orders', symbol)
            if orders_data:
                self._set_cached_data(symbol, 'orders', orders_data)
                return orders_data
        
        return []
    
    def get_tickers_batch(self, symbols: List[str]) -> Dict[str, Dict]:
        """
        Получает тикеры для нескольких символов с оптимизацией
        
        Args:
            symbols: Список торговых пар
            
        Returns:
            Dict {symbol: ticker_data} или пустой dict при ошибке
        """
        self.stats['requests'] += 1
        
        # Проверяем кэш для всех символов
        result = {}
        missing_symbols = []
        
        for symbol in symbols:
            cached = self._get_cached_data(symbol, 'ticker')
            if cached:
                result[symbol] = cached
            else:
                missing_symbols.append(symbol)
        
        # Если все данные в кэше, возвращаем
        if not missing_symbols:
            return result
        
        # Загружаем недостающие данные
        for symbol in missing_symbols:
            ticker_data = self.get_ticker(symbol)
            if ticker_data:
                result[symbol] = ticker_data
        
        return result
    
    def invalidate_cache(self, data_type: str = None, symbol: str = None):
        """
        Инвалидирует кэш
        
        Args:
            data_type: Тип данных ('ticker', 'positions', 'orders', 'tickers_batch')
            symbol: Символ (если None, инвалидирует все)
        """
        if data_type:
            if symbol:
                # Инвалидируем конкретный символ
                if symbol in self.cache[data_type]:
                    del self.cache[data_type][symbol]
            else:
                # Инвалидируем весь тип данных
                self.cache[data_type].clear()
        else:
            # Инвалидируем весь кэш
            for cache_type in self.cache:
                self.cache[cache_type].clear()
        
        self.logger.info(f"🗑️ Cache invalidated: {data_type or 'all'} {symbol or ''}")
    
    def get_stats(self) -> Dict:
        """Возвращает статистику использования"""
        total_requests = self.stats['requests']
        cache_hit_rate = (self.stats['cache_hits'] / max(total_requests, 1)) * 100
        
        return {
            'total_requests': total_requests,
            'cache_hits': self.stats['cache_hits'],
            'api_calls': self.stats['api_calls'],
            'errors': self.stats['errors'],
            'cache_hit_rate': f"{cache_hit_rate:.1f}%",
            'cache_size': {
                'ticker': len(self.cache['ticker']),
                'positions': len(self.cache['positions']),
                'orders': len(self.cache['orders']),
                'tickers_batch': len(self.cache['tickers_batch'])
            }
        }
    
    def clear_stats(self):
        """Очищает статистику"""
        self.stats = {
            'requests': 0,
            'cache_hits': 0,
            'api_calls': 0,
            'errors': 0
        }
    
    # === МЕТОДЫ ДЛЯ КОРРЕЛЯЦИОННОГО АНАЛИЗА ===
    
    def get_returns(self, symbol: str, tf: str = '1h', lookback: int = 200) -> List[float]:
        """
        Получает ретурны для корреляционного анализа
        
        Args:
            symbol: Торговая пара
            tf: Таймфрейм ('15m', '1h', '4h')
            lookback: Количество баров
            
        Returns:
            List[float] с ретурнами или пустой список при ошибке
        """
        cache_key = f"{symbol}_{tf}_{lookback}"
        
        # Проверяем кэш
        cached = self._get_cached_data(cache_key, 'returns')
        if cached:
            return cached
        
        try:
            # Получаем OHLCV данные
            ohlcv = self.exchange.fetch_ohlcv(symbol, tf, limit=lookback)
            if not ohlcv or len(ohlcv) < 2:
                return []
            
            # Рассчитываем ретурны
            returns = []
            for i in range(1, len(ohlcv)):
                prev_close = ohlcv[i-1][4]  # Close предыдущего бара
                curr_close = ohlcv[i][4]     # Close текущего бара
                if prev_close > 0:
                    ret = (curr_close - prev_close) / prev_close
                    returns.append(ret)
            
            # Кэшируем результат
            self._set_cached_data(cache_key, 'returns', returns)
            return returns
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка получения ретурнов {symbol} {tf}: {e}")
            return []
    
    def get_returns_batch(self, symbols: List[str], tf: str = '1h', lookback: int = 200) -> Dict[str, List[float]]:
        """
        Получает ретурны для нескольких символов
        
        Args:
            symbols: Список торговых пар
            tf: Таймфрейм
            lookback: Количество баров
            
        Returns:
            Dict {symbol: returns_list}
        """
        result = {}
        for symbol in symbols:
            returns = self.get_returns(symbol, tf, lookback)
            if returns:
                result[symbol] = returns
        
        return result
    
    def get_correlation_matrix(self, symbols: List[str], tf: str = '1h', lookback: int = 200) -> Dict[str, Dict[str, float]]:
        """
        Рассчитывает матрицу корреляций между символами
        
        Args:
            symbols: Список торговых пар
            tf: Таймфрейм
            lookback: Количество баров
            
        Returns:
            Dict {symbol: {other_symbol: correlation}}
        """
        cache_key = f"corr_{'_'.join(symbols)}_{tf}_{lookback}"
        
        # Проверяем кэш
        cached = self._get_cached_data(cache_key, 'correlations')
        if cached:
            return cached
        
        try:
            # Получаем ретурны для всех символов
            returns_data = self.get_returns_batch(symbols, tf, lookback)
            
            # Находим минимальную длину
            min_length = min(len(returns) for returns in returns_data.values()) if returns_data else 0
            if min_length < 50:  # Минимум 50 баров для корреляции
                return {}
            
            # Обрезаем все ряды до минимальной длины
            aligned_returns = {}
            for symbol, returns in returns_data.items():
                aligned_returns[symbol] = returns[-min_length:]
            
            # Рассчитываем корреляции
            correlation_matrix = {}
            for symbol1 in symbols:
                correlation_matrix[symbol1] = {}
                for symbol2 in symbols:
                    if symbol1 == symbol2:
                        correlation_matrix[symbol1][symbol2] = 1.0
                    elif symbol1 in aligned_returns and symbol2 in aligned_returns:
                        try:
                            corr = np.corrcoef(aligned_returns[symbol1], aligned_returns[symbol2])[0, 1]
                            correlation_matrix[symbol1][symbol2] = corr if not np.isnan(corr) else 0.0
                        except:
                            correlation_matrix[symbol1][symbol2] = 0.0
                    else:
                        correlation_matrix[symbol1][symbol2] = 0.0
            
            # Кэшируем результат
            self._set_cached_data(cache_key, 'correlations', correlation_matrix)
            return correlation_matrix
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка расчета корреляционной матрицы: {e}")
            return {}
    
    def get_market_direction(self, symbols: List[str] = None) -> Dict[str, int]:
        """
        Получает направление рынка по основным символам
        
        Args:
            symbols: Список символов (по умолчанию BTC, ETH, BNB)
            
        Returns:
            Dict {symbol: direction} где direction: 1 (LONG), -1 (SHORT), 0 (NEUTRAL)
        """
        if symbols is None:
            symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']
        
        result = {}
        for symbol in symbols:
            try:
                returns = self.get_returns(symbol, '1h', 20)
                if len(returns) >= 10:
                    # Простая логика направления
                    positive_count = sum(1 for r in returns[-10:] if r > 0)
                    negative_count = sum(1 for r in returns[-10:] if r < 0)
                    
                    if positive_count > negative_count + 2:
                        result[symbol] = 1  # LONG
                    elif negative_count > positive_count + 2:
                        result[symbol] = -1  # SHORT
                    else:
                        result[symbol] = 0  # NEUTRAL
                else:
                    result[symbol] = 0
            except Exception as e:
                self.logger.debug(f"Ошибка определения направления {symbol}: {e}")
                result[symbol] = 0
        
        return result 