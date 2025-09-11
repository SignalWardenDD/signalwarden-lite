#!/usr/bin/env python3
"""
Система мониторинга в реальном времени для предотвращения проблем
"""

import os
import sys
import time
import json
import yaml
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dotenv import load_dotenv
import ccxt
from typing import Dict, List, Any, Optional
import threading
import queue

# Добавляем путь к модулям
sys.path.append('signalwarden_lite')

from core.features import add_indicators
from core.regimes import add_regime, RegimeThresholds
from core.market import compute_market_bias
from core.signals import generate_signals, SignalParams
from core.state_validator import StateValidator

class RealTimeMonitor:
    """Монитор системы в реальном времени"""
    
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.running = False
        self.monitor_thread = None
        self.alert_queue = queue.Queue()
        self.monitoring_data = {}
        self.last_checks = {}
        
        # Загрузить конфигурацию
        with open(config_path, 'r') as f:
            self.cfg = yaml.safe_load(f)
            
        # Настроить подключение к бирже
        self.setup_exchange()
        
        # Валидатор состояния
        self.state_validator = StateValidator('trading_state_v1_6_TXB.json', self.exchange)
        
    def setup_exchange(self):
        """Настроить подключение к бирже"""
        try:
            load_dotenv()
            
            api_key = os.getenv('BINANCE_API_KEY')
            secret = os.getenv('BINANCE_SECRET')
            
            if not api_key or not secret:
                print("❌ Отсутствуют API ключи")
                return
                
            self.exchange = ccxt.binanceusdm({
                'apiKey': api_key,
                'secret': secret,
                'enableRateLimit': True,
                'timeout': 30000,
                'options': {'defaultType': 'future'}
            })
            
            self.exchange.load_markets()
            print("✅ Подключение к бирже установлено")
            
        except Exception as e:
            print(f"❌ Ошибка подключения к бирже: {e}")
            self.exchange = None
            
    def check_state_consistency(self) -> Dict[str, Any]:
        """Проверить консистентность состояния"""
        try:
            result = self.state_validator.run_full_validation(self.cfg['symbols'])
            
            if not result['overall_valid']:
                self.alert_queue.put({
                    'type': 'STATE_INCONSISTENCY',
                    'severity': 'HIGH',
                    'message': f"Найдено {result['total_errors']} проблем консистентности",
                    'details': result
                })
                
            return result
            
        except Exception as e:
            self.alert_queue.put({
                'type': 'STATE_CHECK_ERROR',
                'severity': 'CRITICAL',
                'message': f"Ошибка проверки состояния: {e}",
                'details': {'error': str(e)}
            })
            return {'overall_valid': False, 'total_errors': 1}
            
    def check_balance_health(self) -> Dict[str, Any]:
        """Проверить здоровье баланса"""
        try:
            if not self.exchange:
                return {'healthy': True, 'message': 'Нет подключения к бирже'}
                
            balance = self.exchange.fetch_balance()
            free_usdt = balance.get('USDT', {}).get('free', 0)
            used_usdt = balance.get('USDT', {}).get('used', 0)
            total_usdt = balance.get('USDT', {}).get('total', 0)
            
            # Рассчитать требуемый маржин
            margin_usdt = self.cfg['risk']['margin_usdt']
            leverage = self.cfg['risk']['leverage']
            actual_margin_per_position = margin_usdt / leverage
            required_margin = actual_margin_per_position * 1.05
            
            # Проверки
            if free_usdt < required_margin:
                self.alert_queue.put({
                    'type': 'INSUFFICIENT_BALANCE',
                    'severity': 'CRITICAL',
                    'message': f"Недостаточно средств: {free_usdt:.2f} < {required_margin:.2f} USDT",
                    'details': {
                        'free_usdt': free_usdt,
                        'required_margin': required_margin,
                        'can_open_positions': False
                    }
                })
                return {'healthy': False, 'can_open_positions': False}
                
            # Проверить использование маржи
            margin_usage = (used_usdt / total_usdt) * 100 if total_usdt > 0 else 0
            if margin_usage > 80:
                self.alert_queue.put({
                    'type': 'HIGH_MARGIN_USAGE',
                    'severity': 'HIGH',
                    'message': f"Высокое использование маржи: {margin_usage:.1f}%",
                    'details': {
                        'margin_usage': margin_usage,
                        'used_usdt': used_usdt,
                        'total_usdt': total_usdt
                    }
                })
                
            return {
                'healthy': True,
                'free_usdt': free_usdt,
                'used_usdt': used_usdt,
                'total_usdt': total_usdt,
                'margin_usage': margin_usage,
                'can_open_positions': True,
                'max_positions': int(free_usdt / required_margin)
            }
            
        except Exception as e:
            self.alert_queue.put({
                'type': 'BALANCE_CHECK_ERROR',
                'severity': 'CRITICAL',
                'message': f"Ошибка проверки баланса: {e}",
                'details': {'error': str(e)}
            })
            return {'healthy': False, 'error': str(e)}
            
    def check_positions_health(self) -> Dict[str, Any]:
        """Проверить здоровье позиций"""
        try:
            if not self.exchange:
                return {'healthy': True, 'message': 'Нет подключения к бирже'}
                
            # Получить позиции с биржи
            positions = self.exchange.fetch_positions()
            active_positions = [p for p in positions if float(p['contracts']) != 0]
            
            # Получить позиции из состояния
            with open('trading_state_v1_6_TXB.json', 'r') as f:
                state = json.load(f)
            state_positions = state.get('active_positions', {})
            
            # Анализ позиций
            total_pnl = 0
            large_losses = []
            large_profits = []
            
            for pos in active_positions:
                pnl = float(pos['unrealizedPnl'])
                total_pnl += pnl
                
                if pnl < -50:  # Большие убытки
                    large_losses.append({
                        'symbol': pos['symbol'],
                        'pnl': pnl,
                        'side': pos['side']
                    })
                elif pnl > 100:  # Большие прибыли
                    large_profits.append({
                        'symbol': pos['symbol'],
                        'pnl': pnl,
                        'side': pos['side']
                    })
                    
            # Проверки
            if total_pnl < -200:  # Общие убытки больше 200 USDT
                self.alert_queue.put({
                    'type': 'LARGE_TOTAL_LOSS',
                    'severity': 'HIGH',
                    'message': f"Большие общие убытки: {total_pnl:.2f} USDT",
                    'details': {
                        'total_pnl': total_pnl,
                        'active_positions': len(active_positions)
                    }
                })
                
            if large_losses:
                self.alert_queue.put({
                    'type': 'LARGE_INDIVIDUAL_LOSSES',
                    'severity': 'MEDIUM',
                    'message': f"Большие убытки по позициям: {len(large_losses)} позиций",
                    'details': {'large_losses': large_losses}
                })
                
            return {
                'healthy': total_pnl > -200,
                'total_pnl': total_pnl,
                'active_positions': len(active_positions),
                'state_positions': len(state_positions),
                'large_losses': large_losses,
                'large_profits': large_profits
            }
            
        except Exception as e:
            self.alert_queue.put({
                'type': 'POSITIONS_CHECK_ERROR',
                'severity': 'CRITICAL',
                'message': f"Ошибка проверки позиций: {e}",
                'details': {'error': str(e)}
            })
            return {'healthy': False, 'error': str(e)}
            
    def check_signal_generation(self) -> Dict[str, Any]:
        """Проверить генерацию сигналов"""
        try:
            # Получить BTC данные для market filter
            btc_data = self.fetch_binance_data('BTC/USDT:USDT', '1h', 200)
            if btc_data is None:
                return {'healthy': False, 'error': 'Не удалось получить BTC данные'}
                
            btc_data = add_indicators(btc_data, 
                self.cfg['market_filter']['ema_fast'], 
                self.cfg['market_filter']['ema_slow'])
            btc_market = compute_market_bias(btc_data, 
                self.cfg['market_filter']['ema_fast'], 
                self.cfg['market_filter']['ema_slow'])
                
            latest_btc = btc_market.iloc[-1]
            
            # Проверить market filter
            if pd.isna(latest_btc['mkt_long_ok']) or pd.isna(latest_btc['mkt_short_ok']):
                self.alert_queue.put({
                    'type': 'MARKET_FILTER_ERROR',
                    'severity': 'HIGH',
                    'message': "BTC Market Filter возвращает NaN значения",
                    'details': {'btc_data': latest_btc.to_dict()}
                })
                return {'healthy': False, 'error': 'Market filter NaN'}
                
            # Проверить логику market filter
            if not latest_btc['mkt_long_ok'] and not latest_btc['mkt_short_ok']:
                self.alert_queue.put({
                    'type': 'MARKET_FILTER_BLOCKED',
                    'severity': 'MEDIUM',
                    'message': "Market filter блокирует все позиции",
                    'details': {
                        'mkt_long_ok': latest_btc['mkt_long_ok'],
                        'mkt_short_ok': latest_btc['mkt_short_ok']
                    }
                })
                
            return {
                'healthy': True,
                'btc_market': {
                    'mkt_long_ok': latest_btc['mkt_long_ok'],
                    'mkt_short_ok': latest_btc['mkt_short_ok'],
                    'ema_fast': btc_data.iloc[-1]['ema_fast'],
                    'ema_slow': btc_data.iloc[-1]['ema_slow']
                }
            }
            
        except Exception as e:
            self.alert_queue.put({
                'type': 'SIGNAL_GENERATION_ERROR',
                'severity': 'HIGH',
                'message': f"Ошибка генерации сигналов: {e}",
                'details': {'error': str(e)}
            })
            return {'healthy': False, 'error': str(e)}
            
    def fetch_binance_data(self, symbol: str, timeframe: str, limit: int) -> Optional[pd.DataFrame]:
        """Получить данные с Binance"""
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df
        except Exception as e:
            print(f"❌ Ошибка получения данных {symbol}: {e}")
            return None
            
    def process_alerts(self):
        """Обработать алерты"""
        while not self.alert_queue.empty():
            try:
                alert = self.alert_queue.get_nowait()
                self.handle_alert(alert)
            except queue.Empty:
                break
                
    def handle_alert(self, alert: Dict[str, Any]):
        """Обработать алерт"""
        severity = alert['severity']
        message = alert['message']
        alert_type = alert['type']
        
        timestamp = datetime.utcnow().strftime('%H:%M:%S')
        
        if severity == 'CRITICAL':
            print(f"🚨 [{timestamp}] КРИТИЧЕСКИЙ: {message}")
        elif severity == 'HIGH':
            print(f"⚠️ [{timestamp}] ВЫСОКИЙ: {message}")
        elif severity == 'MEDIUM':
            print(f"🔶 [{timestamp}] СРЕДНИЙ: {message}")
        else:
            print(f"ℹ️ [{timestamp}] ИНФО: {message}")
            
        # Логировать детали
        if 'details' in alert:
            print(f"   Детали: {alert['details']}")
            
        # Сохранить алерт
        self.save_alert(alert)
        
    def save_alert(self, alert: Dict[str, Any]):
        """Сохранить алерт в файл"""
        try:
            alert_file = 'monitoring_alerts.json'
            alerts = []
            
            if os.path.exists(alert_file):
                with open(alert_file, 'r') as f:
                    alerts = json.load(f)
                    
            alert['timestamp'] = datetime.utcnow().isoformat()
            alerts.append(alert)
            
            # Оставить только последние 100 алертов
            if len(alerts) > 100:
                alerts = alerts[-100:]
                
            with open(alert_file, 'w') as f:
                json.dump(alerts, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            print(f"❌ Ошибка сохранения алерта: {e}")
            
    def monitoring_loop(self):
        """Основной цикл мониторинга"""
        print("🔄 Запуск мониторинга в реальном времени...")
        
        while self.running:
            try:
                current_time = datetime.utcnow()
                print(f"\n📊 [{current_time.strftime('%H:%M:%S')}] Проверка системы...")
                
                # Проверка консистентности состояния (каждые 2 минуты)
                if (not self.last_checks.get('state') or 
                    (current_time - self.last_checks['state']).seconds >= 120):
                    print("   🔍 Проверка консистентности состояния...")
                    self.check_state_consistency()
                    self.last_checks['state'] = current_time
                    
                # Проверка баланса (каждую минуту)
                if (not self.last_checks.get('balance') or 
                    (current_time - self.last_checks['balance']).seconds >= 60):
                    print("   💰 Проверка баланса...")
                    self.check_balance_health()
                    self.last_checks['balance'] = current_time
                    
                # Проверка позиций (каждые 30 секунд)
                if (not self.last_checks.get('positions') or 
                    (current_time - self.last_checks['positions']).seconds >= 30):
                    print("   📈 Проверка позиций...")
                    self.check_positions_health()
                    self.last_checks['positions'] = current_time
                    
                # Проверка генерации сигналов (каждые 5 минут)
                if (not self.last_checks.get('signals') or 
                    (current_time - self.last_checks['signals']).seconds >= 300):
                    print("   🎯 Проверка генерации сигналов...")
                    self.check_signal_generation()
                    self.last_checks['signals'] = current_time
                    
                # Обработать алерты
                self.process_alerts()
                
                # Пауза перед следующей проверкой
                time.sleep(10)
                
            except KeyboardInterrupt:
                print("\n⏹️ Остановка мониторинга...")
                break
            except Exception as e:
                print(f"❌ Ошибка в цикле мониторинга: {e}")
                time.sleep(30)  # Пауза при ошибке
                
        print("✅ Мониторинг остановлен")
        
    def start_monitoring(self):
        """Запустить мониторинг"""
        if self.running:
            print("⚠️ Мониторинг уже запущен")
            return
            
        self.running = True
        self.monitor_thread = threading.Thread(target=self.monitoring_loop)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        
        print("🚀 Мониторинг запущен в фоновом режиме")
        
    def stop_monitoring(self):
        """Остановить мониторинг"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        print("⏹️ Мониторинг остановлен")
        
    def get_monitoring_status(self) -> Dict[str, Any]:
        """Получить статус мониторинга"""
        return {
            'running': self.running,
            'last_checks': {k: v.isoformat() if v else None for k, v in self.last_checks.items()},
            'monitoring_data': self.monitoring_data
        }

def main():
    """Главная функция"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Real-time System Monitor')
    parser.add_argument('--config', default='signalwarden_lite/config/config_production.yaml',
                       help='Config file path')
    parser.add_argument('--duration', type=int, default=0,
                       help='Monitoring duration in minutes (0 = infinite)')
    
    args = parser.parse_args()
    
    monitor = RealTimeMonitor(args.config)
    
    try:
        monitor.start_monitoring()
        
        if args.duration > 0:
            print(f"⏰ Мониторинг будет работать {args.duration} минут...")
            time.sleep(args.duration * 60)
            monitor.stop_monitoring()
        else:
            print("⏰ Мониторинг работает бесконечно. Нажмите Ctrl+C для остановки...")
            while True:
                time.sleep(1)
                
    except KeyboardInterrupt:
        print("\n⏹️ Остановка по запросу пользователя...")
        monitor.stop_monitoring()

if __name__ == "__main__":
    main()
