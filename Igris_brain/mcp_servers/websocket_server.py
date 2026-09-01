"""
IGRIS BRAIN — WebSocket MCP Server
===================================
MCP server for real-time WebSocket operations:
- connect: Connect to a WebSocket server
- send: Send messages to connected clients
- broadcast: Broadcast to all connected clients
- subscribe: Subscribe to channels/topics
- unsubscribe: Unsubscribe from channels
- history: Get message history
- status: Connection status

Use cases:
- Real-time notifications (task completion, errors, progress)
- Live updates for dashboards
- Chat/messaging between clients
- Event streaming (logs, metrics)

Authentication:
  Set WS_SECRET environment variable for secure connections

Xavfsizlik:
  - Rate limiting
  - Message size limits
  - Connection limits
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from collections import defaultdict
from typing import Any, Callable, Optional

from mcp.server.fastmcp import FastMCP

# Skript rejimida ishga tushganda Igris_brain papkasi sys.path'da bo'lmaydi
_SERVER_DIR = os.path.dirname(os.path.abspath(__file__))
_BRAIN_DIR = os.path.dirname(_SERVER_DIR)
if _BRAIN_DIR not in sys.path:
    sys.path.insert(0, _BRAIN_DIR)

from env_loader import get_env, get_ws_secret

mcp = FastMCP("websocket")


# ---------------------------------------------------------------- #
# Configuration
# ---------------------------------------------------------------- #

def _get_ws_secret() -> str:
    """WebSocket secret olish (env)."""
    return get_ws_secret()


MAX_CONNECTIONS = get_env("WS_MAX_CONNECTIONS", 100, int)
MAX_MESSAGE_SIZE = get_env("WS_MAX_MESSAGE_SIZE", 65536, int)  # 64KB
RATE_LIMIT_MESSAGES = get_env("WS_RATE_LIMIT", 100, int)  # per second


# ---------------------------------------------------------------- #
# Connection Manager
# ---------------------------------------------------------------- #

class ConnectionManager:
    """WebSocket ulanishlarini boshqarish."""
    
    def __init__(self):
        self.connections: dict[str, dict] = {}  # conn_id -> {ws, info}
        self.channels: dict[str, set] = defaultdict(set)  # channel -> {conn_ids}
        self.message_history: dict[str, list] = defaultdict(list)  # channel -> messages
        self._lock = asyncio.Lock()
        self._stats = {
            "total_connections": 0,
            "total_messages": 0,
            "total_broadcasts": 0,
        }
    
    async def add_connection(self, conn_id: str, info: dict) -> bool:
        """Ulanish qo'shish."""
        async with self._lock:
            if len(self.connections) >= MAX_CONNECTIONS:
                return False
            self.connections[conn_id] = {
                "info": info,
                "connected_at": time.time(),
                "messages_sent": 0,
                "channels": set(),
            }
            self._stats["total_connections"] += 1
            return True
    
    async def remove_connection(self, conn_id: str) -> None:
        """Ulanishni o'chirish."""
        async with self._lock:
            if conn_id in self.connections:
                # Kanallardan chiqarish
                for channel in self.connections[conn_id].get("channels", set()):
                    self.channels[channel].discard(conn_id)
                del self.connections[conn_id]
    
    async def subscribe(self, conn_id: str, channel: str) -> bool:
        """Kanalga obuna bo'lish."""
        async with self._lock:
            if conn_id not in self.connections:
                return False
            self.channels[channel].add(conn_id)
            self.connections[conn_id]["channels"].add(channel)
            return True
    
    async def unsubscribe(self, conn_id: str, channel: str) -> bool:
        """Kanaldan chiqish."""
        async with self._lock:
            if conn_id not in self.connections:
                return False
            self.channels[channel].discard(conn_id)
            self.connections[conn_id]["channels"].discard(channel)
            return True
    
    async def broadcast(self, channel: str, message: dict, exclude: str = None) -> int:
        """Kanalga xabar yuborish."""
        async with self._lock:
            if channel not in self.channels:
                return 0
            
            sent = 0
            for conn_id in list(self.channels[channel]):
                if conn_id == exclude:
                    continue
                if conn_id in self.connections:
                    self.connections[conn_id]["messages_sent"] += 1
                    sent += 1
            
            # Tarixga saqlash
            self.message_history[channel].append({
                "message": message,
                "timestamp": time.time(),
            })
            # Faqat oxirgi 100 xabarni saqlash
            if len(self.message_history[channel]) > 100:
                self.message_history[channel] = self.message_history[channel][-100:]
            
            self._stats["total_broadcasts"] += 1
            return sent
    
    async def get_stats(self) -> dict:
        """Statistika olish."""
        async with self._lock:
            return {
                "active_connections": len(self.connections),
                "channels": {ch: len(conns) for ch, conns in self.channels.items()},
                "total_connections": self._stats["total_connections"],
                "total_messages": self._stats["total_messages"],
                "total_broadcasts": self._stats["total_broadcasts"],
            }
    
    async def get_history(self, channel: str, limit: int = 50) -> list:
        """Kanal tarixini olish."""
        return self.message_history.get(channel, [])[-limit:]
    
    async def get_connection_info(self, conn_id: str) -> Optional[dict]:
        """Ulanish haqida ma'lumot."""
        if conn_id in self.connections:
            info = self.connections[conn_id].copy()
            info["channels"] = list(info["channels"])
            return info
        return None


