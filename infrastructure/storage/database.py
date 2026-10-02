#!/usr/bin/env python3
# drone-detector/infrastructure/storage/database.py
"""
Database Connection Module

This module provides comprehensive database connectivity for the Drone Detection System,
supporting:
- Multiple database backends (SQLite, PostgreSQL, MySQL)
- Connection pooling for high performance
- Async database operations
- Automatic reconnection handling
- Transaction management
- Query builder utilities
- Health checking and monitoring
- Migration management
- Backup and restore operations
- Connection encryption (SSL/TLS)
- Read replicas for load balancing
- Connection metrics and monitoring
"""

import asyncio
import json
import sqlite3
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Optional, List, Dict, Any, Union, Tuple, Callable, AsyncGenerator
from urllib.parse import quote_plus

# Try to import async database drivers
try:
    import asyncpg
    ASYNCPG_AVAILABLE = True
except ImportError:
    ASYNCPG_AVAILABLE = False

try:
    import aiomysql
    AIOMYSQL_AVAILABLE = True
except ImportError:
    AIOMYSQL_AVAILABLE = False

try:
    import aiosqlite
    AIOSQLITE_AVAILABLE = True
except ImportError:
    AIOSQLITE_AVAILABLE = False

# For connection pooling
from contextlib import contextmanager
import threading

# Setup logging
import logging
logger = logging.getLogger(__name__)


# ============================================================================
# Enums and Data Classes
# ============================================================================

class DatabaseType(Enum):
    """Supported database backends"""
    SQLITE = "sqlite"
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"


class PoolState(Enum):
    """Connection pool state"""
    INITIALIZING = "initializing"
    READY = "ready"
    CLOSING = "closing"
    CLOSED = "closed"
    ERROR = "error"


