#!/usr/bin/env python
"""
Rate Limiting Demo Script
Demonstrates the rate limiting middleware functionality
"""

import os
import sys
import time
from datetime import datetime

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

def demo_rate_limiting():
    """Demonstrate rate limiting functionality"""
    print("🚀 Rate Limiting Demo")
    print("=" * 50)

    # Show default rate limits
    print("📋 Default Rate Limits:")
    DEFAULT_RATE_LIMITS = {
        'api_general': {'limit': 1000, 'window': 3600, 'scope': 'user'},
        'postback': {'limit': 10000, 'window': 3600, 'scope': 'global'},
        'withdrawal': {'limit': 5, 'window': 86400, 'scope': 'user'},
        'task_click': {'limit': 100, 'window': 3600, 'scope': 'user'},
        'survey_submit': {'limit': 20, 'window': 3600, 'scope': 'user'},
        'offer_click': {'limit': 100, 'window': 3600, 'scope': 'user'},
        'proof_submit': {'limit': 50, 'window': 3600, 'scope': 'user'},
    }

    for limit_type, config in DEFAULT_RATE_LIMITS.items():
        limit = config['limit']
        window = config['window']
        scope = config.get('scope', 'user')
        print(f"  • {limit_type}: {limit} requests per {window}s ({scope})")

    print("\n🔧 RateLimitService Architecture:")
    print("   - Uses Redis for distributed rate limiting")
    print("   - Falls back to Django cache if Redis unavailable")
    print("   - Loads configuration from database (RateLimitConfig model)")
    print("   - Implements token bucket algorithm")

    print("\n🎯 Simulating Rate Limiting Logic...")

    # Simulate the token bucket algorithm
    class MockRateLimiter:
        def __init__(self):
            self.requests = {}

        def check_limit(self, limit_type, identifier, limit=100, window=3600):
            key = f"{limit_type}:{identifier}"
            now = time.time()

            if key not in self.requests:
                self.requests[key] = []

            # Clean old requests outside window
            self.requests[key] = [
                req_time for req_time in self.requests[key]
                if now - req_time < window
            ]

            # Check if under limit
            if len(self.requests[key]) < limit:
                self.requests[key].append(now)
                remaining = limit - len(self.requests[key])
                return True, remaining
            else:
                return False, 0

    limiter = MockRateLimiter()

    user_id = "demo_user_123"
    print("\nTesting 'task_click' limit (100/hour)...")

    for i in range(5):
        is_allowed, remaining = limiter.check_limit("task_click", f"user_{user_id}", 100, 3600)
        status = "✅ ALLOWED" if is_allowed else "❌ BLOCKED"
        print(f"  Request {i+1}: {status} (remaining: {remaining})")
        time.sleep(0.1)

    print("\n📊 Testing different scenarios...")

    test_cases = [
        ("api_general", "user_456", 1000, 3600),
        ("withdrawal", "user_789", 5, 86400),
        ("postback", "global", 10000, 3600),
    ]

    for limit_type, identifier, limit, window in test_cases:
        is_allowed, remaining = limiter.check_limit(limit_type, identifier, limit, window)
        print(f"  {limit_type} for {identifier}: {'✅' if is_allowed else '❌'} ({remaining} remaining)")

    print("\n🎉 Demo completed successfully!")
    print("\n📝 Note: Full functionality requires Django + Redis setup")
    print("   Run 'python manage.py populate_rate_limits' to set up database configs")
    print("   Access admin at /admin/tasks/ratelimitconfig/ to manage limits")

if __name__ == "__main__":
    demo_rate_limiting()