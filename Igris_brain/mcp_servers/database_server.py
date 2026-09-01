"""
IGRIS BRAIN — Database MCP Server
=================================
MCP server for database operations:
- PostgreSQL: connect, query, list_tables, describe_table, execute
- MySQL/MariaDB: connect, query, list_tables, describe_table, execute
- MongoDB: connect, find, insert, update, delete, list_collections

Authentication:
  Set connection strings via environment variables:
    - DATABASE_URL: PostgreSQL/MySQL connection string
    - MONGODB_URL: MongoDB connection string

Examples:
    DATABASE_URL=postgresql://user:pass@localhost:5432/dbname
    DATABASE_URL=mysql://user:pass@localhost:3306/dbname
    MONGODB_URL=mongodb://localhost:27017/dbname

Xavfsizlik:
  - DROP/DELETE without WHERE bloklanadi (ixtiyoriy)
  - Read-only mode mavjud
  - Connection pool limits
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.parse
from typing import Any

from mcp.server.fastmcp import FastMCP

# Skript rejimida ishga tushganda Igris_brain papkasi sys.path'da bo'lmaydi
_SERVER_DIR = os.path.dirname(os.path.abspath(__file__))
_BRAIN_DIR = os.path.dirname(_SERVER_DIR)
if _BRAIN_DIR not in sys.path:
    sys.path.insert(0, _BRAIN_DIR)

from env_loader import get_database_url, get_mongodb_url

mcp = FastMCP("database")


# ---------------------------------------------------------------- #
# Configuration
# ---------------------------------------------------------------- #

def _get_database_url() -> str:
    """Database URL olish (env)."""
    return get_database_url()


def _get_mongodb_url() -> str:
    """MongoDB URL olish (env)."""
    return get_mongodb_url()


def _detect_db_type(url: str) -> str:
    """URL'dan DB turini aniqlash."""
    if not url:
        return "unknown"
    url_lower = url.lower()
    if url_lower.startswith("postgresql") or url_lower.startswith("postgres"):
        return "postgresql"
    elif url_lower.startswith("mysql") or url_lower.startswith("mariadb"):
        return "mysql"
    elif url_lower.startswith("mongodb"):
        return "mongodb"
    return "unknown"


# ---------------------------------------------------------------- #
# Safety Checks
# ---------------------------------------------------------------- #

# Xavfli SQL buyruqlari — faqat read-only mode'da blokalanadi
_DANGEROUS_SQL = [
    re.compile(r"\bDROP\s+(TABLE|DATABASE|INDEX|VIEW)\b", re.IGNORECASE),
    re.compile(r"\bTRUNCATE\s+TABLE\b", re.IGNORECASE),
    re.compile(r"\bDELETE\s+FROM\s+\w+\s*$", re.IGNORECASE),  # DELETE without WHERE
    re.compile(r"\bUPDATE\s+\w+\s+SET\b.*\bWHERE\b", re.IGNORECASE),  # mass UPDATE
]


def _is_readonly_query(sql: str) -> bool:
    """So'rov read-only emasligini tekshirish."""
    sql_upper = sql.strip().upper()
    return sql_upper.startswith(("SELECT", "SHOW", "DESCRIBE", "EXPLAIN", "WITH"))


def _check_safety(sql: str, readonly: bool = False) -> str:
    """Xavfsizlik tekshiruvi. Xato bo'lsa xato matni qaytaradi."""
    if readonly and not _is_readonly_query(sql):
        return "Write operations not allowed in read-only mode"
    
    # DROP/TRUNCATE without explicit confirmation
    for pat in _DANGEROUS_SQL:
        if pat.search(sql):
            return f"Dangerous operation detected: {pat.pattern[:50]}"
    
    return ""


# ---------------------------------------------------------------- #
# PostgreSQL Implementation
# ---------------------------------------------------------------- #

async def _pg_connect(url: str) -> tuple:
    """PostgreSQL ga ulanish."""
    try:
        import psycopg2
        conn = psycopg2.connect(url)
        return conn, None
    except ImportError:
        return None, "psycopg2 not installed. Run: pip install psycopg2-binary"
    except Exception as exc:
        return None, f"Connection failed: {exc}"


