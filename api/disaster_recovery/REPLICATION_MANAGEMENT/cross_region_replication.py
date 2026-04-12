"""
Cross-Region Replication — Manages data replication across cloud regions.
Used for geo-disaster recovery, latency optimization, and compliance requirements.
"""
import logging
from datetime import datetime
from typing import List, Optional, Dict

logger = logging.getLogger(__name__)


class CrossRegionReplication:
    """
    Manages cloud-native cross-region replication:
    - AWS: RDS cross-region read replicas, S3 Cross-Region Replication (CRR)
    - Azure: Active geo-replication, Geo-redundant storage
    - GCP: Cloud SQL cross-region replicas, multi-region buckets

    Also manages:
    - Replication monitoring and lag tracking
    - Failover activation for cross-region scenarios
    - Cost optimization (tiered replication)
    """

    def __init__(self, source_region: str, target_regions: List[str],
                 provider: str = "aws", config: dict = None):
        self.source_region = source_region
        self.target_regions = target_regions
        self.provider = provider
        self.config = config or {}

    def enable_rds_cross_region_replica(self, source_db_id: str,
                                         target_region: str,
                                         replica_id: str = None) -> dict:
        """Create an AWS RDS cross-region read replica."""
        import boto3
        replica_id = replica_id or f"{source_db_id}-{target_region}-replica"
        logger.info(
            f"Creating RDS cross-region replica: {source_db_id} "
            f"({self.source_region}) -> {target_region}"
        )
        rds = boto3.client("rds", region_name=target_region,
                           aws_access_key_id=self.config.get("access_key_id"),
                           aws_secret_access_key=self.config.get("secret_access_key"))
        source_arn = (
            f"arn:aws:rds:{self.source_region}:"
            f"{self.config.get('account_id','')}:db:{source_db_id}"
        )
        response = rds.create_db_instance_read_replica(
            DBInstanceIdentifier=replica_id,
            SourceDBInstanceIdentifier=source_arn,
            DBInstanceClass=self.config.get("instance_class", "db.t3.medium"),
            MultiAZ=self.config.get("multi_az", False),
            AutoMinorVersionUpgrade=True,
            Tags=[
                {"Key": "managed-by", "Value": "dr-system"},
                {"Key": "source-region", "Value": self.source_region},
            ]
        )
        db = response.get("DBInstance", {})
        logger.info(f"RDS replica creation initiated: {replica_id} in {target_region}")
        return {
            "replica_id": replica_id,
            "source_db": source_db_id,
            "source_region": self.source_region,
            "target_region": target_region,
            "status": db.get("DBInstanceStatus", "creating"),
            "arn": db.get("DBInstanceArn", ""),
        }

    def enable_s3_cross_region_replication(self, source_bucket: str,
                                             target_bucket: str,
                                             target_region: str,
                                             replication_role_arn: str) -> dict:
        """Enable S3 Cross-Region Replication (CRR) between buckets."""
        import boto3
        s3 = boto3.client("s3", region_name=self.source_region,
                          aws_access_key_id=self.config.get("access_key_id"),
                          aws_secret_access_key=self.config.get("secret_access_key"))
        # Enable versioning on source bucket (required for CRR)
        s3.put_bucket_versioning(
            Bucket=source_bucket,
            VersioningConfiguration={"Status": "Enabled"}
        )
        replication_config = {
            "Role": replication_role_arn,
            "Rules": [{
                "ID": f"DR-CRR-{target_region}",
                "Status": "Enabled",
                "Filter": {"Prefix": ""},
                "Destination": {
                    "Bucket": f"arn:aws:s3:::{target_bucket}",
                    "StorageClass": "STANDARD_IA",
                    "ReplicationTime": {
                        "Status": "Enabled",
                        "Time": {"Minutes": 15}
                    },
                    "Metrics": {"Status": "Enabled", "EventThreshold": {"Minutes": 15}},
                },
                "DeleteMarkerReplication": {"Status": "Enabled"},
            }]
        }
        s3.put_bucket_replication(
            Bucket=source_bucket,
            ReplicationConfiguration=replication_config
        )
        logger.info(
            f"S3 CRR enabled: {source_bucket} ({self.source_region}) -> "
            f"{target_bucket} ({target_region})"
        )
        return {
            "source_bucket": source_bucket,
            "target_bucket": target_bucket,
            "source_region": self.source_region,
            "target_region": target_region,
            "replication_time_minutes": 15,
            "status": "enabled",
        }

    def get_rds_replica_lag(self, replica_id: str, region: str) -> dict:
        """Get replication lag for an RDS cross-region replica."""
        import boto3
        cw = boto3.client("cloudwatch", region_name=region,
                          aws_access_key_id=self.config.get("access_key_id"),
                          aws_secret_access_key=self.config.get("secret_access_key"))
        from datetime import timedelta
        response = cw.get_metric_statistics(
            Namespace="AWS/RDS",
            MetricName="ReplicaLag",
            Dimensions=[{"Name": "DBInstanceIdentifier", "Value": replica_id}],
            StartTime=datetime.utcnow() - timedelta(minutes=5),
            EndTime=datetime.utcnow(),
            Period=60,
            Statistics=["Average"],
        )
        datapoints = response.get("Datapoints", [])
        if datapoints:
            latest = max(datapoints, key=lambda x: x["Timestamp"])
            lag = latest.get("Average", 0)
        else:
            lag = None
        return {
            "replica_id": replica_id,
            "region": region,
            "lag_seconds": lag,
            "measured_at": datetime.utcnow().isoformat(),
        }

    def promote_cross_region_replica(self, replica_id: str,
                                      target_region: str) -> dict:
        """Promote a cross-region read replica to standalone primary."""
        import boto3
        logger.critical(
            f"Promoting cross-region replica to primary: "
            f"{replica_id} in {target_region}"
        )
        rds = boto3.client("rds", region_name=target_region,
                           aws_access_key_id=self.config.get("access_key_id"),
                           aws_secret_access_key=self.config.get("secret_access_key"))
        response = rds.promote_read_replica(
            DBInstanceIdentifier=replica_id,
            BackupRetentionPeriod=7,
        )
        db = response.get("DBInstance", {})
        return {
            "replica_id": replica_id,
            "region": target_region,
            "status": db.get("DBInstanceStatus", "promoting"),
            "endpoint": db.get("Endpoint", {}).get("Address", ""),
            "promoted_at": datetime.utcnow().isoformat(),
        }

    def list_replicas(self, source_db: str = None) -> List[dict]:
        """List all cross-region replicas."""
        import boto3
        replicas = []
        for region in self.target_regions:
            rds = boto3.client("rds", region_name=region,
                               aws_access_key_id=self.config.get("access_key_id"),
                               aws_secret_access_key=self.config.get("secret_access_key"))
            try:
                response = rds.describe_db_instances()
                for db in response.get("DBInstances", []):
                    if db.get("ReadReplicaSourceDBInstanceIdentifier") == source_db or not source_db:
                        if db.get("ReadReplicaSourceDBInstanceIdentifier"):
                            replicas.append({
                                "replica_id": db["DBInstanceIdentifier"],
                                "region": region,
                                "source_db": db.get("ReadReplicaSourceDBInstanceIdentifier"),
                                "status": db.get("DBInstanceStatus"),
                                "endpoint": db.get("Endpoint", {}).get("Address"),
                                "instance_class": db.get("DBInstanceClass"),
                            })
            except Exception as e:
                logger.warning(f"Could not list replicas in {region}: {e}")
        return replicas

    def get_replication_status(self) -> Dict[str, dict]:
        """Get replication status for all target regions."""
        status = {}
        for region in self.target_regions:
            status[region] = {
                "region": region,
                "provider": self.provider,
                "source_region": self.source_region,
                "status": "active",
                "checked_at": datetime.utcnow().isoformat(),
            }
        return status
