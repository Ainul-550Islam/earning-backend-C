import functools
from django.core.cache import cache
from api.cache.keys.CacheKeyGenerator import cache_key_generator

def cache_data(timeout=300, key_prefix='', invalidate_on=None, key_func=None):
    """
    Custom decorator to cache Django model/data results in Redis
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # ১. ক্যাশ কি (Key) জেনারেট করা
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # ফাংশনের নাম এবং আর্গুমেন্ট দিয়ে ইউনিক কি তৈরি
                args_str = str(args[1:]) if len(args) > 1 else "" 
                cache_key = f"{key_prefix}:{args_str}:{kwargs}"

            # ২. ক্যাশ থেকে ডেটা খোঁজা
            result = cache.get(cache_key)
            if result is not None:
                return result

            # ৩. ক্যাশে না থাকলে মেইন ফাংশনটি রান করা (Database Query)
            result = func(*args, **kwargs)

            # ৪. রেজাল্ট ক্যাশে সেভ করা
            cache.set(cache_key, result, timeout=timeout)
            
            return result
        return wrapper
    return decorator