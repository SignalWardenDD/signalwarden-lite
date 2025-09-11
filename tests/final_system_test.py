#!/usr/bin/env python3
"""
Финальный тест системы - проверка всех исправлений и предотвращение проблем
"""

import os
import sys
import time
import yaml
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dotenv import load_dotenv
import ccxt
from typing import Dict, List, Any, Optional

# Добавляем путь к модулям
sys.path.append('.')

from signalwarden_lite.core.features import add_indicators
from signalwarden_lite.core.regimes import add_regime, RegimeThresholds
from signalwarden_lite.core.market import compute_market_bias
from signalwarden_lite.core.signals import generate_signals, SignalParams
from signalwarden_lite.core.state_validator import StateValidator
from signalwarden_lite.core.auto_fixer import AutoFixer

class FinalSystemTest:
    """Финальный тест системы"""
    
    def __init__(self):
        self.test_results = {}
        self.passed_tests = 0
        self.failed_tests = 0
        
    def log_test(self, test_name: str, passed: bool, message: str = ""):
        """Логировать результат теста"""
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} {test_name}: {message}")
        
        if passed:
            self.passed_tests += 1
        else:
            self.failed_tests += 1
            
        self.test_results[test_name] = {
            'passed': passed,
            'message': message,
            'timestamp': datetime.utcnow().isoformat()
        }
        
    def test_configuration_loading(self) -> bool:
        """Тест загрузки конфигурации"""
        try:
            with open('signalwarden_lite/config/config_production.yaml', 'r') as f:
                cfg = yaml.safe_load(f)
                
            required_sections = ['signals', 'risk', 'exchange', 'symbols']
            for section in required_sections:
                if section not in cfg:
                    self.log_test("Configuration Loading", False, f"Missing section: {section}")
                    return False
                    
            self.log_test("Configuration Loading", True, f"Loaded {len(cfg)} sections")
            return True
            
        except Exception as e:
            self.log_test("Configuration Loading", False, f"Error: {e}")
            return False
            
    def test_exchange_connection(self) -> bool:
        """Тест подключения к бирже"""
        try:
            load_dotenv()
            
            api_key = os.getenv('BINANCE_API_KEY')
            secret = os.getenv('BINANCE_SECRET')
            
            if not api_key or not secret:
                self.log_test("Exchange Connection", False, "Missing API keys")
                return False
                
            exchange = ccxt.binanceusdm({
                'apiKey': api_key,
                'secret': secret,
                'enableRateLimit': True,
                'timeout': 30000,
                'options': {'defaultType': 'future'}
            })
            
            exchange.load_markets()
            balance = exchange.fetch_balance()
            usdt_balance = balance.get('USDT', {}).get('total', 0)
            
            self.log_test("Exchange Connection", True, f"Balance: {usdt_balance:.2f} USDT")
            return True
            
        except Exception as e:
            self.log_test("Exchange Connection", False, f"Error: {e}")
            return False
            
    def test_state_file_integrity(self) -> bool:
        """Тест целостности файла состояния"""
        try:
            state_file = 'trading_state_v1_6_TXB.json'
            
            if not os.path.exists(state_file):
                self.log_test("State File Integrity", False, "File not found")
                return False
                
            with open(state_file, 'r') as f:
                state = json.load(f)
                
            # Проверка структуры
            required_keys = ['metadata', 'symbols', 'active_positions']
            for key in required_keys:
                if key not in state:
                    self.log_test("State File Integrity", False, f"Missing key: {key}")
                    return False
                    
            # Проверка консистентности
            symbols_data = state.get('symbols', {})
            active_positions = state.get('active_positions', {})
            
            # Проверка на противоречия
            for symbol, pos_info in active_positions.items():
                if symbol in symbols_data:
                    symbol_active_pos = symbols_data[symbol].get('active_position')
                    if symbol_active_pos is None:
                        self.log_test("State File Integrity", False, f"Inconsistency: {symbol}")
                        return False
                        
            self.log_test("State File Integrity", True, f"Valid structure, {len(active_positions)} positions")
            return True
            
        except json.JSONDecodeError as e:
            self.log_test("State File Integrity", False, f"JSON error: {e}")
            return False
        except Exception as e:
            self.log_test("State File Integrity", False, f"Error: {e}")
            return False
            
    def test_state_validator(self) -> bool:
        """Тест валидатора состояния"""
        try:
            validator = StateValidator('trading_state_v1_6_TXB.json')
            
            # Тест валидации консистентности
            valid, errors = validator.validate_state_consistency()
            
            if not valid:
                self.log_test("State Validator", False, f"Validation errors: {errors}")
                return False
                
            self.log_test("State Validator", True, "State validation passed")
            return True
            
        except Exception as e:
            self.log_test("State Validator", False, f"Error: {e}")
            return False
            
    def test_auto_fixer(self) -> bool:
        """Тест автоисправителя"""
        try:
            auto_fixer = AutoFixer('trading_state_v1_6_TXB.json')
            
            # Тест создания резервной копии
            backup_created = auto_fixer.create_backup()
            
            if not backup_created:
                self.log_test("Auto Fixer", False, "Failed to create backup")
                return False
                
            self.log_test("Auto Fixer", True, "Backup creation and basic functionality OK")
            return True
            
        except Exception as e:
            self.log_test("Auto Fixer", False, f"Error: {e}")
            return False
            
    def test_signal_generation(self) -> bool:
        """Тест генерации сигналов"""
        try:
            # Загрузить конфигурацию
            with open('signalwarden_lite/config/config_production.yaml', 'r') as f:
                cfg = yaml.safe_load(f)
                
            # Настроить параметры
            regime_thresholds = RegimeThresholds(**cfg['regime']['calm_thresholds'])
            
            signal_params = SignalParams(
                setup_breakout=cfg['signals']['setups']['breakout']['enabled'],
                setup_inside=cfg['signals']['setups']['inside_bar']['enabled'],
                setup_trend_cont=cfg['signals']['setups']['trend_continuation']['enabled'],
                setup_squeeze=cfg['signals']['setups']['squeeze_breakout']['enabled'],
                lookback_calm=cfg['signals']['dynamic_lookback']['calm'],
                lookback_normal=cfg['signals']['dynamic_lookback']['normal'],
                lookback_high=cfg['signals']['dynamic_lookback']['high'],
                long_cushion_calm=cfg['signals']['atr_cushion_long']['calm'],
                long_cushion_normal=cfg['signals']['atr_cushion_long']['normal'],
                long_cushion_high=cfg['signals']['atr_cushion_long']['high'],
                short_cushion_calm=cfg['signals']['atr_cushion_short']['calm'],
                short_cushion_normal=cfg['signals']['atr_cushion_short']['normal'],
                short_cushion_high=cfg['signals']['atr_cushion_short']['high'],
                ltf_thinbar_k=cfg['signals']['ltf_thinbar_k']
            )
            
            # Создать тестовые данные
            test_data = self.create_test_data()
            
            # Добавить индикаторы и режимы
            test_data = add_indicators(test_data)
            test_data = add_regime(test_data, regime_thresholds)
            
            # Создать BTC market data
            btc_market = pd.DataFrame({
                'timestamp': test_data['timestamp'],
                'mkt_long_ok': [True] * len(test_data),
                'mkt_short_ok': [False] * len(test_data)
            })
            
            # Генерировать сигналы
            signals = generate_signals(test_data, signal_params, btc_market)
            
            # Проверить результат
            if len(signals) == 0:
                self.log_test("Signal Generation", False, "No signals generated")
                return False
                
            # Проверить наличие необходимых колонок
            required_columns = ['allow_long', 'allow_short', 'regime']
            for col in required_columns:
                if col not in signals.columns:
                    self.log_test("Signal Generation", False, f"Missing column: {col}")
                    return False
                    
            self.log_test("Signal Generation", True, f"Generated {len(signals)} bars with signals")
            return True
            
        except Exception as e:
            self.log_test("Signal Generation", False, f"Error: {e}")
            return False
            
    def test_market_filter(self) -> bool:
        """Тест BTC Market Filter"""
        try:
            # Загрузить конфигурацию
            with open('signalwarden_lite/config/config_production.yaml', 'r') as f:
                cfg = yaml.safe_load(f)
                
            # Создать тестовые BTC данные
            btc_data = self.create_test_data()
            btc_data = add_indicators(btc_data, 
                cfg['market_filter']['ema_fast'], 
                cfg['market_filter']['ema_slow'])
                
            # Вычислить market bias
            btc_market = compute_market_bias(btc_data, 
                cfg['market_filter']['ema_fast'], 
                cfg['market_filter']['ema_slow'])
                
            # Проверить результат
            if len(btc_market) == 0:
                self.log_test("Market Filter", False, "No market bias data")
                return False
                
            latest = btc_market.iloc[-1]
            
            # Проверить наличие необходимых колонок
            required_columns = ['mkt_long_ok', 'mkt_short_ok']
            for col in required_columns:
                if col not in latest or pd.isna(latest[col]):
                    self.log_test("Market Filter", False, f"Invalid {col}")
                    return False
                    
            self.log_test("Market Filter", True, f"Market bias: {'BULL' if latest['mkt_long_ok'] else 'BEAR'}")
            return True
            
        except Exception as e:
            self.log_test("Market Filter", False, f"Error: {e}")
            return False
            
    def test_position_execution_conditions(self) -> bool:
        """Тест условий выполнения позиций"""
        try:
            # Загрузить конфигурацию
            with open('signalwarden_lite/config/config_production.yaml', 'r') as f:
                cfg = yaml.safe_load(f)
                
            # Подключиться к бирже
            load_dotenv()
            exchange = ccxt.binanceusdm({
                'apiKey': os.getenv('BINANCE_API_KEY'),
                'secret': os.getenv('BINANCE_SECRET'),
                'enableRateLimit': True,
                'timeout': 30000,
                'options': {'defaultType': 'future'}
            })
            
            # Проверить баланс
            balance = exchange.fetch_balance()
            free_usdt = balance.get('USDT', {}).get('free', 0)
            
            # Рассчитать требуемый маржин
            margin_usdt = cfg['risk']['margin_usdt']
            leverage = cfg['risk']['leverage']
            actual_margin_per_position = margin_usdt / leverage
            required_margin = actual_margin_per_position * 1.05
            
            # Проверить условия
            can_execute = free_usdt >= required_margin
            
            if not can_execute:
                self.log_test("Position Execution Conditions", False, 
                    f"Insufficient balance: {free_usdt:.2f} < {required_margin:.2f}")
                return False
                
            # Проверить активные позиции
            positions = exchange.fetch_positions()
            active_positions = [p for p in positions if float(p['contracts']) != 0]
            
            self.log_test("Position Execution Conditions", True, 
                f"Can execute: {can_execute}, Active positions: {len(active_positions)}")
            return True
            
        except Exception as e:
            self.log_test("Position Execution Conditions", False, f"Error: {e}")
            return False
            
    def create_test_data(self, length: int = 100) -> pd.DataFrame:
        """Создать тестовые данные"""
        dates = pd.date_range(start='2024-01-01', periods=length, freq='1H')
        
        # Создать реалистичные OHLCV данные
        np.random.seed(42)
        base_price = 100.0
        prices = [base_price]
        
        for i in range(1, length):
            change = np.random.normal(0, 0.02)  # 2% волатильность
            new_price = prices[-1] * (1 + change)
            prices.append(new_price)
            
        data = []
        for i, (date, price) in enumerate(zip(dates, prices)):
            high = price * (1 + abs(np.random.normal(0, 0.01)))
            low = price * (1 - abs(np.random.normal(0, 0.01)))
            open_price = prices[i-1] if i > 0 else price
            close = price
            volume = np.random.uniform(1000, 10000)
            
            data.append({
                'timestamp': date,
                'open': open_price,
                'high': high,
                'low': low,
                'close': close,
                'volume': volume
            })
            
        return pd.DataFrame(data)
        
    def run_all_tests(self) -> Dict[str, Any]:
        """Запустить все тесты"""
        print("🚀 ЗАПУСК ФИНАЛЬНОГО ТЕСТИРОВАНИЯ СИСТЕМЫ")
        print("=" * 80)
        
        # Список тестов
        tests = [
            ("Configuration Loading", self.test_configuration_loading),
            ("Exchange Connection", self.test_exchange_connection),
            ("State File Integrity", self.test_state_file_integrity),
            ("State Validator", self.test_state_validator),
            ("Auto Fixer", self.test_auto_fixer),
            ("Signal Generation", self.test_signal_generation),
            ("Market Filter", self.test_market_filter),
            ("Position Execution Conditions", self.test_position_execution_conditions),
        ]
        
        # Запустить тесты
        for test_name, test_func in tests:
            try:
                test_func()
            except Exception as e:
                self.log_test(test_name, False, f"Unexpected error: {e}")
                
        # Результаты
        total_tests = len(tests)
        success_rate = (self.passed_tests / total_tests) * 100
        
        print("\n" + "=" * 80)
        print("📊 РЕЗУЛЬТАТЫ ФИНАЛЬНОГО ТЕСТИРОВАНИЯ")
        print("=" * 80)
        print(f"✅ Пройдено тестов: {self.passed_tests}/{total_tests}")
        print(f"❌ Провалено тестов: {self.failed_tests}/{total_tests}")
        print(f"📈 Успешность: {success_rate:.1f}%")
        
        if success_rate == 100:
            print("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ! СИСТЕМА ГОТОВА К РАБОТЕ!")
        elif success_rate >= 80:
            print("✅ Большинство тестов пройдено. Система в хорошем состоянии.")
        else:
            print("⚠️ Много тестов провалено. Требуется внимание.")
            
        return {
            'timestamp': datetime.utcnow().isoformat(),
            'total_tests': total_tests,
            'passed_tests': self.passed_tests,
            'failed_tests': self.failed_tests,
            'success_rate': success_rate,
            'test_results': self.test_results
        }

def main():
    """Главная функция"""
    tester = FinalSystemTest()
    results = tester.run_all_tests()
    
    # Сохранить результаты
    with open('final_test_results.json', 'w') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n📄 Результаты сохранены в final_test_results.json")

if __name__ == "__main__":
    main()
