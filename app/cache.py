import logging
from typing import Optional
from app.config import settings

logger = logging.getLogger(__name__)

class CacheService:
    def __init__(self):
        self.redis = None
        self._memory_fallback = {}

    async def connect(self):
        try:
            import redis.asyncio as aioredis
            self.redis = aioredis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                decode_responses=True
            )
            await self.redis.ping()
            logger.info("Connected to Redis cache successfully.")
        except Exception as e:
            logger.warning(f"Redis not reachable ({e}). Using in-memory fallback cache.")
            self.redis = None

    async def close(self):
        if self.redis:
            await self.redis.close()

    async def get(self, key: str) -> Optional[str]:
        if self.redis:
            try:
                return await self.redis.get(key)
            except Exception as e:
                logger.error(f"Redis GET failed: {e}")
        return self._memory_fallback.get(key)

    async def set(self, key: str, value: str, ttl_seconds: int = 86400):
        if self.redis:
            try:
                await self.redis.set(key, value, ex=ttl_seconds)
                return
            except Exception as e:
                logger.error(f"Redis SET failed: {e}")
        self._memory_fallback[key] = value

    async def delete(self, key: str):
        if self.redis:
            try:
                await self.redis.delete(key)
                return
            except Exception as e:
                logger.error(f"Redis DELETE failed: {e}")
        self._memory_fallback.pop(key, None)

cache_service = CacheService()