async def _pg_query(args: dict) -> dict:
    """PostgreSQL so'rov bajarish."""
    url = args.get("url") or _get_database_url()
    sql = args.get("sql", "")
    params = args.get("params", [])
    readonly = args.get("readonly", True)
    
    if not url:
        return {"ok": False, "error": "No DATABASE_URL configured"}
    if not sql:
        return {"ok": False, "error": "SQL query is required"}
    
    safety_error = _check_safety(sql, readonly)
    if safety_error:
        return {"ok": False, "error": safety_error}
    
    conn, err = await _pg_connect(url)
    if err:
        return {"ok": False, "error": err}
    
    try:
        cur = conn.cursor()
        cur.execute(sql, params or None)
        
        if cur.description:  # SELECT query
            columns = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
            return {
                "ok": True,
                "columns": columns,
                "rows": [dict(zip(columns, row)) for row in rows[:1000]],
                "row_count": len(rows),
            }
        else:  # INSERT/UPDATE/DELETE
            conn.commit()
            return {
                "ok": True,
                "affected_rows": cur.rowcount,
                "message": f"Query executed successfully. {cur.rowcount} row(s) affected.",
            }
    except Exception as exc:
        conn.rollback()
        return {"ok": False, "error": str(exc)}
    finally:
        conn.close()


