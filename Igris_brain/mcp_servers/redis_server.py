"""
IGRIS BRAIN — Redis MCP Server
==============================
MCP server for Redis caching operations:
- get/set/delete: Basic key operations
- hash operations: hget, hset, hgetall
- list operations: lpush, rpush, lpop, lrange
- set operations: sadd, smembers, sinter
- sorted sets: zadd, zrange, zscore
- pub/sub: publish messages
- TTL management: expire, ttl
- Connection pool management

Authentication:
  Set REDIS_URL environment variable:
    REDIS_URL=redis://localhost:6379/0
    REDIS_URL=redis://:password@localhost:6379/0

Xavfsizlik:
  - FLUSHALL/FLUSHDB blokalanadi
  - Namespace cheklovi (ixtiyoriy)
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

from mcp.server.fastmcp import FastMCP

# Skript rejimida ishga tushganda Igris_brain papkasi sys.path'da bo'lmaydi
_SERVER_DIR = os.path.dirname(os.path.abspath(__file__))
_BRAIN_DIR = os.path.dirname(_SERVER_DIR)
if _BRAIN_DIR not in sys.path:
    sys.path.insert(0, _BRAIN_DIR)

from env_loader import get_redis_url

mcp = FastMCP("redis")


# ---------------------------------------------------------------- #
# Configuration
# ---------------------------------------------------------------- #

def _get_redis_url() -> str:
    """Redis URL olish (env)."""
    return get_redis_url()


# ---------------------------------------------------------------- #
# Connection
# ---------------------------------------------------------------- #

async def _get_redis(url: str = None) -> tuple:
    """Redis ga ulanish."""
    try:
        import redis.asyncio as aioredis
        redis_url = url or _get_redis_url()
        client = aioredis.from_url(redis_url, decode_responses=True)
        # Test connection
        await client.ping()
        return client, None
    except ImportError:
        try:
            import redis
            redis_url = url or _get_redis_url()
            client = redis.from_url(redis_url, decode_responses=True)
            client.ping()
            return client, None
        except ImportError:
            return None, "redis not installed. Run: pip install redis"
        except Exception as exc:
            return None, f"Connection failed: {exc}"
    except Exception as exc:
        return None, f"Connection failed: {exc}"


# ---------------------------------------------------------------- #
# Safety Checks
# ---------------------------------------------------------------- #

_DANGEROUS_COMMANDS = [
    "FLUSHALL", "FLUSHDB", "SHUTDOWN", "SLAVEOF", "REPLICAOF",
]


def _check_safety(command: str, args: list) -> str:
    """Xavfsizlik tekshiruvi."""
    cmd_upper = command.upper()
    if cmd_upper in _DANGEROUS_COMMANDS:
        return f"Dangerous command blocked: {cmd_upper}"
    return ""


# ---------------------------------------------------------------- #
# Tool Implementations
# ---------------------------------------------------------------- #

@mcp.tool()
async def redis_get(key: str, url: str = "") -> str:
    """Get a value by key from Redis.

    Args:
        key: Redis key to get
        url: Redis connection URL (default: REDIS_URL env var)

    Returns:
        The value stored at the key
    """
    client, err = await _get_redis(url)
    if err:
        return json.dumps({"ok": False, "error": err})
    
    try:
        value = await client.get(key) if hasattr(client, 'get') else client.get(key)
        if value is None:
            return json.dumps({"ok": True, "key": key, "value": None, "exists": False})
        return json.dumps({"ok": True, "key": key, "value": value, "exists": True})
    except Exception as exc:
        return json.dumps({"ok": False, "error": str(exc)})
    finally:
        await client.aclose() if hasattr(client, 'aclose') else client.close()


@mcp.tool()
async def redis_set(key: str, value: str, ex: int = 0, url: str = "") -> str:
    """Set a key-value pair in Redis.

    Args:
        key: Redis key
        value: Value to store
        ex: Expiration in seconds (0 = no expiration)
        url: Redis connection URL (default: REDIS_URL env var)

    Returns:
        Success status
    """
    client, err = await _get_redis(url)
    if err:
        return json.dumps({"ok": False, "error": err})
    
    try:
        if ex > 0:
            await client.setex(key, ex, value) if hasattr(client, 'setex') else client.setex(key, ex, value)
        else:
            await client.set(key, value) if hasattr(client, 'set') else client.set(key, value)
        return json.dumps({"ok": True, "key": key, "message": f"Key set successfully" + (f" with TTL {ex}s" if ex > 0 else "")})
    except Exception as exc:
        return json.dumps({"ok": False, "error": str(exc)})
    finally:
        await client.aclose() if hasattr(client, 'aclose') else client.close()


@mcp.tool()
async def redis_delete(keys: list, url: str = "") -> str:
    """Delete one or more keys from Redis.

    Args:
        keys: List of keys to delete
        url: Redis connection URL (default: REDIS_URL env var)

    Returns:
        Number of keys deleted
    """
    client, err = await _get_redis(url)
    if err:
        return json.dumps({"ok": False, "error": err})
    
    try:
        deleted = await client.delete(*keys) if hasattr(client, 'delete') else client.delete(*keys)
        return json.dumps({"ok": True, "deleted": deleted, "message": f"Deleted {deleted} key(s)"})
    except Exception as exc:
        return json.dumps({"ok": False, "error": str(exc)})
    finally:
        await client.aclose() if hasattr(client, 'aclose') else client.close()


@mcp.tool()
async def redis_exists(keys: list, url: str = "") -> str:
    """Check if keys exist in Redis.

    Args:
        keys: List of keys to check
        url: Redis connection URL (default: REDIS_URL env var)

    Returns:
        Number of keys that exist
    """
    client, err = await _get_redis(url)
    if err:
        return json.dumps({"ok": False, "error": err})
    
    try:
        count = await client.exists(*keys) if hasattr(client, 'exists') else client.exists(*keys)
        return json.dumps({"ok": True, "count": count, "keys_checked": len(keys)})
    except Exception as exc:
        return json.dumps({"ok": False, "error": str(exc)})
    finally:
        await client.aclose() if hasattr(client, 'aclose') else client.close()


@mcp.tool()
async def redis_ttl(key: str, url: str = "") -> str:
    """Get the TTL (time to live) of a key.

    Args:
        key: Redis key
        url: Redis connection URL (default: REDIS_URL env var)

    Returns:
        TTL in seconds (-1 = no expiration, -2 = key doesn't exist)
    """
    client, err = await _get_redis(url)
    if err:
        return json.dumps({"ok": False, "error": err})
    
    try:
        ttl = await client.ttl(key) if hasattr(client, 'ttl') else client.ttl(key)
        return json.dumps({"ok": True, "key": key, "ttl": ttl})
    except Exception as exc:
        return json.dumps({"ok": False, "error": str(exc)})
    finally:
        await client.aclose() if hasattr(client, 'aclose') else client.close()


@mcp.tool()
async def redis_expire(key: str, seconds: int, url: str = "") -> str:
    """Set expiration on a key.

    Args:
        key: Redis key
        seconds: Expiration time in seconds
        url: Redis connection URL (default: REDIS_URL env var)

    Returns:
        Success status
    """
    client, err = await _get_redis(url)
    if err:
        return json.dumps({"ok": False, "error": err})
    
    try:
        result = await client.expire(key, seconds) if hasattr(client, 'expire') else client.expire(key, seconds)
        return json.dumps({"ok": True, "key": key, "ttl_set": seconds, "success": bool(result)})
    except Exception as exc:
        return json.dumps({"ok": False, "error": str(exc)})
    finally:
        await client.aclose() if hasattr(client, 'aclose') else client.close()


# ---------------------------------------------------------------- #
# Hash Operations
# ---------------------------------------------------------------- #

@mcp.tool()
async def redis_hget(key: str, field: str, url: str = "") -> str:
    """Get a field value from a Redis hash.

    Args:
        key: Hash key
        field: Field name
        url: Redis connection URL (default: REDIS_URL env var)

    Returns:
        Field value
    """
    client, err = await _get_redis(url)
    if err:
        return json.dumps({"ok": False, "error": err})
    
    try:
        value = await client.hget(key, field) if hasattr(client, 'hget') else client.hget(key, field)
        return json.dumps({"ok": True, "key": key, "field": field, "value": value})
    except Exception as exc:
        return json.dumps({"ok": False, "error": str(exc)})
    finally:
        await client.aclose() if hasattr(client, 'aclose') else client.close()


@mcp.tool()
async def redis_hset(key: str, field: str, value: str, url: str = "") -> str:
    """Set a field value in a Redis hash.

    Args:
        key: Hash key
        field: Field name
        value: Field value
        url: Redis connection URL (default: REDIS_URL env var)

    Returns:
        Success status
    """
    client, err = await _get_redis(url)
    if err:
        return json.dumps({"ok": False, "error": err})
    
    try:
        result = await client.hset(key, field, value) if hasattr(client, 'hset') else client.hset(key, field, value)
        return json.dumps({"ok": True, "key": key, "field": field, "message": f"Field set (new: {result})"})
    except Exception as exc:
        return json.dumps({"ok": False, "error": str(exc)})
    finally:
        await client.aclose() if hasattr(client, 'aclose') else client.close()


@mcp.tool()
async def redis_hgetall(key: str, url: str = "") -> str:
    """Get all fields and values from a Redis hash.

    Args:
        key: Hash key
        url: Redis connection URL (default: REDIS_URL env var)

    Returns:
        All fields and values
    """
    client, err = await _get_redis(url)
    if err:
        return json.dumps({"ok": False, "error": err})
    
    try:
        data = await client.hgetall(key) if hasattr(client, 'hgetall') else client.hgetall(key)
        return json.dumps({"ok": True, "key": key, "fields": data, "count": len(data)})
    except Exception as exc:
        return json.dumps({"ok": False, "error": str(exc)})
    finally:
        await client.aclose() if hasattr(client, 'aclose') else client.close()


# ---------------------------------------------------------------- #
# List Operations
# ---------------------------------------------------------------- #

@mcp.tool()
async def redis_lpush(key: str, values: list, url: str = "") -> str:
    """Push values to the head of a Redis list.

    Args:
        key: List key
        values: Values to push
        url: Redis connection URL (default: REDIS_URL env var)

    Returns:
        New list length
    """
    client, err = await _get_redis(url)
    if err:
        return json.dumps({"ok": False, "error": err})
    
    try:
        length = await client.lpush(key, *values) if hasattr(client, 'lpush') else client.lpush(key, *values)
        return json.dumps({"ok": True, "key": key, "length": length})
    except Exception as exc:
        return json.dumps({"ok": False, "error": str(exc)})
    finally:
        await client.aclose() if hasattr(client, 'aclose') else client.close()


@mcp.tool()
async def redis_rpush(key: str, values: list, url: str = "") -> str:
    """Push values to the tail of a Redis list.

    Args:
        key: List key
        values: Values to push
        url: Redis connection URL (default: REDIS_URL env var)

    Returns:
        New list length
    """
    client, err = await _get_redis(url)
    if err:
        return json.dumps({"ok": False, "error": err})
    
    try:
        length = await client.rpush(key, *values) if hasattr(client, 'rpush') else client.rpush(key, *values)
        return json.dumps({"ok": True, "key": key, "length": length})
    except Exception as exc:
        return json.dumps({"ok": False, "error": str(exc)})
    finally:
        await client.aclose() if hasattr(client, 'aclose') else client.close()


@mcp.tool()
async def redis_lrange(key: str, start: int, stop: int, url: str = "") -> str:
    """Get a range of elements from a Redis list.

    Args:
        key: List key
        start: Start index (0-based)
        stop: Stop index (-1 for all)
        url: Redis connection URL (default: REDIS_URL env var)

    Returns:
        List of elements
    """
    client, err = await _get_redis(url)
    if err:
        return json.dumps({"ok": False, "error": err})
    
    try:
        items = await client.lrange(key, start, stop) if hasattr(client, 'lrange') else client.lrange(key, start, stop)
        return json.dumps({"ok": True, "key": key, "items": items, "count": len(items)})
    except Exception as exc:
        return json.dumps({"ok": False, "error": str(exc)})
    finally:
        await client.aclose() if hasattr(client, 'aclose') else client.close()


@mcp.tool()
async def redis_lpop(key: str, url: str = "") -> str:
    """Pop a value from the head of a Redis list.

    Args:
        key: List key
        url: Redis connection URL (default: REDIS_URL env var)

    Returns:
        Popped value
    """
    client, err = await _get_redis(url)
    if err:
        return json.dumps({"ok": False, "error": err})
    
    try:
        value = await client.lpop(key) if hasattr(client, 'lpop') else client.lpop(key)
        return json.dumps({"ok": True, "key": key, "value": value})
    except Exception as exc:
        return json.dumps({"ok": False, "error": str(exc)})
    finally:
        await client.aclose() if hasattr(client, 'aclose') else client.close()


# ---------------------------------------------------------------- #
# Set Operations
# ---------------------------------------------------------------- #

@mcp.tool()
async def redis_sadd(key: str, members: list, url: str = "") -> str:
    """Add members to a Redis set.

    Args:
        key: Set key
        members: Members to add
        url: Redis connection URL (default: REDIS_URL env var)

    Returns:
        Number of members added
    """
    client, err = await _get_redis(url)
    if err:
        return json.dumps({"ok": False, "error": err})
    
    try:
        count = await client.sadd(key, *members) if hasattr(client, 'sadd') else client.sadd(key, *members)
        return json.dumps({"ok": True, "key": key, "added": count})
    except Exception as exc:
        return json.dumps({"ok": False, "error": str(exc)})
    finally:
        await client.aclose() if hasattr(client, 'aclose') else client.close()


@mcp.tool()
async def redis_smembers(key: str, url: str = "") -> str:
    """Get all members of a Redis set.

    Args:
        key: Set key
        url: Redis connection URL (default: REDIS_URL env var)

    Returns:
        Set members
    """
    client, err = await _get_redis(url)
    if err:
        return json.dumps({"ok": False, "error": err})
    
    try:
        members = await client.smembers(key) if hasattr(client, 'smembers') else client.smembers(key)
        return json.dumps({"ok": True, "key": key, "members": list(members), "count": len(members)})
    except Exception as exc:
        return json.dumps({"ok": False, "error": str(exc)})
    finally:
        await client.aclose() if hasattr(client, 'aclose') else client.close()


@mcp.tool()
async def redis_sinter(keys: list, url: str = "") -> str:
    """Get the intersection of multiple Redis sets.

    Args:
        keys: List of set keys
        url: Redis connection URL (default: REDIS_URL env var)

    Returns:
        Intersection members
    """
    client, err = await _get_redis(url)
    if err:
        return json.dumps({"ok": False, "error": err})
    
    try:
        members = await client.sinter(*keys) if hasattr(client, 'sinter') else client.sinter(*keys)
        return json.dumps({"ok": True, "keys": keys, "members": list(members), "count": len(members)})
    except Exception as exc:
        return json.dumps({"ok": False, "error": str(exc)})
    finally:
        await client.aclose() if hasattr(client, 'aclose') else client.close()


# ---------------------------------------------------------------- #
# Sorted Set Operations
# ---------------------------------------------------------------- #

@mcp.tool()
async def redis_zadd(key: str, members: dict, url: str = "") -> str:
    """Add members to a Redis sorted set with scores.

    Args:
        key: Sorted set key
        members: Dict of member -> score (e.g., {"alice": 100, "bob": 200})
        url: Redis connection URL (default: REDIS_URL env var)

    Returns:
        Number of members added
    """
    client, err = await _get_redis(url)
    if err:
        return json.dumps({"ok": False, "error": err})
    
    try:
        count = await client.zadd(key, members) if hasattr(client, 'zadd') else client.zadd(key, members)
        return json.dumps({"ok": True, "key": key, "added": count})
    except Exception as exc:
        return json.dumps({"ok": False, "error": str(exc)})
    finally:
        await client.aclose() if hasattr(client, 'aclose') else client.close()


@mcp.tool()
async def redis_zrange(key: str, start: int, stop: int, withscores: bool = False, url: str = "") -> str:
    """Get a range of members from a Redis sorted set.

    Args:
        key: Sorted set key
        start: Start index (0-based)
        stop: Stop index (-1 for all)
        withscores: Include scores in result
        url: Redis connection URL (default: REDIS_URL env var)

    Returns:
        Members (optionally with scores)
    """
    client, err = await _get_redis(url)
    if err:
        return json.dumps({"ok": False, "error": err})
    
    try:
        if withscores:
            items = await client.zrange(key, start, stop, withscores=True) if hasattr(client, 'zrange') else client.zrange(key, start, stop, withscores=True)
            return json.dumps({"ok": True, "key": key, "items": items, "count": len(items)})
        else:
            items = await client.zrange(key, start, stop) if hasattr(client, 'zrange') else client.zrange(key, start, stop)
            return json.dumps({"ok": True, "key": key, "items": items, "count": len(items)})
    except Exception as exc:
        return json.dumps({"ok": False, "error": str(exc)})
    finally:
        await client.aclose() if hasattr(client, 'aclose') else client.close()


@mcp.tool()
async def redis_zscore(key: str, member: str, url: str = "") -> str:
    """Get the score of a member in a Redis sorted set.

    Args:
        key: Sorted set key
        member: Member name
        url: Redis connection URL (default: REDIS_URL env var)

    Returns:
        Member score
    """
    client, err = await _get_redis(url)
    if err:
        return json.dumps({"ok": False, "error": err})
    
    try:
        score = await client.zscore(key, member) if hasattr(client, 'zscore') else client.zscore(key, member)
        return json.dumps({"ok": True, "key": key, "member": member, "score": score})
    except Exception as exc:
        return json.dumps({"ok": False, "error": str(exc)})
    finally:
        await client.aclose() if hasattr(client, 'aclose') else client.close()


# ---------------------------------------------------------------- #
# Pub/Sub Operations
# ---------------------------------------------------------------- #

@mcp.tool()
async def redis_publish(channel: str, message: str, url: str = "") -> str:
    """Publish a message to a Redis channel.

    Args:
        channel: Channel name
        message: Message to publish
        url: Redis connection URL (default: REDIS_URL env var)

    Returns:
        Number of subscribers that received the message
    """
    client, err = await _get_redis(url)
    if err:
        return json.dumps({"ok": False, "error": err})
    
    try:
        count = await client.publish(channel, message) if hasattr(client, 'publish') else client.publish(channel, message)
        return json.dumps({"ok": True, "channel": channel, "subscribers": count, "message": f"Published to {count} subscriber(s)"})
    except Exception as exc:
        return json.dumps({"ok": False, "error": str(exc)})
    finally:
        await client.aclose() if hasattr(client, 'aclose') else client.close()


# ---------------------------------------------------------------- #
# Utility Operations
# ---------------------------------------------------------------- #

@mcp.tool()
async def redis_keys(pattern: str = "*", count: int = 100, url: str = "") -> str:
    """List keys matching a pattern.

    Args:
        pattern: Key pattern (default: * for all)
        count: Maximum keys to return (default: 100)
        url: Redis connection URL (default: REDIS_URL env var)

    Returns:
        List of matching keys
    """
    client, err = await _get_redis(url)
    if err:
        return json.dumps({"ok": False, "error": err})
    
    try:
        # Use SCAN instead of KEYS for production safety
        keys = []
        cursor = 0
        while True:
            cursor, batch = await client.scan(cursor, match=pattern, count=min(count, 100)) if hasattr(client, 'scan') else client.scan(cursor, match=pattern, count=min(count, 100))
            keys.extend(batch)
            if len(keys) >= count or cursor == 0:
                break
        return json.dumps({"ok": True, "keys": keys[:count], "count": len(keys[:count])})
    except Exception as exc:
        return json.dumps({"ok": False, "error": str(exc)})
    finally:
        await client.aclose() if hasattr(client, 'aclose') else client.close()


@mcp.tool()
async def redis_type(key: str, url: str = "") -> str:
    """Get the type of a Redis key.

    Args:
        key: Redis key
        url: Redis connection URL (default: REDIS_URL env var)

    Returns:
        Key type (string, list, set, zset, hash, none)
    """
    client, err = await _get_redis(url)
    if err:
        return json.dumps({"ok": False, "error": err})
    
    try:
        key_type = await client.type(key) if hasattr(client, 'type') else client.type(key)
        return json.dumps({"ok": True, "key": key, "type": key_type})
    except Exception as exc:
        return json.dumps({"ok": False, "error": str(exc)})
    finally:
        await client.aclose() if hasattr(client, 'aclose') else client.close()


@mcp.tool()
async def redis_incr(key: str, amount: int = 1, url: str = "") -> str:
    """Increment the integer value of a key.

    Args:
        key: Redis key
        amount: Increment amount (default: 1)
        url: Redis connection URL (default: REDIS_URL env var)

    Returns:
        New value
    """
    client, err = await _get_redis(url)
    if err:
        return json.dumps({"ok": False, "error": err})
    
    try:
        if amount == 1:
            new_value = await client.incr(key) if hasattr(client, 'incr') else client.incr(key)
        else:
            new_value = await client.incrby(key, amount) if hasattr(client, 'incrby') else client.incrby(key, amount)
        return json.dumps({"ok": True, "key": key, "value": new_value})
    except Exception as exc:
        return json.dumps({"ok": False, "error": str(exc)})
    finally:
        await client.aclose() if hasattr(client, 'aclose') else client.close()


@mcp.tool()
async def redis_status(url: str = "") -> str:
    """Check Redis connection status.

    Args:
        url: Redis connection URL (default: REDIS_URL env var)

    Returns:
        Connection status and server info
    """
    client, err = await _get_redis(url)
    if err:
        return json.dumps({"ok": False, "error": err})
    
    try:
        info = await client.info() if hasattr(client, 'info') else client.info()
        return json.dumps({
            "ok": True,
            "status": "connected",
            "redis_version": info.get("redis_version", "unknown"),
            "connected_clients": info.get("connected_clients", 0),
            "used_memory_human": info.get("used_memory_human", "unknown"),
            "uptime_in_seconds": info.get("uptime_in_seconds", 0),
        })
    except Exception as exc:
        return json.dumps({"ok": False, "error": str(exc)})
    finally:
        await client.aclose() if hasattr(client, 'aclose') else client.close()


# ---------------------------------------------------------------- #
# Main
# ---------------------------------------------------------------- #

if __name__ == "__main__":
    mcp.run()
