# =============================================================================
# fraud_detection/tasks_cap.py — DRY SHIM
# All capital tasks now live in tasks.py. Import from there.
# =============================================================================
from api.fraud_detection.tasks import (  # noqa: F401
    CapitalTask,
    CapitalTaskManager,
    get_capital_task_manager,
    critical_fraud_analysis,
    regulatory_compliance_check,
    financial_loss_monitoring,
    terrorist_financing_screening,
    executive_alert_generation,
)
