# config/backup_config.py

import os
import re
from pathlib import Path
from typing import List, Dict, Any, Pattern

# ================= নোটিফিকেশন কনফিগ =================
NOTIFICATION_CONFIG = {
    'ENABLED': True,
    'ON_ERROR': True,  # শুধু এররের সময় নোটিফাই
    'ON_WARNING': True,  # ওয়ার্নিং এর সময় নোটিফাই
    'ON_SUCCESS': False,  # সফল অপারেশনের সময় নোটিফাই (প্রোডাকশনে বন্ধ রাখুন)
    
    # ইমেইল কনফিগ
    'EMAIL': {
        'ENABLED': True,
        'SMTP_SERVER': 'smtp.gmail.com',
        'SMTP_PORT': 587,
        'SENDER_EMAIL': os.getenv('BACKUP_EMAIL', 'your-email@gmail.com'),
        'SENDER_PASSWORD': os.getenv('BACKUP_EMAIL_PASSWORD', ''),
        'RECIPIENT_EMAILS': [
            'admin@yourcompany.com',
            'backup-admin@yourcompany.com'
        ],
        'USE_TLS': True
    },
    
    # টেলিগ্রাম কনফিগ
    'TELEGRAM': {
        'ENABLED': True,
        'BOT_TOKEN': os.getenv('TELEGRAM_BOT_TOKEN', ''),
        'CHAT_IDS': [
            '-1001234567890',  # গ্রুপ বা চ্যানেল আইডি
            '987654321'        # ব্যক্তিগত চ্যাট আইডি
        ],
        'SEND_AS_MARKDOWN': True
    },
    
    # Slack কনফিগ
    'SLACK': {
        'ENABLED': False,
        'WEBHOOK_URL': os.getenv('SLACK_WEBHOOK_URL', ''),
        'CHANNEL': '#backup-alerts',
        'USERNAME': 'Backup Bot'
    },
    
    # Discord কনফিগ
    'DISCORD': {
        'ENABLED': False,
        'WEBHOOK_URL': os.getenv('DISCORD_WEBHOOK_URL', ''),
        'USERNAME': 'Backup Alert'
    },
    
    # Pushover (মোবাইল নোটিফিকেশন)
    'PUSHOVER': {
        'ENABLED': False,
        'APP_TOKEN': os.getenv('PUSHOVER_APP_TOKEN', ''),
        'USER_KEY': os.getenv('PUSHOVER_USER_KEY', ''),
        'PRIORITY': 1  # উচ্চ প্রায়োরিটি (জরুরী)
    }
}

# ================= ডাটা রিটেনশন পলিসি =================
RETENTION_POLICY = {
    # লোকাল স্টোরেজ (সার্ভারে)
    'LOCAL': {
        'MAX_BACKUPS': 10,  # সর্বোচ্চ ১০টি ব্যাকআপ
        'DAYS_TO_KEEP': 30,  # ৩০ দিনের বেশি পুরনো ফাইল রাখবে না
        'SIZE_LIMIT_MB': 1024,  # সর্বোচ্চ ১GB স্টোরেজ
        'AUTO_CLEANUP': True
    },
    
    # ক্লাউড স্টোরেজ
    'CLOUD': {
        'MAX_BACKUPS': 100,  # সর্বোচ্চ ১০০টি ব্যাকআপ
        'DAYS_TO_KEEP': 365,  # ১ বছরের বেশি পুরনো ফাইল রাখবে না
        'VERSIONS_TO_KEEP': 3,  # প্রতিটি ফাইলের সর্বশেষ ৩টি ভার্সন
        'AUTO_CLEANUP': True,
        
        # বিভিন্ন ফাইল টাইপের জন্য আলাদা রিটেনশন পলিসি
        'FILE_TYPE_POLICIES': {
            'database': {
                'DAYS_TO_KEEP': 90,  # ডাটাবেস ব্যাকআপ ৯০ দিন রাখা
                'MAX_BACKUPS': 30
            },
            'logs': {
                'DAYS_TO_KEEP': 30,  # লগ ফাইল ৩০ দিন
                'MAX_BACKUPS': 50
            },
            'config': {
                'DAYS_TO_KEEP': 180,  # কনফিগ ফাইল ১৮০ দিন
                'MAX_BACKUPS': 20
            },
            'media': {
                'DAYS_TO_KEEP': 60,  # মিডিয়া ফাইল ৬০ দিন
                'MAX_BACKUPS': 40
            }
        }
    },
    
    # আর্কাইভ পলিসি (খুব পুরনো ডাটা)
    'ARCHIVE': {
        'ENABLED': True,
        'COMPRESS_BEFORE_ARCHIVE': True,
        'ENCRYPT_BEFORE_ARCHIVE': True,
        'MOVE_TO_COLD_STORAGE': False,  # AWS Glacier বা Google Coldline
        'ARCHIVE_AFTER_DAYS': 365  # ১ বছর পর আর্কাইভে নিন
    }
}

