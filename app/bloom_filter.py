import math
import hashlib

class BloomFilter:
    """
    Space-efficient probabilistic filter to detect hash collision / URL existence.
    - Zero False Negatives (if returns False, key definitely does not exist)
    - Low, bounded False Positive Rate (e.g. 1%)
    """
    def __init__(self, expected_elements: int = 1000000, false_positive_rate: float = 0.01):
        self.expected_elements = expected_elements
        self.false_positive_rate = false_positive_rate

        # Optimal bit array size: m = -(n * ln(p)) / (ln(2)^2)
        self.size = int(- (expected_elements * math.log(false_positive_rate)) / (math.log(2) ** 2))
        
        # Optimal number of hash functions: k = (m / n) * ln(2)
        self.hash_count = int((self.size / expected_elements) * math.log(2))
        
        self.bit_array = bytearray((self.size + 7) // 8)

    def _hashes(self, item: str):
        # Double hashing technique using SHA-256 and MD5
        h1 = int(hashlib.sha256(item.encode('utf-8')).hexdigest(), 16)
        h2 = int(hashlib.md5(item.encode('utf-8')).hexdigest(), 16)
        for i in range(self.hash_count):
            yield (h1 + i * h2) % self.size

    def add(self, item: str):
        for bit_index in self._hashes(item):
            byte_idx = bit_index // 8
            bit_offset = bit_index % 8
            self.bit_array[byte_idx] |= (1 << bit_offset)

    def contains(self, item: str) -> bool:
        for bit_index in self._hashes(item):
            byte_idx = bit_index // 8
            bit_offset = bit_index % 8
            if not (self.bit_array[byte_idx] & (1 << bit_offset)):
                return False
        return True
