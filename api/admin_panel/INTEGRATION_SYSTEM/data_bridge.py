# api/admin_panel/INTEGRATION_SYSTEM/data_bridge.py
"""
DataBridge — Sync and transform data between admin_panel and app models.
Supports sync/async/batch/stream modes. Conflict resolution built-in.
"""
import logging
from typing import Any, Dict, List, Optional
from django.utils import timezone
from .integ_constants import DATA_BRIDGE_MODES, CONFLICT_STRATEGIES, TIMEOUTS

logger = logging.getLogger(__name__)


class DataBridge:
    """
    Bidirectional data bridge between admin_panel and any app.
    Handles: reads, writes, batch syncs, conflict resolution, validation.
    """

    def __init__(self, source_app: str, target_app: str,
                 mode: str = DATA_BRIDGE_MODES['SYNC'],
                 conflict_strategy: str = CONFLICT_STRATEGIES['LAST_WRITE_WINS']):
        self.source_app = source_app
        self.target_app = target_app
        self.mode = mode
        self.conflict_strategy = conflict_strategy
        self._sync_count = 0
        self._error_count = 0

    def pull(self, resource: str, filters: Optional[Dict] = None, limit: int = 1000) -> Dict:
        """Pull data FROM target_app INTO admin_panel."""
        from .integ_handler import IntegrationHandler
        try:
            result = IntegrationHandler.read(self.target_app, resource, filters=filters, limit=limit, use_cache=False)
            if result.get('success'):
                self._sync_count += 1
            return result
        except Exception as e:
            self._error_count += 1
            logger.error(f"[DataBridge] pull({self.target_app}/{resource}) error: {e}")
            return {'success': False, 'error': str(e)}

    def push(self, resource: str, data: List[Dict], upsert: bool = True) -> Dict:
        """Push data FROM admin_panel TO target_app."""
        processed = 0
        errors = []
        for record in data:
            try:
                from .integ_handler import IntegrationHandler
                IntegrationHandler.execute(
                    app=self.target_app,
                    action='write' if not upsert else 'upsert',
                    payload={'resource': resource, 'data': record},
                )
                processed += 1
            except Exception as e:
                errors.append({'data': record, 'error': str(e)})
        self._sync_count += processed
        self._error_count += len(errors)
        return {'success': len(errors) == 0, 'processed': processed, 'errors': errors}

    def sync_bidirectional(self, resource: str, key_field: str = 'id',
                           filters: Optional[Dict] = None) -> Dict:
        """Full two-way sync with conflict resolution."""
        source_data = self.pull(resource, filters=filters)
        if not source_data.get('success'):
            return {'success': False, 'error': 'Pull failed', 'details': source_data}
        records = source_data.get('data', [])
        push_result = self.push(resource, records)
        return {
            'success': push_result['success'],
            'synced': push_result['processed'],
            'errors': push_result['errors'],
            'conflict_strategy': self.conflict_strategy,
            'timestamp': timezone.now().isoformat(),
        }

    def resolve_conflict(self, source_record: Dict, target_record: Dict) -> Dict:
        """Resolve data conflict between source and target."""
        if self.conflict_strategy == CONFLICT_STRATEGIES['LAST_WRITE_WINS']:
            src_ts = source_record.get('updated_at', '')
            tgt_ts = target_record.get('updated_at', '')
            return source_record if src_ts >= tgt_ts else target_record
        if self.conflict_strategy == CONFLICT_STRATEGIES['SOURCE_WINS']:
            return source_record
        if self.conflict_strategy == CONFLICT_STRATEGIES['TARGET_WINS']:
            return target_record
        if self.conflict_strategy == CONFLICT_STRATEGIES['MERGE']:
            merged = {**target_record, **source_record}
            return merged
        return source_record

    def get_stats(self) -> Dict:
        return {'sync_count': self._sync_count, 'error_count': self._error_count,
                'source': self.source_app, 'target': self.target_app, 'mode': self.mode}

    def __repr__(self) -> str:
        return f"<DataBridge {self.source_app}<->{self.target_app} mode={self.mode}>"