# ================= ফাইল এক্সক্লুশন প্যাটার্ন =================
EXCLUSION_PATTERNS = {
    # ডিরেক্টরি প্যাটার্ন
    'DIRECTORIES': [
        r'venv',
        r'__pycache__',
        r'node_modules',
        r'\.git',
        r'\.svn',
        r'\.hg',
        r'build',
        r'dist',
        r'\.idea',
        r'\.vscode',
        r'\.env',
        r'logs',  # logs ডিরেক্টরি (যদি আলাদা থাকে)
        r'temp',
        r'tmp',
        r'cache',
        r'trash',
        r'recycle',
        r'.*/\.cache/.*',
        r'backups',  # ব্যাকআপ ডিরেক্টরি নিজেই ব্যাকআপ নেবেন না
    ],
    
    # ফাইল প্যাটার্ন
    'FILES': [
        r'.*\.pyc$',
        r'.*\.pyo$',
        r'.*\.pyd$',
        r'.*\.so$',
        r'.*\.dll$',
        r'.*\.exe$',
        r'.*\.log$',
        r'.*\.tmp$',
        r'.*\.temp$',
        r'.*\.swp$',
        r'.*\.swo$',
        r'.*\.DS_Store$',
        r'\.DS_Store$',
        r'Thumbs\.db$',
        r'desktop\.ini$',
        r'.*\.cache$',
        r'.*\.bak$',  # অন্য ব্যাকআপ ফাইল
        r'.*\.backup$',
        r'.*\.old$',
        r'.*~$',  # টেম্পোরারি এডিটর ফাইল
        r'.*\.sqlite3$',  # SQLite ডাটাবেস (যদি live থাকে)
        r'.*\.db$',  # অন্যান্য ডাটাবেস ফাইল
        r'.*\.sock$',  # Unix socket ফাইল
        r'.*\.pid$',  # PID ফাইল
    ],
    
    # সাইজ-ভিত্তিক এক্সক্লুশন
    'SIZE_LIMITS': {
        'MAX_FILE_SIZE_MB': 100,  # 100MB এর বেশি ফাইল ব্যাকআপ নেবেন না
        'EXCLUDE_EXTENSIONS_OVER_SIZE': {
            '.mp4': 50,  # 50MB এর বেশি MP4 ফাইল
            '.avi': 50,
            '.mkv': 50,
            '.iso': 10,  # ISO ফাইল
            '.zip': 200,  # 200MB এর বেশি ZIP
            '.tar.gz': 200,
            '.7z': 200,
        }
    },
    
    # কন্টেন্ট-ভিত্তিক এক্সক্লুশন
    'CONTENT_PATTERNS': [
        r'password\s*[:=]\s*\S+',  # পাসওয়ার্ড লাইন
        r'secret\s*[:=]\s*\S+',
        r'api[_-]?key\s*[:=]\s*\S+',
        r'token\s*[:=]\s*\S+',
    ],
    
    # পাথ প্যাটার্ন (regex)
    'PATH_PATTERNS': [
        r'.*/test/.*',  # test ডিরেক্টরির সবকিছু
        r'.*/tests/.*',
        r'.*/debug/.*',
        r'.*/tmp/.*',
        r'.*/upload/.*',
        r'.*/media/temp/.*',
        r'.*/staticfiles/.*',  # Django static files
    ]
}

