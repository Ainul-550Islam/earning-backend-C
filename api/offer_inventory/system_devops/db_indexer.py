# api/offer_inventory/system_devops/db_indexer.py
"""DB Indexer — Database index management and query plan analysis."""
import logging
from django.db import connection

logger = logging.getLogger(__name__)


class DBIndexer:
    """Database index management and optimization."""

    OFFER_INVENTORY_TABLES = [
        'offer_inventory_click', 'offer_inventory_conversion',
        'offer_inventory_offer', 'offer_inventory_walletaudit',
        'offer_inventory_blacklistedip', 'offer_inventory_postbacklog',
    ]

    @staticmethod
    def analyze_tables():
        """Run ANALYZE on all offer_inventory tables for query planner."""
        cursor = connection.cursor()
        for table in DBIndexer.OFFER_INVENTORY_TABLES:
            try:
                cursor.execute(f'ANALYZE {table};')
                logger.info(f'ANALYZE completed: {table}')
            except Exception as e:
                logger.warning(f'ANALYZE failed for {table}: {e}')

    @staticmethod
    def get_table_sizes() -> list:
        """Get table sizes for capacity planning (PostgreSQL)."""
        try:
            cursor = connection.cursor()
            cursor.execute("""
                SELECT tablename,
                       pg_size_pretty(pg_total_relation_size(tablename::regclass)) as size,
                       pg_total_relation_size(tablename::regclass) as bytes
                FROM pg_tables
                WHERE tablename LIKE 'offer_inventory_%'
                ORDER BY bytes DESC;
            """)
            return [{'table': r[0], 'size': r[1], 'bytes': r[2]} for r in cursor.fetchall()]
        except Exception as e:
            logger.warning(f'Table size query failed: {e}')
            return []

    @staticmethod
    def get_missing_indexes() -> list:
        """Find columns that may need indexes (PostgreSQL pg_stats)."""
        try:
            cursor = connection.cursor()
            cursor.execute("""
                SELECT schemaname, tablename, attname, n_distinct, correlation
                FROM pg_stats
                WHERE tablename LIKE 'offer_inventory_%'
                AND n_distinct > 100
                AND correlation < 0.1
                ORDER BY n_distinct DESC
                LIMIT 20;
            """)
            cols = [col[0] for col in cursor.description]
            return [dict(zip(cols, row)) for row in cursor.fetchall()]
        except Exception:
            return []

    @staticmethod
    def get_index_usage() -> list:
        """Get index usage statistics (PostgreSQL pg_stat_user_indexes)."""
        try:
            cursor = connection.cursor()
            cursor.execute("""
                SELECT relname as table, indexrelname as index,
                       idx_scan, idx_tup_read, idx_tup_fetch
                FROM pg_stat_user_indexes
                WHERE relname LIKE 'offer_inventory_%'
                ORDER BY idx_scan DESC
                LIMIT 30;
            """)
            cols = [col[0] for col in cursor.description]
            return [dict(zip(cols, row)) for row in cursor.fetchall()]
        except Exception:
            return []

    @staticmethod
    def get_slow_queries(min_calls: int = 5) -> list:
        """Get slow queries from pg_stat_statements (if available)."""
        try:
            cursor = connection.cursor()
            cursor.execute("""
                SELECT query, calls, total_exec_time, mean_exec_time, rows
                FROM pg_stat_statements
                WHERE query LIKE '%offer_inventory%'
                AND calls >= %s
                ORDER BY mean_exec_time DESC
                LIMIT 20;
            """, [min_calls])
            cols = [col[0] for col in cursor.description]
            return [dict(zip(cols, row)) for row in cursor.fetchall()]
        except Exception:
            return []

    @staticmethod
    def vacuum_tables():
        """Run VACUUM ANALYZE on offer_inventory tables."""
        from django.db import connection
        cursor = connection.cursor()
        for table in DBIndexer.OFFER_INVENTORY_TABLES:
            try:
                cursor.execute(f'VACUUM ANALYZE {table};')
                logger.info(f'VACUUM ANALYZE: {table}')
            except Exception as e:
                logger.warning(f'VACUUM failed for {table}: {e}')