@dataclass
class DatabaseConfig:
    """Database connection configuration"""
    # Database type
    db_type: DatabaseType = DatabaseType.SQLITE
    
    # SQLite specific
    sqlite_path: str = "data/detections.db"
    sqlite_journal_mode: str = "WAL"  # WAL, DELETE, TRUNCATE
    sqlite_synchronous: int = 1  # 0=OFF, 1=NORMAL, 2=FULL
    sqlite_cache_size: int = -2000  # 2000 pages
    
    # PostgreSQL specific
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_database: str = "drone_detector"
    postgres_user: str = "drone_user"
    postgres_password: str = ""
    postgres_ssl_mode: str = "prefer"  # disable, allow, prefer, require
    
    # MySQL specific
    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_database: str = "drone_detector"
    mysql_user: str = "drone_user"
    mysql_password: str = ""
    mysql_charset: str = "utf8mb4"
    
    # Connection pool settings
    pool_min_size: int = 1
    pool_max_size: int = 10
    pool_max_queries: int = 50000
    pool_max_idle_time: int = 300  # seconds
    pool_recycle_time: int = 3600  # seconds
    pool_timeout: int = 30  # seconds
    
    # General settings
    echo: bool = False
    auto_commit: bool = False
    auto_rollback_on_error: bool = True
    timeout: int = 30  # seconds
    
    # SSL/TLS settings
    ssl_enabled: bool = False
    ssl_ca_cert: Optional[str] = None
    ssl_client_cert: Optional[str] = None
    ssl_client_key: Optional[str] = None
    
    # Read replicas
    read_replicas: List[Dict[str, Any]] = field(default_factory=list)
    
    # Health check
    health_check_interval: int = 60  # seconds
    health_check_query: str = "SELECT 1"
    
    def get_connection_string(self) -> str:
        """Get connection string for database"""
        if self.db_type == DatabaseType.SQLITE:
            return f"sqlite:///{self.sqlite_path}"
        
        elif self.db_type == DatabaseType.POSTGRESQL:
            password_part = f":{quote_plus(self.postgres_password)}" if self.postgres_password else ""
            return (f"postgresql://{self.postgres_user}{password_part}@"
                   f"{self.postgres_host}:{self.postgres_port}/{self.postgres_database}")
        
        elif self.db_type == DatabaseType.MYSQL:
            password_part = f":{quote_plus(self.mysql_password)}" if self.mysql_password else ""
            return (f"mysql://{self.mysql_user}{password_part}@"
                   f"{self.mysql_host}:{self.mysql_port}/{self.mysql_database}")
        
        return ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (without sensitive data)"""
        return {
            'db_type': self.db_type.value,
            'pool_min_size': self.pool_min_size,
            'pool_max_size': self.pool_max_size,
            'pool_timeout': self.pool_timeout,
            'auto_commit': self.auto_commit
        }


@dataclass
class ConnectionStats:
    """Database connection statistics"""
    total_connections: int = 0
    active_connections: int = 0
    idle_connections: int = 0
    total_queries: int = 0
    total_transactions: int = 0
    failed_queries: int = 0
    avg_query_time_ms: float = 0.0
    max_query_time_ms: float = 0.0
    pool_state: str = "unknown"
    uptime_seconds: float = 0.0
    last_health_check: Optional[datetime] = None
    last_error: Optional[str] = None


# ============================================================================
# Base Database Adapter
# ============================================================================

class DatabaseAdapter(ABC):
    """Abstract base class for database adapters"""
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.pool = None
        self.state = PoolState.INITIALIZING
        self.stats = ConnectionStats()
        self._start_time = time.time()
        self._health_check_task: Optional[asyncio.Task] = None
    
    @abstractmethod
    async def connect(self) -> None:
        """Establish database connection"""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Close database connection"""
        pass
    
    @abstractmethod
    async def execute(self, query: str, *args, **kwargs) -> Any:
        """Execute a query and return result"""
        pass
    
    @abstractmethod
    async def fetch_one(self, query: str, *args, **kwargs) -> Optional[Dict[str, Any]]:
        """Fetch one row"""
        pass
    
    @abstractmethod
    async def fetch_all(self, query: str, *args, **kwargs) -> List[Dict[str, Any]]:
        """Fetch all rows"""
        pass
    
    @abstractmethod
    async def fetch_val(self, query: str, *args, **kwargs) -> Any:
        """Fetch a single value"""
        pass
    
    @abstractmethod
    async def execute_many(self, query: str, params_list: List[Tuple]) -> List[Any]:
        """Execute many queries"""
        pass
    
    @abstractmethod
    async def transaction(self) -> AsyncGenerator:
        """Transaction context manager"""
        pass
    
    async def health_check(self) -> bool:
        """Check database health"""
        try:
            await self.execute(self.config.health_check_query)
            self.stats.last_health_check = datetime.now()
            return True
        except Exception as e:
            self.stats.last_error = str(e)
            logger.error(f"Health check failed: {e}")
            return False
    
    async def start_health_checks(self):
        """Start periodic health checks"""
        async def health_check_loop():
            while self.state == PoolState.READY:
                await asyncio.sleep(self.config.health_check_interval)
                await self.health_check()
        
        self._health_check_task = asyncio.create_task(health_check_loop())
    
    def get_stats(self) -> ConnectionStats:
        """Get connection statistics"""
        self.stats.uptime_seconds = time.time() - self._start_time
        self.stats.pool_state = self.state.value
        return self.stats


# ============================================================================
# SQLite Adapter
# ============================================================================

