import asyncio
import websockets
import logging
import ssl
import os
import json

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def on_message(ws, message):
    logger.info(f"Received message: {message}")

async def connect_websocket():
    """Connect to WebSocket server and print received messages"""
    # Determine environment
    is_prod = os.getenv('ENV') == 'dev'
    
    # Set URI based on environment
    if is_prod:
        uri = "wss://your-trading-bot.fly.dev:443"
    else:
        uri = "ws://localhost:8080"  # Match the port your server is running on
    
    while True:
        try:
            logger.info(f"Attempting to connect to {uri}")
            async with websockets.connect(
                uri,
                ping_interval=20,
                ping_timeout=60,
                close_timeout=20,
                max_size=None
            ) as websocket:
                websocket.on_message = on_message
                logger.info("Connected to WebSocket server!")
                
                while True:
                    try:
                        message = await websocket.recv()
                        try:
                            parsed_message = json.loads(message)
                            logger.info(f"Received message: {json.dumps(parsed_message, indent=2)}")
                        except json.JSONDecodeError:
                            logger.info(f"Received raw message: {message}")
                    except websockets.exceptions.ConnectionClosed:
                        logger.error("WebSocket connection closed")
                        break
                    except Exception as e:
                        logger.error(f"Error receiving message: {str(e)}")
                        break
                    
        except Exception as e:
            logger.error(f"Connection failed: {str(e)}")
            await asyncio.sleep(5)  # Wait before retrying

if __name__ == "__main__":
    asyncio.run(connect_websocket())