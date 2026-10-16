from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import RedirectResponse, JSONResponse
from pydantic import BaseModel, HttpUrl, Field
from typing import Optional
import uvicorn
import re

from app.config import settings
from app.base62 import Base62Encoder, SnowflakeIdGenerator
from app.bloom_filter import BloomFilter
from app.rate_limiter import RateLimiter
from app.cache import cache_service
from app.database import db_manager

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Horizontally Scalable URL Shortener Microservice with Base62 encoding, Redis write-through caching, database sharding, and Bloom filter collision checks.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Global instances
id_generator = SnowflakeIdGenerator(shard_id=0)
bloom_filter = BloomFilter(expected_elements=1000000, false_positive_rate=0.01)
rate_limiter = RateLimiter(default_capacity=settings.RATE_LIMIT_CAPACITY, default_refill_rate=settings.RATE_LIMIT_REFILL_RATE)

@app.on_event("startup")
async def startup_event():
    await cache_service.connect()

@app.on_event("shutdown")
async def shutdown_event():
    await cache_service.close()

# Pydantic Request/Response Models
class ShortenRequest(BaseModel):
    original_url: HttpUrl = Field(..., description="The original long URL to shorten", example="https://en.wikipedia.org/wiki/Distributed_computing")
    custom_alias: Optional[str] = Field(None, min_length=3, max_length=16, description="Optional custom short alias", example="dist-comp")
    ttl_seconds: Optional[int] = Field(None, ge=60, description="Optional TTL expiration in seconds", example=86400)

class ShortenResponse(BaseModel):
    short_code: str
    short_url: str
    original_url: str
    expires_at: Optional[str] = None
    shard_id: int

class AnalyticsResponse(BaseModel):
    short_code: str
    original_url: str
    click_count: int
    created_at: str
    expires_at: Optional[str] = None
    shard_id: int

@app.post(
    "/api/v1/shorten",
    response_model=ShortenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a shortened URL",
    tags=["URL Operations"]
)
async def shorten_url(payload: ShortenRequest, request: Request):
    # 1. Token Bucket Rate Limiter
    client_ip = request.client.host if request.client else "127.0.0.1"
    allowed, remaining_tokens = rate_limiter.is_allowed(client_ip)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please wait before making more requests."
        )

    short_code = None

    # 2. Handle Custom Alias
    if payload.custom_alias:
        alias = payload.custom_alias.strip()
        if not re.match(r"^[a-zA-Z0-9_-]+$", alias):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Custom alias contains invalid characters. Use alphanumeric, dashes, or underscores."
            )
        
        # Bloom filter fast collision check
        if bloom_filter.contains(alias):
            existing = await db_manager.get_url(alias)
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Custom alias '{alias}' is already in use."
                )
        short_code = alias
    else:
        # 3. Base62 ID Generation with Bloom Collision Check
        while True:
            unique_id = id_generator.next_id()
            candidate_code = Base62Encoder.encode(unique_id)
            # Take 7 characters
            candidate_code = candidate_code[-7:] if len(candidate_code) >= 7 else candidate_code.zfill(7)

            if not bloom_filter.contains(candidate_code):
                short_code = candidate_code
                break

            # If Bloom filter flags existence, verify in DB to rule out false positive
            existing = await db_manager.get_url(candidate_code)
            if not existing:
                short_code = candidate_code
                break

    # Add to Bloom filter
    bloom_filter.add(short_code)

    # 4. Database Shard Persistence
    record = await db_manager.insert_url(
        short_code=short_code,
        original_url=str(payload.original_url),
        custom_alias=bool(payload.custom_alias),
        ttl_seconds=payload.ttl_seconds
    )

    # 5. Redis Write-Through Caching
    ttl = payload.ttl_seconds if payload.ttl_seconds else settings.CACHE_TTL_SECONDS
    await cache_service.set(f"url:{short_code}", str(payload.original_url), ttl_seconds=ttl)

    return ShortenResponse(
        short_code=short_code,
        short_url=f"{settings.BASE_URL}/{short_code}",
        original_url=str(payload.original_url),
        expires_at=record["expires_at"],
        shard_id=record["shard_id"]
    )

@app.get(
    "/{short_code}",
    summary="Redirect to original long URL",
    response_class=RedirectResponse,
    status_code=status.HTTP_302_FOUND,
    tags=["URL Operations"]
)
async def redirect_to_long_url(short_code: str):
    # 1. Fast Path: Check Redis Write-Through Cache
    cached_url = await cache_service.get(f"url:{short_code}")
    if cached_url:
        return RedirectResponse(url=cached_url, status_code=status.HTTP_302_FOUND)

    # 2. Slow Path: Query Database Shard
    record = await db_manager.get_url(short_code)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Short URL '{short_code}' not found or has expired."
        )

    # Populate cache (write-through / read-repair)
    await cache_service.set(f"url:{short_code}", record["original_url"], ttl_seconds=settings.CACHE_TTL_SECONDS)

    return RedirectResponse(url=record["original_url"], status_code=status.HTTP_302_FOUND)

@app.get(
    "/api/v1/analytics/{short_code}",
    response_model=AnalyticsResponse,
    summary="Retrieve URL analytics",
    tags=["Analytics"]
)
async def get_analytics(short_code: str):
    record = await db_manager.get_analytics(short_code)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="URL not found"
        )
    return AnalyticsResponse(
        short_code=record["short_code"],
        original_url=record["original_url"],
        click_count=record["click_count"],
        created_at=record["created_at"],
        expires_at=record["expires_at"],
        shard_id=record["shard_id"]
    )

@app.get("/health", tags=["Monitoring"])
async def health_check():
    return {"status": "healthy", "service": settings.PROJECT_NAME}

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
