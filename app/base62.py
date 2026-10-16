import time
import threading
import hashlib

BASE62_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
BASE = len(BASE62_ALPHABET)

class Base62Encoder:
    @staticmethod
    def encode(num: int) -> str:
        """Encodes an integer into a Base62 string."""
        if num == 0:
            return BASE62_ALPHABET[0]
        
        arr = []
        while num > 0:
            rem = num % BASE
            arr.append(BASE62_ALPHABET[rem])
            num //= BASE
        arr.reverse()
        return "".join(arr)

    @staticmethod
    def decode(s: str) -> int:
        """Decodes a Base62 string back to an integer."""
        num = 0
        for char in s:
            num = num * BASE + BASE62_ALPHABET.index(char)
        return num


class SnowflakeIdGenerator:
    """
    Distributed Snowflake-inspired 64-bit ID generator:
    - 41 bits: Timestamp in milliseconds (gives ~69 years)
    - 10 bits: Shard / Machine ID (supports up to 1,024 shards)
    - 12 bits: Sequence number (supports 4,096 IDs per ms per shard)
    """
    EPOCH = 1704067200000 # Custom Epoch (2024-01-01 00:00:00 UTC in ms)
    SHARD_ID_BITS = 10
    SEQUENCE_BITS = 12

    MAX_SHARD_ID = (1 << SHARD_ID_BITS) - 1
    MAX_SEQUENCE = (1 << SEQUENCE_BITS) - 1

    SHARD_ID_SHIFT = SEQUENCE_BITS
    TIMESTAMP_SHIFT = SEQUENCE_BITS + SHARD_ID_BITS

    def __init__(self, shard_id: int = 0):
        if shard_id < 0 or shard_id > self.MAX_SHARD_ID:
            raise ValueError(f"Shard ID must be between 0 and {self.MAX_SHARD_ID}")
        self.shard_id = shard_id
        self.sequence = 0
        self.last_timestamp = -1
        self._lock = threading.Lock()

    def _current_timestamp_ms(self) -> int:
        return int(time.time() * 1000)

    def next_id(self) -> int:
        with self._lock:
            timestamp = self._current_timestamp_ms()

            if timestamp < self.last_timestamp:
                raise RuntimeError("Clock moved backwards. Refusing to generate ID.")

            if timestamp == self.last_timestamp:
                self.sequence = (self.sequence + 1) & self.MAX_SEQUENCE
                if self.sequence == 0:
                    # Sequence exhausted for this millisecond, wait for next ms
                    while timestamp <= self.last_timestamp:
                        timestamp = self._current_timestamp_ms()
            else:
                self.sequence = 0

            self.last_timestamp = timestamp

            id_val = ((timestamp - self.EPOCH) << self.TIMESTAMP_SHIFT) | \
                     (self.shard_id << self.SHARD_ID_SHIFT) | \
                     self.sequence
            return id_val
