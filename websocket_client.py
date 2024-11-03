import websocket
import json
import time
import requests
from datetime import datetime
import indicators

# Configuration
SYMBOLS = ['INJ_USDT']
TIMEFRAMES = ['1m', '5m', '15m']
CANDLE_INTERVALS = {
    '1m': 'Min1',
    '5m': 'Min5',
    '15m': 'Min15'
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
    api_symbol = symbol  # Keep INJ_USDT as is
    now = int(time.time())
    five_hours_ago = now - (5 * 60 * 60)
    
    url = f"https://contract.mexc.com/api/v1/contract/kline/{api_symbol}?interval=Min1&start={five_hours_ago}&end={now}"
    
    try:
        print('Query:', url)
        response = requests.get(url)
        data = response.json()
        
        # Log the raw response structure
        print('Raw response data:', json.dumps(data, indent=2))
        
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
        message = json.loads(message)
        
        if message.get('channel') == "pong":
            print('Received pong:', message.get('data'))
            return

        if message.get('data') and message['data'].get('lastPrice'):
            processed_data = {
                's': message.get('symbol'),
                't': message['data'].get('timestamp'),
                'c': str(message['data'].get('lastPrice'))
            }
            update_candles(processed_data)
    except Exception as error:
        print('Error processing message:', error)

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
    websocket.enableTrace(True)
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
            
            # Calculate the candle start time (floor to the nearest interval)
            interval_seconds = int(timeframe[:-1]) * 60  # Convert '1m' to 60 seconds, '5m' to 300 seconds, etc.
            candle_start = (timestamp // (interval_seconds * 1000)) * (interval_seconds * 1000)
            
            if not candles or candles[0]['timestamp'] < candle_start:
                # Create a new candle
                new_candle = {
                    'timestamp': candle_start,
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
        
        # Calculate WaveTrend using the existing method
        wt_results = indicators.indicators.calculate_wave_trend(candles)
        
        # Debug print
        print(f"\nWaveTrend Results for {symbol} {timeframe}:")
        print(f"WT1: {wt_results['wt1']:.2f}")
        print(f"WT2: {wt_results['wt2']:.2f}")
        
        # Store results in the latest candle
        if candles:
            candles[0]['wt1'] = wt_results['wt1']
            candles[0]['wt2'] = wt_results['wt2']
            candles[0]['overbought1'] = wt_results['overbought1']
            candles[0]['overbought2'] = wt_results['overbought2']
            candles[0]['oversold1'] = wt_results['oversold1']
            candles[0]['oversold2'] = wt_results['oversold2']
            candles[0]['cross_over'] = wt_results['cross_over']
            candles[0]['cross_under'] = wt_results['cross_under']
            
            # Print signal conditions
            if wt_results['cross_over']:
                print(f"\n🔵 BULLISH SIGNAL: WaveTrend Cross Over for {symbol} {timeframe}")
            elif wt_results['cross_under']:
                print(f"\n🔴 BEARISH SIGNAL: WaveTrend Cross Under for {symbol} {timeframe}")
            
            if wt_results['overbought1']:
                print(f"⚠️ OVERBOUGHT Level 1: {symbol} {timeframe}")
            elif wt_results['oversold1']:
                print(f"⚠️ OVERSOLD Level 1: {symbol} {timeframe}")
        
    except Exception as error:
        print(f"Error calculating WaveTrend indicators: {error}")

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