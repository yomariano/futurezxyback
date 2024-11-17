import websocket
import json
import time
import requests
from datetime import datetime, timedelta
import indicators
import logging
from typing import List, Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
SYMBOLS = [
'INJ_USDT',
# 'BTC_USDT',
# 'ETH_USDT',
# 'SOL_USDT',
# 'XRP_USDT',
# 'ADA_USDT',
# 'DOT_USDT',
# 'AVAX_USDT',
# 'DOGE_USDT',
# 'LTC_USDT',
# 'LINK_USDT',
# 'UNI_USDT',
# 'BCH_USDT',
# 'EOS_USDT',
# 'XLM_USDT',
# 'TRX_USDT',
# 'ETC_USDT',
#  'WLD_USDT',
# 'JASMY_USDT',
# 'POPCAT_USDT',
#  'HOT_USDT',
# 'PEPE_USDT',
# 'TOKEN_USDT',
#  'TURBO_USDT',
# 'RARE_USDT',
# 'CRV_USDT',
# 'RENDER_USDT',
# 'TAO_USDT',
# 'ZEC_USDT',
# 'CAT_USDT',
# 'CLOUD_USDT',
# "VELO_USDT",
# "LUNA_USDT",
# "TON_USDT",
# "PORTAL_USDT",
# "NOT_USDT",
# "MBL_USDT",
# "CHZ_USDT",
# "XLM_USDT",
# "VANRY_USDT",
# "RUNE_USDT",
# "MEW_USDT",
# "MKR_USDT",
# "SOL_USDT",
# "FET_USDT",
# "HOOK_USDT",
# "XAI_USDT",
# "WIF_USDT",
# "OP_USDT",
# "TIA_USDT",
# "ENA_USDT",
# "WOO_USDT",
# "GALA_USDT",
# "WUSDT",
#  "EGLD_USDT"
]
TIMEFRAMES = ['1m', '5m', '15m', '1h', '4h', '1d', '1w']
#TIMEFRAMES = ['1m']
CANDLE_INTERVALS = {
    '1m': 'Min1',
    '5m': 'Min5',
    '15m': 'Min15',
    '1h': 'Min60',
    '4h': 'Hour4',
    '1d': 'Day1',
    '1w': 'Week1'
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
        '1m': 4,      # 200 candles * 1 min = 3.33 hours (rounded up)
        '5m': 17,     # 200 candles * 5 min = 16.67 hours (rounded up)
        '15m': 50,    # 200 candles * 15 min = 50 hours
        '1h': 200,    # 200 candles * 1 hour = 200 hours
        '4h': 800,    # 200 candles * 4 hours = 800 hours
        '1d': 4800,   # 200 candles * 24 hours = 4800 hours
        '1w': 33600   # 200 candles * 168 hours = 33600 hours
    }
    
    period = hours_lookback[timeframe] * 60 * 60  # Convert hours to seconds
    start_time = now - period
    
    interval = CANDLE_INTERVALS[timeframe]
    url = f"https://contract.mexc.com/api/v1/contract/kline/{api_symbol}?interval={interval}&start={start_time}&end={now}"
    
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
        
        logger.info(f"Fetched historical data for {symbol} {timeframe}:")
        logger.info(f"Number of candles: {len(candles)}")
        logger.info(f"First candle timestamp: {datetime.fromtimestamp(candles[0]['timestamp']/1000)}")
        logger.info(f"Last candle timestamp: {datetime.fromtimestamp(candles[-1]['timestamp']/1000)}")
        
    except Exception as error:
        print(f"Error fetching historical candles for {symbol} {timeframe}:", str(error))

# WebSocket connection handling
ws = None

