"""
Автоматическое исправление проблем системы
"""

import os
import json
import time
import shutil
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
import ccxt
from ..utils.logger import get_logger
from .state_validator import StateValidator

logger = get_logger(__name__)

class AutoFixer:
    """Автоматическое исправление проблем"""
    
    def __init__(self, state_file: str, exchange: Optional[ccxt.Exchange] = None):
        self.state_file = state_file
        self.exchange = exchange
        self.fixes_applied = []
        self.backup_created = False
        
    def create_backup(self) -> bool:
        """Создать резервную копию файла состояния"""
        try:
            if not os.path.exists(self.state_file):
                return True  # Нет файла для резервного копирования
                
            # Создаем папку для бэкапов
            backup_dir = os.path.join(os.path.dirname(self.state_file), 'backups')
            os.makedirs(backup_dir, exist_ok=True)
            
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            filename = os.path.basename(self.state_file)
            backup_file = os.path.join(backup_dir, f"{filename}.backup.{timestamp}")
            
            shutil.copy2(self.state_file, backup_file)
            self.backup_created = True
            
            logger.info(f"💾 Создана резервная копия: {backup_file}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания резервной копии: {e}")
            return False
            
    def fix_ghost_positions(self, configured_symbols: List[str]) -> bool:
        """Исправить призрачные позиции"""
        try:
            if not self.exchange:
                logger.warning("⚠️ Нет подключения к бирже - пропуск исправления призрачных позиций")
                return True
                
            # Создать резервную копию
            if not self.backup_created:
                self.create_backup()
                
            # Получить позиции с биржи
            positions = self.exchange.fetch_positions()
            active_exchange_positions = [p for p in positions if float(p['contracts']) != 0]
            
            # Конвертировать в наш формат
            exchange_symbols = set()
            for pos in active_exchange_positions:
                symbol_ccxt = pos['symbol']
                if ':USDT' not in symbol_ccxt:
                    continue
                base_quote = symbol_ccxt.split(':')[0]
                symbol = base_quote.replace('/', '_')
                if symbol in configured_symbols:
                    exchange_symbols.add(symbol)
                    
            # Загрузить состояние
            with open(self.state_file, 'r') as f:
                state = json.load(f)
                
            active_positions = state.get('active_positions', {})
            symbols_data = state.get('symbols', {})
            
            # Найти и удалить призрачные позиции
            ghost_positions = []
            for symbol in list(active_positions.keys()):
                if symbol not in exchange_symbols:
                    ghost_positions.append(symbol)
                    
            # Также проверяем позиции в секции symbols
            ghost_in_symbols = []
            for symbol, symbol_data in symbols_data.items():
                if symbol_data.get('active_position') is not None:
                    if symbol not in exchange_symbols:
                        ghost_in_symbols.append(symbol)
                        
            # Объединяем списки призрачных позиций
            all_ghost_positions = list(set(ghost_positions + ghost_in_symbols))
                    
            if all_ghost_positions:
                logger.warning(f"🗑️ Найдены призрачные позиции: {all_ghost_positions}")
                logger.info(f"   - В active_positions: {ghost_positions}")
                logger.info(f"   - В symbols: {ghost_in_symbols}")
                
                for symbol in all_ghost_positions:
                    # Удаляем из active_positions
                    if symbol in active_positions:
                        del active_positions[symbol]
                        logger.info(f"🗑️ Удалена позиция из active_positions: {symbol}")
                    
                    # Очищаем в symbols
                    if symbol in symbols_data and symbols_data[symbol].get('active_position') is not None:
                        symbols_data[symbol]['active_position'] = None
                        logger.info(f"🗑️ Очищена позиция в symbols: {symbol}")
                        
                # Сохранить исправленное состояние
                state['active_positions'] = active_positions
                state['symbols'] = symbols_data
                state['metadata']['last_updated'] = datetime.utcnow().isoformat()
                state['metadata']['ghost_positions_fixed'] = True
                state['metadata']['fix_timestamp'] = time.time()
                
                with open(self.state_file, 'w') as f:
                    json.dump(state, f, indent=2)
                    
                self.fixes_applied.append({
                    'type': 'ghost_positions',
                    'symbols': all_ghost_positions,
                    'timestamp': datetime.utcnow().isoformat()
                })
                
                logger.info(f"✅ Удалены призрачные позиции: {all_ghost_positions}")
                return True
            else:
                logger.info("✅ Призрачные позиции не найдены")
                return True
                
        except Exception as e:
            logger.error(f"❌ Ошибка исправления призрачных позиций: {e}")
            return False
            
    def fix_missing_positions(self, configured_symbols: List[str]) -> bool:
        """Исправить отсутствующие позиции (есть на бирже, но нет в состоянии)"""
        try:
            if not self.exchange:
                logger.warning("⚠️ Нет подключения к бирже - пропуск исправления отсутствующих позиций")
                return True
                
            # Создать резервную копию
            if not self.backup_created:
                self.create_backup()
                
            # Получить позиции с биржи
            positions = self.exchange.fetch_positions()
            active_exchange_positions = [p for p in positions if float(p['contracts']) != 0]
            
            # Загрузить состояние
            with open(self.state_file, 'r') as f:
                state = json.load(f)
                
            active_positions = state.get('active_positions', {})
            symbols_data = state.get('symbols', {})
            
            # Найти отсутствующие позиции
            missing_positions = []
            for pos in active_exchange_positions:
                symbol_ccxt = pos['symbol']
                if ':USDT' not in symbol_ccxt:
                    continue
                    
                base_quote = symbol_ccxt.split(':')[0]
                symbol = base_quote.replace('/', '_')
                
                # Проверяем что позиции действительно нет В ОБЕИХ секциях
                has_active_pos = symbol in active_positions
                has_symbols_pos = (symbol in symbols_data and 
                                 symbols_data[symbol].get('active_position') is not None)
                
                if symbol in configured_symbols and not has_active_pos and not has_symbols_pos:
                    missing_positions.append({
                        'symbol': symbol,
                        'side': 'LONG' if pos['side'] == 'long' else 'SHORT',
                        'entry': float(pos['entryPrice']),
                        'qty': abs(float(pos['contracts'])),
                        'unrealized_pnl': float(pos['unrealizedPnl'])
                    })
                    
            if missing_positions:
                logger.warning(f"🔍 Найдены отсутствующие позиции: {[p['symbol'] for p in missing_positions]}")
                
                for pos_info in missing_positions:
                    symbol = pos_info['symbol']
                    
                    # Создать базовую информацию о позиции
                    position_data = {
                        'symbol': symbol,
                        'side': pos_info['side'],
                        'entry': pos_info['entry'],
                        'qty': pos_info['qty'],
                        'sl_initial': pos_info['entry'] * (0.98 if pos_info['side'] == 'LONG' else 1.02),
                        'sl_current': pos_info['entry'] * (0.98 if pos_info['side'] == 'LONG' else 1.02),
                        'atr': pos_info['entry'] * 0.02,  # 2% fallback
                        'timestamp': time.time(),
                        'order_id': None,
                        'trailing_active': False,
                        'unrealized_pnl': pos_info['unrealized_pnl'],
                        'peak_pnl_usdt': 0.0,
                        'synced_from_exchange': True,
                        'auto_fixed': True
                    }
                    
                    # Добавить в состояние
                    active_positions[symbol] = position_data
                    
                    # Обновить symbols секцию
                    if symbol not in symbols_data:
                        symbols_data[symbol] = {}
                    symbols_data[symbol]['active_position'] = position_data
                    
                # Сохранить исправленное состояние
                state['active_positions'] = active_positions
                state['symbols'] = symbols_data
                state['metadata']['last_updated'] = datetime.utcnow().isoformat()
                state['metadata']['missing_positions_fixed'] = True
                state['metadata']['fix_timestamp'] = time.time()
                
                with open(self.state_file, 'w') as f:
                    json.dump(state, f, indent=2)
                    
                self.fixes_applied.append({
                    'type': 'missing_positions',
                    'positions': missing_positions,
                    'timestamp': datetime.utcnow().isoformat()
                })
                
                logger.info(f"✅ Добавлены отсутствующие позиции: {[p['symbol'] for p in missing_positions]}")
                return True
            else:
                logger.info("✅ Отсутствующие позиции не найдены")
                return True
                
        except Exception as e:
            logger.error(f"❌ Ошибка исправления отсутствующих позиций: {e}")
            return False
            
    def fix_state_inconsistencies(self, configured_symbols: List[str]) -> bool:
        """Исправить несоответствия в состоянии"""
        try:
            # Создать резервную копию
            if not self.backup_created:
                self.create_backup()
                
            validator = StateValidator(self.state_file, self.exchange)
            fixed = validator.fix_state_inconsistencies(configured_symbols)
            
            if fixed:
                self.fixes_applied.append({
                    'type': 'state_inconsistencies',
                    'timestamp': datetime.utcnow().isoformat()
                })
                logger.info("✅ Исправлены несоответствия в состоянии")
                
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка исправления несоответствий: {e}")
            return False
            
    def fix_corrupted_state_file(self) -> bool:
        """Исправить поврежденный файл состояния"""
        try:
            # Создать резервную копию поврежденного файла
            if os.path.exists(self.state_file):
                # Создаем папку для бэкапов
                backup_dir = os.path.join(os.path.dirname(self.state_file), 'backups')
                os.makedirs(backup_dir, exist_ok=True)
                
                timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
                filename = os.path.basename(self.state_file)
                corrupted_backup = os.path.join(backup_dir, f"{filename}.corrupted.{timestamp}")
                shutil.copy2(self.state_file, corrupted_backup)
                logger.info(f"💾 Поврежденный файл сохранен как: {corrupted_backup}")
                
            # Создать новый чистый файл состояния
            clean_state = {
                'metadata': {
                    'version': 'v1.6-TXB',
                    'created': datetime.utcnow().isoformat(),
                    'last_updated': datetime.utcnow().isoformat(),
                    'recovery_mode': True,
                    'auto_fixed': True,
                    'fix_reason': 'corrupted_state_file'
                },
                'symbols': {},
                'signals_history': [],
                'performance': {'total_signals': 0, 'total_trades': 0},
                'active_positions': {}
            }
            
            with open(self.state_file, 'w') as f:
                json.dump(clean_state, f, indent=2)
                
            self.fixes_applied.append({
                'type': 'corrupted_state_file',
                'timestamp': datetime.utcnow().isoformat()
            })
            
            logger.info("✅ Создан новый чистый файл состояния")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка исправления поврежденного файла: {e}")
            return False
            
    def run_auto_fix(self, configured_symbols: List[str]) -> Dict[str, Any]:
        """Запустить автоматическое исправление"""
        logger.info("🔧 Запуск автоматического исправления...")
        
        start_time = time.time()
        results = {
            'timestamp': datetime.utcnow().isoformat(),
            'fixes_applied': [],
            'success': True,
            'errors': []
        }
        
        try:
            # 1. Проверить, существует ли файл состояния
            if not os.path.exists(self.state_file):
                logger.warning("⚠️ Файл состояния не найден, будет создан новый")
                self.fix_corrupted_state_file()
                results['fixes_applied'].append('created_missing_state_file')
                
            # 2. Проверить, не поврежден ли файл
            try:
                with open(self.state_file, 'r') as f:
                    json.load(f)
            except (json.JSONDecodeError, IOError):
                logger.warning("⚠️ Файл состояния поврежден, создается новый")
                self.fix_corrupted_state_file()
                results['fixes_applied'].append('fixed_corrupted_state_file')
                
            # 3. Исправить призрачные позиции
            if self.fix_ghost_positions(configured_symbols):
                if any(fix['type'] == 'ghost_positions' for fix in self.fixes_applied):
                    results['fixes_applied'].append('ghost_positions')
            else:
                results['errors'].append('Failed to fix ghost positions')
                
            # 4. Исправить отсутствующие позиции
            if self.fix_missing_positions(configured_symbols):
                if any(fix['type'] == 'missing_positions' for fix in self.fixes_applied):
                    results['fixes_applied'].append('missing_positions')
            else:
                results['errors'].append('Failed to fix missing positions')
                
            # 5. Исправить несоответствия в состоянии
            if self.fix_state_inconsistencies(configured_symbols):
                if any(fix['type'] == 'state_inconsistencies' for fix in self.fixes_applied):
                    results['fixes_applied'].append('state_inconsistencies')
            else:
                results['errors'].append('Failed to fix state inconsistencies')
                
            # 6. Финальная валидация
            validator = StateValidator(self.state_file, self.exchange)
            validation_result = validator.run_full_validation(configured_symbols)
            
            if not validation_result['overall_valid']:
                results['errors'].extend(validation_result.get('state_errors', []))
                results['errors'].extend(validation_result.get('exchange_errors', []))
                
            results['validation_result'] = validation_result
            results['success'] = len(results['errors']) == 0
            results['fixes_applied'] = self.fixes_applied
            results['duration'] = time.time() - start_time
            
            if results['success']:
                logger.info("✅ Автоматическое исправление завершено успешно")
            else:
                logger.warning(f"⚠️ Автоматическое исправление завершено с ошибками: {results['errors']}")
                
            return results
            
        except Exception as e:
            logger.error(f"❌ Критическая ошибка автоматического исправления: {e}")
            results['success'] = False
            results['errors'].append(str(e))
            results['duration'] = time.time() - start_time
            return results
            
    def get_fix_summary(self) -> Dict[str, Any]:
        """Получить сводку исправлений"""
        return {
            'total_fixes': len(self.fixes_applied),
            'fixes_by_type': {},
            'backup_created': self.backup_created,
            'fixes_applied': self.fixes_applied
        }
