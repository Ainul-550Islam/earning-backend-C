# publisher_tools/app_management/app_quality.py
"""
Re-export module — views_app_management_full.py এই module থেকে import করে।

    from .app_management.app_quality import AppQualityScore

app_quality_score.py-তে AppQualityScore define করা আছে।
এই file শুধু সেই class re-export করে যাতে view-এর import path কাজ করে।
"""
from .app_quality_score import AppQualityScore

__all__ = ['AppQualityScore']
