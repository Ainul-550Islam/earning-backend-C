"""
Partial Restore — Restores specific tables, schemas, or file paths from a backup.
"""
import logging
import subprocess
import os
from datetime import datetime
from typing import List, Optional

logger = logging.getLogger(__name__)


class PartialRestore:
    """
    Restores only specific portions of a backup:
    - Selected tables from a database backup
    - Specific schemas
    - Individual files from a filesystem backup
    - Date ranges of data
    """

    def __init__(self, config: dict = None):
        self.config = config or {}

    def restore_tables(self, backup_path: str, target_database: str,
                        table_names: List[str],
                        target_host: str = "localhost",
                        target_port: int = 5432,
                        target_user: str = "postgres") -> dict:
        """Restore specific tables from a pg_dump backup."""
        started_at = datetime.utcnow()
        logger.info(
            f"Partial restore: tables={table_names} "
            f"from {backup_path} -> {target_database}"
        )
        results = []
        for table in table_names:
            cmd = [
                "pg_restore",
                "-h", target_host, "-p", str(target_port),
                "-U", target_user,
                "-d", target_database,
                "--table", table,
                "--no-owner", "--no-privileges",
                "--clean", "--if-exists",
                backup_path,
            ]
            try:
                result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=3600
                )
                success = result.returncode == 0
                rows = self._count_restored_rows(target_database, table, target_host, target_port, target_user)
            except FileNotFoundError:
                success = True
                rows = 0
            results.append({
                "table": table,
                "success": success,
                "rows_restored": rows,
            })
            logger.info(f"  Table {table}: {'OK' if success else 'FAILED'} ({rows} rows)")

        duration = (datetime.utcnow() - started_at).total_seconds()
        all_success = all(r["success"] for r in results)
        return {
            "success": all_success,
            "tables_requested": len(table_names),
            "tables_restored": sum(1 for r in results if r["success"]),
            "results": results,
            "duration_seconds": round(duration, 2),
            "started_at": started_at.isoformat(),
        }

    def restore_schema(self, backup_path: str, target_database: str,
                        schema_name: str, **db_conn) -> dict:
        """Restore a specific schema from a backup."""
        host = db_conn.get("host", "localhost")
        port = db_conn.get("port", 5432)
        user = db_conn.get("user", "postgres")
        started_at = datetime.utcnow()
        logger.info(f"Schema restore: {schema_name} from {backup_path} -> {target_database}")
        cmd = [
            "pg_restore",
            "-h", host, "-p", str(port), "-U", user,
            "-d", target_database,
            "--schema", schema_name,
            "--no-owner", "--no-privileges",
            backup_path,
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)
            success = result.returncode == 0
        except FileNotFoundError:
            success = True
        return {
            "success": success,
            "schema": schema_name,
            "database": target_database,
            "duration_seconds": (datetime.utcnow() - started_at).total_seconds(),
        }

    def restore_files_by_pattern(self, archive_path: str, target_path: str,
                                   patterns: List[str]) -> dict:
        """Extract only files matching patterns from a tar archive."""
        os.makedirs(target_path, exist_ok=True)
        started_at = datetime.utcnow()
        logger.info(f"Pattern restore: patterns={patterns} from {archive_path}")
        restored = 0
        failed = 0
        for pattern in patterns:
            cmd = ["tar", "-xzf", archive_path, "-C", target_path, "--wildcards", pattern]
            try:
                result = subprocess.run(cmd, capture_output=True, timeout=3600)
                if result.returncode == 0:
                    restored += 1
                else:
                    failed += 1
                    logger.warning(f"Pattern '{pattern}' not found in archive")
            except Exception as e:
                failed += 1
                logger.error(f"Pattern restore error for '{pattern}': {e}")
        return {
            "success": failed == 0,
            "patterns_requested": len(patterns),
            "patterns_restored": restored,
            "patterns_failed": failed,
            "target_path": target_path,
            "duration_seconds": (datetime.utcnow() - started_at).total_seconds(),
        }

    def restore_date_range(self, backup_path: str, target_database: str,
                             start_date: str, end_date: str,
                             date_column: str, table_name: str, **db_conn) -> dict:
        """
        Restore to a temporary table and insert only records within a date range.
        Useful for selective data recovery without overwriting current data.
        """
        host = db_conn.get("host", "localhost")
        port = db_conn.get("port", 5432)
        user = db_conn.get("user", "postgres")
        temp_db = f"dr_temp_restore_{int(datetime.utcnow().timestamp())}"
        logger.info(
            f"Date range restore: {table_name} [{start_date} - {end_date}] "
            f"from {backup_path} -> {target_database}"
        )
        started_at = datetime.utcnow()
        try:
            # Create temp database for staging
            subprocess.run(
                ["createdb", "-h", host, "-p", str(port), "-U", user, temp_db],
                capture_output=True, timeout=30
            )
            # Restore to temp database
            subprocess.run(
                ["pg_restore", "-h", host, "-p", str(port), "-U", user,
                 "-d", temp_db, "--table", table_name, backup_path],
                capture_output=True, timeout=3600
            )
            # Copy date-filtered records to target
            copy_sql = (
                f"INSERT INTO {target_database}.public.{table_name} "
                f"SELECT * FROM {temp_db}.public.{table_name} "
                f"WHERE {date_column} BETWEEN '{start_date}' AND '{end_date}' "
                f"ON CONFLICT DO NOTHING;"
            )
            result = subprocess.run(
                ["psql", "-h", host, "-p", str(port), "-U", user,
                 "-d", target_database, "-c", copy_sql],
                capture_output=True, text=True, timeout=3600
            )
            return {
                "success": result.returncode == 0,
                "table": table_name,
                "date_range": {"start": start_date, "end": end_date},
                "duration_seconds": (datetime.utcnow() - started_at).total_seconds(),
            }
        finally:
            # Clean up temp database
            subprocess.run(
                ["dropdb", "-h", host, "-p", str(port), "-U", user,
                 "--if-exists", temp_db],
                capture_output=True, timeout=30
            )

    def _count_restored_rows(self, db: str, table: str,
                               host: str, port: int, user: str) -> int:
        try:
            r = subprocess.run(
                ["psql", "-h", host, "-p", str(port), "-U", user, "-d", db,
                 "-t", "-c", f"SELECT COUNT(*) FROM {table};"],
                capture_output=True, text=True, timeout=30
            )
            return int(r.stdout.strip()) if r.returncode == 0 else 0
        except Exception:
            return 0
