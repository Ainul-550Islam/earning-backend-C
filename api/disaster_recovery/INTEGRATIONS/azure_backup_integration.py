"""
Azure Backup Integration — Microsoft Azure Backup service integration.
"""
import logging
import json
from datetime import datetime
from typing import List, Optional

logger = logging.getLogger(__name__)


class AzureBackupIntegration:
    """
    Azure Backup integration using Azure Recovery Services Vault.
    Supports Azure VMs, Azure SQL, Azure Files, and Blob snapshots.
    """

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.subscription_id = config.get("subscription_id", "") if config else ""
        self.resource_group = config.get("resource_group", "") if config else ""
        self.vault_name = config.get("vault_name", "dr-backup-vault") if config else "dr-backup-vault"
        self.location = config.get("location", "eastus") if config else "eastus"
        self._credential = None

    def _get_credential(self):
        """Get Azure DefaultAzureCredential."""
        if not self._credential:
            from azure.identity import DefaultAzureCredential, ClientSecretCredential
            if all(k in self.config for k in ["tenant_id", "client_id", "client_secret"]):
                self._credential = ClientSecretCredential(
                    tenant_id=self.config["tenant_id"],
                    client_id=self.config["client_id"],
                    client_secret=self.config["client_secret"],
                )
            else:
                self._credential = DefaultAzureCredential()
        return self._credential

    def create_recovery_vault(self) -> dict:
        """Create or ensure the Azure Recovery Services Vault exists."""
        from azure.mgmt.recoveryservices import RecoveryServicesClient
        client = RecoveryServicesClient(self._get_credential(), self.subscription_id)
        vault_params = {
            "location": self.location,
            "sku": {"name": "RS0", "tier": "Standard"},
            "properties": {},
        }
        try:
            vault = client.vaults.begin_create_or_update(
                self.resource_group, self.vault_name, vault_params
            ).result()
            logger.info(f"Azure vault created/verified: {self.vault_name}")
            return {
                "vault_name": self.vault_name,
                "id": vault.id,
                "location": vault.location,
                "status": "Ready",
            }
        except Exception as e:
            logger.error(f"Vault creation error: {e}")
            return {"vault_name": self.vault_name, "error": str(e)}

    def backup_azure_vm(self, vm_name: str, vm_resource_group: str = None) -> dict:
        """Trigger an on-demand backup of an Azure VM."""
        from azure.mgmt.recoveryservicesbackup import RecoveryServicesBackupClient
        client = RecoveryServicesBackupClient(self._get_credential(), self.subscription_id)
        rg = vm_resource_group or self.resource_group
        container_name = f"iaasvmcontainerv2;{rg};{vm_name}"
        item_name = f"vm;iaasvmcontainerv2;{rg};{vm_name}"
        try:
            operation = client.backups.trigger(
                vault_name=self.vault_name,
                resource_group_name=self.resource_group,
                fabric_name="Azure",
                container_name=container_name,
                protected_item_name=item_name,
                parameters={
                    "properties": {
                        "objectType": "IaasVMBackupRequest",
                        "recoveryPointExpiryTimeInUTC": None,
                    }
                }
            )
            logger.info(f"Azure VM backup triggered: {vm_name}")
            return {
                "vm_name": vm_name,
                "vault": self.vault_name,
                "status": "BackupTriggered",
                "initiated_at": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            logger.error(f"Azure VM backup error: {e}")
            return {"vm_name": vm_name, "error": str(e), "success": False}

    def list_vm_backups(self, vm_name: str, vm_resource_group: str = None) -> List[dict]:
        """List recovery points for an Azure VM."""
        from azure.mgmt.recoveryservicesbackup import RecoveryServicesBackupClient
        client = RecoveryServicesBackupClient(self._get_credential(), self.subscription_id)
        rg = vm_resource_group or self.resource_group
        container_name = f"iaasvmcontainerv2;{rg};{vm_name}"
        item_name = f"vm;iaasvmcontainerv2;{rg};{vm_name}"
        recovery_points = []
        try:
            points = client.recovery_points.list(
                vault_name=self.vault_name,
                resource_group_name=self.resource_group,
                fabric_name="Azure",
                container_name=container_name,
                protected_item_name=item_name,
            )
            for point in points:
                recovery_points.append({
                    "id": point.name,
                    "type": point.properties.recovery_point_type if hasattr(point.properties, "recovery_point_type") else "",
                    "time": point.properties.recovery_point_time.isoformat() if hasattr(point.properties, "recovery_point_time") and point.properties.recovery_point_time else "",
                })
        except Exception as e:
            logger.error(f"List backups error: {e}")
        return recovery_points

    def restore_azure_vm(self, vm_name: str, recovery_point_id: str,
                          target_resource_group: str = None,
                          target_vm_name: str = None) -> dict:
        """Restore an Azure VM from a recovery point."""
        from azure.mgmt.recoveryservicesbackup import RecoveryServicesBackupClient
        client = RecoveryServicesBackupClient(self._get_credential(), self.subscription_id)
        rg = self.resource_group
        container_name = f"iaasvmcontainerv2;{rg};{vm_name}"
        item_name = f"vm;iaasvmcontainerv2;{rg};{vm_name}"
        target_rg = target_resource_group or rg
        target_name = target_vm_name or f"{vm_name}-restored"
        try:
            operation = client.restores.begin_trigger(
                vault_name=self.vault_name,
                resource_group_name=rg,
                fabric_name="Azure",
                container_name=container_name,
                protected_item_name=item_name,
                recovery_point_id=recovery_point_id,
                parameters={
                    "properties": {
                        "objectType": "IaasVMRestoreRequest",
                        "recoveryType": "AlternateLocation",
                        "targetResourceGroupId": f"/subscriptions/{self.subscription_id}/resourceGroups/{target_rg}",
                        "targetVirtualMachineId": f"/subscriptions/{self.subscription_id}/resourceGroups/{target_rg}/providers/Microsoft.Compute/virtualMachines/{target_name}",
                    }
                }
            )
            logger.info(f"Azure VM restore initiated: {vm_name} -> {target_name}")
            return {
                "source_vm": vm_name,
                "target_vm": target_name,
                "recovery_point": recovery_point_id,
                "status": "RestoreInitiated",
            }
        except Exception as e:
            logger.error(f"Azure VM restore error: {e}")
            return {"source_vm": vm_name, "error": str(e), "success": False}

    def configure_backup_policy(self, policy_name: str,
                                  schedule_type: str = "Daily",
                                  retention_days: int = 30) -> dict:
        """Configure a backup policy in the Recovery Vault."""
        from azure.mgmt.recoveryservicesbackup import RecoveryServicesBackupClient
        client = RecoveryServicesBackupClient(self._get_credential(), self.subscription_id)
        policy = {
            "location": self.location,
            "properties": {
                "backupManagementType": "AzureIaasVM",
                "schedulePolicy": {
                    "schedulePolicyType": "SimpleSchedulePolicy",
                    "scheduleRunFrequency": schedule_type,
                    "scheduleRunTimes": ["2023-01-01T02:00:00Z"],
                },
                "retentionPolicy": {
                    "retentionPolicyType": "LongTermRetentionPolicy",
                    "dailySchedule": {
                        "retentionTimes": ["2023-01-01T02:00:00Z"],
                        "retentionDuration": {"count": retention_days, "durationType": "Days"},
                    },
                },
            }
        }
        try:
            result = client.protection_policies.create_or_update(
                vault_name=self.vault_name,
                resource_group_name=self.resource_group,
                policy_name=policy_name,
                parameters=policy,
            )
            logger.info(f"Azure backup policy configured: {policy_name}")
            return {
                "policy_name": policy_name,
                "vault": self.vault_name,
                "schedule": schedule_type,
                "retention_days": retention_days,
                "status": "Configured",
            }
        except Exception as e:
            logger.error(f"Policy config error: {e}")
            return {"policy_name": policy_name, "error": str(e)}

    def get_vault_storage_usage(self) -> dict:
        """Get storage usage for the Recovery Services Vault."""
        from azure.mgmt.recoveryservices import RecoveryServicesClient
        client = RecoveryServicesClient(self._get_credential(), self.subscription_id)
        try:
            usages = list(client.usages.list_by_vaults(self.resource_group, self.vault_name))
            result = {}
            for usage in usages:
                result[usage.name.value] = {
                    "current_value": usage.current_value,
                    "limit": usage.limit,
                    "unit": usage.unit,
                }
            return {"vault": self.vault_name, "storage_usage": result}
        except Exception as e:
            return {"vault": self.vault_name, "error": str(e)}
