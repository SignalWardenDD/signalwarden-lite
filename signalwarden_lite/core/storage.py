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
        """Read entire storage"""
        with open(self.path, 'r') as f:
            return json.load(f)
    
    def write(self, data: Dict[str, Any]):
        """Write entire storage atomically"""
        # Ensure metadata exists
        if 'metadata' not in data:
            data['metadata'] = {
                'version': 'v1.6-TXB',
                'created': datetime.utcnow().isoformat()
            }
        
        data['metadata']['last_updated'] = datetime.utcnow().isoformat()
        tmp_path = self.path + '.tmp'
        with open(tmp_path, 'w') as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, self.path)
    
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