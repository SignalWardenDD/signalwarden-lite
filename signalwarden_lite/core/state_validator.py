"""
Валидатор состояния системы для предотвращения проблем консистентности
"""

import os
import json
import time
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
import pandas as pd
import ccxt
from ..utils.logger import get_logger

logger = get_logger(__name__)

class StateValidator:
    """Валидатор состояния системы"""
    
    def __init__(self, state_file: str, exchange: Optional[ccxt.Exchange] = None):
        self.state_file = state_file
        self.exchange = exchange
        self.validation_errors = []
        self.validation_warnings = []
        
    def validate_state_consistency(self) -> Tuple[bool, List[str]]:
        """Проверить консистентность файла состояния"""
        errors = []
        
        if not os.path.exists(self.state_file):
            errors.append("Файл состояния не найден")
            return False, errors
            
        try:
            with open(self.state_file, 'r') as f:
                state = json.load(f)
                
            # Проверка структуры
            if 'symbols' not in state:
                errors.append("Отсутствует секция 'symbols'")
            if 'active_positions' not in state:
                errors.append("Отсутствует секция 'active_positions'")
                
            if errors:
                return False, errors
                
            symbols_data = state.get('symbols', {})
            active_positions = state.get('active_positions', {})
            
            # Проверка консистентности позиций
            for symbol, pos_info in active_positions.items():
                if symbol in symbols_data:
                    symbol_active_pos = symbols_data[symbol].get('active_position')
                    if symbol_active_pos is None:
                        errors.append(f"Противоречие: {symbol} есть в active_positions, но active_position = null")
                    elif not self._positions_match(symbol_active_pos, pos_info):
                        errors.append(f"Несоответствие данных позиции {symbol} между секциями")
                        
            # Проверка валидности данных позиций
            for symbol, pos_info in active_positions.items():
                pos_errors = self._validate_position_data(symbol, pos_info)
                errors.extend(pos_errors)
                
            return len(errors) == 0, errors
            
        except json.JSONDecodeError as e:
            errors.append(f"Файл состояния поврежден (JSON): {e}")
            return False, errors
        except Exception as e:
            errors.append(f"Ошибка чтения файла состояния: {e}")
            return False, errors
            
    def validate_exchange_consistency(self, configured_symbols: List[str]) -> Tuple[bool, List[str]]:
        """Проверить консистентность с биржей"""
        if not self.exchange:
            return True, []  # Нет биржи - пропускаем проверку
            
        errors = []
        
        try:
            # Получить позиции с биржи
            positions = self.exchange.fetch_positions()
            active_exchange_positions = [p for p in positions if float(p['contracts']) != 0]
            
            # Получить позиции из состояния
            with open(self.state_file, 'r') as f:
                state = json.load(f)
            active_positions = state.get('active_positions', {})
            
            # Конвертировать позиции биржи в наш формат
            exchange_positions_dict = {}
            for pos in active_exchange_positions:
                symbol_ccxt = pos['symbol']
                if ':USDT' not in symbol_ccxt:
                    continue
                    
                base_quote = symbol_ccxt.split(':')[0]
                symbol = base_quote.replace('/', '_')
                
                if symbol in configured_symbols:
                    exchange_positions_dict[symbol] = {
                        'side': 'LONG' if pos['side'] == 'long' else 'SHORT',
                        'entry': float(pos['entryPrice']),
                        'qty': abs(float(pos['contracts'])),
                        'unrealized_pnl': float(pos['unrealizedPnl'])
                    }
                    
            # Проверить соответствие
            for symbol in configured_symbols:
                state_has_pos = symbol in active_positions
                exchange_has_pos = symbol in exchange_positions_dict
                
                if state_has_pos and not exchange_has_pos:
                    errors.append(f"Призрачная позиция: {symbol} есть в состоянии, но нет на бирже")
                elif not state_has_pos and exchange_has_pos:
                    errors.append(f"Отсутствующая позиция: {symbol} есть на бирже, но нет в состоянии")
                elif state_has_pos and exchange_has_pos:
                    # Проверить соответствие данных
                    state_pos = active_positions[symbol]
                    exchange_pos = exchange_positions_dict[symbol]
                    
                    if state_pos.get('side') != exchange_pos['side']:
                        errors.append(f"Несоответствие стороны позиции {symbol}: состояние={state_pos.get('side')}, биржа={exchange_pos['side']}")
                        
                    # Проверить размер позиции (допускаем небольшие различия)
                    state_qty = state_pos.get('qty', 0)
                    exchange_qty = exchange_pos['qty']
                    if abs(state_qty - exchange_qty) > 0.001:
                        errors.append(f"Несоответствие размера позиции {symbol}: состояние={state_qty}, биржа={exchange_qty}")
                        
            return len(errors) == 0, errors
            
        except Exception as e:
            errors.append(f"Ошибка проверки консистентности с биржей: {e}")
            return False, errors
            
    def validate_position_data(self, symbol: str, pos_info: Dict[str, Any]) -> List[str]:
        """Проверить валидность данных позиции"""
        errors = []
        
        required_fields = ['symbol', 'side', 'entry', 'qty', 'sl_initial', 'sl_current']
        for field in required_fields:
            if field not in pos_info:
                errors.append(f"Отсутствует поле {field} в позиции {symbol}")
                
        # Проверка значений
        if 'entry' in pos_info and pos_info['entry'] <= 0:
            errors.append(f"Некорректная цена входа для {symbol}: {pos_info['entry']}")
            
        if 'qty' in pos_info and pos_info['qty'] <= 0:
            errors.append(f"Некорректное количество для {symbol}: {pos_info['qty']}")
            
        if 'side' in pos_info and pos_info['side'] not in ['LONG', 'SHORT']:
            errors.append(f"Некорректная сторона позиции для {symbol}: {pos_info['side']}")
            
        # Проверка логики стоп-лосса
        if all(field in pos_info for field in ['side', 'entry', 'sl_initial']):
            side = pos_info['side']
            entry = pos_info['entry']
            sl = pos_info['sl_initial']
            
            if side == 'LONG' and sl >= entry:
                errors.append(f"Некорректный стоп-лосс для LONG {symbol}: SL={sl} >= Entry={entry}")
            elif side == 'SHORT' and sl <= entry:
                errors.append(f"Некорректный стоп-лосс для SHORT {symbol}: SL={sl} <= Entry={entry}")
                
        return errors
        
    def _positions_match(self, pos1: Dict[str, Any], pos2: Dict[str, Any]) -> bool:
        """Проверить соответствие двух позиций"""
        key_fields = ['symbol', 'side', 'entry', 'qty']
        
        for field in key_fields:
            if pos1.get(field) != pos2.get(field):
                return False
                
        return True
        
    def _validate_position_data(self, symbol: str, pos_info: Dict[str, Any]) -> List[str]:
        """Внутренний метод валидации данных позиции"""
        return self.validate_position_data(symbol, pos_info)
        
    def fix_state_inconsistencies(self, configured_symbols: List[str]) -> bool:
        """Исправить несоответствия в состоянии"""
        try:
            with open(self.state_file, 'r') as f:
                state = json.load(f)
                
            symbols_data = state.get('symbols', {})
            active_positions = state.get('active_positions', {})
            
            fixed = False
            
            # Удалить призрачные позиции (есть в состоянии, но нет на бирже)
            if self.exchange:
                positions = self.exchange.fetch_positions()
                active_exchange_positions = [p for p in positions if float(p['contracts']) != 0]
                
                exchange_symbols = set()
                for pos in active_exchange_positions:
                    symbol_ccxt = pos['symbol']
                    if ':USDT' not in symbol_ccxt:
                        continue
                    base_quote = symbol_ccxt.split(':')[0]
                    symbol = base_quote.replace('/', '_')
                    if symbol in configured_symbols:
                        exchange_symbols.add(symbol)
                        
                # Удалить позиции, которых нет на бирже
                symbols_to_remove = []
                for symbol in active_positions:
                    if symbol not in exchange_symbols:
                        symbols_to_remove.append(symbol)
                        
                for symbol in symbols_to_remove:
                    logger.warning(f"🗑️ Удаление призрачной позиции: {symbol}")
                    del active_positions[symbol]
                    if symbol in symbols_data:
                        symbols_data[symbol]['active_position'] = None
                    fixed = True
                    
            # Синхронизировать секции symbols и active_positions
            for symbol, pos_info in active_positions.items():
                if symbol in symbols_data:
                    symbols_data[symbol]['active_position'] = pos_info
                    
            # Очистить active_position для символов без позиций
            for symbol in symbols_data:
                if symbol not in active_positions:
                    symbols_data[symbol]['active_position'] = None
                    
            # Сохранить исправленное состояние
            if fixed:
                state['symbols'] = symbols_data
                state['active_positions'] = active_positions
                state['metadata']['last_updated'] = datetime.utcnow().isoformat()
                state['metadata']['state_fixed'] = True
                state['metadata']['fix_timestamp'] = time.time()
                
                with open(self.state_file, 'w') as f:
                    json.dump(state, f, indent=2)
                    
                logger.info("✅ Состояние исправлено и сохранено")
                
            return fixed
            
        except Exception as e:
            logger.error(f"❌ Ошибка исправления состояния: {e}")
            return False
            
    def run_full_validation(self, configured_symbols: List[str]) -> Dict[str, Any]:
        """Запустить полную валидацию"""
        logger.info("🔍 Запуск полной валидации состояния...")
        
        # Валидация файла состояния
        state_valid, state_errors = self.validate_state_consistency()
        
        # Валидация консистентности с биржей
        exchange_valid, exchange_errors = self.validate_exchange_consistency(configured_symbols)
        
        all_errors = state_errors + exchange_errors
        
        result = {
            'timestamp': datetime.utcnow().isoformat(),
            'state_valid': state_valid,
            'exchange_valid': exchange_valid,
            'overall_valid': len(all_errors) == 0,
            'state_errors': state_errors,
            'exchange_errors': exchange_errors,
            'total_errors': len(all_errors)
        }
        
        if all_errors:
            logger.warning(f"⚠️ Найдено {len(all_errors)} проблем валидации:")
            for error in all_errors:
                logger.warning(f"   - {error}")
        else:
            logger.info("✅ Валидация пройдена успешно")
            
        return result
