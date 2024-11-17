import websocket
import json
import time
import requests
from datetime import datetime
import indicators
import asyncio
import websocket_server
# Configuration
SYMBOLS = [
'INJ_USDT'
'BTC_USDT',
'ETH_USDT',
'SOL_USDT',
'XRP_USDT',
'ADA_USDT',
'DOT_USDT',
'AVAX_USDT',
'DOGE_USDT',
'LTC_USDT',
'LINK_USDT',
'UNI_USDT',
'BCH_USDT',
'EOS_USDT',
'XLM_USDT',
'TRX_USDT',
'ETC_USDT',
 'WLD_USDT',
'JASMY_USDT',
'POPCAT_USDT',
 'HOT_USDT',
'PEPE_USDT',
'TOKEN_USDT',
 'TURBO_USDT',
'RARE_USDT',
'CRV_USDT',
'RENDER_USDT',
'TAO_USDT',
'ZEC_USDT',
'CAT_USDT',
'CLOUD_USDT',
"VELO_USDT",
"LUNA_USDT",
"TON_USDT",
"PORTAL_USDT",
"NOT_USDT",
"MBL_USDT",
"CHZ_USDT",
"XLM_USDT",
"VANRY_USDT",
"RUNE_USDT",
"MEW_USDT",
"MKR_USDT",
"SOL_USDT",
"FET_USDT",
"HOOK_USDT",
"XAI_USDT",
"WIF_USDT",
"OP_USDT",
"TIA_USDT",
"ENA_USDT",
"WOO_USDT",
"GALA_USDT",
"WUSDT",
 "EGLD_USDT"
]

TIMEFRAMES = ['1m', '5m', '15m', '1h', '4h']
CANDLE_INTERVALS = {
    '1m': 'Min1',
    '5m': 'Min5',
    '15m': 'Min15',
    '1h': 'Min60',
    '4h': 'Hour4'
}

# Data structure to store candles
candle_store = {}

def convert_symbol_format(symbol, to_websocket=False):
    if to_websocket:
        return symbol.replace('_', '')  # INJ_USDT -> INJUSDT
    else:
        return symbol  # Keep original format since MEXC already uses INJ_USDT

# Initialize candle store structure
for symbol in SYMBOLS:
    candle_store[symbol] = {}
    for timeframe in TIMEFRAMES:
        candle_store[symbol][timeframe] = []

async def fetch_historical_candles(symbol, timeframe):
    api_symbol = symbol
    now = int(time.time())
    
    # Adjust the lookback period based on timeframe
    hours_lookback = {
        '1m': 5,    # 5 hours = 300 candles for 1m
        '5m': 24,   # 24 hours = 288 candles for 5m
        '15m': 48,  # 48 hours = 192 candles for 15m
        '1h': 168,  # 7 days = 168 candles for 1h
        '4h': 480   # 20 days = 120 candles for 4h
    }
    
    period = hours_lookback[timeframe] * 60 * 60  # Convert hours to seconds
    start_time = now - period
    
    interval = CANDLE_INTERVALS[timeframe]
    url = f"https://contract.mexc.com/api/v1/contract/kline/{api_symbol}?interval={interval}&start={start_time}&end={now}"
    
    try:
        #print('Query:', url)
        response = requests.get(url)
        data = response.json()
        
        # Log the raw response structure
        #print('Raw response data:', json.dumps(data, indent=2))
        
        # The response has arrays for each field
        time_data = data['data']['time']
        open_data = data['data']['open']
        high_data = data['data']['high']
        low_data = data['data']['low']
        close_data = data['data']['close']
        vol_data = data['data']['vol']
        
        # Create candles by combining the arrays
        candles = [
            {
                'timestamp': int(t) * 1000,
                'open': float(o),
                'high': float(h),
                'low': float(l),
                'close': float(c),
                'volume': float(v)
            }
            for t, o, h, l, c, v in zip(time_data, open_data, high_data, low_data, close_data, vol_data)
        ]
        
        print(f"Processed {len(candles)} candles for {symbol} {timeframe}")
        
        # Sort candles by timestamp in descending order (newest first)
        candles.sort(key=lambda x: x['timestamp'], reverse=True)
        candle_store[symbol][timeframe] = candles
        
    except Exception as error:
        print(f"Error fetching historical candles for {symbol} {timeframe}:", str(error))

# WebSocket connection handling
ws = None

def on_message(ws, message):
    try:
        message_data = json.loads(message)
        
        if isinstance(message_data, str):
            message_data = json.loads(message_data)
        
        if message_data.get('channel') == "pong":
            print('Received pong:', message_data.get('data'))
            return

        if message_data.get('data') and message_data['data'].get('lastPrice'):
            # Get the current price and timestamp
            symbol = message_data.get('symbol')
            timestamp = message_data['data'].get('timestamp')
            price = float(message_data['data'].get('lastPrice'))
            
            # Update the latest candle with the new price
            for timeframe in TIMEFRAMES:
                if symbol in candle_store and timeframe in candle_store[symbol]:
                    candles = candle_store[symbol][timeframe]
                    if candles:
                        candles[0]['close'] = price
                        candles[0]['high'] = max(candles[0]['high'], price)
                        candles[0]['low'] = min(candles[0]['low'], price)
                        
                        # Calculate and broadcast indicators immediately
                        calculate_indicators(symbol, timeframe)
            
            # Also process regular candle updates
            processed_data = {
                's': symbol,
                't': timestamp,
                'c': str(price)
            }
            update_candles(processed_data)
            
    except json.JSONDecodeError as e:
        print(f'Error decoding JSON message: {e}')
    except Exception as error:
        print(f'Error processing message: {error}')
        print(f'Raw message: {message}')

