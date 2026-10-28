"""
Ransomware & Malware Detection
Inspired by: Veeam Threat Hunter, Rubrik Threat Monitoring, Acronis AI ransomware protection
Scans backup data for ransomware indicators before sealing and during restore.
"""

import re
import hashlib
import logging
import fnmatch
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class ThreatLevel(str, Enum):
    CLEAN     = "clean"
    LOW       = "low"
    MEDIUM    = "medium"
    HIGH      = "high"
    CRITICAL  = "critical"


class DetectionMethod(str, Enum):
    FILE_HASH       = "file_hash"
    YARA_RULE       = "yara_rule"
    ENTROPY_ANALYSIS= "entropy_analysis"
    EXTENSION_MATCH = "extension_match"
    BEHAVIORAL      = "behavioral"


@dataclass
class ThreatIndicator:
    name: str
    method: DetectionMethod
    level: ThreatLevel
    description: str
    pattern: Optional[str] = None    # regex / glob / YARA rule name


@dataclass
class ScanResult:
    backup_id: str
    scanned_at: datetime = field(default_factory=datetime.utcnow)
    threat_level: ThreatLevel = ThreatLevel.CLEAN
    indicators_found: List[ThreatIndicator] = field(default_factory=list)
    files_scanned: int = 0
    scan_duration_ms: int = 0
    is_safe_to_restore: bool = True
    notes: str = ""

    @property
    def has_threats(self) -> bool:
        return self.threat_level not in (ThreatLevel.CLEAN, ThreatLevel.LOW)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "backup_id": self.backup_id,
            "scanned_at": self.scanned_at.isoformat(),
            "threat_level": self.threat_level.value,
            "indicators_found": len(self.indicators_found),
            "is_safe_to_restore": self.is_safe_to_restore,
            "files_scanned": self.files_scanned,
            "notes": self.notes,
        }


# ---------------------------------------------------------------------------
# Known ransomware extension signatures (commonly used extensions)
# ---------------------------------------------------------------------------

RANSOMWARE_EXTENSIONS: Set[str] = {
    ".locked", ".encrypted", ".enc", ".crypt", ".crypted",
    ".crypto", ".xxx", ".ttt", ".micro", ".mp3", ".cerber",
    ".locky", ".zepto", ".odin", ".aesir", ".osiris",
    ".zzzzz", ".lol", ".wncrypt", ".wcry", ".wncry",
    ".wncryt", ".onion", ".dharma", ".wallet", ".globe",
    ".xtbl", ".breaking_bad", ".ha3", ".gefickt",
}

RANSOM_NOTE_FILENAMES: Set[str] = {
    "readme.txt", "how_to_decrypt.txt", "restore_files.txt",
    "ransom.txt", "how_to_recover.html", "decrypt_instructions.html",
    "_readme.txt", "!how_to_decrypt!.txt", "recovery.txt",
    "how_to_restore_files.txt", "recovery_key.txt",
}

# Known malicious file hashes (SHA-256) — sample list for demonstration
KNOWN_MALICIOUS_HASHES: Set[str] = {
    "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",  # empty — placeholder
}


# ---------------------------------------------------------------------------
# YARA-like rule definitions (simplified pattern matching)
# ---------------------------------------------------------------------------

YARA_RULES: List[Dict[str, Any]] = [
    {
        "name": "WannaCry",
        "strings": ["WANACRY!", "wncry", "tasksche.exe"],
        "level": ThreatLevel.CRITICAL,
    },
    {
        "name": "Ryuk",
        "strings": ["RyukReadMe", "UNIQUE_ID_DO_NOT_REMOVE"],
        "level": ThreatLevel.CRITICAL,
    },
    {
        "name": "Locky",
        "strings": [".locky", "_LOCKY_recover_instructions"],
        "level": ThreatLevel.HIGH,
    },
    {
        "name": "GenericRansomNote",
        "strings": ["your files have been encrypted", "bitcoin", "pay ransom", "decryption key"],
        "level": ThreatLevel.HIGH,
    },
]


# ---------------------------------------------------------------------------
# Entropy analysis (high entropy = possible encryption)
# ---------------------------------------------------------------------------

def calculate_entropy(data: bytes) -> float:
    """Shannon entropy of byte string. >7.5 suggests encrypted/compressed data."""
    import math
    if not data:
        return 0.0
    freq = [0] * 256
    for byte in data:
        freq[byte] += 1
    entropy = 0.0
    length = len(data)
    for count in freq:
        if count:
            p = count / length
            entropy -= p * math.log2(p)
    return entropy


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------

