"""다운로드 없는 고정 문자 n-gram 해시 임베딩.

파라미터를 학습하지 않는다. 식별자는 hashing-char-ngram-v1이다.
"""

from __future__ import annotations

import hashlib

import torch

EMBEDDING_ID = "hashing-char-ngram-v1"
EMBEDDING_DIM = 256
_NGRAMS = (3, 4, 5)


class HashingCharNgramEmbedder:
    def __init__(self, dimension: int = EMBEDDING_DIM) -> None:
        if dimension != EMBEDDING_DIM:
            raise ValueError("임베딩 차원은 256으로 고정되어 있습니다.")
        self.dimension = dimension

    def embed(self, text: str) -> torch.Tensor:
        vector = torch.zeros(self.dimension, dtype=torch.float32)
        folded = " " + " ".join(text.casefold().split()) + " "
        for width in _NGRAMS:
            if len(folded) < width:
                continue
            for start in range(len(folded) - width + 1):
                digest = hashlib.sha256(folded[start : start + width].encode("utf-8")).digest()
                bucket = int.from_bytes(digest[:4], "little") % self.dimension
                sign = 1.0 if digest[4] % 2 == 0 else -1.0
                vector[bucket] += sign
        norm = torch.linalg.vector_norm(vector)
        if float(norm) > 0:
            vector = vector / norm
        return vector

    def embed_batch(self, texts: list[str]) -> torch.Tensor:
        if not texts:
            return torch.zeros((0, self.dimension), dtype=torch.float32)
        return torch.stack([self.embed(text) for text in texts])
