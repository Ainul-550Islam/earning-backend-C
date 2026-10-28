# =============================================================================
# fraud_detection/background_jobs.py — DRY SHIM
# All background jobs now live in tasks.py. Import from there.
# =============================================================================
from api.fraud_detection.tasks import (  # noqa: F401
    FraudDetectionJobManager,
    get_job_manager,
    run_fraud_scan,
    batch_risk_assessment,
    process_sanctions_screening,
    generate_compliance_report,
    warm_fraud_cache,
    cleanup_fraud_cache,
    update_external_threat_intelligence,
    generate_daily_analytics,
)
