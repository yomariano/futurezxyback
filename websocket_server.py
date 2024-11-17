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

connected_clients = set()
message_queue = asyncio.Queue()  # Define message queue
broadcast_lock = asyncio.Lock()  # Add lock for thread safety

async def handle_client(websocket, path):
    """Handle individual client connections"""
    try:
        # Register client
        connected_clients.add(websocket)
        logger.info(f"New client connected from {websocket.remote_address}")
        
        try:
            async for message in websocket:
                # Process any incoming messages if needed
                logger.info(f"Received message from client: {message}")
            
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Client connection closed normally")
        except Exception as e:
            logger.error(f"Error handling client message: {str(e)}")
        finally:
            connected_clients.remove(websocket)
            logger.info(f"Client disconnected from {websocket.remote_address}")
    except Exception as e:
        logger.error(f"Error in handle_client: {str(e)}")

async def broadcast(message):
    """Broadcast message to all connected clients"""
    if connected_clients:
        logger.info(f"Broadcasting message to {len(connected_clients)} clients: {message}")
        async with broadcast_lock:
            disconnected_clients = set()
            for client in connected_clients:
                try:
                    await client.send(message)
                    logger.info(f"Message sent to client: {client.remote_address}")
                except Exception as e:
                    logger.error(f"Error sending to client {client.remote_address}: {str(e)}")
                    disconnected_clients.add(client)
            
            # Remove disconnected clients
            for client in disconnected_clients:
                connected_clients.remove(client)

async def start_server(port=8080, host='0.0.0.0'):
    """Start the WebSocket server"""
    server = await websockets.serve(
        handle_client,
        host,
        port,
        ping_interval=20,  # Add ping interval to keep connections alive
        ping_timeout=60,
        max_size=None,
        compression=None
    )
    logger.info(f"WebSocket server is listening on ws://{host}:{port}")
    return server