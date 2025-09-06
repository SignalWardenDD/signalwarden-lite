import json
import os
from typing import Dict, Any

class JSONStore:
    """Simple JSON-based storage for trading state"""
    
    def __init__(self, path: str):
        self.path = path
        if not os.path.exists(self.path):
            with open(self.path, 'w') as f:
                json.dump({}, f)
    
    def read(self) -> Dict[str, Any]:
        """Read entire storage"""
        with open(self.path, 'r') as f:
            return json.load(f)
    
    def write(self, data: Dict[str, Any]):
        """Write entire storage atomically"""
        tmp_path = self.path + '.tmp'
        with open(tmp_path, 'w') as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, self.path)
    
    def update_symbol(self, symbol: str, payload: Dict[str, Any]):
        """Update data for specific symbol"""
        db = self.read()
        db[symbol] = payload
        self.write(db)
    
    def get_symbol(self, symbol: str) -> Dict[str, Any]:
        """Get data for specific symbol"""
        return self.read().get(symbol, {})
