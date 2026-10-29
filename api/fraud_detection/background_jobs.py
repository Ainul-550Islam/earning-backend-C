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


def submit_fraud_detection_job(user_id, payload=None, context=None, priority='normal'):
    """Queue a per-user fraud check. Never raises: it is called from a post_save signal."""
    import logging
    log = logging.getLogger(__name__)
    try:
        from api.fraud_detection.tasks import batch_risk_assessment
        batch_risk_assessment.apply_async(
            kwargs={}, priority=9 if priority == 'high' else 5
        )
        return True
    except Exception as exc:
        log.warning("submit_fraud_detection_job(%s) not queued: %s", user_id, exc)
        return False
