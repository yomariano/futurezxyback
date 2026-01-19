import asyncio
import websockets
import json
import logging
import sys
import os
from datetime import datetime

# Configure logging to stdout
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

connected_clients = set()
broadcast_lock = asyncio.Lock()
_server_loop = None

def get_event_loop():
    """Get the server's event loop for cross-thread calls"""
    return _server_loop

async def handle_client(websocket):
    """Handle individual client connections"""
    global _server_loop
    _server_loop = asyncio.get_running_loop()

    print(f"[WS] handle_client called!", flush=True)
    try:
        connected_clients.add(websocket)
        print(f"[WS] New client connected! Total: {len(connected_clients)}", flush=True)
        logger.info(f"New client connected from {websocket.remote_address}")

        # Send initial connection acknowledgment
        try:
            await websocket.send(json.dumps({
                "type": "connection",
                "status": "connected",
                "message": "Welcome to trading signals server"
            }))
        except Exception as e:
            logger.error(f"Error sending welcome message: {e}")

        try:
            async for message in websocket:
                logger.info(f"Received message from client: {message}")
                # Handle subscribe messages
                try:
                    data = json.loads(message)
                    if data.get("type") == "subscribe":
                        await websocket.send(json.dumps({
                            "type": "subscribed",
                            "symbols": data.get("symbols", [])
                        }))
                except json.JSONDecodeError:
                    pass
        except websockets.exceptions.ConnectionClosed as e:
            logger.info(f"Client connection closed: {e}")
        except Exception as e:
            logger.error(f"Error handling client message: {str(e)}")
        finally:
            connected_clients.discard(websocket)
            print(f"[WS] Client disconnected. Total: {len(connected_clients)}", flush=True)
    except Exception as e:
        logger.error(f"Error in handle_client: {str(e)}")
        import traceback
        traceback.print_exc()

async def broadcast(message):
    """Broadcast message to all connected clients"""
    if connected_clients:
        # Make a copy to avoid modification during iteration
        clients = set(connected_clients)
        logger.info(f"Broadcasting to {len(clients)} clients")
        try:
            # Use websockets.broadcast which handles multiple clients efficiently
            websockets.broadcast(clients, message)
        except Exception as e:
            logger.error(f"Broadcast error: {e}")

async def start_server(port=None, host='0.0.0.0'):
    """Start the WebSocket server"""
    global _server_loop
    _server_loop = asyncio.get_running_loop()

    # Use PORT env var (for cloud platforms like Coolify/Railway) or default to 8080
    if port is None:
        port = int(os.environ.get('PORT', 8080))

    server = await websockets.serve(
        handle_client,
        host,
        port,
        ping_interval=20,
        ping_timeout=60,
    )
    logger.info(f"WebSocket server is listening on ws://{host}:{port}")
    print(f"[WS] WebSocket server started on ws://{host}:{port}", flush=True)
    await server.wait_closed()
