"""hashing-char-ngram-v1 코사인 검색과 기록 인용 답변.

외부 임베딩 API를 쓰지 않는다. 유사도는 정답 확률이 아니다.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass

from maidops_tui.domain.models import DataOrigin, ErrorLabel, SearchKind, SimilarAdvice, SimilarHit

EMBEDDING_ID = "hashing-char-ngram-v1"
EMBEDDING_DIM = 256
SIMILARITY_NOTE = "유사도는 hashing-char-ngram-v1 코사인입니다. 정답 확률이 아닙니다."
EMPTY_ANSWER = "비슷한 확정 기록이 없습니다."
THRESHOLD = 0.35
_LIMIT = 5


@dataclass(frozen=True)
class IndexedRecord:
    kind: SearchKind
    origin: DataOrigin
    hit_id: str
    error_case_id: str
    label: str
    document: str
    excerpt: str
    cause: str | None
    method: str | None


def embed(text: str) -> list[float]:
    vector = [0.0] * EMBEDDING_DIM
    folded = " " + " ".join(text.casefold().split()) + " "
    for width in (3, 4, 5):
        if len(folded) < width:
            continue
        for start in range(len(folded) - width + 1):
            digest = hashlib.sha256(folded[start : start + width].encode("utf-8")).digest()
            bucket = int.from_bytes(digest[:4], "little") % EMBEDDING_DIM
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[bucket] += sign
    norm = math.sqrt(sum(value * value for value in vector))
    if norm > 0:
        vector = [value / norm for value in vector]
    return vector


def cosine(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))


def advise(query: str, records: list[IndexedRecord]) -> SimilarAdvice:
    query_vector = embed(query)
    hits: list[SimilarHit] = []
    for record in records:
        similarity = cosine(query_vector, embed(record.document))
        if similarity < THRESHOLD:
            continue
        hits.append(
            SimilarHit(
                kind=record.kind,
                origin=record.origin,
                hit_id=record.hit_id,
                error_case_id=record.error_case_id,
                label=record.label,
                similarity=round(similarity, 4),
                excerpt=_excerpt(record.excerpt),
                cause=record.cause,
                method=record.method,
            )
        )
    hits.sort(key=lambda hit: (-hit.similarity, hit.hit_id))
    chosen = tuple(hits[:_LIMIT])
    return SimilarAdvice(
        embedding_id=EMBEDDING_ID,
        similarity_note=SIMILARITY_NOTE,
        answer=_answer(chosen),
        hits=chosen,
    )


def _answer(hits: tuple[SimilarHit, ...]) -> str:
    if not hits:
        return EMPTY_ANSWER
    top = hits[0]
    cause = top.cause or "원인 기록이 없습니다"
    method = top.method or "해결 기록이 없습니다"
    label = top.label if isinstance(top.label, str) else top.label
    return (
        f"비슷한 확정 사례 {len(hits)}건. 가장 가까운 기록은 {top.hit_id} "
        f"[{top.origin.value}] 라벨 {label} / 원인 {cause} / 해결 {method}. {SIMILARITY_NOTE}"
    )


def _excerpt(text: str) -> str:
    compact = " ".join(text.split())
    if len(compact) <= 180:
        return compact
    return compact[:179] + "…"


def label_name(label: ErrorLabel | None) -> str:
    return "대기" if label is None else label.value
