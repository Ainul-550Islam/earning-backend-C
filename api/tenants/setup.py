"""
Setup script for Tenant Management System

This script provides installation configuration for the tenant management
Django application with all necessary dependencies and metadata.
"""

from setuptools import setup, find_packages

# Read the contents of README file
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

# Read the contents of requirements file
with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="django-tenant-management",
    version="1.0.0",
    author="Tenant Management Team",
    author_email="support@tenantmanagement.com",
    description="A comprehensive Django application for multi-tenant SaaS management",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/tenantmanagement/django-tenant-management",
    packages=find_packages(),
    include_package_data=True,
    install_requires=requirements,
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: Web Environment",
        "Framework :: Django",
        "Framework :: Django :: 4.0",
        "Framework :: Django :: 4.1",
        "Framework :: Django :: 4.2",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Software Development :: Libraries :: Application Frameworks",
    ],
    python_requires=">=3.8",
    keywords="django, multi-tenant, saas, management, billing, analytics",
    project_urls={
        "Bug Reports": "https://github.com/tenantmanagement/django-tenant-management/issues",
        "Source": "https://github.com/tenantmanagement/django-tenant-management",
        "Documentation": "https://django-tenant-management.readthedocs.io/",
        "Changelog": "https://github.com/tenantmanagement/django-tenant-management/blob/main/CHANGELOG.md",
    },
    entry_points={
        "console_scripts": [
            "tenant-manage=api.tenants.management.commands.tenants:Command",
        ],
    },
    package_data={
        "api.tenants": [
            "templates/*.html",
            "templates/emails/*.html",
            "templates/tenants/*.html",
            "docs/*.md",
            "static/*",
        ],
    },
    zip_safe=False,
    platforms=["any"],
)
