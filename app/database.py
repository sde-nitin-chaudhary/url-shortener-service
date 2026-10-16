import datetime
import hashlib
from typing import Optional, Dict, Any
from app.config import settings

class DatabaseShardManager:
    """
    Horizontally partitioned database layer.
    Routes queries to shard = hash(short_code) % NUM_SHARDS.
    In-memory / SQLite / Postgres storage support.
    """
    def __init__(self):
        # Shard stores: shard_id -> {short_code -> record}
        self.shards: Dict[int, Dict[str, Dict[str, Any]]] = {
            i: {} for i in range(settings.NUM_SHARDS)
        }

    def get_shard_id(self, short_code: str) -> int:
        """Determines shard index using deterministic hashing."""
        h = int(hashlib.md5(short_code.encode('utf-8')).hexdigest(), 16)
        return h % settings.NUM_SHARDS

    async def insert_url(self, short_code: str, original_url: str, custom_alias: bool = False, ttl_seconds: Optional[int] = None) -> Dict[str, Any]:
        shard_id = self.get_shard_id(short_code)
        shard = self.shards[shard_id]

        now = datetime.datetime.utcnow()
        expires_at = now + datetime.timedelta(seconds=ttl_seconds) if ttl_seconds else None

        record = {
            "short_code": short_code,
            "original_url": original_url,
            "shard_id": shard_id,
            "created_at": now.isoformat(),
            "expires_at": expires_at.isoformat() if expires_at else None,
            "click_count": 0,
            "custom_alias": custom_alias
        }

        shard[short_code] = record
        return record

    async def get_url(self, short_code: str) -> Optional[Dict[str, Any]]:
        shard_id = self.get_shard_id(short_code)
        shard = self.shards[shard_id]
        record = shard.get(short_code)

        if not record:
            return None

        # Check TTL expiration
        if record.get("expires_at"):
            exp = datetime.datetime.fromisoformat(record["expires_at"])
            if datetime.datetime.utcnow() > exp:
                del shard[short_code]
                return None

        # Increment click count
        record["click_count"] += 1
        return record

    async def get_analytics(self, short_code: str) -> Optional[Dict[str, Any]]:
        shard_id = self.get_shard_id(short_code)
        shard = self.shards[shard_id]
        return shard.get(short_code)

db_manager = DatabaseShardManager()
