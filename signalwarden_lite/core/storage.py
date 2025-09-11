import json
import os
from typing import Dict, Any, List
from datetime import datetime

class JSONStore:
    """Enhanced JSON-based storage for trading state v1.6-TXB"""
    
    def __init__(self, path: str):
        self.path = path
        if not os.path.exists(self.path):
            with open(self.path, 'w') as f:
                json.dump({
                    'metadata': {
                        'version': 'v1.6-TXB',
                        'created': datetime.utcnow().isoformat(),
                        'last_updated': datetime.utcnow().isoformat()
                    },
                    'symbols': {},
                    'signals_history': [],
                    'performance': {
                        'total_signals': 0,
                        'total_trades': 0,
                        'session_start': datetime.utcnow().isoformat()
                    }
                }, f, indent=2)
    
    def read(self) -> Dict[str, Any]:
        """Read entire storage with corruption recovery"""
        try:
            with open(self.path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError, IOError) as e:
            print(f"⚠️ Storage file corrupted or missing: {e}")
            
            # Try to backup corrupted file
            if os.path.exists(self.path):
                # Создаем папку для бэкапов
                backup_dir = os.path.join(os.path.dirname(self.path), 'backups')
                os.makedirs(backup_dir, exist_ok=True)
                
                filename = os.path.basename(self.path)
                backup_path = os.path.join(backup_dir, f"{filename}.corrupted.{int(datetime.utcnow().timestamp())}")
                try:
                    os.rename(self.path, backup_path)
                    print(f"💾 Corrupted file backed up as: {backup_path}")
                except:
                    pass
            
            # Create new minimal state
            minimal_state = {
                'metadata': {
                    'version': 'v1.6-TXB',
                    'created': datetime.utcnow().isoformat(),
                    'last_updated': datetime.utcnow().isoformat(),
                    'recovery_mode': True,
                    'recovery_reason': str(e)
                },
                'symbols': {},
                'signals_history': [],
                'performance': {'total_signals': 0, 'total_trades': 0}
            }
            
            # Write minimal state
            try:
                with open(self.path, 'w') as f:
                    json.dump(minimal_state, f, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                print(f"✅ Created new clean storage file")
            except Exception as e2:
                print(f"❌ Critical: Could not create new storage: {e2}")
                raise e2
                
            return minimal_state
    
    def write(self, data: Dict[str, Any]):
        """Write entire storage atomically with corruption protection"""
        try:
            # Ensure metadata exists
            if 'metadata' not in data:
                data['metadata'] = {
                    'version': 'v1.6-TXB',
                    'created': datetime.utcnow().isoformat()
                }
            
            data['metadata']['last_updated'] = datetime.utcnow().isoformat()
            
            # Validate JSON serializability before writing
            json_str = json.dumps(data, indent=2)
            
            # Write to temporary file first
            tmp_path = self.path + '.tmp'
            with open(tmp_path, 'w') as f:
                f.write(json_str)
                f.flush()  # Ensure data is written to disk
                os.fsync(f.fileno())  # Force OS to write to disk
            
            # Verify the temporary file is valid JSON
            with open(tmp_path, 'r') as f:
                json.load(f)  # This will raise an exception if JSON is invalid
            
            # Atomically replace the original file
            os.replace(tmp_path, self.path)
            
        except Exception as e:
            # Clean up temporary file if it exists
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except:
                    pass
            
            # Log error but don't crash the system
            print(f"❌ JSON write error: {e}")
            
            # Try to create a minimal valid state file
            try:
                minimal_state = {
                    'metadata': {
                        'version': 'v1.6-TXB',
                        'created': datetime.utcnow().isoformat(),
                        'last_updated': datetime.utcnow().isoformat(),
                        'recovery_mode': True,
                        'original_error': str(e)
                    },
                    'symbols': {},
                    'signals_history': [],
                    'performance': {'total_signals': 0, 'total_trades': 0}
                }
                
                with open(self.path, 'w') as f:
                    json.dump(minimal_state, f, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                    
                print(f"✅ Created minimal recovery state file")
                
            except Exception as e2:
                print(f"❌ Critical: Could not create recovery file: {e2}")
                raise e2
    
    def update_symbol(self, symbol: str, payload: Dict[str, Any]):
        """Update data for specific symbol"""
        db = self.read()
        if 'symbols' not in db:
            db['symbols'] = {}
        db['symbols'][symbol] = payload
        self.write(db)
    
    def get_symbol(self, symbol: str) -> Dict[str, Any]:
        """Get data for specific symbol"""
        db = self.read()
        return db.get('symbols', {}).get(symbol, {})
        
    def add_signal(self, symbol: str, signal_data: Dict[str, Any]):
        """Add signal to history"""
        db = self.read()
        if 'signals_history' not in db:
            db['signals_history'] = []
            
        signal_entry = {
            'symbol': symbol,
            'timestamp': signal_data['timestamp'],
            'signal': signal_data['signal'],
            'result': signal_data['result'],
            'datetime': datetime.fromtimestamp(signal_data['timestamp']).isoformat()
        }
        
        db['signals_history'].append(signal_entry)
        
        # Keep only last 1000 signals
        if len(db['signals_history']) > 1000:
            db['signals_history'] = db['signals_history'][-1000:]
            
        # Update performance counters
        if 'performance' not in db:
            db['performance'] = {'total_signals': 0, 'total_trades': 0}
            
        db['performance']['total_signals'] += 1
        if "✅" in signal_data['result']:
            db['performance']['total_trades'] += 1
            
        self.write(db)
        
    def get_recent_signals(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent signals"""
        db = self.read()
        signals = db.get('signals_history', [])
        return signals[-limit:] if signals else []
        
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        db = self.read()
        return db.get('performance', {})