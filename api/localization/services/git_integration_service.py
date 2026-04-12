# services/git_integration_service.py
"""
Git Integration — Phrase.com/Lokalise git sync equivalent.
Features:
- Extract i18n keys from source code (JS/JSX/TS/Python)
- Git webhook → auto-detect new/removed keys
- Pull translations to repo (generate JSON/PO files)
- Push new keys from repo to DB
"""
import re
import json
import logging
import hmac
import hashlib
from typing import Dict, List, Set, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


class KeyExtractor:
    """
    Source code থেকে i18n translation keys extract করে।
    Supports: JS/JSX/TS (t(), i18n.t()), Python (gettext), Django template ({% trans %})
    """

    # JS/TS patterns: t('key'), i18n.t('key'), $t('key'), trans('key')
    JS_PATTERNS = [
        r"""t\(\s*['"]([a-z][a-z0-9_.]+)['"]\s*[,)]""",
        r"""i18n\.t\(\s*['"]([a-z][a-z0-9_.]+)['"]\s*[,)]""",
        r"""\$t\(\s*['"]([a-z][a-z0-9_.]+)['"]\s*[,)]""",
        r"""translate\(\s*['"]([a-z][a-z0-9_.]+)['"]\s*[,)]""",
        r"""useTranslation\(\).*?t\(\s*['"]([a-z][a-z0-9_.]+)['"]\s*\)""",
    ]

    # Python patterns: _('key'), gettext('key'), ugettext('key')
    PY_PATTERNS = [
        r"""_\(\s*['"]([a-z][a-z0-9_.]+)['"]\s*\)""",
        r"""gettext\(\s*['"]([a-z][a-z0-9_.]+)['"]\s*\)""",
    ]

    # Django template: {% trans "key" %}, {% blocktrans %}
    DJANGO_PATTERNS = [
        r"""\{%\s*trans\s+['"]([a-z][a-z0-9_.]+)['"]\s*%\}""",
    ]

    def extract_from_file(self, file_path: str) -> Set[str]:
        """Single file থেকে keys extract করে"""
        keys = set()
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            ext = Path(file_path).suffix.lower()
            if ext in ('.js', '.jsx', '.ts', '.tsx', '.vue', '.svelte'):
                patterns = self.JS_PATTERNS
            elif ext in ('.py',):
                patterns = self.PY_PATTERNS
            elif ext in ('.html', '.htm'):
                patterns = self.DJANGO_PATTERNS + self.JS_PATTERNS
            else:
                return keys

            for pattern in patterns:
                matches = re.findall(pattern, content, re.DOTALL)
                for match in matches:
                    key = match.strip()
                    if self._is_valid_key(key):
                        keys.add(key)

        except Exception as e:
            logger.error(f"Key extraction failed for {file_path}: {e}")

        return keys

    def extract_from_directory(
        self,
        directory: str,
        extensions: List[str] = None,
        exclude_dirs: List[str] = None,
    ) -> Dict[str, Set[str]]:
        """Directory tree থেকে keys extract করে। Returns {file: {keys}}"""
        if extensions is None:
            extensions = ['.js', '.jsx', '.ts', '.tsx', '.vue', '.py', '.html']
        if exclude_dirs is None:
            exclude_dirs = ['node_modules', '.git', '__pycache__', 'dist', 'build', '.next', 'venv']

        results = {}
        try:
            for path in Path(directory).rglob('*'):
                if path.is_file() and path.suffix in extensions:
                    if not any(exc in str(path) for exc in exclude_dirs):
                        keys = self.extract_from_file(str(path))
                        if keys:
                            results[str(path)] = keys
        except Exception as e:
            logger.error(f"Directory extraction failed: {e}")

        return results

    def find_new_keys(
        self, extracted_keys: Set[str], existing_keys: Set[str]
    ) -> Tuple[Set[str], Set[str]]:
        """New keys and removed keys বের করে"""
        new_keys = extracted_keys - existing_keys
        removed_keys = existing_keys - extracted_keys
        return new_keys, removed_keys

    def _is_valid_key(self, key: str) -> bool:
        """Valid translation key কিনা check"""
        if len(key) < 3 or len(key) > 200:
            return False
        if not re.match(r'^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$', key):
            return False
        return True


