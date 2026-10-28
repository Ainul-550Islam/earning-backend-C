# publisher_tools/app_management/app_download.py
"""
Re-export module — views_app_management_full.py এই module থেকে import করে।

    from .app_management.app_download import AppDownloadSnapshot

app_downloads.py-তে AppDownloadSnapshot define করা আছে।
এই file শুধু সেই class re-export করে যাতে view-এর import path কাজ করে।
"""
from .app_downloads import AppDownloadSnapshot

__all__ = ['AppDownloadSnapshot']
