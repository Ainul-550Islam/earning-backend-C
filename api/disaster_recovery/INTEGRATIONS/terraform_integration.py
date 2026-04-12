"""
Terraform Integration — Infrastructure as Code for DR environments
"""
import logging
import subprocess
import json
import os
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class TerraformIntegration:
    """
    Manages Terraform operations for DR infrastructure:
    - Provision DR environments on demand
    - Destroy environments after drills
    - Import existing infrastructure
    - Run terraform plan/apply for DR failover
    """

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.working_dir = config.get("working_dir", "/opt/terraform/dr")
        self.state_backend = config.get("state_backend", "s3")
        self.workspace = config.get("workspace", "production")
        self.env_vars = {
            "TF_IN_AUTOMATION": "1",
            **config.get("env_vars", {})
        }

    def _terraform(self, *args, cwd: str = None, timeout: int = 600) -> dict:
        """Run terraform command."""
        cmd = ["terraform"] + list(args)
        env = {**os.environ, **self.env_vars}
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=timeout, cwd=cwd or self.working_dir,
                env=env
            )
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }
        except FileNotFoundError:
            return {"success": False, "error": "Terraform not installed"}

    def init(self, reconfigure: bool = False) -> dict:
        """Initialize Terraform working directory."""
        args = ["init", "-input=false"]
        if reconfigure:
            args.append("-reconfigure")
        result = self._terraform(*args)
        logger.info(f"Terraform init: {'success' if result['success'] else 'failed'}")
        return result

    def workspace_select(self, workspace: str) -> dict:
        result = self._terraform("workspace", "select", workspace)
        if not result["success"]:
            # Try to create if doesn't exist
            result = self._terraform("workspace", "new", workspace)
        logger.info(f"Terraform workspace: {workspace}")
        return result

    def plan(self, var_file: str = None, vars: Dict[str, str] = None,
             out_file: str = "tfplan") -> dict:
        """Run terraform plan and save to file."""
        args = ["plan", "-input=false", f"-out={out_file}"]
        if var_file:
            args.append(f"-var-file={var_file}")
        if vars:
            for k, v in vars.items():
                args.append(f"-var={k}={v}")
        result = self._terraform(*args, timeout=300)
        logger.info(f"Terraform plan completed: {result['success']}")
        return result

    def apply(self, plan_file: str = "tfplan", auto_approve: bool = False) -> dict:
        """Apply Terraform changes."""
        if plan_file and os.path.exists(os.path.join(self.working_dir, plan_file)):
            args = ["apply", "-input=false", plan_file]
        else:
            args = ["apply", "-input=false"]
            if auto_approve:
                args.append("-auto-approve")
        result = self._terraform(*args, timeout=1800)
        logger.info(f"Terraform apply: {'success' if result['success'] else 'failed'}")
        return result

    def destroy(self, auto_approve: bool = False,
                vars: Dict[str, str] = None) -> dict:
        """Destroy Terraform-managed infrastructure."""
        args = ["destroy", "-input=false"]
        if auto_approve:
            args.append("-auto-approve")
        if vars:
            for k, v in vars.items():
                args.append(f"-var={k}={v}")
        result = self._terraform(*args, timeout=1800)
        logger.warning(f"Terraform destroy: {'success' if result['success'] else 'failed'}")
        return result

    def output(self, output_name: str = None) -> dict:
        """Get Terraform outputs."""
        args = ["output", "-json"]
        if output_name:
            args.append(output_name)
        result = self._terraform(*args)
        if result["success"] and result["stdout"]:
            try:
                return {"success": True, "outputs": json.loads(result["stdout"])}
            except json.JSONDecodeError:
                pass
        return result

    def state_list(self) -> List[str]:
        """List all resources in Terraform state."""
        result = self._terraform("state", "list")
        if result["success"]:
            return [r.strip() for r in result["stdout"].splitlines() if r.strip()]
        return []

    def import_resource(self, resource_address: str, resource_id: str) -> dict:
        """Import existing infrastructure into Terraform state."""
        result = self._terraform("import", resource_address, resource_id)
        logger.info(f"Terraform import: {resource_address} = {resource_id}")
        return result

    def get_state(self) -> dict:
        """Get current Terraform state as JSON."""
        result = self._terraform("show", "-json")
        if result["success"] and result["stdout"]:
            try:
                return {"success": True, "state": json.loads(result["stdout"])}
            except json.JSONDecodeError:
                pass
        return result

    def provision_dr_environment(self, environment: str = "dr",
                                  region: str = "us-west-2") -> dict:
        """Provision a complete DR environment using Terraform."""
        logger.critical(f"Provisioning DR environment: {environment} in {region}")
        steps = []
        # 1. Init
        init_result = self.init()
        steps.append({"step": "init", **init_result})
        if not init_result["success"]:
            return {"success": False, "steps": steps, "error": "Init failed"}
        # 2. Select/create workspace
        ws_result = self.workspace_select(environment)
        steps.append({"step": "workspace", **ws_result})
        # 3. Plan
        plan_result = self.plan(vars={"region": region, "environment": environment})
        steps.append({"step": "plan", **plan_result})
        if not plan_result["success"]:
            return {"success": False, "steps": steps, "error": "Plan failed"}
        # 4. Apply
        apply_result = self.apply(auto_approve=True)
        steps.append({"step": "apply", **apply_result})
        # 5. Get outputs
        output_result = self.output()
        steps.append({"step": "output", **output_result})
        success = apply_result["success"]
        logger.info(f"DR environment provision: {'SUCCESS' if success else 'FAILED'}")
        return {
            "success": success,
            "environment": environment,
            "region": region,
            "steps": steps,
            "outputs": output_result.get("outputs", {}),
            "provisioned_at": datetime.utcnow().isoformat(),
        }
