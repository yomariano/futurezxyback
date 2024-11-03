import asyncio
import websocket_client
from indicators import indicators
import logging
import signal
import sys
import time
from datetime import datetime
from typing import Dict, Any

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
            wt = indicators.calculate_wave_trend_for_symbol(
                websocket_client.candle_store, 
                symbol, 
                timeframe
            )
            
            # Log the Wave Trend signals
            logger.info(f"\nWave Trend Analysis for {symbol} {timeframe}:")
            logger.info(f"WT1: {wt['wt1']:.2f}")
            logger.info(f"WT2: {wt['wt2']:.2f}")
            
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
        if timeframe == '1m':
            return 60
        elif timeframe == '5m':
            return 300
        elif timeframe == '15m':
            return 900
        else:
            return 60  # Default to 1 minute

    async def initialize(self) -> None:
        """Initialize the trading bot"""
        logger.info("Initializing Trading Bot...")
        
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
        
        # Create and initialize trading bot
        bot = TradingBot()
        await bot.initialize()
        
        # Start WebSocket connection
        logger.info("Initializing WebSocket connection...")
        websocket_task = asyncio.create_task(
            asyncio.to_thread(websocket_client.initialize_websocket)
        )
        
        # Start periodic calculations
        calculation_task = asyncio.create_task(bot.periodic_calculation())
        
        # Wait for tasks to complete
        await asyncio.gather(
            websocket_task,
            calculation_task,
            return_exceptions=True
        )
        
    except KeyboardInterrupt:
        logger.info("Shutting down gracefully...")
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        raise
    finally:
        logger.info("Cleanup complete. Exiting...")

if __name__ == "__main__":
    try:
        # Run the main function
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application terminated by user")
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        sys.exit(1)