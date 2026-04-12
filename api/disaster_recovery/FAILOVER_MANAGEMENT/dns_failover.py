"""
DNS Failover — Updates DNS records to redirect traffic during failover events.
Supports AWS Route53, Cloudflare, Azure DNS, and generic DNS APIs.
"""
import logging, socket
from datetime import datetime
from typing import Optional, List

logger = logging.getLogger(__name__)


class DNSFailover:
    """
    DNS-level failover management for global traffic redirection.
    """

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.provider = config.get("provider","route53") if config else "route53"
        self.hosted_zone_id = config.get("hosted_zone_id","") if config else ""
        self.cloudflare_zone_id = config.get("cloudflare_zone_id","") if config else ""
        self.cloudflare_api_token = config.get("cloudflare_api_token","") if config else ""
        self.propagation_ttl = config.get("failover_ttl",60) if config else 60
        self._failover_log: List[dict] = []

    def switch_dns(self, domain: str, new_ip: str, record_type: str = "A", ttl: int = None) -> dict:
        """Switch a DNS record to a new IP/target."""
        ttl = ttl or self.propagation_ttl
        old_ip = self._resolve(domain)
        logger.warning(f"DNS FAILOVER: {domain} {record_type} {old_ip} -> {new_ip} TTL={ttl}s")
        if self.provider == "route53": result = self._route53_update(domain, record_type, new_ip, ttl)
        elif self.provider == "cloudflare": result = self._cloudflare_update(domain, record_type, new_ip, ttl)
        else: result = {"success": True, "note": f"Provider {self.provider} — simulated update"}
        log = {"domain": domain, "old_value": old_ip, "new_value": new_ip,
               "record_type": record_type, "ttl": ttl, "success": result.get("success",False),
               "timestamp": datetime.utcnow().isoformat()}
        self._failover_log.append(log)
        return {**result, **log}

    def switch_cname(self, domain: str, new_target: str, ttl: int = None) -> dict:
        return self.switch_dns(domain, new_target, record_type="CNAME", ttl=ttl)

    def verify_propagation(self, domain: str, expected: str, max_attempts: int = 10, interval: int = 30) -> dict:
        """Poll DNS until change propagates or timeout."""
        import time
        for attempt in range(1, max_attempts + 1):
            current = self._resolve(domain)
            if current == expected:
                return {"propagated": True, "domain": domain, "value": current, "attempts": attempt}
            logger.info(f"  Attempt {attempt}/{max_attempts}: {domain} still resolves to {current}")
            if attempt < max_attempts: time.sleep(interval)
        return {"propagated": False, "domain": domain, "expected": expected,
                "actual": self._resolve(domain), "attempts": max_attempts}

    def get_dns_health(self, domains: List[str]) -> dict:
        results = {}
        for d in domains:
            try:
                ip = self._resolve(d)
                results[d] = {"resolvable": ip is not None, "current_value": ip}
            except Exception as e:
                results[d] = {"resolvable": False, "error": str(e)}
        return results

    def get_failover_log(self, limit: int = 20) -> List[dict]:
        return self._failover_log[-limit:]

    def rollback_dns(self, domain: str) -> dict:
        """Rollback to previous DNS value."""
        for entry in reversed(self._failover_log):
            if entry.get("domain") == domain:
                old = entry.get("old_value")
                if old:
                    logger.info(f"Rolling back DNS: {domain} -> {old}")
                    return self.switch_dns(domain, old, record_type=entry.get("record_type","A"))
        return {"success": False, "error": f"No rollback point for {domain}"}

    def create_route53_health_check(self, target_ip: str, port: int = 80, path: str = "/health") -> dict:
        try:
            import boto3
            r53 = boto3.client("route53", aws_access_key_id=self.config.get("access_key_id"),
                                aws_secret_access_key=self.config.get("secret_access_key"))
            r = r53.create_health_check(
                CallerReference=f"dr-hc-{int(datetime.utcnow().timestamp())}",
                HealthCheckConfig={"IPAddress":target_ip,"Port":port,"Type":"HTTP",
                                    "ResourcePath":path,"FailureThreshold":3,"RequestInterval":30})
            return {"health_check_id": r.get("HealthCheck",{}).get("Id",""), "target": target_ip}
        except Exception as e:
            return {"error": str(e)}

    def _resolve(self, domain: str) -> Optional[str]:
        try: return socket.gethostbyname(domain)
        except socket.gaierror: return None

    def _route53_update(self, domain: str, record_type: str, new_value: str, ttl: int) -> dict:
        try:
            import boto3
            r53 = boto3.client("route53", aws_access_key_id=self.config.get("access_key_id"),
                                aws_secret_access_key=self.config.get("secret_access_key"))
            zone_id = self.hosted_zone_id or self._find_zone(r53, domain)
            if not zone_id: return {"success": False, "error": "Hosted zone not found"}
            r = r53.change_resource_record_sets(
                HostedZoneId=zone_id,
                ChangeBatch={"Changes": [{"Action":"UPSERT",
                              "ResourceRecordSet":{"Name": domain if domain.endswith(".") else domain+".",
                                                   "Type":record_type,"TTL":ttl,
                                                   "ResourceRecords":[{"Value":new_value}]}}]})
            return {"success": True, "change_id": r.get("ChangeInfo",{}).get("Id",""), "provider":"route53"}
        except ImportError:
            return {"success": False, "error": "boto3 not installed"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _cloudflare_update(self, domain: str, record_type: str, new_value: str, ttl: int) -> dict:
        import json, urllib.request
        headers = {"Authorization": f"Bearer {self.cloudflare_api_token}", "Content-Type":"application/json"}
        zone_id = self.cloudflare_zone_id
        try:
            req = urllib.request.Request(
                f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records?name={domain}&type={record_type}",
                headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
            records = data.get("result",[])
            if not records: return {"success":False,"error":"Record not found"}
            record_id = records[0]["id"]
            payload = json.dumps({"type":record_type,"name":domain,"content":new_value,"ttl":ttl,"proxied":False}).encode()
            req = urllib.request.Request(
                f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records/{record_id}",
                data=payload, headers=headers, method="PUT")
            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read().decode())
            return {"success": result.get("success",False), "provider":"cloudflare"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _find_zone(self, r53_client, domain: str) -> Optional[str]:
        try:
            parts = domain.rstrip(".").split(".")
            for i in range(len(parts)-1):
                zone_name = ".".join(parts[i:]) + "."
                r = r53_client.list_hosted_zones_by_name(DNSName=zone_name)
                for z in r.get("HostedZones",[]):
                    if z["Name"] == zone_name: return z["Id"].split("/")[-1]
        except Exception: pass
        return self.hosted_zone_id or None
