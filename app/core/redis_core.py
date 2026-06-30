import redis
from app.core.config import settings

redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

def set_cache(key: str, value: str, ex: int = 3600):
    redis_client.set(key, value, ex=ex)

def get_cache(key: str):
    return redis_client.get(key)

def clear_cache():
    redis_client.flushall()