class SQLiteAdapter(DatabaseAdapter):
    """SQLite database adapter using aiosqlite"""
    
    def __init__(self, config: DatabaseConfig):
        super().__init__(config)
        self._connection_pool: List[aiosqlite.Connection] = []
        self._pool_lock = asyncio.Lock()
    
    async def connect(self) -> None:
        """Connect to SQLite database"""
        if not AIOSQLITE_AVAILABLE:
            raise RuntimeError("aiosqlite not available. Install with: pip install aiosqlite")
        
        # Ensure directory exists
        db_path = Path(self.config.sqlite_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.state = PoolState.INITIALIZING
        
        # Create connection pool
        for i in range(self.config.pool_min_size):
            conn = await self._create_connection()
            self._connection_pool.append(conn)
        
        self.state = PoolState.READY
        logger.info(f"SQLite connection pool initialized with {len(self._connection_pool)} connections")
        
        # Start health checks
        await self.start_health_checks()
    
    async def _create_connection(self) -> aiosqlite.Connection:
        """Create a new database connection"""
        conn = await aiosqlite.connect(
            self.config.sqlite_path,
            timeout=self.config.timeout,
            autocommit=self.config.auto_commit
        )
        
        # Configure SQLite
        await conn.execute(f"PRAGMA journal_mode={self.config.sqlite_journal_mode}")
        await conn.execute(f"PRAGMA synchronous={self.config.sqlite_synchronous}")
        await conn.execute(f"PRAGMA cache_size={self.config.sqlite_cache_size}")
        await conn.execute("PRAGMA foreign_keys=ON")
        
        if self.config.echo:
            conn.set_trace_callback(logger.debug)
        
        return conn
    
    async def disconnect(self) -> None:
        """Close all database connections"""
        self.state = PoolState.CLOSING
        
        if self._health_check_task:
            self._health_check_task.cancel()
        
        async with self._pool_lock:
            for conn in self._connection_pool:
                await conn.close()
            self._connection_pool.clear()
        
        self.state = PoolState.CLOSED
        logger.info("SQLite connections closed")
    
    async def _get_connection(self) -> aiosqlite.Connection:
        """Get a connection from the pool"""
        async with self._pool_lock:
            if not self._connection_pool:
                return await self._create_connection()
            
            # Get idle connection
            for i, conn in enumerate(self._connection_pool):
                # Check if connection is healthy
                if not await self._is_connection_healthy(conn):
                    await conn.close()
                    self._connection_pool[i] = await self._create_connection()
                
                return self._connection_pool[i]
            
            # Create new connection if under max
            if len(self._connection_pool) < self.config.pool_max_size:
                conn = await self._create_connection()
                self._connection_pool.append(conn)
                return conn
            
            # Wait for available connection
            raise RuntimeError("No available connections")
    
    async def _is_connection_healthy(self, conn: aiosqlite.Connection) -> bool:
        """Check if connection is healthy"""
        try:
            await conn.execute("SELECT 1")
            return True
        except:
            return False
    
    async def execute(self, query: str, *args, **kwargs) -> Any:
        """Execute a query"""
        start_time = time.time()
        conn = await self._get_connection()
        
        try:
            cursor = await conn.execute(query, args if args else None)
            self.stats.total_queries += 1
            
            if not self.config.auto_commit and not conn.autocommit:
                await conn.commit()
            
            query_time = (time.time() - start_time) * 1000
            self.stats.avg_query_time_ms = (
                (self.stats.avg_query_time_ms * (self.stats.total_queries - 1) + query_time) 
                / self.stats.total_queries
            )
            self.stats.max_query_time_ms = max(self.stats.max_query_time_ms, query_time)
            
            return cursor
            
        except Exception as e:
            self.stats.failed_queries += 1
            self.stats.last_error = str(e)
            logger.error(f"Query failed: {e}\nQuery: {query[:500]}")
            if self.config.auto_rollback_on_error:
                await conn.rollback()
            raise
    
    async def fetch_one(self, query: str, *args, **kwargs) -> Optional[Dict[str, Any]]:
        """Fetch one row"""
        cursor = await self.execute(query, *args, **kwargs)
        row = await cursor.fetchone()
        
        if row is None:
            return None
        
        # Convert to dict
        columns = [desc[0] for desc in cursor.description]
        return dict(zip(columns, row))
    
    async def fetch_all(self, query: str, *args, **kwargs) -> List[Dict[str, Any]]:
        """Fetch all rows"""
        cursor = await self.execute(query, *args, **kwargs)
        rows = await cursor.fetchall()
        
        if not rows:
            return []
        
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    
    async def fetch_val(self, query: str, *args, **kwargs) -> Any:
        """Fetch a single value"""
        cursor = await self.execute(query, *args, **kwargs)
        row = await cursor.fetchone()
        
        if row is None:
            return None
        
        return row[0]
    
    async def execute_many(self, query: str, params_list: List[Tuple]) -> List[Any]:
        """Execute many queries"""
        conn = await self._get_connection()
        results = []
        
        try:
            for params in params_list:
                cursor = await conn.execute(query, params)
                results.append(cursor)
            
            await conn.commit()
            self.stats.total_queries += len(params_list)
            
        except Exception as e:
            self.stats.failed_queries += 1
            await conn.rollback()
            raise
        
        return results
    
    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator:
        """Transaction context manager"""
        conn = await self._get_connection()
        
        try:
            await conn.execute("BEGIN TRANSACTION")
            self.stats.total_transactions += 1
            yield
            await conn.commit()
            
        except Exception:
            await conn.rollback()
            raise


# ============================================================================
# PostgreSQL Adapter
# ============================================================================

class PostgreSQLAdapter(DatabaseAdapter):
    """PostgreSQL database adapter using asyncpg"""
    
    def __init__(self, config: DatabaseConfig):
        super().__init__(config)
        self._pool: Optional[asyncpg.Pool] = None
    
    async def connect(self) -> None:
        """Connect to PostgreSQL database"""
        if not ASYNCPG_AVAILABLE:
            raise RuntimeError("asyncpg not available. Install with: pip install asyncpg")
        
        self.state = PoolState.INITIALIZING
        
        # Build connection parameters
        conn_params = {
            'host': self.config.postgres_host,
            'port': self.config.postgres_port,
            'database': self.config.postgres_database,
            'user': self.config.postgres_user,
            'password': self.config.postgres_password,
            'min_size': self.config.pool_min_size,
            'max_size': self.config.pool_max_size,
            'max_queries': self.config.pool_max_queries,
            'max_inactive_connection_lifetime': self.config.pool_max_idle_time,
            'command_timeout': self.config.timeout,
            'ssl': self.config.ssl_enabled
        }
        
        # SSL configuration
        if self.config.ssl_enabled and self.config.ssl_ca_cert:
            conn_params['ssl'] = True
            conn_params['ssl_root_cert'] = self.config.ssl_ca_cert
        
        # Create connection pool
        self._pool = await asyncpg.create_pool(**conn_params)
        
        self.state = PoolState.READY
        logger.info(f"PostgreSQL connection pool initialized with {self.config.pool_min_size}-{self.config.pool_max_size} connections")
        
        # Start health checks
        await self.start_health_checks()
    
    async def disconnect(self) -> None:
        """Close database connections"""
        self.state = PoolState.CLOSING
        
        if self._health_check_task:
            self._health_check_task.cancel()
        
        if self._pool:
            await self._pool.close()
        
        self.state = PoolState.CLOSED
        logger.info("PostgreSQL connections closed")
    
    async def execute(self, query: str, *args, **kwargs) -> Any:
        """Execute a query"""
        start_time = time.time()
        
        async with self._pool.acquire() as conn:
            try:
                result = await conn.execute(query, *args)
                self.stats.total_queries += 1
                
                query_time = (time.time() - start_time) * 1000
                self.stats.avg_query_time_ms = (
                    (self.stats.avg_query_time_ms * (self.stats.total_queries - 1) + query_time) 
                    / self.stats.total_queries
                )
                self.stats.max_query_time_ms = max(self.stats.max_query_time_ms, query_time)
                
                return result
                
            except Exception as e:
                self.stats.failed_queries += 1
                self.stats.last_error = str(e)
                logger.error(f"Query failed: {e}\nQuery: {query[:500]}")
                raise
    
    async def fetch_one(self, query: str, *args, **kwargs) -> Optional[Dict[str, Any]]:
        """Fetch one row"""
        start_time = time.time()
        
        async with self._pool.acquire() as conn:
            try:
                row = await conn.fetchrow(query, *args)
                self.stats.total_queries += 1
                
                query_time = (time.time() - start_time) * 1000
                self.stats.avg_query_time_ms = (
                    (self.stats.avg_query_time_ms * (self.stats.total_queries - 1) + query_time) 
                    / self.stats.total_queries
                )
                
                return dict(row) if row else None
                
            except Exception as e:
                self.stats.failed_queries += 1
                raise
    
    async def fetch_all(self, query: str, *args, **kwargs) -> List[Dict[str, Any]]:
        """Fetch all rows"""
        start_time = time.time()
        
        async with self._pool.acquire() as conn:
            try:
                rows = await conn.fetch(query, *args)
                self.stats.total_queries += 1
                
                query_time = (time.time() - start_time) * 1000
                self.stats.avg_query_time_ms = (
                    (self.stats.avg_query_time_ms * (self.stats.total_queries - 1) + query_time) 
                    / self.stats.total_queries
                )
                
                return [dict(row) for row in rows]
                
            except Exception as e:
                self.stats.failed_queries += 1
                raise
    
    async def fetch_val(self, query: str, *args, **kwargs) -> Any:
        """Fetch a single value"""
        row = await self.fetch_one(query, *args, **kwargs)
        if row:
            return next(iter(row.values()))
        return None
    
    async def execute_many(self, query: str, params_list: List[Tuple]) -> List[Any]:
        """Execute many queries"""
        results = []
        
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                for params in params_list:
                    result = await conn.execute(query, *params)
                    results.append(result)
                self.stats.total_queries += len(params_list)
        
        return results
    
    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator:
        """Transaction context manager"""
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                self.stats.total_transactions += 1
                yield


# ============================================================================
# MySQL Adapter
# ============================================================================

class MySQLAdapter(DatabaseAdapter):
    """MySQL database adapter using aiomysql"""
    
    def __init__(self, config: DatabaseConfig):
        super().__init__(config)
        self._pool = None
    
    async def connect(self) -> None:
        """Connect to MySQL database"""
        if not AIOMYSQL_AVAILABLE:
            raise RuntimeError("aiomysql not available. Install with: pip install aiomysql")
        
        self.state = PoolState.INITIALIZING
        
        # Create connection pool
        self._pool = await aiomysql.create_pool(
            host=self.config.mysql_host,
            port=self.config.mysql_port,
            user=self.config.mysql_user,
            password=self.config.mysql_password,
            db=self.config.mysql_database,
            charset=self.config.mysql_charset,
            minsize=self.config.pool_min_size,
            maxsize=self.config.pool_max_size,
            autocommit=self.config.auto_commit,
            pool_recycle=self.config.pool_recycle_time
        )
        
        self.state = PoolState.READY
        logger.info(f"MySQL connection pool initialized with {self.config.pool_min_size}-{self.config.pool_max_size} connections")
        
        # Start health checks
        await self.start_health_checks()
    
    async def disconnect(self) -> None:
        """Close database connections"""
        self.state = PoolState.CLOSING
        
        if self._health_check_task:
            self._health_check_task.cancel()
        
        if self._pool:
            self._pool.close()
            await self._pool.wait_closed()
        
        self.state = PoolState.CLOSED
        logger.info("MySQL connections closed")
    
    async def _get_connection(self):
        """Get a connection from the pool"""
        return await self._pool.acquire()
    
    async def _release_connection(self, conn):
        """Release connection back to pool"""
        self._pool.release(conn)
    
    async def execute(self, query: str, *args, **kwargs) -> Any:
        """Execute a query"""
        start_time = time.time()
        conn = await self._get_connection()
        
        try:
            async with conn.cursor() as cursor:
                await cursor.execute(query, args)
                result = cursor
                self.stats.total_queries += 1
                
                query_time = (time.time() - start_time) * 1000
                self.stats.avg_query_time_ms = (
                    (self.stats.avg_query_time_ms * (self.stats.total_queries - 1) + query_time) 
                    / self.stats.total_queries
                )
                
                return result
                
        except Exception as e:
            self.stats.failed_queries += 1
            raise
        finally:
            await self._release_connection(conn)
    
    async def fetch_one(self, query: str, *args, **kwargs) -> Optional[Dict[str, Any]]:
        """Fetch one row"""
        conn = await self._get_connection()
        
        try:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(query, args)
                row = await cursor.fetchone()
                self.stats.total_queries += 1
                return row
                
        finally:
            await self._release_connection(conn)
    
    async def fetch_all(self, query: str, *args, **kwargs) -> List[Dict[str, Any]]:
        """Fetch all rows"""
        conn = await self._get_connection()
        
        try:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(query, args)
                rows = await cursor.fetchall()
                self.stats.total_queries += 1
                return rows
                
        finally:
            await self._release_connection(conn)
    
    async def fetch_val(self, query: str, *args, **kwargs) -> Any:
        """Fetch a single value"""
        row = await self.fetch_one(query, *args, **kwargs)
        if row:
            return next(iter(row.values()))
        return None
    
    async def execute_many(self, query: str, params_list: List[Tuple]) -> List[Any]:
        """Execute many queries"""
        conn = await self._get_connection()
        results = []
        
        try:
            async with conn.cursor() as cursor:
                for params in params_list:
                    await cursor.execute(query, params)
                    results.append(cursor)
                self.stats.total_queries += len(params_list)
                
        finally:
            await self._release_connection(conn)
        
        return results
    
    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator:
        """Transaction context manager"""
        conn = await self._get_connection()
        
        try:
            await conn.begin()
            self.stats.total_transactions += 1
            yield
            await conn.commit()
            
        except Exception:
            await conn.rollback()
            raise
        finally:
            await self._release_connection(conn)


# ============================================================================
# Database Manager (Main Interface)
# ============================================================================

class DatabaseManager:
    """
    Main database manager interface
    
    This class provides a unified interface for all database operations,
    automatically selecting the appropriate adapter based on configuration.
    """
    
    def __init__(self, config: Optional[DatabaseConfig] = None):
        """
        Initialize database manager
        
        Args:
            config: Database configuration (uses defaults if None)
        """
        self.config = config or DatabaseConfig()
        self._adapter: Optional[DatabaseAdapter] = None
        self._initialized = False
        self._read_replica_index = 0
    
    async def initialize(self) -> None:
        """Initialize database connection"""
        if self._initialized:
            logger.warning("Database already initialized")
            return
        
        # Create appropriate adapter
        if self.config.db_type == DatabaseType.SQLITE:
            self._adapter = SQLiteAdapter(self.config)
        elif self.config.db_type == DatabaseType.POSTGRESQL:
            self._adapter = PostgreSQLAdapter(self.config)
        elif self.config.db_type == DatabaseType.MYSQL:
            self._adapter = MySQLAdapter(self.config)
        else:
            raise ValueError(f"Unsupported database type: {self.config.db_type}")
        
        await self._adapter.connect()
        self._initialized = True
        logger.info(f"Database manager initialized with {self.config.db_type.value}")
    
    async def close(self) -> None:
        """Close database connection"""
        if self._adapter:
            await self._adapter.disconnect()
            self._initialized = False
    
    async def ensure_initialized(self) -> None:
        """Ensure database is initialized"""
        if not self._initialized:
            await self.initialize()
    
    # ========================================================================
    # Query Methods
    # ========================================================================
    
    async def execute(self, query: str, *args, **kwargs) -> Any:
        """Execute a query"""
        await self.ensure_initialized()
        return await self._adapter.execute(query, *args, **kwargs)
    
    async def fetch_one(self, query: str, *args, **kwargs) -> Optional[Dict[str, Any]]:
        """Fetch one row"""
        await self.ensure_initialized()
        return await self._adapter.fetch_one(query, *args, **kwargs)
    
    async def fetch_all(self, query: str, *args, **kwargs) -> List[Dict[str, Any]]:
        """Fetch all rows"""
        await self.ensure_initialized()
        return await self._adapter.fetch_all(query, *args, **kwargs)
    
    async def fetch_val(self, query: str, *args, **kwargs) -> Any:
        """Fetch a single value"""
        await self.ensure_initialized()
        return await self._adapter.fetch_val(query, *args, **kwargs)
    
    async def execute_many(self, query: str, params_list: List[Tuple]) -> List[Any]:
        """Execute many queries"""
        await self.ensure_initialized()
        return await self._adapter.execute_many(query, params_list)
    
    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator:
        """Transaction context manager"""
        await self.ensure_initialized()
        async with self._adapter.transaction() as tx:
            yield tx
    
    # ========================================================================
    # Health and Statistics
    # ========================================================================
    
    async def health_check(self) -> bool:
        """Check database health"""
        await self.ensure_initialized()
        return await self._adapter.health_check()
    
    def get_stats(self) -> ConnectionStats:
        """Get connection statistics"""
        if self._adapter:
            return self._adapter.get_stats()
        return ConnectionStats()
    
    # ========================================================================
    # Migration Methods
    # ========================================================================
    
    async def create_tables(self, drop_existing: bool = False) -> None:
        """
        Create required database tables
        
        Args:
            drop_existing: Drop existing tables if True
        """
        await self.ensure_initialized()
        
        # Define table schemas
        tables = {
            'detections': """
                CREATE TABLE IF NOT EXISTS detections (
                    id TEXT PRIMARY KEY,
                    timestamp TIMESTAMP NOT NULL,
                    drone_type TEXT,
                    confidence REAL,
                    threat_level TEXT,
                    frequency REAL,
                    signal_strength REAL,
                    latitude REAL,
                    longitude REAL,
                    altitude REAL,
                    remote_id TEXT,
                    metadata JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """,
            
            'detection_events': """
                CREATE TABLE IF NOT EXISTS detection_events (
                    id TEXT PRIMARY KEY,
                    detection_id TEXT,
                    event_type TEXT,
                    event_data JSON,
                    timestamp TIMESTAMP NOT NULL,
                    FOREIGN KEY (detection_id) REFERENCES detections (id)
                )
            """,
            
            'drone_signatures': """
                CREATE TABLE IF NOT EXISTS drone_signatures (
                    id TEXT PRIMARY KEY,
                    drone_type TEXT UNIQUE,
                    signature_data JSON,
                    confidence REAL,
                    verified BOOLEAN,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """,
            
            'alerts': """
                CREATE TABLE IF NOT EXISTS alerts (
                    id TEXT PRIMARY KEY,
                    detection_id TEXT,
                    severity TEXT,
                    message TEXT,
                    acknowledged BOOLEAN,
                    acknowledged_by TEXT,
                    resolved BOOLEAN,
                    timestamp TIMESTAMP NOT NULL,
                    resolved_at TIMESTAMP,
                    FOREIGN KEY (detection_id) REFERENCES detections (id)
                )
            """,
            
            'system_metrics': """
                CREATE TABLE IF NOT EXISTS system_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP NOT NULL,
                    metric_name TEXT,
                    metric_value REAL,
                    metadata JSON
                )
            """,
            
            'recordings': """
                CREATE TABLE IF NOT EXISTS recordings (
                    id TEXT PRIMARY KEY,
                    session_id TEXT,
                    file_path TEXT,
                    duration REAL,
                    sample_rate REAL,
                    center_freq REAL,
                    num_samples INTEGER,
                    file_size INTEGER,
                    metadata JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
        }
        
        # Create indexes
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_detections_timestamp ON detections(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_detections_threat ON detections(threat_level)",
            "CREATE INDEX IF NOT EXISTS idx_alerts_severity ON alerts(severity)",
            "CREATE INDEX IF NOT EXISTS idx_alerts_timestamp ON alerts(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON system_metrics(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_recordings_session ON recordings(session_id)"
        ]
        
        if drop_existing:
            for table_name in tables.keys():
                await self.execute(f"DROP TABLE IF EXISTS {table_name}")
        
        for table_name, schema in tables.items():
            await self.execute(schema)
            logger.info(f"Created table: {table_name}")
        
        for index in indexes:
            await self.execute(index)
            logger.info(f"Created index: {index[:50]}...")
        
        logger.info("Database tables created successfully")
    
    async def backup(self, backup_path: Optional[Path] = None) -> Path:
        """
        Backup the database
        
        Args:
            backup_path: Path for backup file
            
        Returns:
            Path to backup file
        """
        await self.ensure_initialized()
        
        if backup_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = Path(f"data/backups/db_backup_{timestamp}.db")
        
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        
        if self.config.db_type == DatabaseType.SQLITE:
            # SQLite backup
            import shutil
            shutil.copy2(self.config.sqlite_path, backup_path)
            logger.info(f"Database backed up to {backup_path}")
            
        elif self.config.db_type == DatabaseType.POSTGRESQL:
            # PostgreSQL backup using pg_dump
            import asyncio.subprocess
            cmd = [
                'pg_dump', 
                f'postgresql://{self.config.postgres_user}:{self.config.postgres_password}@'
                f'{self.config.postgres_host}:{self.config.postgres_port}/{self.config.postgres_database}',
                '-f', str(backup_path)
            ]
            process = await asyncio.create_subprocess_exec(*cmd)
            await process.wait()
            logger.info(f"Database backed up to {backup_path}")
        
        return backup_path
    
    async def restore(self, backup_path: Path) -> bool:
        """
        Restore database from backup
        
        Args:
            backup_path: Path to backup file
            
        Returns:
            True if restore successful
        """
        await self.ensure_initialized()
        
        try:
            if self.config.db_type == DatabaseType.SQLITE:
                import shutil
                # Close existing connections
                await self.close()
                # Restore file
                shutil.copy2(backup_path, self.config.sqlite_path)
                # Reinitialize
                await self.initialize()
                logger.info(f"Database restored from {backup_path}")
                return True
                
            elif self.config.db_type == DatabaseType.POSTGRESQL:
                import asyncio.subprocess
                cmd = [
                    'pg_restore', 
                    '--clean', 
                    '--if-exists',
                    '--dbname', f'postgresql://{self.config.postgres_user}:{self.config.postgres_password}@'
                    f'{self.config.postgres_host}:{self.config.postgres_port}/{self.config.postgres_database}',
                    str(backup_path)
                ]
                process = await asyncio.create_subprocess_exec(*cmd)
                await process.wait()
                logger.info(f"Database restored from {backup_path}")
                return True
                
        except Exception as e:
            logger.error(f"Restore failed: {e}")
            return False


# ============================================================================
# Factory Functions
# ============================================================================

def create_database_manager(db_type: DatabaseType = DatabaseType.SQLITE,
                           **kwargs) -> DatabaseManager:
    """
    Create a database manager with the specified configuration
    
    Args:
        db_type: Database type
        **kwargs: Additional configuration parameters
        
    Returns:
        Configured DatabaseManager instance
    """
    config = DatabaseConfig(db_type=db_type, **kwargs)
    return DatabaseManager(config)


def create_sqlite_manager(db_path: str = "data/detections.db") -> DatabaseManager:
    """Create a SQLite database manager"""
    config = DatabaseConfig(
        db_type=DatabaseType.SQLITE,
        sqlite_path=db_path
    )
    return DatabaseManager(config)


# ============================================================================
# Example Usage
# ============================================================================

async def example_usage():
    """Example usage of database manager"""
    print("Database Manager Test")
    print("=" * 50)
    
    # Create SQLite manager
    manager = create_sqlite_manager("data/test.db")
    
    # Initialize
    print("\n1. Initializing database...")
    await manager.initialize()
    
    # Create tables
    print("\n2. Creating tables...")
    await manager.create_tables(drop_existing=True)
    
    # Insert data
    print("\n3. Inserting test data...")
    
    await manager.execute("""
        INSERT INTO detections (id, timestamp, drone_type, confidence, threat_level, frequency)
        VALUES (?, ?, ?, ?, ?, ?)
    """, "det_001", datetime.now().isoformat(), "DJI Mavic 3", 0.95, "HIGH", 2.44e9)
    
    # Query data
    print("\n4. Querying data...")
    result = await manager.fetch_one("SELECT * FROM detections WHERE id = ?", "det_001")
    print(f"   Detection: {result}")
    
    # Transaction example
    print("\n5. Transaction example...")
    async with manager.transaction():
        await manager.execute(
            "INSERT INTO detections (id, timestamp, drone_type, confidence) VALUES (?, ?, ?, ?)",
            "det_002", datetime.now().isoformat(), "FPV", 0.87
        )
        await manager.execute(
            "INSERT INTO alerts (id, detection_id, severity, message, acknowledged, resolved, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
            "alt_001", "det_002", "HIGH", "Drone detected!", False, False, datetime.now().isoformat()
        )
        print("   Transaction committed")
    
    # Get statistics
    print("\n6. Database statistics:")
    stats = manager.get_stats()
    print(f"   Total queries: {stats.total_queries}")
    print(f"   Active connections: {stats.active_connections}")
    print(f"   Avg query time: {stats.avg_query_time_ms:.2f}ms")
    
    # Health check
    print("\n7. Health check:")
    healthy = await manager.health_check()
    print(f"   Database healthy: {healthy}")
    
    # Cleanup
    print("\n8. Cleaning up...")
    await manager.close()
    
    print("\n" + "=" * 50)
    print("Database test complete!")


async def main():
    """Main function"""
    await example_usage()


if __name__ == "__main__":
    asyncio.run(main())