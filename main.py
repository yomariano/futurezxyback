import asyncio
import websocket_client
from indicators import indicators
import logging
import signal
import sys
import time
from datetime import datetime
from typing import Dict, Any
import json
import random

# Import the websocket_server module
import websocket_server

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trading_bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Global flag for graceful shutdown
is_running = True

class TradingBot:
    def __init__(self):
        self.last_calculation_time: Dict[str, Dict[str, float]] = {}
        for symbol in websocket_client.SYMBOLS:
            self.last_calculation_time[symbol] = {}
            for timeframe in websocket_client.TIMEFRAMES:
                self.last_calculation_time[symbol][timeframe] = 0
        self.stop_event = asyncio.Event()

    async def calculate_and_log_indicators(self, symbol: str, timeframe: str) -> None:
        """Calculate and log indicators for a specific symbol and timeframe"""
        try:
            wt = indicators.calculate_wave_trend(
                websocket_client.candle_store[symbol][timeframe]
            )
            
            # Log the Wave Trend signals
            logger.info(f"\nWave Trend Analysis for {symbol} {timeframe}:")
            logger.info(f"WT1: {wt['wt1']:.2f}")
            logger.info(f"WT2: {wt['wt2']:.2f}")
            
            # Broadcast the WT1 and WT2 values
            try:
                message = json.dumps({
                    'symbol': symbol,
                    'timeframe': timeframe,
                    'wt1': round(wt['wt1'], 2),
                    'wt2': round(wt['wt2'], 2),
                    'timestamp': datetime.now().isoformat()
                })
                logger.info(f"Preparing to broadcast: {message}")
                await websocket_server.broadcast(message)
            except Exception as broadcast_error:
                logger.error(f"Error broadcasting message: {broadcast_error}")
            
            # Log trading signals
            if wt['cross_over']:
                logger.info(f"🚀 BULLISH SIGNAL: Wave Trend Cross Over detected for {symbol}")
            elif wt['cross_under']:
                logger.info(f"🔻 BEARISH SIGNAL: Wave Trend Cross Under detected for {symbol}")
            
            # Log overbought/oversold conditions
            if wt['overbought1']:
                logger.info(f"⚠️ STRONG OVERBOUGHT: {symbol} is strongly overbought (Level 1)")
            elif wt['overbought2']:
                logger.info(f"⚠️ OVERBOUGHT: {symbol} is overbought (Level 2)")
            elif wt['oversold1']:
                logger.info(f"⚠️ STRONG OVERSOLD: {symbol} is strongly oversold (Level 1)")
            elif wt['oversold2']:
                logger.info(f"⚠️ OVERSOLD: {symbol} is oversold (Level 2)")

        except Exception as e:
            logger.error(f"Error calculating indicators for {symbol} {timeframe}: {str(e)}")

    async def periodic_calculation(self) -> None:
        """Periodically calculate indicators for all symbols and timeframes"""
        while is_running and not self.stop_event.is_set():
            try:
                current_time = time.time()
                
                for symbol in websocket_client.SYMBOLS:
                    for timeframe in websocket_client.TIMEFRAMES:
                        # Convert timeframe to seconds
                        interval_seconds = self.timeframe_to_seconds(timeframe)
                        
                        # Check if it's time to calculate
                        if (current_time - self.last_calculation_time[symbol][timeframe]) >= interval_seconds:
                            await self.calculate_and_log_indicators(symbol, timeframe)
                            self.last_calculation_time[symbol][timeframe] = current_time
                
                # Sleep for a short time to prevent CPU overuse
                await asyncio.sleep(1)
                
                # Check for stop event with timeout
                try:
                    await asyncio.wait_for(self.stop_event.wait(), timeout=1)
                except asyncio.TimeoutError:
                    continue
                    
            except Exception as e:
                logger.error(f"Error in periodic calculation: {str(e)}")
                await asyncio.sleep(5)

    @staticmethod
    def timeframe_to_seconds(timeframe: str) -> int:
        """Convert timeframe string to seconds"""
        timeframe_map = {
            '1m': 60,
            '5m': 300,
            '15m': 900,
            '1h': 3600,
            '4h': 14400,
            '1d': 86400,
            '1w': 604800
        }
        return timeframe_map.get(timeframe, 60)  # Default to 1 minute if timeframe not found

    async def initialize(self) -> None:
        """Initialize the trading bot"""
        logger.info("Initializing Trading Bot...")
        
        # Send a test message
        test_message = json.dumps({
            'symbol': 'TEST',
            'timeframe': '1m',
            'wt1': 0.00,
            'wt2': 0.00,
            'timestamp': datetime.now().isoformat(),
            'type': 'test_message'
        })
        logger.info("Sending test broadcast message")
        await websocket_server.broadcast(test_message)
        
        # Fetch historical data
        logger.info("Fetching historical data...")
        for symbol in websocket_client.SYMBOLS:
            for timeframe in websocket_client.TIMEFRAMES:
                logger.info(f"Fetching data for {symbol} {timeframe}")
                await websocket_client.fetch_historical_candles(symbol, timeframe)
                # Calculate initial indicators
                await self.calculate_and_log_indicators(symbol, timeframe)

    async def stop(self):
        """Stop the trading bot gracefully"""
        global is_running
        logger.info("Stopping trading bot...")
        is_running = False
        self.stop_event.set()

    async def periodic_test_broadcast(self) -> None:
        """Send periodic Wave Trend calculations for all symbols and timeframes"""
        while is_running and not self.stop_event.is_set():
            try:
                for symbol in websocket_client.SYMBOLS:
                    logger.info(f"\nChecking data for symbol: {symbol}")
                    for timeframe in websocket_client.TIMEFRAMES:
                        candles = websocket_client.candle_store[symbol][timeframe]
                        logger.info(f"Timeframe {timeframe}: {len(candles)} candles available")
                        
                        if candles:
                            latest_candle = candles[0]
                            
                            # Create message with all signals
                            message = {
                                'type': 'indicators',
                                'symbol': symbol,
                                'timeframe': timeframe,
                                'wt1': round(latest_candle.get('wt1', 0), 8),
                                'wt2': round(latest_candle.get('wt2', 0), 8),
                                'sma50': round(latest_candle.get('sma50', 0), 8),
                                'sma200': round(latest_candle.get('sma200', 0), 8),
                                'rsi': round(latest_candle.get('rsi', 0), 2),
                                'timestamp': datetime.now().isoformat(),
                                'price': round(latest_candle.get('close', 0), 8),
                                'signals': {
                                    # Existing signals
                                    'cross_over': bool(latest_candle.get('cross_over', False)),
                                    'cross_under': bool(latest_candle.get('cross_under', False)),
                                    'overbought': bool(latest_candle.get('overbought', False)),
                                    'oversold': bool(latest_candle.get('oversold', False)),
                                    'price_above_sma50': bool(latest_candle.get('price_above_sma50', False)),
                                    'price_above_sma200': bool(latest_candle.get('price_above_sma200', False)),
                                    'sma50_above_sma200': bool(latest_candle.get('sma50_above_sma200', False)),
                                    'bullish_divergence': bool(latest_candle.get('bullish_divergence', False)),
                                    'hidden_bullish_divergence': bool(latest_candle.get('hidden_bullish_divergence', False)),
                                    'bearish_divergence': bool(latest_candle.get('bearish_divergence', False)),
                                    'hidden_bearish_divergence': bool(latest_candle.get('hidden_bearish_divergence', False)),
                                    # New MA touch signals
                                    'price_touching_sma50_from_above': bool(latest_candle.get('price_touching_sma50_from_above', False)),
                                    'price_touching_sma50_from_below': bool(latest_candle.get('price_touching_sma50_from_below', False)),
                                    'price_touching_sma200_from_above': bool(latest_candle.get('price_touching_sma200_from_above', False)),
                                    'price_touching_sma200_from_below': bool(latest_candle.get('price_touching_sma200_from_below', False)),
                                    # New 3% margin signals
                                    'price_near_sma50_from_above': bool(latest_candle.get('price_near_sma50_from_above', False)),
                                    'price_near_sma50_from_below': bool(latest_candle.get('price_near_sma50_from_below', False)),
                                    'price_near_sma200_from_above': bool(latest_candle.get('price_near_sma200_from_above', False)),
                                    'price_near_sma200_from_below': bool(latest_candle.get('price_near_sma200_from_below', False))
                                },
                                # Add distance measurements
                                'distances': {
                                    'distance_to_sma50': round(latest_candle.get('distance_to_sma50', 0), 2),
                                    'distance_to_sma200': round(latest_candle.get('distance_to_sma200', 0), 2)
                                }
                            }
                            
                            logger.info(f"Broadcasting for {symbol} {timeframe}")
                            await websocket_server.broadcast(json.dumps(message))
                        else:
                            logger.warning(f"No candles available for {symbol} {timeframe}")
                            
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Error in indicator broadcast: {str(e)}")
                await asyncio.sleep(5)

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    global is_running
    logger.info("Received shutdown signal. Cleaning up...")
    is_running = False

async def main():
    try:
        # Register signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Try different ports if the default one is in use
        server = None
        ports = [8080, 8081, 8082, 8083]  # List of ports to try
        
        for port in ports:
            try:
                logger.info(f"Starting WebSocket server on port {port}...")
                server = await websocket_server.start_server(port=port)
                logger.info(f"WebSocket server successfully started on port {port}")
                break
            except OSError as e:
                if e.errno == 48:  # Address already in use
                    logger.warning(f"Port {port} is already in use, trying next port...")
                    continue
                raise  # Re-raise other OSErrors
        
        if server is None:
            raise RuntimeError("Could not find an available port for the WebSocket server")

        # Create and initialize trading bot
        bot = TradingBot()
        await bot.initialize()
        
        # Start all tasks
        tasks = [
            asyncio.create_task(bot.periodic_calculation()),
            asyncio.create_task(bot.periodic_test_broadcast()),
            asyncio.create_task(
                asyncio.to_thread(websocket_client.initialize_websocket)
            )
        ]
        
        # Wait for tasks to complete or for shutdown
        await asyncio.gather(*tasks, return_exceptions=True)
        
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        raise

if __name__ == "__main__":
    try:
        # Run the main function
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application terminated by user")
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        sys.exit(1)