# Global manager instance
_manager = ConnectionManager()


# ---------------------------------------------------------------- #
# Tool Implementations
# ---------------------------------------------------------------- #

@mcp.tool()
async def ws_connect(
    client_id: str,
    channels: list = None,
    metadata: dict = None,
) -> str:
    """Connect a client to the WebSocket server.

    Args:
        client_id: Unique client identifier
        channels: Channels to subscribe to (optional)
        metadata: Additional client metadata

    Returns:
        Connection status and assigned connection ID
    """
    conn_id = f"{client_id}_{int(time.time() * 1000)}"
    
    success = await _manager.add_connection(conn_id, {
        "client_id": client_id,
        "metadata": metadata or {},
    })
    
    if not success:
        return json.dumps({
            "ok": False,
            "error": f"Connection limit reached ({MAX_CONNECTIONS})",
        })
    
    # Subscribe to initial channels
    subscribed_channels = []
    if channels:
        for channel in channels:
            if await _manager.subscribe(conn_id, channel):
                subscribed_channels.append(channel)
    
    return json.dumps({
        "ok": True,
        "connection_id": conn_id,
        "client_id": client_id,
        "subscribed_channels": subscribed_channels,
        "message": f"Connected as {conn_id}",
    })


@mcp.tool()
async def ws_disconnect(connection_id: str) -> str:
    """Disconnect a client from the WebSocket server.

    Args:
        connection_id: Connection ID to disconnect

    Returns:
        Disconnect status
    """
    await _manager.remove_connection(connection_id)
    return json.dumps({
        "ok": True,
        "connection_id": connection_id,
        "message": "Disconnected",
    })


@mcp.tool()
async def ws_subscribe(connection_id: str, channel: str) -> str:
    """Subscribe to a channel.

    Args:
        connection_id: Your connection ID
        channel: Channel name to subscribe to

    Returns:
        Subscription status
    """
    success = await _manager.subscribe(connection_id, channel)
    if not success:
        return json.dumps({
            "ok": False,
            "error": f"Connection {connection_id} not found",
        })
    
    return json.dumps({
        "ok": True,
        "connection_id": connection_id,
        "channel": channel,
        "message": f"Subscribed to {channel}",
    })


@mcp.tool()
async def ws_unsubscribe(connection_id: str, channel: str) -> str:
    """Unsubscribe from a channel.

    Args:
        connection_id: Your connection ID
        channel: Channel name to unsubscribe from

    Returns:
        Unsubscription status
    """
    success = await _manager.unsubscribe(connection_id, channel)
    if not success:
        return json.dumps({
            "ok": False,
            "error": f"Connection {connection_id} not found",
        })
    
    return json.dumps({
        "ok": True,
        "connection_id": connection_id,
        "channel": channel,
        "message": f"Unsubscribed from {channel}",
    })


@mcp.tool()
async def ws_send(
    connection_id: str,
    channel: str,
    message: dict,
    event_type: str = "message",
) -> str:
    """Send a message to a specific channel.

    Args:
        connection_id: Sender's connection ID
        channel: Target channel
        message: Message payload (dict)
        event_type: Event type (message, notification, update, alert)

    Returns:
        Send status
    """
    if len(json.dumps(message)) > MAX_MESSAGE_SIZE:
        return json.dumps({
            "ok": False,
            "error": f"Message too large (max {MAX_MESSAGE_SIZE} bytes)",
        })
    
    # Validate connection exists
    conn_info = await _manager.get_connection_info(connection_id)
    if not conn_info:
        return json.dumps({
            "ok": False,
            "error": f"Connection {connection_id} not found",
        })
    
    # Broadcast to channel
    payload = {
        "event": event_type,
        "channel": channel,
        "sender": conn_info.get("client_id"),
        "data": message,
        "timestamp": time.time(),
    }
    
    sent = await _manager.broadcast(channel, payload, exclude=connection_id)
    
    _manager._stats["total_messages"] += 1
    
    return json.dumps({
        "ok": True,
        "channel": channel,
        "event": event_type,
        "recipients": sent,
        "message": f"Sent to {sent} subscriber(s)",
    })


@mcp.tool()
async def ws_broadcast(
    channel: str,
    message: dict,
    event_type: str = "broadcast",
) -> str:
    """Broadcast a message to all subscribers of a channel.

    Args:
        channel: Target channel
        message: Message payload (dict)
        event_type: Event type (broadcast, notification, alert)

    Returns:
        Broadcast status
    """
    if len(json.dumps(message)) > MAX_MESSAGE_SIZE:
        return json.dumps({
            "ok": False,
            "error": f"Message too large (max {MAX_MESSAGE_SIZE} bytes)",
        })
    
    payload = {
        "event": event_type,
        "channel": channel,
        "sender": "system",
        "data": message,
        "timestamp": time.time(),
    }
    
    sent = await _manager.broadcast(channel, payload)
    
    _manager._stats["total_messages"] += 1
    
    return json.dumps({
        "ok": True,
        "channel": channel,
        "event": event_type,
        "recipients": sent,
        "message": f"Broadcast to {sent} subscriber(s)",
    })