# ================= ব্যাকআপ কনফিগারেশন =================
BACKUP_CONFIG = {
    'BACKUP_DIR': Path('backups'),
    'MAX_LOCAL_BACKUPS': 10,
    'COMPRESS_FILES': True,
    'COMPRESS_THRESHOLD_KB': 100,
    'COMPRESSION_LEVEL': 6,  # 1-9 (1=ফাস্ট, 9=বেস্ট কম্প্রেশন)
    
    'ENCRYPTION': {
        'ENABLED': True,
        'ALGORITHM': 'AES256',
        'KEY_FILE': Path('config/backup_key.bin'),
        'ENCRYPT_SENSITIVE_ONLY': True  # শুধু সেনসিটিভ ফাইল এনক্রিপ্ট
    },
    
    'CLOUD_UPLOAD': {
        'ENABLED': True,
        'PROVIDER': 'google_drive',
        'OFFLOAD_OLD_BACKUPS': True,
        'DAYS_TO_KEEP_LOCAL': 7,
        'MAX_CLOUD_BACKUPS': 100,
        'CLOUD_RETENTION_POLICY': RETENTION_POLICY['CLOUD']
    },
    
    'VERIFICATION': {
        'DRY_RUN_TEST': True,
        'HASH_VERIFICATION': True,
        'PERIODIC_TEST_DAYS': 7,
        'VERIFY_AFTER_BACKUP': True,
        'VERIFY_AFTER_RESTORE': True
    },
    
    'THREAD_SAFETY': {
        'ENABLED': True,
        'LOCK_TIMEOUT_SECONDS': 30,
        'MAX_CONCURRENT_BACKUPS': 3
    },
    
    'SCHEDULE': {
        'FULL_BACKUP_INTERVAL_DAYS': 7,
        'INCREMENTAL_BACKUP_INTERVAL_HOURS': 24,
        'DIFFERENTIAL_BACKUP_ENABLED': True,
        'BACKUP_WINDOW_START': '02:00',  # রাত ২টা
        'BACKUP_WINDOW_END': '06:00',    # সকাল ৬টা
        'PAUSE_ON_HIGH_LOAD': True,
        'MAX_CPU_PERCENT': 70,
        'MAX_MEMORY_PERCENT': 80
    },
    
    'NOTIFICATION': NOTIFICATION_CONFIG,
    'RETENTION_POLICY': RETENTION_POLICY,
    'EXCLUSION_PATTERNS': EXCLUSION_PATTERNS,
    
    # মনিটরিং
    'MONITORING': {
        'ENABLED': True,
        'LOG_SUCCESS': True,
        'LOG_FAILURES': True,
        'METRICS_FILE': Path('backup_metrics.json'),
        'SEND_METRICS_TO_CLOUD': True,
        'ALERT_ON_SPACE_LOW': True,
        'SPACE_WARNING_PERCENT': 80,
        'SPACE_CRITICAL_PERCENT': 90
    }
}

# ================= ক্লাউড কনফিগ =================

# Google Drive কনফিগারেশন
GOOGLE_DRIVE_CONFIG = {
    'CREDENTIALS_FILE': Path('credentials/google-drive-credentials.json'),
    'FOLDER_ID': 'your-google-drive-folder-id',
    'SCOPES': ['https://www.googleapis.com/auth/drive.file'],
    'SHARED_DRIVE_ID': None,  # যদি Shared Drive ব্যবহার করেন
    'MAX_UPLOAD_SIZE_MB': 5000,  # 5GB (Google Drive limit)
    'CHUNK_SIZE_MB': 100,  # 100MB chunks
    'TIMEOUT_SECONDS': 300
}

# AWS S3 কনফিগারেশন
AWS_S3_CONFIG = {
    'BUCKET_NAME': 'your-backup-bucket',
    'REGION': 'us-east-1',
    'ACCESS_KEY': os.getenv('AWS_ACCESS_KEY_ID'),
    'SECRET_KEY': os.getenv('AWS_SECRET_ACCESS_KEY'),
    'STORAGE_CLASS': 'STANDARD_IA',  # STANDARD, STANDARD_IA, GLACIER
    'ENCRYPTION': 'AES256',  # SSE-S3
    'MULTIPART_THRESHOLD_MB': 100,
    'MAX_CONCURRENT_UPLOADS': 5,
    'LIFECYCLE_RULES': {
        'GLACIER_TRANSITION_DAYS': 90,  # ৯০ দিন পর Glacier-এ পাঠান
        'EXPIRATION_DAYS': 365  # ১ বছর পর এক্সপায়ার
    }
}

