import asyncio
import websockets
import json
import logging
import traceback
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

connected_clients = set()

async def broadcast(message):
    if connected_clients:
        try:
            # Log the raw message first
            logger.info(f"Raw message to broadcast: {message}")
            
            # Parse the message if it's a JSON string
            if isinstance(message, str):
                try:
                    message_content = json.loads(message)
                    logger.info(f"Parsed JSON message: {message_content}")
                except json.JSONDecodeError as je:
                    logger.warning(f"Could not parse message as JSON: {je}")
                    message_content = message
            else:
                message_content = message
            
            # Log broadcast attempt
            logger.info(f"Broadcasting to {len(connected_clients)} clients at {datetime.now().isoformat()}")
            
            # Broadcast to each client
            for client in connected_clients:
                try:
                    await client.send(message)
                    logger.info(f"Successfully sent to client: {client.remote_address}")
                except Exception as e:
                    logger.error(f"Failed to send to client {client.remote_address}: {str(e)}")
                    logger.error(traceback.format_exc())
            
            logger.info("Broadcast completed successfully")
            
        except Exception as e:
            logger.error(f"Error during broadcast operation: {str(e)}")
            logger.error(traceback.format_exc())
    else:
        logger.warning("No connected clients to broadcast to")

async def handler(websocket, path):
    # Register client
    client_info = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
    # logger.info(f"New client connected: {client_info}")
    connected_clients.add(websocket)
    # logger.info(f"Total connected clients: {len(connected_clients)}")
    
    try:
        # Keep the connection open and handle incoming messages
        async for message in websocket:
            logger.info(f"Received message from {client_info}: {message}")
            
        # If we get here, the client has closed the connection
        logger.info(f"Client {client_info} has closed the connection")
    except websockets.exceptions.ConnectionClosed:
        logger.info(f"Client {client_info} connection closed unexpectedly")
    except Exception as e:
        logger.error(f"Error handling client {client_info}: {str(e)}")
        logger.error(traceback.format_exc())
    finally:
        # Unregister client
        connected_clients.remove(websocket)
        logger.info(f"Client disconnected: {client_info}")
        logger.info(f"Remaining connected clients: {len(connected_clients)}")

async def start_server():
    try:
        logger.info("Starting WebSocket server on ws://localhost:8765")
        server = await websockets.serve(handler, "localhost", 8765)
        logger.info("WebSocket server is running and ready for connections")
        await server.wait_closed()
    except Exception as e:
        logger.error(f"Error starting WebSocket server: {str(e)}")
        logger.error(traceback.format_exc())
        raise