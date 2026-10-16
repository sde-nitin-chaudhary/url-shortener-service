import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.base62 import Base62Encoder, SnowflakeIdGenerator
from app.bloom_filter import BloomFilter
from app.rate_limiter import TokenBucket

client = TestClient(app)

def test_base62_encoding():
    assert Base62Encoder.encode(0) == "0"
    assert Base62Encoder.encode(125) == "21"
    for val in [1, 62, 999, 123456789, 9876543210]:
        encoded = Base62Encoder.encode(val)
        decoded = Base62Encoder.decode(encoded)
        assert decoded == val

def test_snowflake_id_uniqueness():
    gen = SnowflakeIdGenerator(shard_id=1)
    ids = {gen.next_id() for _ in range(1000)}
    assert len(ids) == 1000

def test_bloom_filter():
    bf = BloomFilter(expected_elements=1000, false_positive_rate=0.01)
    bf.add("test_key_1")
    bf.add("test_key_2")
    assert bf.contains("test_key_1") is True
    assert bf.contains("test_key_2") is True
    assert bf.contains("non_existent_key_xyz") is False

def test_token_bucket_rate_limiter():
    bucket = TokenBucket(capacity=2, refill_rate=0.1)
    # First 2 requests should be allowed
    allowed1, _ = bucket.allow_request()
    allowed2, _ = bucket.allow_request()
    assert allowed1 is True
    assert allowed2 is True

    # 3rd request immediately should be rejected
    allowed3, _ = bucket.allow_request()
    assert allowed3 is False

def test_api_shorten_and_redirect():
    response = client.post(
        "/api/v1/shorten",
        json={"original_url": "https://www.google.com", "ttl_seconds": 3600}
    )
    assert response.status_code == 201
    data = response.json()
    assert "short_code" in data
    assert data["original_url"] == "https://www.google.com/"
    short_code = data["short_code"]

    # Redirect test
    redirect_resp = client.get(f"/{short_code}", follow_redirects=False)
    assert redirect_resp.status_code == 302
    assert redirect_resp.headers["location"] == "https://www.google.com/"

    # Analytics test
    analytics_resp = client.get(f"/api/v1/analytics/{short_code}")
    assert analytics_resp.status_code == 200
    analytics_data = analytics_resp.json()
    assert analytics_data["click_count"] >= 1
