import ccxt
import pandas as pd
from loguru import logger
from data.realtime_gateway import RealtimeGateway
from utils.market_meta import MarketMeta

class BinanceLive:
    def __init__(self, api_key: str, api_secret: str, testnet: bool=False):
        self.ex = ccxt.binanceusdm({
            "apiKey": api_key,
            "secret": api_secret,
            "enableRateLimit": True,
            "options": {"defaultType": "future"},
        })
        self.ex.set_sandbox_mode(False if not testnet else True)
        
        # Инициализация RealtimeGateway и MarketMeta
        self.rt = RealtimeGateway(self.ex)
        self.meta = MarketMeta(self.ex)

    def load_markets(self):
        return self.ex.load_markets()

    def market(self, symbol: str):
        return self.ex.market(symbol)

    def fetch_ohlcv_df(self, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
        raw = self.ex.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        df = pd.DataFrame(raw, columns=["ts","open","high","low","close","volume"])
        df["ts"] = pd.to_datetime(df["ts"], unit="ms")
        df.set_index("ts", inplace=True)
        return df

    def fetch_positions(self):
        """ИСПРАВЛЕНО: Получение позиций с улучшенной обработкой ошибок"""
        try:
            positions = self.ex.fetch_positions()
            
            # ИСПРАВЛЕНО: Фильтруем и валидируем позиции
            valid_positions = []
            for pos in positions:
                try:
                    # Проверяем обязательные поля
                    if 'symbol' not in pos:
                        continue
                    
                    # ИСПРАВЛЕНО: Нормализуем contracts
                    contracts = pos.get('contracts', pos.get('positionAmt', 0))
                    if contracts is None:
                        contracts = 0
                    
                    # Конвертируем в float
                    try:
                        contracts = float(contracts)
                    except (ValueError, TypeError):
                        contracts = 0.0
                    
                    # ИСПРАВЛЕНО: Обновляем позицию с нормализованными данными
                    pos['contracts'] = contracts
                    pos['positionAmt'] = contracts
                    
                    # ИСПРАВЛЕНО: Нормализуем другие поля
                    for field in ['entryPrice', 'markPrice', 'unrealizedPnl', 'realizedPnl']:
                        if field in pos:
                            try:
                                pos[field] = float(pos[field]) if pos[field] is not None else 0.0
                            except (ValueError, TypeError):
                                pos[field] = 0.0
                    
                    valid_positions.append(pos)
                    
                except Exception as e:
                    print(f"⚠️ Ошибка обработки позиции {pos.get('symbol', 'UNKNOWN')}: {e}")
                    continue
            
            return valid_positions
            
        except Exception as e:
            print(f"❌ Критическая ошибка получения позиций: {e}")
            return []

    def fetch_open_orders(self, symbol: str):
        return self.ex.fetch_open_orders(symbol)

    def cancel_order(self, symbol: str, order_id: str):
        return self.ex.cancel_order(order_id, symbol)

    def cancel_all_orders(self, symbol: str):
        try:
            return self.ex.cancel_all_orders(symbol)
        except Exception:
            for o in self.fetch_open_orders(symbol):
                self.cancel_order(symbol, o["id"])

    def create_order(self, symbol: str, type_: str, side: str, amount: float, price=None, params=None):
        return self.ex.create_order(symbol, type_, side, amount, price, params or {})

    def create_market_buy_order(self, symbol: str, amount: float, params=None):
        """Создает рыночный ордер на покупку"""
        return self.ex.create_market_buy_order(symbol, amount, params or {})

    def create_market_sell_order(self, symbol: str, amount: float, params=None):
        """Создает рыночный ордер на продажу"""
        return self.ex.create_market_sell_order(symbol, amount, params or {})

    def fetch_ticker(self, symbol: str):
        return self.ex.fetch_ticker(symbol)

    def get_data(self, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
        """Получает OHLCV данные с улучшенной обработкой ошибок"""
        try:
            logger.info(f"🔍 Запрос данных для {symbol}: {timeframe}, лимит: {limit}")
            
            # Нормализуем символ для Binance
            normalized_symbol = symbol.replace('/', '').replace(':USDT', 'USDT')
            
            # Получаем данные
            raw_data = self.ex.fetch_ohlcv(normalized_symbol, timeframe=timeframe, limit=limit)
            
            if not raw_data:
                logger.warning(f"⚠️ Нет данных для {symbol}")
                return pd.DataFrame()
            
            # Создаем DataFrame
            df = pd.DataFrame(raw_data, columns=["ts", "open", "high", "low", "close", "volume"])
            df["ts"] = pd.to_datetime(df["ts"], unit="ms")
            df.set_index("ts", inplace=True)
            
            # Проверяем качество данных
            if df.empty:
                logger.warning(f"⚠️ Пустой DataFrame для {symbol}")
                return df
            
            # Проверяем на NaN
            nan_count = df.isna().sum().sum()
            if nan_count > 0:
                logger.warning(f"⚠️ {symbol}: найдено {nan_count} NaN значений")
                df = df.fillna(method='ffill').fillna(method='bfill')
            
            logger.info(f"📊 Результат для {symbol}: {len(df)} свечей")
            return df
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения данных {symbol}: {e}")
            # Возвращаем пустой DataFrame с правильной структурой
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    
    def fetch_tickers(self, symbols=None):
        """Получение тикеров для всех символов или указанных символов"""
        try:
            if symbols:
                tickers = {}
                for symbol in symbols:
                    try:
                        ticker = self.ex.fetch_ticker(symbol)
                        tickers[symbol] = ticker
                    except Exception as e:
                        print(f"⚠️ Ошибка получения тикера для {symbol}: {e}")
                        continue
                return tickers
            else:
                return self.ex.fetch_tickers()
        except Exception as e:
            print(f"❌ Ошибка получения тикеров: {e}")
            return {}

    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int):
        """ИСПРАВЛЕНО: Получение OHLCV данных с улучшенной обработкой ошибок"""
        try:
            # ИСПРАВЛЕНО: Проверяем валидность символа
            if not symbol or ':' not in symbol:
                raise ValueError(f"Невалидный символ: {symbol}")
            
            # ИСПРАВЛЕНО: Получаем данные с повторными попытками
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    ohlcv_data = self.ex.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
                    
                    # ИСПРАВЛЕНО: Проверяем качество данных
                    if not ohlcv_data or len(ohlcv_data) == 0:
                        raise ValueError(f"Пустые данные для {symbol}")
                    
                    # ИСПРАВЛЕНО: Проверяем структуру данных
                    for candle in ohlcv_data:
                        if len(candle) < 6:
                            raise ValueError(f"Неполная свеча для {symbol}: {candle}")
                        if any(not isinstance(val, (int, float)) or val <= 0 for val in candle[1:5]):
                            raise ValueError(f"Невалидные цены для {symbol}: {candle}")
                    
                    return ohlcv_data
                    
                except Exception as e:
                    if attempt < max_retries - 1:
                        print(f"⚠️ Попытка {attempt + 1} получения данных для {symbol} не удалась: {e}")
                        import time
                        time.sleep(1)  # Пауза перед повторной попыткой
                    else:
                        raise e
            
        except Exception as e:
            print(f"❌ Критическая ошибка получения данных для {symbol}: {e}")
            # ИСПРАВЛЕНО: Возвращаем пустой список вместо None
            return []

    def get_tick_size(self, symbol: str) -> float:
        """Получает размер тика для символа"""
        return self.meta.tick_size(symbol)
    
    def fetch_balance(self):
        return self.ex.fetch_balance()

    def get_symbol_info(self, symbol: str):
        """Получает информацию о символе"""
        try:
            # Загружаем markets если не загружены
            if not self.ex.markets:
                self.ex.load_markets()
            
            return self.ex.market(symbol)
        except Exception as e:
            print(f"⚠️ Ошибка получения информации о символе {symbol}: {e}")
            return None

    def get_exchange_info(self, symbol: str):
        """Получает информацию о бирже для символа (совместимость с emergency-системой)"""
        try:
            market = self.get_symbol_info(symbol)
            if not market:
                return {}
            
            # Извлекаем информацию о тиках и лимитах
            precision = market.get("precision", {})
            limits = market.get("limits", {})
            
            return {
                "tickSize": limits.get("price", {}).get("min", 0.000001),
                "pricePrecision": precision.get("price", 6),
                "amountPrecision": precision.get("amount", 3),
                "minAmount": limits.get("amount", {}).get("min", 0),
                "maxAmount": limits.get("amount", {}).get("max", float('inf')),
                "minCost": limits.get("cost", {}).get("min", 0),
                "maxCost": limits.get("cost", {}).get("max", float('inf'))
            }
        except Exception as e:
            print(f"⚠️ Ошибка получения информации о бирже для {symbol}: {e}")
            return {
                "tickSize": 0.000001,
                "pricePrecision": 6,
                "amountPrecision": 3,
                "minAmount": 0,
                "maxAmount": float('inf'),
                "minCost": 0,
                "maxCost": float('inf')
            }

    def price_to_step(self, symbol: str, price: float) -> float:
        m = self.market(symbol)
        p = m.get("precision",{}).get("price", 2)
        step = m.get("limits",{}).get("price",{}).get("min", None)
        if p is not None and isinstance(p, int):
            price = float(f"{price:.{p}f}")
        if step:
            price = round(price / step) * step
        return price

    def amount_to_step(self, symbol: str, amount: float) -> float:
        m = self.market(symbol)
        p = m.get("precision",{}).get("amount", 3)
        step = m.get("limits",{}).get("amount",{}).get("min", None)
        if p is not None and isinstance(p, int):
            amount = float(f"{amount:.{p}f}")
        if step:
            amount = max(step, round(amount / step) * step)
        return amount

    def close_position(self, symbol: str):
        """Закрывает позицию по символу рыночным ордером"""
        positions = self.fetch_positions()
        
        for pos in positions:
            contracts = float(pos.get("contracts") or pos.get("positionAmt") or 0)
            if abs(contracts) > 0 and pos["symbol"] == symbol:
                direction = "LONG" if contracts > 0 else "SHORT"
                
                # Отменяем все ордера для символа
                try:
                    self.cancel_all_orders(symbol)
                except Exception:
                    pass  # Игнорируем ошибки отмены
                
                # ИСПРАВЛЕНО: Закрываем позицию с обработкой ReduceOnly ошибки
                close_side = "sell" if direction == "LONG" else "buy"
                
                try:
                    # Сначала пробуем с reduceOnly
                    close_order = self.create_order(symbol, "MARKET", close_side, abs(contracts), None, {"reduceOnly": True})
                    print(f"✅ {symbol}: Позиция закрыта (reduceOnly)")
                    return close_order
                except Exception as e:
                    print(f"⚠️ {symbol}: ReduceOnly не сработал, пробую без него: {e}")
                    try:
                        # Пробуем без reduceOnly
                        close_order = self.create_order(symbol, "MARKET", close_side, abs(contracts), None)
                        print(f"✅ {symbol}: Позиция закрыта (обычный ордер)")
                        return close_order
                    except Exception as e2:
                        print(f"❌ {symbol}: Не удалось закрыть позицию: {e2}")
                        return None
        
        return None  # Позиция не найдена