def on_error(ws, error):
    print('WebSocket error:', error)

def on_close(ws, close_status_code, close_msg):
    print('WebSocket disconnected. Reconnecting...')
    time.sleep(5)
    initialize_websocket()

def on_open(ws):
    print('WebSocket connected')
    
    def send_ping():
        while True:
            if ws.sock and ws.sock.connected:
                ws.send(json.dumps({"method": "ping"}))
            time.sleep(15)
    
    # Start ping thread
    import threading
    ping_thread = threading.Thread(target=send_ping)
    ping_thread.daemon = True
    ping_thread.start()
    
    for pair in SYMBOLS:
        ticker_subscription = {
            "method": "sub.ticker",
            "param": {
                "symbol": pair
            }
        }
        print(f"Subscribing to ticker for {pair}:", ticker_subscription)
        ws.send(json.dumps(ticker_subscription))

def initialize_websocket():
    global ws
    websocket.enableTrace(False)
    ws = websocket.WebSocketApp(
        'wss://contract.mexc.com/edge',
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
        on_open=on_open
    )
    ws.run_forever()

def update_candles(ticker_data):
    try:
        symbol = convert_symbol_format(ticker_data['s'], to_websocket=False)
        timestamp = ticker_data['t']
        close_price = float(ticker_data['c'])
        
        # Process for each timeframe
        for timeframe in TIMEFRAMES:
            # Get the current candle list
            candles = candle_store[symbol][timeframe]
            
            # Convert timestamp to datetime for easier manipulation
            dt = datetime.fromtimestamp(timestamp / 1000)
            
            # Align timestamp to the correct interval
            if timeframe == '1m':
                # Round down to the nearest minute
                aligned_dt = dt.replace(second=0, microsecond=0)
            elif timeframe == '5m':
                # Round down to the nearest 5 minutes
                minutes = (dt.minute // 5) * 5
                aligned_dt = dt.replace(minute=minutes, second=0, microsecond=0)
            elif timeframe == '15m':
                # Round down to the nearest 15 minutes
                minutes = (dt.minute // 15) * 15
                aligned_dt = dt.replace(minute=minutes, second=0, microsecond=0)
            elif timeframe == '1h':
                # Round down to the nearest hour
                aligned_dt = dt.replace(minute=0, second=0, microsecond=0)
            elif timeframe == '4h':
                # Round down to the nearest 4-hour interval
                hour = (dt.hour // 4) * 4
                aligned_dt = dt.replace(hour=hour, minute=0, second=0, microsecond=0)
            
            # Convert back to milliseconds timestamp
            aligned_timestamp = int(aligned_dt.timestamp() * 1000)
            
            if not candles or candles[0]['timestamp'] < aligned_timestamp:
                # Create a new candle
                new_candle = {
                    'timestamp': aligned_timestamp,
                    'open': close_price,
                    'high': close_price,
                    'low': close_price,
                    'close': close_price,
                    'volume': 0  # Volume not available in ticker data
                }
                candles.insert(0, new_candle)
                
                # Calculate indicators for the new candle
                calculate_indicators(symbol, timeframe)
                
                # Keep only last 500 candles
                if len(candles) > 500:
                    candles.pop()
            else:
                # Update the current candle
                current_candle = candles[0]
                current_candle['close'] = close_price
                current_candle['high'] = max(current_candle['high'], close_price)
                current_candle['low'] = min(current_candle['low'], close_price)
                
                # Recalculate indicators for the updated candle
                calculate_indicators(symbol, timeframe)
                
    except Exception as error:
        print(f"Error updating candles: {error}")

def calculate_indicators(symbol, timeframe):
    try:
        # Get candles for the symbol and timeframe
        candles = candle_store[symbol][timeframe]
        
        # Calculate WaveTrend
        wt_results = indicators.indicators.calculate_wave_trend(candles)
        
        # Calculate RSI
        rsi_value = indicators.indicators.calculate_rsi(candles)
        
        # Store results in the latest candle
        if candles:
            candles[0]['wt1'] = wt_results['wt1']
            candles[0]['wt2'] = wt_results['wt2']
            candles[0]['rsi'] = float(rsi_value.iloc[-1]) if not rsi_value.empty else None
            
            # Create and broadcast WaveTrend message
            signals = {
                'type': 'indicators',
                'symbol': symbol,
                'timeframe': timeframe,
                'wt1': round(wt_results['wt1'], 2),
                'wt2': round(wt_results['wt2'], 2),
                'rsi': round(float(rsi_value.iloc[-1]), 2) if not rsi_value.empty else None,
                'price': round(float(candles[0]['close']), 4),  # Add current price from latest candle
                'timestamp': datetime.now().isoformat()
            }
            
            # Broadcast both messages separately
            asyncio.run(websocket_server.broadcast(json.dumps(signals)))
        
    except Exception as error:
        print(f"Error calculating indicators: {error}")

# Main execution
if __name__ == "__main__":
    # Fetch historical data for all symbols and timeframes
    import asyncio
    
    async def init_historical_data():
        tasks = []
        for symbol in SYMBOLS:
            for timeframe in TIMEFRAMES:
                tasks.append(fetch_historical_candles(symbol, timeframe))
        await asyncio.gather(*tasks)
    
    # Run historical data fetch
    asyncio.run(init_historical_data())
    
    # Start WebSocket connection
    initialize_websocket()