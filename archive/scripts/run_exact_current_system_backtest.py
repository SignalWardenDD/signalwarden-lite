#!/usr/bin/env python3
"""
Точный бектест текущей системы с гибридным trailing + PnL-уровни
Использует реальные данные из data/historical_candles/
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pickle
from typing import Dict, List, Optional, Tuple
import yaml

# Добавляем путь к модулям
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from signalwarden_lite.core.features import add_indicators
from signalwarden_lite.core.regimes import add_regime, RegimeThresholds
from signalwarden_lite.core.market import compute_market_bias
from signalwarden_lite.core.signals import generate_signals, SignalParams
from signalwarden_lite.core.trailing import TrailingConfig, update_trailing_hybrid
from signalwarden_lite.core.types import Position, Side

def load_local_data(symbol: str, timeframe: str) -> pd.DataFrame:
    """Загрузка данных из pickle файлов"""
    try:
        # Пробуем разные варианты имен файлов
        possible_names = [
            f"{symbol}_{timeframe}.pkl",
            f"{symbol}:USDT_{timeframe}.pkl"
        ]
        
        for filename in possible_names:
            filepath = f"data/historical_candles/{filename}"
            if os.path.exists(filepath):
                with open(filepath, 'rb') as f:
                    df = pickle.load(f)
                
                # Убеждаемся, что timestamp в правильном формате
                if 'timestamp' in df.columns:
                    if df['timestamp'].dtype == 'int64':
                        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
                    df.set_index('timestamp', inplace=True)
                
                print(f"✅ Загружены данные {symbol} {timeframe}: {len(df)} свечей")
                print(f"   Период: {df.index[0]} - {df.index[-1]}")
                return df
        
        print(f"❌ Не найден файл для {symbol} {timeframe}")
        return pd.DataFrame()
        
    except Exception as e:
        print(f"❌ Ошибка загрузки {symbol} {timeframe}: {e}")
        return pd.DataFrame()

def load_config() -> dict:
    """Загрузка конфигурации"""
    with open('signalwarden_lite/config/config_production.yaml', 'r') as f:
        return yaml.safe_load(f)

class ExactBacktest:
    """Точный бектест текущей системы"""
    
    def __init__(self, config: dict):
        self.cfg = config
        self.symbols = self.cfg['symbols']
        self.margin_usdt = self.cfg['risk']['margin_usdt']  # 21 USDT
        self.leverage = self.cfg['risk']['leverage']  # 5x
        self.sl_atr_mult = self.cfg['risk']['sl_atr_mult']  # 1.5
        
        # Trailing config
        self.trailing = TrailingConfig(**self.cfg['trailing'])
        
        # Signal params
        self.signal_params = SignalParams(
            setup_breakout=self.cfg['signals']['setups']['breakout']['enabled'],
            setup_inside=self.cfg['signals']['setups']['inside_bar']['enabled'],
            setup_trend_cont=self.cfg['signals']['setups']['trend_continuation']['enabled'],
            setup_squeeze=self.cfg['signals']['setups']['squeeze_breakout']['enabled'],
            ib_min_prev_range_k_atr=self.cfg['signals']['setups']['inside_bar']['min_prev_range_k_atr'],
            tc_min_body_k_range=self.cfg['signals']['setups']['trend_continuation']['min_body_k_range'],
            tc_confirm_close_k_body=self.cfg['signals']['setups']['trend_continuation']['confirm_close_k_body'],
            bb_period=self.cfg['signals']['setups']['squeeze_breakout']['bb_period'],
            bb_k=self.cfg['signals']['setups']['squeeze_breakout']['bb_k'],
            width_k_perc=self.cfg['signals']['setups']['squeeze_breakout']['width_k_perc']
        )
        
        # Regime thresholds
        self.regime_thresholds = RegimeThresholds(**self.cfg['regime']['calm_thresholds'])
        
        # Результаты
        self.trades = []
        self.positions = {}
        self.balance = 1000.0  # Начальный баланс
        
        print(f"🚀 Инициализирован точный бектест:")
        print(f"   Символы: {self.symbols}")
        print(f"   Размер позиции: {self.margin_usdt} USDT")
        print(f"   Плечо: {self.leverage}x")
        print(f"   SL multiplier: {self.sl_atr_mult}")
        print(f"   Trailing: {self.trailing}")
    
    def load_all_data(self) -> Dict[str, Dict[str, pd.DataFrame]]:
        """Загрузка всех данных"""
        data = {}
        
        for symbol in self.symbols:
            data[symbol] = {}
            
            # Загружаем 1h данные
            df_1h = load_local_data(symbol, '1h')
            if not df_1h.empty:
                data[symbol]['1h'] = df_1h
            
            # Загружаем 15m данные
            df_15m = load_local_data(symbol, '15m')
            if not df_15m.empty:
                data[symbol]['15m'] = df_15m
        
        return data
    
    def prepare_data(self, df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """Подготовка данных с индикаторами"""
        if df.empty:
            return df
        
        # Добавляем индикаторы
        df = add_indicators(df, 
                          atr_p=14,
                          ema_fast=20, 
                          ema_slow=50,
                          rsi_p=14)
        
        # Добавляем regime
        df = add_regime(df, self.regime_thresholds)
        
        return df
    
    def generate_signals_mtf(self, symbol: str, data: Dict[str, pd.DataFrame], timestamp: datetime) -> List[dict]:
        """Генерация MTF сигналов (как в live системе)"""
        signals = []
        
        # Получаем данные для символа
        if symbol not in data:
            return signals
        
        symbol_data = data[symbol]
        
        # Проверяем наличие данных
        if '1h' not in symbol_data or '15m' not in symbol_data:
            return signals
        
        df_1h = symbol_data['1h']
        df_15m = symbol_data['15m']
        
        # Фильтруем данные до текущего времени
        df_1h_filtered = df_1h[df_1h.index <= timestamp]
        df_15m_filtered = df_15m[df_15m.index <= timestamp]
        
        if len(df_1h_filtered) < 50 or len(df_15m_filtered) < 50:
            return signals
        
        # Генерируем сигналы на 1h (breakout)
        signals_df_1h = generate_signals(df_1h_filtered, self.signal_params, None)
        
        # Генерируем сигналы на 15m (inside_bar, trend_continuation, squeeze_breakout)
        signals_df_15m = generate_signals(df_15m_filtered, self.signal_params, None)
        
        # Извлекаем сигналы из DataFrame
        current_signals = []
        
        # Проверяем сигналы на 1h
        if timestamp in signals_df_1h.index:
            row_1h = signals_df_1h.loc[timestamp]
            if pd.notna(row_1h['long_entry_final']):
                current_signals.append({
                    'symbol': symbol,
                    'side': 'LONG',
                    'entry_price': row_1h['long_entry_final'],
                    'reason': row_1h['long_reason'],
                    'timestamp': timestamp,
                    'atr': row_1h['atr']
                })
            if pd.notna(row_1h['short_entry_final']):
                current_signals.append({
                    'symbol': symbol,
                    'side': 'SHORT',
                    'entry_price': row_1h['short_entry_final'],
                    'reason': row_1h['short_reason'],
                    'timestamp': timestamp,
                    'atr': row_1h['atr']
                })
        
        # Проверяем сигналы на 15m
        if timestamp in signals_df_15m.index:
            row_15m = signals_df_15m.loc[timestamp]
            if pd.notna(row_15m['long_entry_final']):
                current_signals.append({
                    'symbol': symbol,
                    'side': 'LONG',
                    'entry_price': row_15m['long_entry_final'],
                    'reason': row_15m['long_reason'],
                    'timestamp': timestamp,
                    'atr': row_15m['atr']
                })
            if pd.notna(row_15m['short_entry_final']):
                current_signals.append({
                    'symbol': symbol,
                    'side': 'SHORT',
                    'entry_price': row_15m['short_entry_final'],
                    'reason': row_15m['short_reason'],
                    'timestamp': timestamp,
                    'atr': row_15m['atr']
                })
        
        return current_signals
    
    def calculate_position_size(self, entry_price: float) -> float:
        """Расчет размера позиции"""
        position_value_usdt = self.margin_usdt * self.leverage  # 21 * 5 = 105 USDT
        qty = position_value_usdt / entry_price
        return qty
    
    def calculate_sl(self, entry_price: float, side: str, atr: float) -> float:
        """Расчет стоп-лосса"""
        # Минимальная защита от микроубытков
        min_atr = entry_price * 0.008  # 0.8% от цены
        effective_atr = max(atr, min_atr)
        
        if side == 'LONG':
            sl_price = entry_price - (self.sl_atr_mult * effective_atr)
        else:  # SHORT
            sl_price = entry_price + (self.sl_atr_mult * effective_atr)
        
        return sl_price
    
    def update_trailing(self, symbol: str, current_price: float, atr: float) -> bool:
        """Обновление trailing stop"""
        if symbol not in self.positions:
            return False
        
        pos = self.positions[symbol]
        
        # Создаем Position объект
        position = Position(
            side=Side.LONG if pos['side'] == 'LONG' else Side.SHORT,
            entry=pos['entry'],
            qty=pos['qty'],
            remaining_qty=pos['qty'],
            sl=pos['sl_current'],
            r_per_unit=abs(pos['entry'] - pos['sl_initial']),
            atr=atr,
            peak_R=pos.get('peak_R', 0.0),
            peak_pnl_usdt=pos.get('peak_pnl_usdt', 0.0),
            sl_initial=pos['sl_initial'],
            be_applied=pos.get('be_applied', False)
        )
        
        # Обновляем trailing
        updated_pos = update_trailing_hybrid(
            position,
            current_price,  # hi
            current_price,  # lo
            atr,
            self.trailing
        )
        
        # Проверяем, изменился ли SL
        old_sl = pos['sl_current']
        new_sl = updated_pos.sl
        
        if pos['side'] == 'LONG':
            if new_sl > old_sl:
                pos['sl_current'] = new_sl
                pos['peak_R'] = updated_pos.peak_R
                pos['peak_pnl_usdt'] = updated_pos.peak_pnl_usdt
                pos['be_applied'] = updated_pos.be_applied
                return True
        else:  # SHORT
            if new_sl < old_sl:
                pos['sl_current'] = new_sl
                pos['peak_R'] = updated_pos.peak_R
                pos['peak_pnl_usdt'] = updated_pos.peak_pnl_usdt
                pos['be_applied'] = updated_pos.be_applied
                return True
        
        return False
    
    def check_exit_conditions(self, symbol: str, current_price: float) -> bool:
        """Проверка условий выхода"""
        if symbol not in self.positions:
            return False
        
        pos = self.positions[symbol]
        
        if pos['side'] == 'LONG':
            return current_price <= pos['sl_current']
        else:  # SHORT
            return current_price >= pos['sl_current']
    
    def close_position(self, symbol: str, exit_price: float, exit_time: datetime, reason: str):
        """Закрытие позиции"""
        if symbol not in self.positions:
            return
        
        pos = self.positions[symbol]
        
        # Расчет PnL
        if pos['side'] == 'LONG':
            pnl_usdt = (exit_price - pos['entry']) * pos['qty']
        else:  # SHORT
            pnl_usdt = (pos['entry'] - exit_price) * pos['qty']
        
        # Комиссии (maker 0.02% + taker 0.05% = 0.07%)
        fees = (pos['entry'] + exit_price) * pos['qty'] * 0.0007
        net_pnl = pnl_usdt - fees
        
        # Обновляем баланс
        self.balance += net_pnl
        
        # Сохраняем сделку
        trade = {
            'symbol': symbol,
            'side': pos['side'],
            'entry_time': pos['entry_time'],
            'exit_time': exit_time,
            'entry_price': pos['entry'],
            'exit_price': exit_price,
            'qty': pos['qty'],
            'pnl_usdt': pnl_usdt,
            'fees': fees,
            'net_pnl': net_pnl,
            'exit_reason': reason,
            'peak_R': pos.get('peak_R', 0.0),
            'peak_pnl_usdt': pos.get('peak_pnl_usdt', 0.0)
        }
        
        self.trades.append(trade)
        
        # Удаляем позицию
        del self.positions[symbol]
        
        print(f"🔚 {symbol} {pos['side']} закрыта: {exit_price:.6f}, PnL: ${net_pnl:.4f} ({reason})")
    
    def open_position(self, signal: dict, current_price: float, atr: float, timestamp: datetime):
        """Открытие позиции"""
        symbol = signal['symbol']
        side = signal['side']
        
        # Проверяем, нет ли уже открытой позиции
        if symbol in self.positions:
            return
        
        # Расчет параметров позиции
        qty = self.calculate_position_size(current_price)
        sl_price = self.calculate_sl(current_price, side, atr)
        
        # Создаем позицию
        self.positions[symbol] = {
            'side': side,
            'entry': current_price,
            'qty': qty,
            'sl_initial': sl_price,
            'sl_current': sl_price,
            'entry_time': timestamp,
            'peak_R': 0.0,
            'peak_pnl_usdt': 0.0,
            'be_applied': False
        }
        
        print(f"🟢 {symbol} {side} открыта: {current_price:.6f}, SL: {sl_price:.6f}, Qty: {qty:.4f}")
    
    def run_backtest(self, start_date: str = "2022-01-01", end_date: str = "2024-01-01"):
        """Запуск бектеста"""
        print(f"🚀 Запуск точного бектеста: {start_date} - {end_date}")
        
        # Загружаем данные
        data = self.load_all_data()
        
        # Подготавливаем данные
        for symbol in data:
            for timeframe in data[symbol]:
                data[symbol][timeframe] = self.prepare_data(data[symbol][timeframe], symbol)
        
        # Получаем все уникальные временные метки
        all_timestamps = set()
        for symbol in data:
            for timeframe in data[symbol]:
                df = data[symbol][timeframe]
                if not df.empty:
                    # Фильтруем по датам
                    mask = (df.index >= start_date) & (df.index <= end_date)
                    timestamps = df[mask].index
                    all_timestamps.update(timestamps)
        
        # Сортируем временные метки
        timestamps = sorted(list(all_timestamps))
        
        print(f"📊 Обработка {len(timestamps)} временных меток")
        
        # Основной цикл бектеста
        for i, timestamp in enumerate(timestamps):
            if i % 1000 == 0:
                print(f"⏳ Обработано {i}/{len(timestamps)} ({i/len(timestamps)*100:.1f}%)")
            
            # Обновляем trailing для всех открытых позиций
            for symbol in list(self.positions.keys()):
                if symbol in data and '1h' in data[symbol]:
                    df_1h = data[symbol]['1h']
                    if not df_1h.empty and timestamp in df_1h.index:
                        current_price = df_1h.loc[timestamp, 'close']
                        atr = df_1h.loc[timestamp, 'atr']
                        
                        # Обновляем trailing
                        self.update_trailing(symbol, current_price, atr)
                        
                        # Проверяем условия выхода
                        if self.check_exit_conditions(symbol, current_price):
                            self.close_position(symbol, current_price, timestamp, "SL")
            
            # Генерируем новые сигналы
            for symbol in self.symbols:
                if symbol in data:
                    signals = self.generate_signals_mtf(symbol, data, timestamp)
                    
                    for signal in signals:
                        # Получаем текущую цену и ATR
                        if '1h' in data[symbol]:
                            df_1h = data[symbol]['1h']
                            if not df_1h.empty and timestamp in df_1h.index:
                                current_price = df_1h.loc[timestamp, 'close']
                                atr = df_1h.loc[timestamp, 'atr']
                                
                                # Открываем позицию
                                self.open_position(signal, current_price, atr, timestamp)
        
        # Закрываем все оставшиеся позиции
        for symbol in list(self.positions.keys()):
            if symbol in data and '1h' in data[symbol]:
                df_1h = data[symbol]['1h']
                if not df_1h.empty:
                    last_price = df_1h.iloc[-1]['close']
                    last_time = df_1h.index[-1]
                    self.close_position(symbol, last_price, last_time, "END")
        
        print(f"✅ Бектест завершен!")
        self.print_results()
    
    def print_results(self):
        """Вывод результатов"""
        if not self.trades:
            print("❌ Нет сделок")
            return
        
        trades_df = pd.DataFrame(self.trades)
        
        total_trades = len(trades_df)
        winning_trades = len(trades_df[trades_df['net_pnl'] > 0])
        losing_trades = len(trades_df[trades_df['net_pnl'] < 0])
        win_rate = winning_trades / total_trades * 100
        
        total_pnl = trades_df['net_pnl'].sum()
        avg_win = trades_df[trades_df['net_pnl'] > 0]['net_pnl'].mean() if winning_trades > 0 else 0
        avg_loss = trades_df[trades_df['net_pnl'] < 0]['net_pnl'].mean() if losing_trades > 0 else 0
        
        profit_factor = abs(avg_win * winning_trades / (avg_loss * losing_trades)) if losing_trades > 0 else float('inf')
        
        print(f"\n📊 РЕЗУЛЬТАТЫ БЕКТЕСТА:")
        print(f"   Всего сделок: {total_trades}")
        print(f"   Прибыльных: {winning_trades} ({win_rate:.1f}%)")
        print(f"   Убыточных: {losing_trades}")
        print(f"   Общий PnL: ${total_pnl:.2f}")
        print(f"   Средняя прибыль: ${avg_win:.4f}")
        print(f"   Средний убыток: ${avg_loss:.4f}")
        print(f"   Profit Factor: {profit_factor:.2f}")
        print(f"   Финальный баланс: ${self.balance:.2f}")
        
        # Статистика по символам
        print(f"\n📈 СТАТИСТИКА ПО СИМВОЛАМ:")
        symbol_stats = trades_df.groupby('symbol').agg({
            'net_pnl': ['count', 'sum', 'mean'],
            'pnl_usdt': 'sum'
        }).round(4)
        
        for symbol in symbol_stats.index:
            count = symbol_stats.loc[symbol, ('net_pnl', 'count')]
            total_pnl = symbol_stats.loc[symbol, ('net_pnl', 'sum')]
            avg_pnl = symbol_stats.loc[symbol, ('net_pnl', 'mean')]
            print(f"   {symbol}: {count} сделок, PnL: ${total_pnl:.2f}, Средний: ${avg_pnl:.4f}")

def main():
    """Основная функция"""
    print("🚀 ТОЧНЫЙ БЕКТЕСТ ТЕКУЩЕЙ СИСТЕМЫ")
    print("=" * 60)
    
    # Загружаем конфигурацию
    config = load_config()
    
    # Создаем бектест
    backtest = ExactBacktest(config)
    
    # Запускаем бектест
    backtest.run_backtest()

if __name__ == "__main__":
    main()
