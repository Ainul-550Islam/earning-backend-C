#!/usr/bin/env python3
# publisher_tools/dry_fix.py
"""
DRY fix script — দুটি violation fix করে:

  1. _get_publisher() duplications (12 found)
     → সব local def _get_publisher() remove করে।
     → views already import PublisherViewMixin which provides self.publisher
     → Safety: মিশ্র pattern check করে, শুধু safe ক্ষেত্রে remove করে।

  2. Raw try/except patterns (457 found)
     → bare `try: ... except Exception as e: return Response(...)` blocks
     → handle_errors() context manager দিয়ে replace করে না (too risky to auto-patch)
     → Instead: একটি comprehensive REPORT তৈরি করে কোথায় কোথায় আছে

Run করো:
    cd earning_backend/
    python publisher_tools/dry_fix.py [--apply] [--report-only]

Flags:
    --apply       : actual file modification করো
    --report-only : শুধু report দাও, file touch করো না (default)
"""

import os
import re
import sys
import json
from pathlib import Path
from typing import NamedTuple

BASE = Path(__file__).parent


# ─────────────────────────────────────────────────────────────────────────────
# PATTERN DEFINITIONS
# ─────────────────────────────────────────────────────────────────────────────

# Pattern: local _get_publisher that is SAFE to remove
# (only if the file also imports PublisherViewMixin or already has self.publisher)
GET_PUBLISHER_PATTERN = re.compile(
    r'    def _get_publisher\(self\)[^\n]*\n'
    r'(?:        [^\n]+\n)*'       # body lines
    r'(?:        return [^\n]+\n)',
    re.MULTILINE,
)

# Pattern: raw try/except in view methods
RAW_TRY_EXCEPT = re.compile(
    r'        try:\n'
    r'(?:            [^\n]+\n)+'   # body
    r'        except (?:Exception|[A-Za-z]+Error)[^\n]*:\n'
    r'(?:            [^\n]+\n)+',  # handler
    re.MULTILINE,
)


class Violation(NamedTuple):
    file:    str
    line_no: int
    kind:    str
    preview: str


def find_violations(view_files: list[Path]) -> tuple[list[Violation], list[Violation]]:
    """Scan all view files and return (get_publisher_dups, raw_try_excepts)."""
    dups      = []
    raw_trys  = []

    for path in view_files:
        content = path.read_text(encoding='utf-8')
        lines   = content.splitlines()

        # 1. _get_publisher duplications
        for m in GET_PUBLISHER_PATTERN.finditer(content):
            line_no = content[:m.start()].count('\n') + 1
            has_mixin = 'PublisherViewMixin' in content
            if has_mixin:
                dups.append(Violation(
                    file=path.name,
                    line_no=line_no,
                    kind='_get_publisher_dup',
                    preview=m.group(0)[:80].strip(),
                ))

        # 2. Raw try/except blocks
        for m in RAW_TRY_EXCEPT.finditer(content):
            line_no = content[:m.start()].count('\n') + 1
            body = m.group(0)
            # Skip if already using handle_errors
            if 'handle_errors' in body:
                continue
            raw_trys.append(Violation(
                file=path.name,
                line_no=line_no,
                kind='raw_try_except',
                preview=body[:100].strip(),
            ))

    return dups, raw_trys


def remove_get_publisher_dups(view_files: list[Path]) -> int:
    """
    Remove local _get_publisher() methods from files that use PublisherViewMixin.
    Returns number of removals made.
    """
    removed = 0

    for path in view_files:
        content = path.read_text(encoding='utf-8')

        if 'PublisherViewMixin' not in content:
            continue

        matches = list(GET_PUBLISHER_PATTERN.finditer(content))
        if not matches:
            continue

        new_content = content
        for m in reversed(matches):
            block = m.group(0)
            replacement = (
                '    # _get_publisher() removed — use self.publisher (PublisherViewMixin)\n'
            )
            new_content = new_content[:m.start()] + replacement + new_content[m.end():]
            removed += 1

        if new_content != content:
            path.write_text(new_content, encoding='utf-8')
            print(f'  ✅ {path.name}: {len(matches)} _get_publisher() dup(s) removed')

    return removed


