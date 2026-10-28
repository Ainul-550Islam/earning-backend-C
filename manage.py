#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys

from config.import_aliases import install_import_aliases
from config.url_converter_patch import install_url_converter_patch

install_import_aliases()
install_url_converter_patch()


def main():
    # Fix Windows UTF-8 encoding — prevents UnicodeEncodeError from CMS unicode chars
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.base')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