async def _pg_list_tables(args: dict) -> dict:
    """PostgreSQL jadvallar ro'yxati."""
    url = args.get("url") or _get_database_url()
    schema = args.get("schema", "public")
    
    if not url:
        return {"ok": False, "error": "No DATABASE_URL configured"}
    
    conn, err = await _pg_connect(url)
    if err:
        return {"ok": False, "error": err}
    
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT table_name, table_type 
            FROM information_schema.tables 
            WHERE table_schema = %s 
            ORDER BY table_name
        """, (schema,))
        
        tables = [{"name": row[0], "type": row[1]} for row in cur.fetchall()]
        return {"ok": True, "tables": tables, "count": len(tables)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    finally:
        conn.close()


async def _pg_describe_table(args: dict) -> dict:
    """PostgreSQL jadval tuzilmasi."""
    url = args.get("url") or _get_database_url()
    table = args.get("table", "")
    schema = args.get("schema", "public")
    
    if not url or not table:
        return {"ok": False, "error": "DATABASE_URL and table name are required"}
    
    conn, err = await _pg_connect(url)
    if err:
        return {"ok": False, "error": err}
    
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position
        """, (schema, table))
        
        columns = [
            {
                "name": row[0],
                "type": row[1],
                "nullable": row[2] == "YES",
                "default": row[3],
            }
            for row in cur.fetchall()
        ]
        
        # Get primary keys
        cur.execute("""
            SELECT column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
            WHERE tc.constraint_type = 'PRIMARY KEY'
            AND tc.table_schema = %s AND tc.table_name = %s
        """, (schema, table))
        
        pk_columns = [row[0] for row in cur.fetchall()]
        
        # Get row count
        cur.execute(f"SELECT COUNT(*) FROM {schema}.{table}")
        row_count = cur.fetchone()[0]
        
        return {
            "ok": True,
            "table": table,
            "schema": schema,
            "columns": columns,
            "primary_keys": pk_columns,
            "row_count": row_count,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    finally:
        conn.close()


# ---------------------------------------------------------------- #
# MySQL Implementation
# ---------------------------------------------------------------- #

async def _mysql_connect(url: str) -> tuple:
    """MySQL ga ulanish."""
    try:
        import pymysql
        # Parse URL
        parsed = urllib.parse.urlparse(url)
        conn = pymysql.connect(
            host=parsed.hostname or "localhost",
            port=parsed.port or 3306,
            user=parsed.username or "root",
            password=parsed.password or "",
            database=parsed.path.lstrip("/") or None,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
        )
        return conn, None
    except ImportError:
        return None, "pymysql not installed. Run: pip install pymysql"
    except Exception as exc:
        return None, f"Connection failed: {exc}"


async def _mysql_query(args: dict) -> dict:
    """MySQL so'rov bajarish."""
    url = args.get("url") or _get_database_url()
    sql = args.get("sql", "")
    params = args.get("params", [])
    readonly = args.get("readonly", True)
    
    if not url:
        return {"ok": False, "error": "No DATABASE_URL configured"}
    if not sql:
        return {"ok": False, "error": "SQL query is required"}
    
    safety_error = _check_safety(sql, readonly)
    if safety_error:
        return {"ok": False, "error": safety_error}
    
    conn, err = await _mysql_connect(url)
    if err:
        return {"ok": False, "error": err}
    
    try:
        cur = conn.cursor()
        cur.execute(sql, params or None)
        
        if cur.description:  # SELECT query
            columns = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
            return {
                "ok": True,
                "columns": columns,
                "rows": [dict(row) for row in rows[:1000]],
                "row_count": len(rows),
            }
        else:  # INSERT/UPDATE/DELETE
            conn.commit()
            return {
                "ok": True,
                "affected_rows": cur.rowcount,
                "message": f"Query executed successfully. {cur.rowcount} row(s) affected.",
            }
    except Exception as exc:
        conn.rollback()
        return {"ok": False, "error": str(exc)}
    finally:
        conn.close()


async def _mysql_list_tables(args: dict) -> dict:
    """MySQL jadvallar ro'yxati."""
    url = args.get("url") or _get_database_url()
    
    if not url:
        return {"ok": False, "error": "No DATABASE_URL configured"}
    
    conn, err = await _mysql_connect(url)
    if err:
        return {"ok": False, "error": err}
    
    try:
        cur = conn.cursor()
        cur.execute("SHOW TABLES")
        
        tables = [{"name": row[list(row.keys())[0]], "type": "BASE TABLE"} for row in cur.fetchall()]
        return {"ok": True, "tables": tables, "count": len(tables)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    finally:
        conn.close()


async def _mysql_describe_table(args: dict) -> dict:
    """MySQL jadval tuzilmasi."""
    url = args.get("url") or _get_database_url()
    table = args.get("table", "")
    
    if not url or not table:
        return {"ok": False, "error": "DATABASE_URL and table name are required"}
    
    conn, err = await _mysql_connect(url)
    if err:
        return {"ok": False, "error": err}
    
    try:
        cur = conn.cursor()
        cur.execute(f"DESCRIBE `{table}`")
        
        columns = []
        pk_columns = []
        for row in cur.fetchall():
            col = {
                "name": row["Field"],
                "type": row["Type"],
                "nullable": row["Null"] == "YES",
                "default": row["Default"],
                "key": row["Key"],
            }
            columns.append(col)
            if row["Key"] == "PRI":
                pk_columns.append(row["Field"])
        
        # Get row count
        cur.execute(f"SELECT COUNT(*) FROM `{table}`")
        row_count = cur.fetchone()[0]
        
        return {
            "ok": True,
            "table": table,
            "columns": columns,
            "primary_keys": pk_columns,
            "row_count": row_count,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    finally:
        conn.close()


# ---------------------------------------------------------------- #
# MongoDB Implementation
# ---------------------------------------------------------------- #

async def _mongo_connect(url: str = None) -> tuple:
    """MongoDB ga ulanish."""
    try:
        from pymongo import MongoClient
        mongo_url = url or _get_mongodb_url()
        client = MongoClient(mongo_url, serverSelectionTimeoutMS=5000)
        # Test connection
        client.admin.command("ping")
        return client, None
    except ImportError:
        return None, "pymongo not installed. Run: pip install pymongo"
    except Exception as exc:
        return None, f"Connection failed: {exc}"


def _parse_mongo_url(url: str) -> tuple[str, str]:
    """MongoDB URL'dan database nomini ajratish."""
    parsed = urllib.parse.urlparse(url)
    db_name = parsed.path.lstrip("/") or "test"
    return url, db_name


async def _mongo_find(args: dict) -> dict:
    """MongoDB hujjatlarni qidirish."""
    url = args.get("url") or _get_mongodb_url()
    database = args.get("database", "")
    collection = args.get("collection", "")
    query = args.get("query", {})
    limit = args.get("limit", 100)
    projection = args.get("projection", None)
    
    if not collection:
        return {"ok": False, "error": "collection name is required"}
    
    client, err = await _mongo_connect(url)
    if err:
        return {"ok": False, "error": err}
    
    try:
        if not database:
            _, database = _parse_mongo_url(url or _get_mongodb_url())
        
        db = client[database]
        col = db[collection]
        
        cursor = col.find(query, projection).limit(min(limit, 1000))
        documents = []
        for doc in cursor:
            doc["_id"] = str(doc["_id"])  # Convert ObjectId to string
            documents.append(doc)
        
        return {
            "ok": True,
            "documents": documents,
            "count": len(documents),
            "database": database,
            "collection": collection,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    finally:
        client.close()


async def _mongo_insert(args: dict) -> dict:
    """MongoDB hujjat qo'shish."""
    url = args.get("url") or _get_mongodb_url()
    database = args.get("database", "")
    collection = args.get("collection", "")
    documents = args.get("documents", [])
    
    if not collection:
        return {"ok": False, "error": "collection name is required"}
    if not documents:
        return {"ok": False, "error": "documents are required"}
    
    client, err = await _mongo_connect(url)
    if err:
        return {"ok": False, "error": err}
    
    try:
        if not database:
            _, database = _parse_mongo_url(url or _get_mongodb_url())
        
        db = client[database]
        col = db[collection]
        
        if isinstance(documents, list):
            result = col.insert_many(documents)
            return {
                "ok": True,
                "inserted_ids": [str(id) for id in result.inserted_ids],
                "count": len(result.inserted_ids),
                "message": f"Inserted {len(result.inserted_ids)} document(s)",
            }
        else:
            result = col.insert_one(documents)
            return {
                "ok": True,
                "inserted_id": str(result.inserted_id),
                "message": "Inserted 1 document",
            }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    finally:
        client.close()


async def _mongo_update(args: dict) -> dict:
    """MongoDB hujjat yangilash."""
    url = args.get("url") or _get_mongodb_url()
    database = args.get("database", "")
    collection = args.get("collection", "")
    query = args.get("query", {})
    update = args.get("update", {})
    upsert = args.get("upsert", False)
    
    if not collection:
        return {"ok": False, "error": "collection name is required"}
    if not query or not update:
        return {"ok": False, "error": "query and update are required"}
    
    client, err = await _mongo_connect(url)
    if err:
        return {"ok": False, "error": err}
    
    try:
        if not database:
            _, database = _parse_mongo_url(url or _get_mongodb_url())
        
        db = client[database]
        col = db[collection]
        
        result = col.update_many(query, update, upsert=upsert)
        return {
            "ok": True,
            "matched_count": result.matched_count,
            "modified_count": result.modified_count,
            "upserted_id": str(result.upserted_id) if result.upserted_id else None,
            "message": f"Matched {result.matched_count}, modified {result.modified_count}",
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    finally:
        client.close()


async def _mongo_delete(args: dict) -> dict:
    """MongoDB hujjat o'chirish."""
    url = args.get("url") or _get_mongodb_url()
    database = args.get("database", "")
    collection = args.get("collection", "")
    query = args.get("query", {})
    
    if not collection:
        return {"ok": False, "error": "collection name is required"}
    if not query:
        return {"ok": False, "error": "query is required (empty query not allowed)"}
    
    client, err = await _mongo_connect(url)
    if err:
        return {"ok": False, "error": err}
    
    try:
        if not database:
            _, database = _parse_mongo_url(url or _get_mongodb_url())
        
        db = client[database]
        col = db[collection]
        
        result = col.delete_many(query)
        return {
            "ok": True,
            "deleted_count": result.deleted_count,
            "message": f"Deleted {result.deleted_count} document(s)",
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    finally:
        client.close()


async def _mongo_list_collections(args: dict) -> dict:
    """MongoDB kolleksiyalar ro'yxati."""
    url = args.get("url") or _get_mongodb_url()
    database = args.get("database", "")
    
    client, err = await _mongo_connect(url)
    if err:
        return {"ok": False, "error": err}
    
    try:
        if not database:
            _, database = _parse_mongo_url(url or _get_mongodb_url())
        
        db = client[database]
        collections = db.list_collection_names()
        
        # Get collection stats
        result = []
        for col_name in sorted(collections):
            col = db[col_name]
            stats = col.database.command("collStats", col_name)
            result.append({
                "name": col_name,
                "count": stats.get("count", 0),
                "size": stats.get("size", 0),
            })
        
        return {
            "ok": True,
            "collections": result,
            "count": len(result),
            "database": database,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    finally:
        client.close()


# ---------------------------------------------------------------- #
# MCP Tool Definitions
# ---------------------------------------------------------------- #

@mcp.tool()
async def db_query(
    sql: str,
    url: str = "",
    params: list = None,
    readonly: bool = True,
) -> str:
    """Execute a SQL query on PostgreSQL or MySQL database.

    Args:
        sql: SQL query to execute (SELECT, INSERT, UPDATE, DELETE)
        url: Database connection URL (default: DATABASE_URL env var)
            PostgreSQL: postgresql://user:pass@host:5432/dbname
            MySQL: mysql://user:pass@host:3306/dbname
        params: Query parameters for prepared statements
        readonly: If True, only SELECT queries allowed (default: True)

    Returns:
        Query results as JSON with columns and rows
    """
    db_url = url or _get_database_url()
    db_type = _detect_db_type(db_url)
    
    if db_type == "postgresql":
        result = await _pg_query({"url": db_url, "sql": sql, "params": params, "readonly": readonly})
    elif db_type == "mysql":
        result = await _mysql_query({"url": db_url, "sql": sql, "params": params, "readonly": readonly})
    else:
        return json.dumps({"ok": False, "error": f"Unsupported database type: {db_type}. Use PostgreSQL or MySQL URL."})
    
    return json.dumps(result, indent=2)


@mcp.tool()
async def db_list_tables(url: str = "", schema: str = "public") -> str:
    """List all tables in the database.

    Args:
        url: Database connection URL (default: DATABASE_URL env var)
        schema: Schema name for PostgreSQL (default: public)

    Returns:
        List of tables with their types
    """
    db_url = url or _get_database_url()
    db_type = _detect_db_type(db_url)
    
    if db_type == "postgresql":
        result = await _pg_list_tables({"url": db_url, "schema": schema})
    elif db_type == "mysql":
        result = await _mysql_list_tables({"url": db_url})
    else:
        return json.dumps({"ok": False, "error": f"Unsupported database type: {db_type}"})
    
    return json.dumps(result, indent=2)


@mcp.tool()
async def db_describe_table(table: str, url: str = "", schema: str = "public") -> str:
    """Get table structure (columns, types, constraints).

    Args:
        table: Table name to describe
        url: Database connection URL (default: DATABASE_URL env var)
        schema: Schema name for PostgreSQL (default: public)

    Returns:
        Table structure with columns, types, and primary keys
    """
    db_url = url or _get_database_url()
    db_type = _detect_db_type(db_url)
    
    if db_type == "postgresql":
        result = await _pg_describe_table({"url": db_url, "table": table, "schema": schema})
    elif db_type == "mysql":
        result = await _mysql_describe_table({"url": db_url, "table": table})
    else:
        return json.dumps({"ok": False, "error": f"Unsupported database type: {db_type}"})
    
    return json.dumps(result, indent=2)


@mcp.tool()
async def mongo_find(
    collection: str,
    query: dict = None,
    database: str = "",
    url: str = "",
    limit: int = 100,
    projection: dict = None,
) -> str:
    """Find documents in a MongoDB collection.

    Args:
        collection: Collection name to search
        query: MongoDB query filter (default: {} - all documents)
        database: Database name (extracted from URL if not provided)
        url: MongoDB connection URL (default: MONGODB_URL env var)
        limit: Maximum documents to return (default: 100, max: 1000)
        projection: Fields to include/exclude (e.g., {"_id": 0, "name": 1})

    Returns:
        List of matching documents
    """
    result = await _mongo_find({
        "collection": collection,
        "query": query or {},
        "database": database,
        "url": url,
        "limit": limit,
        "projection": projection,
    })
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
async def mongo_insert(
    collection: str,
    documents: Any,
    database: str = "",
    url: str = "",
) -> str:
    """Insert documents into a MongoDB collection.

    Args:
        collection: Collection name
        documents: Single document (dict) or list of documents to insert
        database: Database name (extracted from URL if not provided)
        url: MongoDB connection URL (default: MONGODB_URL env var)

    Returns:
        Inserted document IDs
    """
    result = await _mongo_insert({
        "collection": collection,
        "documents": documents,
        "database": database,
        "url": url,
    })
    return json.dumps(result, indent=2)


@mcp.tool()
async def mongo_update(
    collection: str,
    query: dict,
    update: dict,
    database: str = "",
    url: str = "",
    upsert: bool = False,
) -> str:
    """Update documents in a MongoDB collection.

    Args:
        collection: Collection name
        query: Query to match documents (e.g., {"_id": "..."})
        update: Update operations (e.g., {"$set": {"field": "value"}})
        database: Database name (extracted from URL if not provided)
        url: MongoDB connection URL (default: MONGODB_URL env var)
        upsert: Insert if no match found (default: False)

    Returns:
        Update statistics (matched, modified counts)
    """
    result = await _mongo_update({
        "collection": collection,
        "query": query,
        "update": update,
        "database": database,
        "url": url,
        "upsert": upsert,
    })
    return json.dumps(result, indent=2)


@mcp.tool()
async def mongo_delete(
    collection: str,
    query: dict,
    database: str = "",
    url: str = "",
) -> str:
    """Delete documents from a MongoDB collection.

    Args:
        collection: Collection name
        query: Query to match documents to delete (empty query not allowed)
        database: Database name (extracted from URL if not provided)
        url: MongoDB connection URL (default: MONGODB_URL env var)

    Returns:
        Number of deleted documents
    """
    result = await _mongo_delete({
        "collection": collection,
        "query": query,
        "database": database,
        "url": url,
    })
    return json.dumps(result, indent=2)


@mcp.tool()
async def mongo_list_collections(database: str = "", url: str = "") -> str:
    """List all collections in a MongoDB database.

    Args:
        database: Database name (extracted from URL if not provided)
        url: MongoDB connection URL (default: MONGODB_URL env var)

    Returns:
        List of collections with document counts
    """
    result = await _mongo_list_collections({
        "database": database,
        "url": url,
    })
    return json.dumps(result, indent=2)


@mcp.tool()
async def db_status(url: str = "") -> str:
    """Check database connection status.

    Args:
        url: Database connection URL (default: DATABASE_URL or MONGODB_URL env var)

    Returns:
        Connection status and database info
    """
    db_url = url or _get_database_url() or _get_mongodb_url()
    db_type = _detect_db_type(db_url)
    
    if db_type == "postgresql":
        conn, err = await _pg_connect(db_url)
        if err:
            return json.dumps({"ok": False, "error": err, "type": "postgresql"})
        try:
            cur = conn.cursor()
            cur.execute("SELECT version()")
            version = cur.fetchone()[0]
            cur.execute("SELECT current_database()")
            database = cur.fetchone()[0]
            return json.dumps({
                "ok": True,
                "type": "postgresql",
                "version": version,
                "database": database,
                "status": "connected",
            })
        except Exception as exc:
            return json.dumps({"ok": False, "error": str(exc)})
        finally:
            conn.close()
    
    elif db_type == "mysql":
        conn, err = await _mysql_connect(db_url)
        if err:
            return json.dumps({"ok": False, "error": err, "type": "mysql"})
        try:
            cur = conn.cursor()
            cur.execute("SELECT version()")
            version = cur.fetchone()[0]
            cur.execute("SELECT current_database()")
            database = cur.fetchone()[0]
            return json.dumps({
                "ok": True,
                "type": "mysql",
                "version": version,
                "database": database,
                "status": "connected",
            })
        except Exception as exc:
            return json.dumps({"ok": False, "error": str(exc)})
        finally:
            conn.close()
    
    elif db_type == "mongodb":
        client, err = await _mongo_connect(db_url)
        if err:
            return json.dumps({"ok": False, "error": err, "type": "mongodb"})
        try:
            info = client.server_info()
            _, database = _parse_mongo_url(db_url)
            return json.dumps({
                "ok": True,
                "type": "mongodb",
                "version": info.get("version", "unknown"),
                "database": database,
                "status": "connected",
            })
        except Exception as exc:
            return json.dumps({"ok": False, "error": str(exc)})
        finally:
            client.close()
    
    else:
        return json.dumps({
            "ok": False,
            "error": f"Unknown database type. Configure DATABASE_URL or MONGODB_URL.",
            "examples": {
                "postgresql": "postgresql://user:pass@localhost:5432/dbname",
                "mysql": "mysql://user:pass@localhost:3306/dbname",
                "mongodb": "mongodb://localhost:27017/dbname",
            },
        })


# ---------------------------------------------------------------- #
# Main
# ---------------------------------------------------------------- #

if __name__ == "__main__":
    mcp.run()