class RansomwareScanner:
    """
    Scans backup files for ransomware indicators.
    Methods: file hash, YARA-like rules, entropy, extension matching.
    """

    ENTROPY_THRESHOLD = 7.5       # above this = suspicious
    SAMPLE_SIZE = 4096            # bytes to sample for entropy check

    def __init__(self, extra_hashes: Optional[Set[str]] = None,
                 extra_extensions: Optional[Set[str]] = None):
        self.malicious_hashes = KNOWN_MALICIOUS_HASHES | (extra_hashes or set())
        self.ransomware_extensions = RANSOMWARE_EXTENSIONS | (extra_extensions or set())

    def scan_file(self, file_path: str) -> List[ThreatIndicator]:
        """Scan a single file and return any threat indicators found"""
        import os
        indicators: List[ThreatIndicator] = []

        filename = os.path.basename(file_path).lower()
        ext = os.path.splitext(filename)[1].lower()

        # 1. Extension check
        if ext in self.ransomware_extensions:
            indicators.append(ThreatIndicator(
                name="SuspiciousExtension",
                method=DetectionMethod.EXTENSION_MATCH,
                level=ThreatLevel.HIGH,
                description=f"File has known ransomware extension: {ext}",
                pattern=ext,
            ))

        # 2. Ransom note filename
        if filename in RANSOM_NOTE_FILENAMES:
            indicators.append(ThreatIndicator(
                name="RansomNote",
                method=DetectionMethod.EXTENSION_MATCH,
                level=ThreatLevel.CRITICAL,
                description=f"Ransom note filename detected: {filename}",
            ))

        if not os.path.exists(file_path):
            return indicators

        # 3. File hash check
        try:
            file_hash = self._hash_file(file_path)
            if file_hash in self.malicious_hashes:
                indicators.append(ThreatIndicator(
                    name="KnownMaliciousHash",
                    method=DetectionMethod.FILE_HASH,
                    level=ThreatLevel.CRITICAL,
                    description=f"File hash matches known malware: {file_hash[:16]}...",
                ))
        except OSError:
            pass

        # 4. Content-based checks (YARA-like + entropy)
        try:
            with open(file_path, "rb") as f:
                sample = f.read(self.SAMPLE_SIZE)

            text_sample = sample.decode("utf-8", errors="ignore").lower()

            # YARA-like string matching
            for rule in YARA_RULES:
                if any(s.lower() in text_sample for s in rule["strings"]):
                    indicators.append(ThreatIndicator(
                        name=rule["name"],
                        method=DetectionMethod.YARA_RULE,
                        level=rule["level"],
                        description=f"YARA rule matched: {rule['name']}",
                    ))

            # Entropy analysis
            entropy = calculate_entropy(sample)
            if entropy > self.ENTROPY_THRESHOLD:
                indicators.append(ThreatIndicator(
                    name="HighEntropy",
                    method=DetectionMethod.ENTROPY_ANALYSIS,
                    level=ThreatLevel.MEDIUM,
                    description=f"High entropy ({entropy:.2f}) suggests encryption",
                ))
        except OSError:
            pass

        return indicators

    def scan_backup(self, backup_id: str, backup_path: str) -> ScanResult:
        """Scan an entire backup directory or file"""
        import os, time
        start = time.time()
        result = ScanResult(backup_id=backup_id)

        paths_to_scan: List[str] = []
        if os.path.isdir(backup_path):
            for root, _, files in os.walk(backup_path):
                for f in files:
                    paths_to_scan.append(os.path.join(root, f))
        elif os.path.isfile(backup_path):
            paths_to_scan = [backup_path]

        all_indicators: List[ThreatIndicator] = []
        for path in paths_to_scan:
            all_indicators.extend(self.scan_file(path))
            result.files_scanned += 1

        result.indicators_found = all_indicators
        result.scan_duration_ms = int((time.time() - start) * 1000)

        # Determine overall threat level
        if any(i.level == ThreatLevel.CRITICAL for i in all_indicators):
            result.threat_level = ThreatLevel.CRITICAL
            result.is_safe_to_restore = False
        elif any(i.level == ThreatLevel.HIGH for i in all_indicators):
            result.threat_level = ThreatLevel.HIGH
            result.is_safe_to_restore = False
        elif any(i.level == ThreatLevel.MEDIUM for i in all_indicators):
            result.threat_level = ThreatLevel.MEDIUM
            result.is_safe_to_restore = True  # warn but allow
        else:
            result.threat_level = ThreatLevel.CLEAN

        if result.has_threats:
            logger.warning("Ransomware scan: backup %s — threat level %s (%d indicators)",
                           backup_id, result.threat_level.value, len(all_indicators))
        return result

    @staticmethod
    def _hash_file(path: str) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()


class ThreatIntelligenceFeed:
    """
    Manages and updates threat intelligence data (hashes, YARA rules, extensions).
    In production, syncs with external threat feeds.
    """

    def __init__(self):
        self._custom_hashes: Set[str] = set()
        self._custom_extensions: Set[str] = set()
        self._last_updated: Optional[datetime] = None

    def add_hash(self, sha256: str) -> None:
        self._custom_hashes.add(sha256.lower())

    def add_extension(self, ext: str) -> None:
        self._custom_extensions.add(ext.lower() if ext.startswith(".") else f".{ext.lower()}")

    def build_scanner(self) -> RansomwareScanner:
        return RansomwareScanner(
            extra_hashes=self._custom_hashes,
            extra_extensions=self._custom_extensions,
        )

    def update_from_feed(self, feed_url: str) -> int:
        """Pull latest threat indicators from external feed. Returns count added."""
        import requests
        try:
            resp = requests.get(feed_url, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            added = 0
            for h in data.get("hashes", []):
                self.add_hash(h)
                added += 1
            for ext in data.get("extensions", []):
                self.add_extension(ext)
                added += 1
            self._last_updated = datetime.utcnow()
            logger.info("Threat feed updated: %d indicators added from %s", added, feed_url)
            return added
        except Exception as exc:
            logger.error("Threat feed update failed: %s", exc)
            return 0
