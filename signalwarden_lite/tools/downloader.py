import os, time, argparse, ccxt, pandas as pd
from datetime import datetime

def ccxt_symbol(sym: str) -> str:
    """Convert symbol format: ADA_USDT -> ADA/USDT:USDT"""
    # If already in CCXT format, return as-is
    if '/' in sym and ':' in sym:
        return sym
        
    # If contains underscore, convert from our format
    if '_' in sym:
        parts = sym.split('_')
        if len(parts) == 2:
            base, quote = parts
            return f"{base}/{quote}:{quote}"  # USDT-M futures notation
        else:
            raise ValueError(f"Invalid symbol format: {sym}")
    
    # If no underscore, assume it's already in some other format
    return sym

def fetch_ohlcv_paginated(ex, symbol_ccxt: str, timeframe: str, start_ms: int, end_ms: int,
                          limit: int = 1500, pause_ms: int = 200) -> pd.DataFrame:
    """Fetch OHLCV data with pagination"""
    print(f"   Fetching {symbol_ccxt} {timeframe} from {datetime.fromtimestamp(start_ms/1000)} to {datetime.fromtimestamp(end_ms/1000)}")
    
    rows, since = [], start_ms
    total_requests = 0
    
    while since < end_ms:
        try:
            batch = ex.fetch_ohlcv(symbol_ccxt, timeframe, since=since, limit=limit)
            total_requests += 1
            
            if not batch:
                print(f"   No more data at {datetime.fromtimestamp(since/1000)}")
                break
            
            df = pd.DataFrame(batch, columns=['timestamp','open','high','low','close','volume'])
            rows.append(df)
            
            last_ts = int(df['timestamp'].iloc[-1])
            if last_ts >= end_ms:
                print(f"   Reached end timestamp at {datetime.fromtimestamp(last_ts/1000)}")
                break
            
            # Move to next batch
            if timeframe == '1h':
                since = last_ts + (60 * 60 * 1000)  # +1 hour
            elif timeframe == '15m':
                since = last_ts + (15 * 60 * 1000)  # +15 minutes
            else:
                since = last_ts + 1
            
            if total_requests % 10 == 0:
                print(f"   Progress: {total_requests} requests, current: {datetime.fromtimestamp(last_ts/1000)}")
            
            time.sleep(pause_ms / 1000.0)
            
        except Exception as e:
            print(f"   Error at {datetime.fromtimestamp(since/1000)}: {e}")
            time.sleep(1.0)
            continue
    
    if not rows:
        print(f"   WARNING: No data retrieved for {symbol_ccxt} {timeframe}")
        return pd.DataFrame(columns=['timestamp','open','high','low','close','volume'])
    
    # Combine and clean data
    out = pd.concat(rows, ignore_index=True)
    out = out.drop_duplicates('timestamp').sort_values('timestamp').reset_index(drop=True)
    
    # Filter to exact period
    out = out[(out['timestamp'] >= start_ms) & (out['timestamp'] <= end_ms)]
    
    # Convert timestamp to seconds
    out['timestamp'] = (out['timestamp'] // 1000).astype(int)
    
    print(f"   ✅ Retrieved {len(out)} bars for {symbol_ccxt} {timeframe}")
    return out

def main():
    ap = argparse.ArgumentParser(description="Download historical OHLCV data from Binance USDM futures")
    ap.add_argument('--symbols', nargs='+', required=True, help="Symbols to download (e.g., ADA_USDT LTC_USDT)")
    ap.add_argument('--timeframes', nargs='+', default=['1h','15m'], help="Timeframes to download")
    ap.add_argument('--start', required=True, help="Start date YYYY-MM-DD")
    ap.add_argument('--end', required=True, help="End date YYYY-MM-DD")
    ap.add_argument('--out', default='./data/historical_candles', help="Output directory")
    args = ap.parse_args()

    # Create output directory
    os.makedirs(args.out, exist_ok=True)
    
    # Initialize exchange
    ex = ccxt.binanceusdm({
        'enableRateLimit': True, 
        'options': {'defaultType': 'future'},
        'timeout': 30000
    })
    
    try:
        ex.load_markets()
        print(f"✅ Connected to Binance USDM futures")
    except Exception as e:
        print(f"❌ Failed to connect to exchange: {e}")
        return

    # Convert dates to timestamps
    start_ms = int(pd.Timestamp(args.start, tz='UTC').timestamp() * 1000)
    end_ms = int(pd.Timestamp(args.end, tz='UTC').timestamp() * 1000)
    
    print(f"📅 Period: {args.start} to {args.end}")
    print(f"🎯 Symbols: {args.symbols}")
    print(f"📊 Timeframes: {args.timeframes}")

    # Download data for each symbol and timeframe
    for sym in args.symbols:
        for tf in args.timeframes:
            try:
                print(f"\n📥 Processing {sym} {tf}...")
                
                cc_symbol = ccxt_symbol(sym)
                df = fetch_ohlcv_paginated(ex, cc_symbol, tf, start_ms, end_ms)
                
                if df.empty:
                    print(f"⚠️ No data retrieved for {sym} {tf}")
                    continue
                
                # Save to pickle
                output_path = os.path.join(args.out, f"{sym}_{tf}.pkl")
                df.to_pickle(output_path)
                
                print(f"💾 Saved: {output_path} ({len(df)} bars)")
                print(f"   Period: {datetime.fromtimestamp(df['timestamp'].min())} - {datetime.fromtimestamp(df['timestamp'].max())}")
                
            except Exception as e:
                print(f"❌ Failed to process {sym} {tf}: {e}")
                continue
    
    print("\n🎉 Download completed!")

if __name__ == '__main__':
    main()