def on_message(ws, message):
    try:
        # First try to parse the message
        if isinstance(message, str):
            try:
                message_data = json.loads(message)
            except json.JSONDecodeError:
                print('Received non-JSON string message:', message)
                return
        else:
            message_data = message

        # Handle subscription confirmation
        if message_data.get('channel') == 'rs.sub.ticker':
            print('Subscription confirmed:', message_data)
            return

        # Handle pong messages
        if message_data.get('channel') == "pong":
            print('Received pong:', message_data.get('data'))
            return

        # Handle ticker updates
        if message_data.get('data') and message_data['data'].get('lastPrice'):
            processed_data = {
                's': message_data.get('symbol'),
                't': message_data['data'].get('timestamp'),
                'c': str(message_data['data'].get('lastPrice'))
            }
            update_candles(processed_data)
    except Exception as error:
        print('Error processing message:', error)
        print('Raw message:', message)

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
                aligned_dt = dt.replace(second=0, microsecond=0)
            elif timeframe == '3m':
                # Round down to the nearest 3 minutes
                minutes = (dt.minute // 3) * 3
                aligned_dt = dt.replace(minute=minutes, second=0, microsecond=0)
                logger.info(f"3m aligned timestamp: {aligned_dt}")
            elif timeframe == '5m':
                minutes = (dt.minute // 5) * 5
                aligned_dt = dt.replace(minute=minutes, second=0, microsecond=0)
            elif timeframe == '15m':
                minutes = (dt.minute // 15) * 15
                aligned_dt = dt.replace(minute=minutes, second=0, microsecond=0)
            elif timeframe == '1h':
                aligned_dt = dt.replace(minute=0, second=0, microsecond=0)
            elif timeframe == '4h':
                hour = (dt.hour // 4) * 4
                aligned_dt = dt.replace(hour=hour, minute=0, second=0, microsecond=0)
            elif timeframe == '1d':
                aligned_dt = dt.replace(hour=0, minute=0, second=0, microsecond=0)
            elif timeframe == '1w':
                aligned_dt = dt.replace(hour=0, minute=0, second=0, microsecond=0)
                days_to_subtract = dt.weekday()
                aligned_dt = aligned_dt - timedelta(days=days_to_subtract)
            
            # Convert back to milliseconds timestamp
            aligned_timestamp = int(aligned_dt.timestamp() * 1000)
            
            if timeframe == '3m':
                logger.info(f"Current candles for 3m: {len(candles)}")
                if candles:
                    logger.info(f"Latest 3m candle timestamp: {datetime.fromtimestamp(candles[0]['timestamp']/1000)}")
                    logger.info(f"New aligned timestamp: {datetime.fromtimestamp(aligned_timestamp/1000)}")
            
            if not candles or candles[0]['timestamp'] < aligned_timestamp:
                # Create a new candle
                new_candle = aggregate_candle_data(timeframe, close_price, aligned_dt)
                candles.insert(0, new_candle)
                
                calculate_indicators(symbol, timeframe)
                
                if len(candles) > 500:
                    candles.pop()
            else:
                # Update the current candle
                current_candle = candles[0]
                updated_candle = aggregate_candle_data(timeframe, close_price, aligned_dt, current_candle)
                candles[0].update(updated_candle)
                                
    except Exception as error:
        logger.error(f"Error updating candles: {error}")

def calculate_indicators(symbol, timeframe):
    try:
        candles = candle_store[symbol][timeframe]
        
        indicator_values = {
            'wt1': 0,
            'wt2': 0,
            'sma50': 0,
            'sma200': 0,
            'rsi': 0,
            'price_above_sma50': False,
            'price_above_sma200': False,
            'sma50_above_sma200': False,
            'bullish_divergence': False,
            'hidden_bullish_divergence': False,
            'bearish_divergence': False,
            'hidden_bearish_divergence': False,
            # Touch signals
            'price_touching_sma50_from_above': False,
            'price_touching_sma50_from_below': False,
            'price_touching_sma200_from_above': False,
            'price_touching_sma200_from_below': False,
            # 3% margin signals
            'price_near_sma50_from_above': False,
            'price_near_sma50_from_below': False,
            'price_near_sma200_from_above': False,
            'price_near_sma200_from_below': False,
            # Distance to MAs (as percentage)
            'distance_to_sma50': 0,
            'distance_to_sma200': 0
        }
        
        # Define minimum candles needed for each timeframe
        min_candles = {
            '1m': 200,
            '5m': 200,
            '15m': 100,
            '1h': 50,
            '4h': 25,
            '1d': 20,
            '1w': 15
        }
        
        # Get minimum candles requirement for current timeframe
        required_candles = min_candles.get(timeframe, 200)
        
        if len(candles) >= required_candles:
            try:
                # Calculate RSI
                rsi_values = indicators.indicators.calculate_rsi(candles)
                if not rsi_values.empty:
                    indicator_values['rsi'] = round(rsi_values.iloc[-1], 2)
                    
                # Calculate RSI divergences
                rsi_results = indicators.indicators.calculate_rsi_divergences(candles)
                indicator_values.update(rsi_results)
            except Exception as e:
                logger.error(f"Error calculating RSI and Divergences: {e}")

            try:
                wt_results = indicators.indicators.calculate_wave_trend(candles)
                if wt_results:
                    indicator_values.update(wt_results)
            except Exception as e:
                logger.error(f"Error calculating Wave Trend: {e}")

            # try:
            #     ma_results = indicators.indicators.calculate_moving_averages(candles)
            #     indicator_values.update(ma_results)
                
            #     current_price = candles[0]['close']
            #     previous_price = candles[1]['close']
            #     sma50 = ma_results['sma50']
            #     sma200 = ma_results['sma200']
                
            #     # Define thresholds
            #     touch_threshold = 0.001  # 0.1%
            #     margin_threshold = 0.03  # 3%
                
            #     # Calculate distance to MAs as percentage
            #     distance_to_sma50 = (current_price - sma50) / sma50
            #     distance_to_sma200 = (current_price - sma200) / sma200
                
            #     indicator_values['distance_to_sma50'] = distance_to_sma50 * 100  # Store as percentage
            #     indicator_values['distance_to_sma200'] = distance_to_sma200 * 100  # Store as percentage
                
            #     # Check SMA50 touches and margin
            #     if abs(distance_to_sma50) < touch_threshold:
            #         if previous_price > sma50:
            #             indicator_values['price_touching_sma50_from_above'] = True
            #         elif previous_price < sma50:
            #             indicator_values['price_touching_sma50_from_below'] = True
                
            #     if abs(distance_to_sma50) < margin_threshold:
            #         if current_price > sma50:
            #             indicator_values['price_near_sma50_from_below'] = True
            #         else:
            #             indicator_values['price_near_sma50_from_above'] = True
                
            #     # Check SMA200 touches and margin
            #     if abs(distance_to_sma200) < touch_threshold:
            #         if previous_price > sma200:
            #             indicator_values['price_touching_sma200_from_above'] = True
            #         elif previous_price < sma200:
            #             indicator_values['price_touching_sma200_from_below'] = True
                
            #     if abs(distance_to_sma200) < margin_threshold:
            #         if current_price > sma200:
            #             indicator_values['price_near_sma200_from_below'] = True
            #         else:
            #             indicator_values['price_near_sma200_from_above'] = True
                
            # except Exception as e:
            #     logger.error(f"Error calculating Moving Averages: {e}")

        # Store results in the latest candle
        if candles:
            candles[0].update(indicator_values)
            # Send update via websocket
            send_indicator_update(symbol, timeframe, indicator_values)
        
    except Exception as error:
        logger.error(f"Error calculating indicators for {symbol} {timeframe}: {error}")
        # Don't re-raise the exception to prevent fatal errors
        return None

def aggregate_candle_data(timeframe, current_price, current_dt, previous_candle=None):
    """Aggregate candle data based on timeframe."""
    if previous_candle:
        return {
            'timestamp': previous_candle['timestamp'],
            'open': previous_candle['open'],
            'high': max(previous_candle['high'], current_price),
            'low': min(previous_candle['low'], current_price),
            'close': current_price,
            'volume': previous_candle['volume']  # Add volume if you're tracking it
        }
    else:
        return {
            'timestamp': int(current_dt.timestamp() * 1000),
            'open': current_price,
            'high': current_price,
            'low': current_price,
            'close': current_price,
            'volume': 0
        }

def send_indicator_update(symbol, timeframe, indicator_values):
    message = {
        "type": "indicators",
        "symbol": symbol,
        "timeframe": timeframe,
        "timestamp": datetime.now().isoformat(),
        "price": indicator_values.get('close', 0),
        **indicator_values
    }
    
    try:
        ws = websocket.create_connection("ws://localhost:8080")
        ws.send(json.dumps(message))
        ws.close()
    except Exception as e:
        logger.error(f"Error sending indicator update: {e}")

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