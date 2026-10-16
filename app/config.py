import os

class Settings:
    PROJECT_NAME: str = "Scalable URL Shortener Service"
    API_V1_STR: str = "/api/v1"
    
    # Base URL for short links
    BASE_URL: str = os.getenv("BASE_URL", "http://localhost:8000")

    # Redis Configuration
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", 6379))
    REDIS_DB: int = int(os.getenv("REDIS_DB", 0))
    CACHE_TTL_SECONDS: int = int(os.getenv("CACHE_TTL_SECONDS", 86400)) # 24 hours

    # Rate Limiter Settings (Token Bucket)
    RATE_LIMIT_CAPACITY: int = int(os.getenv("RATE_LIMIT_CAPACITY", 100)) # 100 tokens max
    RATE_LIMIT_REFILL_RATE: float = float(os.getenv("RATE_LIMIT_REFILL_RATE", 10.0)) # 10 tokens/sec

    # Database Shards Configuration
    # Shard 0 and Shard 1 connections
    DB_SHARDS = {
        0: os.getenv("DB_SHARD_0_URL", "sqlite+aiosqlite:///./shard_0.db"),
        1: os.getenv("DB_SHARD_1_URL", "sqlite+aiosqlite:///./shard_1.db")
    }
    NUM_SHARDS: int = len(DB_SHARDS)

settings = Settings()
