"""Auto Scaling — Automatically scales infrastructure based on load."""
import logging
logger = logging.getLogger(__name__)

class AutoScaling:
    def __init__(self, provider: str = "aws", config: dict = None):
        self.provider = provider
        self.config = config or {}

    def scale_out(self, group_name: str, increment: int = 1) -> dict:
        logger.info(f"Scaling out: {group_name} +{increment}")
        if self.provider == "aws":
            import boto3
            asg = boto3.client("autoscaling")
            r = asg.describe_auto_scaling_groups(AutoScalingGroupNames=[group_name])
            groups = r.get("AutoScalingGroups", [])
            if groups:
                current = groups[0]["DesiredCapacity"]
                asg.update_auto_scaling_group(
                    AutoScalingGroupName=group_name,
                    DesiredCapacity=current + increment
                )
        return {"group": group_name, "action": "scale_out", "increment": increment}

    def scale_in(self, group_name: str, decrement: int = 1) -> dict:
        logger.info(f"Scaling in: {group_name} -{decrement}")
        return {"group": group_name, "action": "scale_in", "decrement": decrement}

    def get_current_capacity(self, group_name: str) -> int:
        if self.provider == "aws":
            import boto3
            asg = boto3.client("autoscaling")
            r = asg.describe_auto_scaling_groups(AutoScalingGroupNames=[group_name])
            groups = r.get("AutoScalingGroups", [])
            return groups[0]["DesiredCapacity"] if groups else 0
        return 1
