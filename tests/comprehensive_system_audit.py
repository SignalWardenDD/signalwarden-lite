#!/usr/bin/env python3
"""
Комплексный аудит системы SignalWarden Lite v1.6-TXB
Проверяет все критические компоненты и потенциальные проблемы
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
sys.path.append('signalwarden_lite')

from core.features import add_indicators
from core.regimes import add_regime, RegimeThresholds
from core.market import compute_market_bias
from core.signals import generate_signals, SignalParams
from core.storage import JSONStore

class SystemAuditor:
    """Комплексный аудитор системы"""
    
    def __init__(self):
        self.issues = []
        self.warnings = []
        self.recommendations = []
        self.test_results = {}
        
    def add_issue(self, component: str, issue: str, severity: str = "HIGH"):
        """Добавить критическую проблему"""
        self.issues.append({
            'component': component,
            'issue': issue,
            'severity': severity,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    def add_warning(self, component: str, warning: str):
        """Добавить предупреждение"""
        self.warnings.append({
            'component': component,
            'warning': warning,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    def add_recommendation(self, component: str, recommendation: str):
        """Добавить рекомендацию"""
        self.recommendations.append({
            'component': component,
            'recommendation': recommendation,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    def audit_configuration(self) -> Dict[str, Any]:
        """Аудит конфигурации"""
        print("🔍 АУДИТ КОНФИГУРАЦИИ...")
        
        try:
            with open('signalwarden_lite/config/config_production.yaml', 'r') as f:
                cfg = yaml.safe_load(f)
                
            # Проверка обязательных секций
            required_sections = [
                'signals', 'short_guard', 'market_filter', 'timeframes',
                'risk', 'exchange', 'symbols', 'regime'
            ]
            
            for section in required_sections:
                if section not in cfg:
                    self.add_issue('CONFIG', f"Отсутствует обязательная секция: {section}")
                    
            # Проверка параметров риска
            risk = cfg.get('risk', {})
            if risk.get('margin_usdt', 0) <= 0:
                self.add_issue('CONFIG', "margin_usdt должен быть больше 0")
            if risk.get('leverage', 0) <= 0:
                self.add_issue('CONFIG', "leverage должен быть больше 0")
            if risk.get('sl_atr_mult', 0) <= 0:
                self.add_issue('CONFIG', "sl_atr_mult должен быть больше 0")
                
            # Проверка символов
            symbols = cfg.get('symbols', [])
            if not symbols:
                self.add_issue('CONFIG', "Список символов пуст")
            elif len(symbols) > 10:
                self.add_warning('CONFIG', f"Много символов ({len(symbols)}), может быть сложно управлять")
                
            # Проверка режима тестнета
            if not cfg.get('exchange', {}).get('testnet', True):
                self.add_warning('CONFIG', "Включен LIVE режим торговли!")
                
            return cfg
            
        except Exception as e:
            self.add_issue('CONFIG', f"Ошибка загрузки конфигурации: {e}")
            return {}
            
    def audit_exchange_connection(self, cfg: Dict[str, Any]) -> Optional[ccxt.Exchange]:
        """Аудит подключения к бирже"""
        print("🔍 АУДИТ ПОДКЛЮЧЕНИЯ К БИРЖЕ...")
        
        try:
            load_dotenv()
            
            api_key = os.getenv('BINANCE_API_KEY')
            secret = os.getenv('BINANCE_SECRET')
            
            if not api_key or not secret:
                self.add_issue('EXCHANGE', "Отсутствуют API ключи в .env файле")
                return None
                
            if len(api_key) < 10 or len(secret) < 10:
                self.add_issue('EXCHANGE', "API ключи выглядят некорректно")
                return None
                
            exchange = ccxt.binanceusdm({
                'apiKey': api_key,
                'secret': secret,
                'enableRateLimit': True,
                'timeout': 30000,
                'options': {'defaultType': 'future'}
            })
            
            # Проверка подключения
            exchange.load_markets()
            balance = exchange.fetch_balance()
            
            usdt_balance = balance.get('USDT', {}).get('total', 0)
            if usdt_balance <= 0:
                self.add_issue('EXCHANGE', f"Нулевой баланс USDT: {usdt_balance}")
            elif usdt_balance < 50:
                self.add_warning('EXCHANGE', f"Низкий баланс USDT: {usdt_balance}")
                
            print(f"✅ Подключение к бирже успешно. Баланс: {usdt_balance:.2f} USDT")
            return exchange
            
        except Exception as e:
            self.add_issue('EXCHANGE', f"Ошибка подключения к бирже: {e}")
            return None
            
    def audit_trading_state(self) -> Dict[str, Any]:
        """Аудит файла состояния торговли"""
        print("🔍 АУДИТ ФАЙЛА СОСТОЯНИЯ...")
        
        state_file = 'trading_state_v1_6_TXB.json'
        
        if not os.path.exists(state_file):
            self.add_warning('STATE', "Файл состояния не найден, будет создан новый")
            return {}
            
        try:
            with open(state_file, 'r') as f:
                state = json.load(f)
                
            # Проверка структуры
            if 'symbols' not in state:
                self.add_issue('STATE', "Отсутствует секция 'symbols' в файле состояния")
                
            if 'active_positions' not in state:
                self.add_issue('STATE', "Отсутствует секция 'active_positions' в файле состояния")
                
            # Проверка консистентности позиций
            symbols_data = state.get('symbols', {})
            active_positions = state.get('active_positions', {})
            
            # Проверка на противоречия
            for symbol, pos_info in active_positions.items():
                if symbol in symbols_data:
                    symbol_active_pos = symbols_data[symbol].get('active_position')
                    if symbol_active_pos is None:
                        self.add_issue('STATE', 
                            f"Противоречие: {symbol} есть в active_positions, но active_position = null")
                    elif symbol_active_pos != pos_info:
                        self.add_warning('STATE', 
                            f"Несоответствие данных позиции {symbol} между секциями")
                            
            # Проверка на "призрачные" позиции
            for symbol, pos_info in active_positions.items():
                if not isinstance(pos_info, dict):
                    self.add_issue('STATE', f"Некорректные данные позиции {symbol}")
                    continue
                    
                required_fields = ['symbol', 'side', 'entry', 'qty']
                for field in required_fields:
                    if field not in pos_info:
                        self.add_issue('STATE', f"Отсутствует поле {field} в позиции {symbol}")
                        
            print(f"✅ Файл состояния проверен. Активных позиций: {len(active_positions)}")
            return state
            
        except json.JSONDecodeError as e:
            self.add_issue('STATE', f"Файл состояния поврежден (JSON): {e}")
            return {}
        except Exception as e:
            self.add_issue('STATE', f"Ошибка чтения файла состояния: {e}")
            return {}
            
    def audit_exchange_positions(self, exchange: ccxt.Exchange, cfg: Dict[str, Any]) -> List[Dict]:
        """Аудит позиций на бирже"""
        print("🔍 АУДИТ ПОЗИЦИЙ НА БИРЖЕ...")
        
        try:
            positions = exchange.fetch_positions()
            active_positions = [p for p in positions if float(p['contracts']) != 0]
            
            # Проверка символов
            configured_symbols = set(cfg.get('symbols', []))
            
            for pos in active_positions:
                symbol_ccxt = pos['symbol']
                if ':USDT' not in symbol_ccxt:
                    continue
                    
                # Конвертация в наш формат
                base_quote = symbol_ccxt.split(':')[0]
                symbol = base_quote.replace('/', '_')
                
                if symbol not in configured_symbols:
                    self.add_warning('EXCHANGE', 
                        f"Позиция {symbol} не в списке отслеживаемых символов")
                        
                # Проверка размера позиции
                size = abs(float(pos['contracts']))
                if size <= 0:
                    self.add_issue('EXCHANGE', f"Некорректный размер позиции {symbol}: {size}")
                    
                # Проверка PnL
                pnl = float(pos['unrealizedPnl'])
                if abs(pnl) > 1000:  # Большие убытки/прибыли
                    self.add_warning('EXCHANGE', 
                        f"Большой PnL для {symbol}: {pnl:.2f} USDT")
                        
            print(f"✅ Позиции на бирже проверены. Активных: {len(active_positions)}")
            return active_positions
            
        except Exception as e:
            self.add_issue('EXCHANGE', f"Ошибка получения позиций с биржи: {e}")
            return []
            
    def audit_signal_generation(self, cfg: Dict[str, Any]) -> Dict[str, Any]:
        """Аудит генерации сигналов"""
        print("🔍 АУДИТ ГЕНЕРАЦИИ СИГНАЛОВ...")
        
        try:
            # Параметры сигналов
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
            
            # Проверка параметров
            if signal_params.lookback_calm <= 0:
                self.add_issue('SIGNALS', "lookback_calm должен быть больше 0")
            if signal_params.long_cushion_calm <= 0:
                self.add_issue('SIGNALS', "long_cushion_calm должен быть больше 0")
            if signal_params.short_cushion_calm <= 0:
                self.add_issue('SIGNALS', "short_cushion_calm должен быть больше 0")
                
            # Проверка асимметрии подушек
            if signal_params.short_cushion_calm < signal_params.long_cushion_calm:
                self.add_warning('SIGNALS', 
                    "Подушка для шортов меньше чем для лонгов - может быть рискованно")
                    
            print("✅ Параметры сигналов проверены")
            return {
                'signal_params': signal_params,
                'regime_thresholds': regime_thresholds
            }
            
        except Exception as e:
            self.add_issue('SIGNALS', f"Ошибка настройки параметров сигналов: {e}")
            return {}
            
    def audit_market_filter(self, exchange: ccxt.Exchange, cfg: Dict[str, Any]) -> Dict[str, Any]:
        """Аудит BTC Market Filter"""
        print("🔍 АУДИТ BTC MARKET FILTER...")
        
        try:
            # Получить BTC данные
            btc_data = self.fetch_binance_data(exchange, 'BTC/USDT:USDT', '1h', 200)
            if btc_data is None:
                self.add_issue('MARKET_FILTER', "Не удалось получить BTC данные")
                return {}
                
            # Добавить индикаторы
            btc_data = add_indicators(btc_data, 
                cfg['market_filter']['ema_fast'], 
                cfg['market_filter']['ema_slow'])
                
            # Вычислить market bias
            btc_market = compute_market_bias(btc_data, 
                cfg['market_filter']['ema_fast'], 
                cfg['market_filter']['ema_slow'])
                
            latest_btc = btc_market.iloc[-1]
            
            # Проверка данных
            if pd.isna(latest_btc['mkt_long_ok']) or pd.isna(latest_btc['mkt_short_ok']):
                self.add_issue('MARKET_FILTER', "BTC market filter возвращает NaN значения")
                
            # Проверка логики
            if latest_btc['mkt_long_ok'] and latest_btc['mkt_short_ok']:
                self.add_warning('MARKET_FILTER', 
                    "BTC filter разрешает и лонги и шорты одновременно")
            elif not latest_btc['mkt_long_ok'] and not latest_btc['mkt_short_ok']:
                self.add_warning('MARKET_FILTER', 
                    "BTC filter запрещает и лонги и шорты одновременно")
                    
            print(f"✅ BTC Market Filter: {'BULL' if latest_btc['mkt_long_ok'] else 'BEAR'}")
            return {
                'btc_data': btc_data,
                'btc_market': btc_market,
                'latest_btc': latest_btc
            }
            
        except Exception as e:
            self.add_issue('MARKET_FILTER', f"Ошибка BTC Market Filter: {e}")
            return {}
            
    def audit_signal_execution_conditions(self, cfg: Dict[str, Any], 
                                        exchange: ccxt.Exchange,
                                        state: Dict[str, Any]) -> Dict[str, Any]:
        """Аудит условий выполнения сигналов"""
        print("🔍 АУДИТ УСЛОВИЙ ВЫПОЛНЕНИЯ СИГНАЛОВ...")
        
        try:
            # Проверка баланса
            balance = exchange.fetch_balance()
            free_usdt = balance.get('USDT', {}).get('free', 0)
            
            margin_usdt = cfg['risk']['margin_usdt']
            leverage = cfg['risk']['leverage']
            actual_margin_per_position = margin_usdt / leverage
            required_margin = actual_margin_per_position * 1.05
            
            if free_usdt < required_margin:
                self.add_issue('EXECUTION', 
                    f"Недостаточно средств: {free_usdt:.2f} < {required_margin:.2f} USDT")
            else:
                max_positions = free_usdt / required_margin
                self.add_recommendation('EXECUTION', 
                    f"Можно открыть до {int(max_positions)} позиций")
                    
            # Проверка активных позиций
            active_positions = state.get('active_positions', {})
            symbols = cfg.get('symbols', [])
            
            if len(active_positions) >= len(symbols):
                self.add_warning('EXECUTION', 
                    f"Достигнут лимит позиций: {len(active_positions)}/{len(symbols)}")
                    
            # Проверка конкретных символов
            execution_status = {}
            for symbol in symbols[:3]:  # Проверяем первые 3 символа
                has_position = symbol in active_positions
                can_execute = not has_position and free_usdt >= required_margin
                
                execution_status[symbol] = {
                    'has_position': has_position,
                    'can_execute': can_execute,
                    'free_usdt': free_usdt,
                    'required_margin': required_margin
                }
                
                if has_position:
                    self.add_warning('EXECUTION', f"{symbol} уже имеет активную позицию")
                    
            print(f"✅ Условия выполнения проверены. Free USDT: {free_usdt:.2f}")
            return execution_status
            
        except Exception as e:
            self.add_issue('EXECUTION', f"Ошибка проверки условий выполнения: {e}")
            return {}
            
    def fetch_binance_data(self, exchange: ccxt.Exchange, symbol: str, 
                          timeframe: str, limit: int) -> Optional[pd.DataFrame]:
        """Получить данные с Binance"""
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df
        except Exception as e:
            print(f"❌ Ошибка получения данных {symbol}: {e}")
            return None
            
    def run_comprehensive_audit(self) -> Dict[str, Any]:
        """Запустить комплексный аудит"""
        print("🚀 ЗАПУСК КОМПЛЕКСНОГО АУДИТА СИСТЕМЫ")
        print("=" * 80)
        
        # 1. Аудит конфигурации
        cfg = self.audit_configuration()
        if not cfg:
            return self.get_audit_report()
            
        # 2. Аудит подключения к бирже
        exchange = self.audit_exchange_connection(cfg)
        if not exchange:
            return self.get_audit_report()
            
        # 3. Аудит файла состояния
        state = self.audit_trading_state()
        
        # 4. Аудит позиций на бирже
        exchange_positions = self.audit_exchange_positions(exchange, cfg)
        
        # 5. Аудит генерации сигналов
        signal_config = self.audit_signal_generation(cfg)
        
        # 6. Аудит BTC Market Filter
        market_config = self.audit_market_filter(exchange, cfg)
        
        # 7. Аудит условий выполнения
        execution_config = self.audit_signal_execution_conditions(cfg, exchange, state)
        
        return self.get_audit_report()
        
    def get_audit_report(self) -> Dict[str, Any]:
        """Получить отчет аудита"""
        return {
            'timestamp': datetime.utcnow().isoformat(),
            'issues': self.issues,
            'warnings': self.warnings,
            'recommendations': self.recommendations,
            'summary': {
                'total_issues': len(self.issues),
                'total_warnings': len(self.warnings),
                'total_recommendations': len(self.recommendations),
                'critical_issues': len([i for i in self.issues if i['severity'] == 'CRITICAL']),
                'high_issues': len([i for i in self.issues if i['severity'] == 'HIGH'])
            }
        }
        
    def print_audit_report(self, report: Dict[str, Any]):
        """Вывести отчет аудита"""
        print("\n" + "=" * 80)
        print("📊 ОТЧЕТ КОМПЛЕКСНОГО АУДИТА")
        print("=" * 80)
        
        summary = report['summary']
        print(f"🔍 Всего проверок: {summary['total_issues'] + summary['total_warnings'] + summary['total_recommendations']}")
        print(f"❌ Критических проблем: {summary['critical_issues']}")
        print(f"⚠️ Высокоприоритетных проблем: {summary['high_issues']}")
        print(f"⚠️ Предупреждений: {summary['total_warnings']}")
        print(f"💡 Рекомендаций: {summary['total_recommendations']}")
        
        if self.issues:
            print("\n🚨 КРИТИЧЕСКИЕ ПРОБЛЕМЫ:")
            for issue in self.issues:
                print(f"   ❌ [{issue['component']}] {issue['issue']} ({issue['severity']})")
                
        if self.warnings:
            print("\n⚠️ ПРЕДУПРЕЖДЕНИЯ:")
            for warning in self.warnings:
                print(f"   ⚠️ [{warning['component']}] {warning['warning']}")
                
        if self.recommendations:
            print("\n💡 РЕКОМЕНДАЦИИ:")
            for rec in self.recommendations:
                print(f"   💡 [{rec['component']}] {rec['recommendation']}")
                
        # Общий статус
        if summary['critical_issues'] > 0:
            print(f"\n🔴 СТАТУС: КРИТИЧЕСКИЕ ПРОБЛЕМЫ ТРЕБУЮТ НЕМЕДЛЕННОГО ИСПРАВЛЕНИЯ!")
        elif summary['high_issues'] > 0:
            print(f"\n🟡 СТАТУС: ЕСТЬ ПРОБЛЕМЫ, ТРЕБУЮЩИЕ ВНИМАНИЯ")
        else:
            print(f"\n🟢 СТАТУС: СИСТЕМА В НОРМАЛЬНОМ СОСТОЯНИИ")

def main():
    """Главная функция"""
    auditor = SystemAuditor()
    report = auditor.run_comprehensive_audit()
    auditor.print_audit_report(report)
    
    # Сохранить отчет
    with open('system_audit_report.json', 'w') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\n📄 Отчет сохранен в system_audit_report.json")

if __name__ == "__main__":
    main()