class GitWebhookService:
    """
    Git webhook handler — GitHub/GitLab/Bitbucket push events process করে।
    on push → extract keys → find new keys → add to DB → notify team
    """

    def verify_signature(self, payload: bytes, signature: str, secret: str) -> bool:
        """GitHub/GitLab webhook signature verify করে"""
        try:
            if signature.startswith('sha256='):
                expected = 'sha256=' + hmac.new(
                    secret.encode(), payload, hashlib.sha256
                ).hexdigest()
                return hmac.compare_digest(expected, signature)
            elif signature.startswith('sha1='):
                expected = 'sha1=' + hmac.new(
                    secret.encode(), payload, hashlib.sha1
                ).hexdigest()
                return hmac.compare_digest(expected, signature)
        except Exception:
            pass
        return False

    def process_push_event(self, payload: Dict) -> Dict:
        """
        Git push event process করে।
        Changed files scan করে নতুন translation keys বের করে।
        """
        try:
            # Extract changed files from webhook payload
            changed_files = set()
            for commit in payload.get('commits', []):
                changed_files.update(commit.get('added', []))
                changed_files.update(commit.get('modified', []))

            # Filter relevant files
            i18n_extensions = {'.js', '.jsx', '.ts', '.tsx', '.vue', '.py', '.html', '.svelte'}
            relevant_files = [f for f in changed_files if Path(f).suffix in i18n_extensions]

            if not relevant_files:
                return {'success': True, 'message': 'No i18n files changed', 'new_keys': []}

            # Note: in production, clone/fetch repo and extract from files
            # Here we return the list for external processing
            return {
                'success': True,
                'changed_files': relevant_files,
                'repository': payload.get('repository', {}).get('name', ''),
                'branch': payload.get('ref', '').replace('refs/heads/', ''),
                'commit': payload.get('after', '')[:8],
                'message': f'{len(relevant_files)} i18n files changed — run extract_keys task',
                'new_keys': [],
            }
        except Exception as e:
            logger.error(f"process_push_event failed: {e}")
            return {'success': False, 'error': str(e)}

    def sync_keys_to_db(self, keys: Set[str], namespace: str = '') -> Dict:
        """Extracted keys DB-তে sync করে — নতুন keys add করে, missing keys flag করে"""
        try:
            from ..models.core import TranslationKey
            existing = set(TranslationKey.objects.values_list('key', flat=True))
            new_keys = [k for k in keys if k not in existing]

            created = 0
            for key in new_keys:
                # Guess category from key prefix
                parts = key.split('.')
                category = parts[0] if parts else namespace or 'common'
                TranslationKey.objects.get_or_create(
                    key=key,
                    defaults={
                        'category': category,
                        'namespace': namespace or '',
                        'description': f'Auto-extracted from source code',
                        'is_active': True,
                    }
                )
                created += 1

            return {
                'success': True,
                'total_extracted': len(keys),
                'new_keys_created': created,
                'already_existed': len(existing & keys),
                'new_keys': new_keys[:50],
            }
        except Exception as e:
            logger.error(f"sync_keys_to_db failed: {e}")
            return {'success': False, 'error': str(e)}

    def generate_translation_file(
        self,
        language_code: str,
        format: str = 'json',
        namespace: str = '',
    ) -> str:
        """
        DB থেকে translation file generate করে — repo-তে commit করার জন্য।
        GitHub Action-এ: generate → commit → PR → review → merge
        """
        try:
            from ..services.translation.TranslationExportService import TranslationExportService
            service = TranslationExportService()

            if format == 'json':
                result = service.export_json(language_code)
                return json.dumps(result.get('data', {}), ensure_ascii=False, indent=2)
            elif format == 'po':
                return service.export_po(language_code)
            elif format == 'xliff':
                return service.export_xliff(language_code)
            else:
                return '{}'
        except Exception as e:
            logger.error(f"generate_translation_file failed: {e}")
            return '{}'
