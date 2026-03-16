# =============================================================================
# behavior_analytics/analytics/path_analyzer.py
# =============================================================================
"""
Path analysis engine — pure Python, no Django ORM.

Analyses a single user's navigation path (a list of node dicts) and returns
structured insights:
  - entry / exit URLs
  - unique pages visited
  - total path depth
  - most visited pages
  - drop-off points
  - loop detection (user revisiting the same page multiple times)
  - funnel step completion (optional)
"""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Iterator

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class PathAnalysisError(Exception):
    """Raised when path data is malformed and cannot be analysed."""


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PathNode:
    """
    Normalised representation of a single navigation event in a path.
    """
    url:    str
    type:   str   = "navigation"
    ts:     int   = 0
    method: str   = "GET"
    status: int   = 200

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "PathNode":
        if not isinstance(raw, dict):
            raise PathAnalysisError(f"Expected a dict node, got {type(raw).__name__}.")
        return cls(
            url=str(raw.get("url", ""))[:2048],
            type=str(raw.get("type", "navigation")),
            ts=int(raw.get("ts", 0)),
            method=str(raw.get("method", "GET")).upper(),
            status=int(raw.get("status", 200)),
        )


@dataclass
class PathAnalysisResult:
    """Full analysis output for one path."""
    entry_url:      str
    exit_url:       str
    total_nodes:    int
    unique_pages:   int
    depth:          int                           # unique pages visited
    page_frequency: dict[str, int]                # url → visit count
    top_pages:      list[tuple[str, int]]         # sorted by frequency desc
    drop_off_pages: list[str]                     # pages followed by exit
    loops:          list[str]                     # pages visited 2+ times
    error_pages:    list[str]                     # nodes where status >= 400
    is_bounce:      bool
    funnel_completion: dict[str, bool] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Analyser
# ---------------------------------------------------------------------------

class PathAnalyzer:
    """
    Stateless path analysis engine.

    Usage::

        analyzer = PathAnalyzer()
        result   = analyzer.analyse(nodes=path.nodes)
        print(result.depth)
        print(result.top_pages[:3])
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyse(
        self,
        nodes: list[dict | PathNode],
        funnel_steps: list[str] | None = None,
    ) -> PathAnalysisResult:
        """
        Analyse a node list and return a PathAnalysisResult.

        Parameters
        ----------
        nodes:
            Raw list of navigation node dicts (or PathNode instances).
        funnel_steps:
            Optional ordered list of URLs to check for funnel completion.
            e.g. ["/cart/", "/checkout/", "/order-confirmed/"]

        Raises
        ------
        PathAnalysisError
            If nodes is not a list or any node is unparseable.
        """
        if not isinstance(nodes, list):
            raise PathAnalysisError(
                f"nodes must be a list, got {type(nodes).__name__}."
            )

        parsed: list[PathNode] = self._parse_nodes(nodes)

        if not parsed:
            return self._empty_result()

        entry_url  = parsed[0].url
        exit_url   = parsed[-1].url
        urls       = [n.url for n in parsed]
        freq       = Counter(urls)
        top_pages  = freq.most_common()
        loops      = [url for url, count in freq.items() if count > 1]
        error_pages = [n.url for n in parsed if n.status >= 400]
        drop_offs  = self._find_drop_offs(parsed)

        funnel_completion: dict[str, bool] = {}
        if funnel_steps:
            visited = set(urls)
            funnel_completion = {step: step in visited for step in funnel_steps}

        return PathAnalysisResult(
            entry_url=entry_url,
            exit_url=exit_url,
            total_nodes=len(parsed),
            unique_pages=len(freq),
            depth=len(freq),
            page_frequency=dict(freq),
            top_pages=top_pages,
            drop_off_pages=drop_offs,
            loops=loops,
            error_pages=error_pages,
            is_bounce=len(parsed) <= 1,
            funnel_completion=funnel_completion,
        )

    def analyse_batch(
        self,
        paths: list[list[dict]],
        funnel_steps: list[str] | None = None,
    ) -> list[PathAnalysisResult | Exception]:
        """
        Analyse a batch of paths.  Returns one result per path.
        If a path fails, the corresponding list item is the caught exception
        (rather than raising, to prevent one bad path from failing the batch).
        """
        results: list[PathAnalysisResult | Exception] = []
        for idx, nodes in enumerate(paths):
            try:
                results.append(self.analyse(nodes, funnel_steps=funnel_steps))
            except Exception as exc:
                logger.warning(
                    "path_analyzer.batch_item_failed index=%d error=%s", idx, exc
                )
                results.append(exc)
        return results

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_nodes(raw_nodes: list) -> list[PathNode]:
        parsed: list[PathNode] = []
        for idx, node in enumerate(raw_nodes):
            if isinstance(node, PathNode):
                parsed.append(node)
                continue
            try:
                parsed.append(PathNode.from_dict(node))
            except (PathAnalysisError, ValueError, TypeError) as exc:
                logger.warning(
                    "path_analyzer.node_parse_error index=%d error=%s", idx, exc
                )
                # Skip unparseable nodes rather than aborting the whole path
        return parsed

    @staticmethod
    def _find_drop_offs(nodes: list[PathNode]) -> list[str]:
        """
        Return a list of page URLs that were the last step before the session
        ended (i.e., the exit URL and any node followed by an exit-type node).
        """
        drop_offs: list[str] = []
        for i, node in enumerate(nodes):
            is_last = (i == len(nodes) - 1)
            next_is_exit = (
                i + 1 < len(nodes) and nodes[i + 1].type == "exit"
            )
            if is_last or next_is_exit:
                drop_offs.append(node.url)
        return drop_offs

    @staticmethod
    def _empty_result() -> PathAnalysisResult:
        return PathAnalysisResult(
            entry_url="",
            exit_url="",
            total_nodes=0,
            unique_pages=0,
            depth=0,
            page_frequency={},
            top_pages=[],
            drop_off_pages=[],
            loops=[],
            error_pages=[],
            is_bounce=True,
        )

    # ------------------------------------------------------------------
    # Utility: merge multiple paths into a single aggregate
    # ------------------------------------------------------------------

    def merge_paths(
        self,
        paths: list[list[dict]],
    ) -> dict[str, Any]:
        """
        Aggregate statistics across multiple paths (e.g. all paths for a user
        in a date range).

        Returns a plain dict with:
          - total_paths
          - bounce_count / bounce_rate
          - avg_depth
          - top_pages (top 10 across all paths)
          - common_entry_urls
          - common_exit_urls
        """
        results = [r for r in self.analyse_batch(paths) if isinstance(r, PathAnalysisResult)]

        if not results:
            return {
                "total_paths":        0,
                "bounce_count":       0,
                "bounce_rate":        0.0,
                "avg_depth":          0.0,
                "top_pages":          [],
                "common_entry_urls":  [],
                "common_exit_urls":   [],
            }

        total   = len(results)
        bounces = sum(1 for r in results if r.is_bounce)

        all_pages = Counter[str]()
        for r in results:
            all_pages.update(r.page_frequency)

        entry_counter = Counter(r.entry_url for r in results if r.entry_url)
        exit_counter  = Counter(r.exit_url  for r in results if r.exit_url)

        avg_depth = sum(r.depth for r in results) / total

        return {
            "total_paths":       total,
            "bounce_count":      bounces,
            "bounce_rate":       round(bounces / total * 100, 2),
            "avg_depth":         round(avg_depth, 2),
            "top_pages":         all_pages.most_common(10),
            "common_entry_urls": entry_counter.most_common(5),
            "common_exit_urls":  exit_counter.most_common(5),
        }