def generate_report(dups: list[Violation], raw_trys: list[Violation]) -> dict:
    """Build a JSON-serializable report."""

    def group_by_file(violations):
        grouped = {}
        for v in violations:
            grouped.setdefault(v.file, []).append({
                'line': v.line_no,
                'preview': v.preview,
            })
        return grouped

    return {
        'summary': {
            '_get_publisher_dups': len(dups),
            'raw_try_excepts':     len(raw_trys),
            'total_violations':    len(dups) + len(raw_trys),
        },
        '_get_publisher_dups_by_file': group_by_file(dups),
        'raw_try_excepts_by_file':     group_by_file(raw_trys),
        'recommended_actions': [
            'Run --apply flag to auto-remove _get_publisher() dups',
            'For raw try/except: manually replace with `with self.handle_errors() as guard:` pattern',
            'See publisher_tools/mixins.py for handle_errors() documentation',
        ],
    }


def print_report(report: dict) -> None:
    s = report['summary']
    print(f"\n{'='*60}")
    print(f"DRY VIOLATION REPORT")
    print(f"{'='*60}")
    print(f"  _get_publisher() dups : {s['_get_publisher_dups']}")
    print(f"  raw try/except blocks : {s['raw_try_excepts']}")
    print(f"  Total violations      : {s['total_violations']}")

    print(f"\n{'─'*60}")
    print("_get_publisher() DUPLICATIONS (safe to auto-remove):")
    for fname, items in report['_get_publisher_dups_by_file'].items():
        for item in items:
            print(f"  {fname}:{item['line']}  {item['preview'][:70]}")

    print(f"\n{'─'*60}")
    print("RAW try/except BLOCKS (manual fix needed):")
    by_file = report['raw_try_excepts_by_file']
    for fname in sorted(by_file, key=lambda f: len(by_file[f]), reverse=True)[:15]:
        count = len(by_file[fname])
        print(f"  {fname}: {count} blocks")
        for item in by_file[fname][:2]:
            print(f"    line {item['line']}: {item['preview'][:60]}...")

    if len(by_file) > 15:
        print(f"  ... and {len(by_file) - 15} more files")

    print(f"\n{'─'*60}")
    print("RECOMMENDED FIX for raw try/except:")
    print("""
  BEFORE:
      try:
          from .some_module import some_func
          data = some_func(pub)
          return self.ok(data)
      except Exception as e:
          return Response({'error': str(e)}, status=503)

  AFTER:
      with self.handle_errors() as guard:
          from .some_module import some_func
          data = some_func(pub)
          return self.ok(data)
      return guard.response   # auto-handled 503 on exception
    """)


def main():
    apply       = '--apply' in sys.argv
    report_only = '--report-only' in sys.argv or not apply

    view_files = sorted(BASE.glob('views_*.py'))
    print(f"Scanning {len(view_files)} view files...")

    dups, raw_trys = find_violations(view_files)
    report = generate_report(dups, raw_trys)

    print_report(report)

    # Write JSON report
    report_path = BASE / 'dry_violation_report.json'
    report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(f"\nFull report written to: {report_path}")

    if apply:
        print(f"\n{'='*60}")
        print("APPLYING FIXES...")
        removed = remove_get_publisher_dups(view_files)
        print(f"\nApplied: {removed} _get_publisher() dups removed")
        print("NOTE: raw try/except blocks require manual fix (see report above)")
    else:
        print(f"\nRun with --apply to auto-fix _get_publisher() dups")
        print("raw try/except blocks always require manual review")

    return 0


if __name__ == '__main__':
    sys.exit(main())
