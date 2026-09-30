"""
IGRIS BRAIN — server package
=============================
FastAPI bridge server, chat history, circuit breaker,
health metrics, process management.

Import example:
    from server.server import app
    from server.server_chat_history import ChatHistory
"""

__all__ = [
    "server",
    "server_chat_history",
    "server_circuit",
    "server_health",
    "server_process",
]
