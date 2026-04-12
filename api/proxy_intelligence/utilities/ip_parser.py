"""IP Parser — parses and normalises various IP string formats."""
import ipaddress, re
from typing import Optional, List

class IPParser:
    @staticmethod
    def parse(ip_str: str) -> Optional[str]:
        try:
            return str(ipaddress.ip_address(ip_str.strip()))
        except ValueError:
            return None

    @staticmethod
    def parse_cidr(cidr: str) -> Optional[str]:
        try:
            return str(ipaddress.ip_network(cidr.strip(), strict=False))
        except ValueError:
            return None

    @staticmethod
    def extract_from_string(text: str) -> List[str]:
        """Extract all valid IPs from a text string."""
        pattern = r'\b(?:\d{1,3}\.){3}\d{1,3}\b'
        candidates = re.findall(pattern, text)
        return [ip for ip in candidates if IPParser.parse(ip)]

    @staticmethod
    def is_ipv6(ip_str: str) -> bool:
        try:
            return ipaddress.ip_address(ip_str).version == 6
        except ValueError:
            return False

    @staticmethod
    def expand_ipv6(ip_str: str) -> str:
        try:
            return str(ipaddress.ip_address(ip_str).exploded)
        except ValueError:
            return ip_str

    @staticmethod
    def to_int(ip_str: str) -> Optional[int]:
        try:
            return int(ipaddress.ip_address(ip_str))
        except ValueError:
            return None

    @staticmethod
    def from_int(n: int) -> str:
        try:
            return str(ipaddress.ip_address(n))
        except Exception:
            return ''
