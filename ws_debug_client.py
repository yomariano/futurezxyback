import asyncio
import websockets
import json
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def connect_websocket():
    """Connect to WebSocket server and print received messages"""
    uri = "ws://localhost:8080"
    #uri = "wss://your-trading-bot.fly.dev"
    
    try:
        logger.info(f"Attempting to connect to {uri}")
        async with websockets.connect(uri) as websocket:
            logger.info("Successfully connected to WebSocket server")
            
            # Keep listening for messages
            while True:
                try:
                    # Wait for message
                    message = await websocket.recv()
                    
                    # Log raw message
                    logger.info(f"Raw message received: {message}")
                    
                    # Try to parse as JSON
                    try:
                        data = json.loads(message)
                        logger.info("Parsed message:")
                        logger.info(json.dumps(data, indent=2))
                        
                        # If it's a Wave Trend message, format it nicely
                        if all(key in data for key in ['symbol', 'timeframe', 'wt1', 'wt2']):
                            logger.info(f"""
Wave Trend Analysis:
Symbol: {data['symbol']}
Timeframe: {data['timeframe']}
WT1: {data['wt1']}
WT2: {data['wt2']}
Timestamp: {data.get('timestamp', 'N/A')}
""")
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse message as JSON: {e}")
                        
                except websockets.exceptions.ConnectionClosed:
                    logger.warning("Connection closed by server")
                    break
                except Exception as e:
                    logger.error(f"Error receiving message: {e}")
                    break
                    
    except Exception as e:
        logger.error(f"Failed to connect to WebSocket server: {e}")
        return

async def main():
    while True:
        try:
            await connect_websocket()
        except KeyboardInterrupt:
            logger.info("Client stopped by user")
            break
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
        
        logger.info("Attempting to reconnect in 5 seconds...")
        await asyncio.sleep(5)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nClient stopped by user") 