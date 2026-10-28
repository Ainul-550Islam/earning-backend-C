#!/usr/bin/env python3
# publisher_tools/scripts/add_loggers.py
# ============================================================
# Script: সব views_*.py ফাইলে logging import + logger যোগ করে।
#
# Run (project root থেকে):
#   python publisher_tools/scripts/add_loggers.py
#
# Safe: ইতিমধ্যে logger আছে এমন ফাইল skip করে।
# ============================================================
import os
import re

VIEWS_DIR = os.path.join(os.path.dirname(__file__), '..')
IMPORT_LINE  = 'import logging\n'
LOGGER_LINE  = "logger = logging.getLogger(__name__)\n"
MARKER       = 'logger = logging.getLogger'

def patch_file(filepath: str) -> bool:
    """logger না থাকলে যোগ করে। Return True if patched."""
    with open(filepath, encoding='utf-8', errors='replace') as f:
        original = f.read()

    if MARKER in original:
        return False  # already has logger

    lines     = original.splitlines(keepends=True)
    new_lines = list(lines)

    # Find insert position: after all imports block
    last_import_idx = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(('import ', 'from ')) or stripped == '':
            last_import_idx = i
        elif stripped and not stripped.startswith('#'):
            # First non-import, non-blank, non-comment line
            if last_import_idx > 0:
                break

    insert_at = last_import_idx + 1

    # Add import logging if missing
    has_logging_import = any('import logging' in l for l in lines)
    additions = []
    if not has_logging_import:
        additions.append(IMPORT_LINE)
    additions.append(LOGGER_LINE)
    additions.append('\n')

    for i, line in enumerate(additions):
        new_lines.insert(insert_at + i, line)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)

    return True


def main():
    patched = []
    skipped = []

    for fname in sorted(os.listdir(VIEWS_DIR)):
        if not (fname.startswith('views') and fname.endswith('.py')):
            continue
        fpath = os.path.join(VIEWS_DIR, fname)
        if patch_file(fpath):
            patched.append(fname)
            print(f'  ✅ PATCHED : {fname}')
        else:
            skipped.append(fname)
            print(f'  ⏭  SKIPPED : {fname} (already has logger)')

    print(f'\nDone — {len(patched)} patched, {len(skipped)} skipped.')


if __name__ == '__main__':
    main()