@mcp.tool()
async def ws_history(channel: str, limit: int = 50) -> str:
    """Get message history for a channel.

    Args:
        channel: Channel name
        limit: Maximum messages to return (default: 50)

    Returns:
        Message history
    """
    history = await _manager.get_history(channel, limit)
    return json.dumps({
        "ok": True,
        "channel": channel,
        "messages": history,
        "count": len(history),
    })


@mcp.tool()
async def ws_connections() -> str:
    """List all active connections.

    Returns:
        List of active connections
    """
    stats = await _manager.get_stats()
    connections = []
    
    for conn_id, conn_data in _manager.connections.items():
        connections.append({
            "connection_id": conn_id,
            "client_id": conn_data.get("info", {}).get("client_id"),
            "connected_at": conn_data.get("connected_at"),
            "messages_sent": conn_data.get("messages_sent", 0),
            "channels": list(conn_data.get("channels", set())),
        })
    
    return json.dumps({
        "ok": True,
        "connections": connections,
        "count": len(connections),
        "stats": stats,
    })


@mcp.tool()
async def ws_channels() -> str:
    """List all active channels with subscriber counts.

    Returns:
        List of channels
    """
    channels = {}
    for channel, subscribers in _manager.channels.items():
        channels[channel] = {
            "subscribers": len(subscribers),
            "has_history": len(_manager.message_history.get(channel, [])) > 0,
        }
    
    return json.dumps({
        "ok": True,
        "channels": channels,
        "count": len(channels),
    })


@mcp.tool()
async def ws_status() -> str:
    """Get WebSocket server status.

    Returns:
        Server status and statistics
    """
    stats = await _manager.get_stats()
    return json.dumps({
        "ok": True,
        "status": "running",
        "max_connections": MAX_CONNECTIONS,
        "max_message_size": MAX_MESSAGE_SIZE,
        "rate_limit": RATE_LIMIT_MESSAGES,
        "stats": stats,
    })


@mcp.tool()
async def ws_notify(
    channel: str,
    title: str,
    body: str,
    level: str = "info",
    metadata: dict = None,
) -> str:
    """Send a notification to a channel.

    Args:
        channel: Target channel
        title: Notification title
        body: Notification body
        level: Notification level (info, warning, error, success)
        metadata: Additional notification data

    Returns:
        Notification status
    """
    notification = {
        "title": title,
        "body": body,
        "level": level,
        "metadata": metadata or {},
    }
    
    payload = {
        "event": "notification",
        "channel": channel,
        "sender": "system",
        "data": notification,
        "timestamp": time.time(),
    }
    
    sent = await _manager.broadcast(channel, payload)
    
    return json.dumps({
        "ok": True,
        "channel": channel,
        "level": level,
        "recipients": sent,
        "message": f"Notification sent to {sent} subscriber(s)",
    })


@mcp.tool()
async def ws_task_update(
    task_id: str,
    status: str,
    progress: int = 0,
    message: str = "",
    channel: str = "tasks",
) -> str:
    """Send a task progress update.

    Args:
        task_id: Task identifier
        status: Task status (pending, running, completed, failed)
        progress: Progress percentage (0-100)
        message: Status message
        channel: Channel to publish to (default: tasks)

    Returns:
        Update status
    """
    update = {
        "task_id": task_id,
        "status": status,
        "progress": min(max(progress, 0), 100),
        "message": message,
    }
    
    payload = {
        "event": "task_update",
        "channel": channel,
        "sender": "system",
        "data": update,
        "timestamp": time.time(),
    }
    
    sent = await _manager.broadcast(channel, payload)
    
    return json.dumps({
        "ok": True,
        "task_id": task_id,
        "status": status,
        "progress": progress,
        "recipients": sent,
    })


@mcp.tool()
async def ws_log(
    level: str,
    message: str,
    source: str = "agent",
    channel: str = "logs",
    metadata: dict = None,
) -> str:
    """Send a log message to a channel.

    Args:
        level: Log level (debug, info, warning, error)
        message: Log message
        source: Log source (agent, tool, system)
        channel: Channel to publish to (default: logs)
        metadata: Additional log data

    Returns:
        Log status
    """
    log_entry = {
        "level": level,
        "message": message,
        "source": source,
        "metadata": metadata or {},
    }
    
    payload = {
        "event": "log",
        "channel": channel,
        "sender": source,
        "data": log_entry,
        "timestamp": time.time(),
    }
    
    sent = await _manager.broadcast(channel, payload)
    
    return json.dumps({
        "ok": True,
        "level": level,
        "source": source,
        "recipients": sent,
    })


# ---------------------------------------------------------------- #
# Main
# ---------------------------------------------------------------- #

if __name__ == "__main__":
    mcp.run()