# Dropbox কনফিগারেশন
DROPBOX_CONFIG = {
    'ACCESS_TOKEN': os.getenv('DROPBOX_ACCESS_TOKEN'),
    'FOLDER_PATH': '/Backups',
    'APP_KEY': os.getenv('DROPBOX_APP_KEY'),
    'APP_SECRET': os.getenv('DROPBOX_APP_SECRET'),
    'TIMEOUT_SECONDS': 300,
    'CHUNK_SIZE_MB': 150  # Dropbox recommended chunk size
}

# OneDrive কনফিগারেশন (যদি দরকার)
ONEDRIVE_CONFIG = {
    'CLIENT_ID': os.getenv('ONEDRIVE_CLIENT_ID'),
    'CLIENT_SECRET': os.getenv('ONEDRIVE_CLIENT_SECRET'),
    'TENANT_ID': 'common',
    'FOLDER_NAME': 'Backups',
    'TIMEOUT_SECONDS': 300
}

# ================= হেল্পার ফাংশন =================

def should_exclude_file(filepath: Path) -> bool:
    """
    ফাইলটি এক্সক্লুড করা উচিত কিনা চেক করুন
    """
    try:
        filepath_str = str(filepath)
        
        # ১. ডিরেক্টরি প্যাটার্ন চেক
        for pattern in EXCLUSION_PATTERNS['DIRECTORIES']:
            if re.search(pattern, filepath_str, re.IGNORECASE):
                return True
        
        # ২. ফাইল প্যাটার্ন চেক
        filename = filepath.name
        for pattern in EXCLUSION_PATTERNS['FILES']:
            if re.search(pattern, filename, re.IGNORECASE):
                return True
        
        # ৩. পাথ প্যাটার্ন চেক
        for pattern in EXCLUSION_PATTERNS['PATH_PATTERNS']:
            if re.search(pattern, filepath_str, re.IGNORECASE):
                return True
        
        # ৪. সাইজ চেক (যদি ফাইল থাকে)
        if filepath.is_file():
            file_size_mb = filepath.stat().st_size / (1024 * 1024)
            
            # সর্বোচ্চ সাইজ লিমিট
            if file_size_mb > EXCLUSION_PATTERNS['SIZE_LIMITS']['MAX_FILE_SIZE_MB']:
                return True
            
            # এক্সটেনশন ভিত্তিক সাইজ লিমিট
            for ext, size_limit in EXCLUSION_PATTERNS['SIZE_LIMITS']['EXCLUDE_EXTENSIONS_OVER_SIZE'].items():
                if filename.endswith(ext) and file_size_mb > size_limit:
                    return True
        
        return False
        
    except Exception:
        # যদি কোনো ইরর হয়, সেফটির জন্য এক্সক্লুড করুন
        return True

def get_compiled_exclusion_patterns() -> Dict[str, List[Pattern]]:
    """
    কম্পাইলড regex প্যাটার্নস পান
    """
    compiled = {
        'directories': [],
        'files': [],
        'paths': [],
        'content': []
    }
    
    for pattern in EXCLUSION_PATTERNS['DIRECTORIES']:
        compiled['directories'].append(re.compile(pattern, re.IGNORECASE))
    
    for pattern in EXCLUSION_PATTERNS['FILES']:
        compiled['files'].append(re.compile(pattern, re.IGNORECASE))
    
    for pattern in EXCLUSION_PATTERNS['PATH_PATTERNS']:
        compiled['paths'].append(re.compile(pattern, re.IGNORECASE))
    
    for pattern in EXCLUSION_PATTERNS['CONTENT_PATTERNS']:
        compiled['content'].append(re.compile(pattern, re.IGNORECASE))
    
    return compiled

def get_file_type(filepath: Path) -> str:
    """
    ফাইলের টাইপ নির্ধারণ করুন (রিটেনশন পলিসির জন্য)
    """
    filename = filepath.name.lower()
    
    if filename.endswith(('.sql', '.sqlite', '.db', '.sqlite3')):
        return 'database'
    elif filename.endswith(('.log', '.txt', '.csv')):
        return 'logs'
    elif filename.endswith(('.json', '.yaml', '.yml', '.ini', '.cfg', '.conf', '.env')):
        return 'config'
    elif filename.endswith(('.jpg', '.jpeg', '.png', '.gif', '.mp4', '.avi', '.mp3')):
        return 'media'
    elif filename.endswith(('.py', '.js', '.java', '.cpp', '.html', '.css')):
        return 'code'
    elif filename.endswith(('.zip', '.tar.gz', '.7z', '.rar')):
        return 'archive'
    else:
        return 'other'