"""Matched-information retrieval policies and evidence readers.

All policies use the exact same EvidenceRecord.render() serialization. The
deterministic reader can follow only edges present in returned records. This
keeps retrieved candidates separate from an assertion that they are affected.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from collections import defaultdict, deque
import hashlib
import importlib.metadata
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping, Sequence


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


@dataclass(frozen=True)
class EvidenceRecord:
    id: str
    title: str
    logical_id: str
    tool: str
    inputs: tuple[str, ...]
    description: str = ""
    tool_version_id: str = ""
    parameters: Mapping[str, Any] = field(default_factory=dict)
    input_labels: Mapping[str, str] = field(default_factory=dict)
    current_direct_versions: Mapping[str, str] = field(default_factory=dict)
    result: Any = None

    @property
    def dependencies(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys((*self.inputs, *([self.tool_version_id] if self.tool_version_id else []))))

    def render(self) -> str:
        """Compact, complete direct provenance; identical in every condition."""
        return canonical(asdict(self))


@dataclass(frozen=True)
class RetrievalQuery:
    text: str
    changed_ids: tuple[str, ...]

    def render(self) -> str:
        return self.text + "\nChanged version identifiers: " + " ".join(self.changed_ids)


@dataclass
class PackedContext:
    records: list[EvidenceRecord]
    tokens: int
    skipped_ids: list[str]
    retrieval_calls: int = 1


class TokenCounter:
    def __init__(self, encoding: str = "cl100k_base") -> None:
        import tiktoken
        self.encoding_name = encoding
        self.encoding = tiktoken.get_encoding(encoding)

    def __call__(self, text: str) -> int:
        return len(self.encoding.encode(text))


def render_context(records: Iterable[EvidenceRecord]) -> str:
    return "\n".join(record.render() for record in records)


def pack_records(
    records: Sequence[EvidenceRecord], budget: int | None, counter: TokenCounter
) -> PackedContext:
    """Greedy rank packing, continuing after an oversized record.

    Count the final concatenated serialization, including record separators.
    The graph receives the same record packing as every other policy.
    """
    chosen: list[EvidenceRecord] = []
    skipped: list[str] = []
    seen: set[str] = set()
    tokens = 0
    for record in records:
        if record.id in seen:
            continue
        seen.add(record.id)
        next_tokens = counter(render_context([*chosen, record]))
        if budget is not None and next_tokens > budget:
            skipped.append(record.id)
            continue
        chosen.append(record)
        tokens = next_tokens
    return PackedContext(chosen, tokens, skipped)


def lexical_tokens(text: str) -> list[str]:
    """Keep complete IDs/paths as well as readable constituent words."""
    lowered = text.lower()
    words = re.findall(r"[a-z0-9]+", lowered)
    identifiers = re.findall(r"[a-z0-9]+(?:[_.:/-][a-z0-9]+)+", lowered)
    return words + identifiers


def _ordered(scores: Sequence[float], records: Sequence[EvidenceRecord]) -> list[str]:
    return [records[i].id for i in sorted(range(len(records)), key=lambda i: (-float(scores[i]), records[i].id))]


class BM25Index:
    def __init__(self, records: Sequence[EvidenceRecord], *, k1: float = 1.5, b: float = 0.75) -> None:
        from rank_bm25 import BM25Okapi
        self.records = list(records)
        self.index = BM25Okapi([lexical_tokens(r.render()) for r in records], k1=k1, b=b)
        self.parameters = {"k1": k1, "b": b}

    def rank(self, query: str) -> list[str]:
        return _ordered(self.index.get_scores(lexical_tokens(query)), self.records)


class DenseEncoder:
    """Real ONNX sentence embeddings, with no substitute on failure."""
    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5", cache_dir: str | Path = ".cache/fastembed") -> None:
        from fastembed import TextEmbedding
        from tokenizers import Tokenizer
        self.model_name = model_name
        self.cache_dir = Path(cache_dir)
        self.model = TextEmbedding(model_name=model_name, cache_dir=str(cache_dir), threads=4, providers=["CPUExecutionProvider"])
        self.memo: dict[tuple[str, str], Any] = {}
        tokenizer = self.model.model.tokenizer
        if tokenizer is None:
            raise RuntimeError("Embedding tokenizer is unavailable; cannot verify truncation safety")
        self.tokenizer = Tokenizer.from_str(tokenizer.to_str())
        self.tokenizer.no_truncation()
        self.tokenizer.no_padding()
        self.model_dir = Path(self.model.model._model_dir)
        self.file_hashes = {}
        for path in sorted(self.model_dir.rglob("*")):
            if path.is_file() and (path.suffix == ".onnx" or path.name in {"config.json", "tokenizer.json", "tokenizer_config.json"}):
                sha = hashlib.sha256()
                with path.open("rb") as stream:
                    for block in iter(lambda: stream.read(1024 * 1024), b""):
                        sha.update(block)
                self.file_hashes[str(path.relative_to(self.model_dir))] = sha.hexdigest()

    def chunk(self, text: str, *, size: int = 384, overlap: int = 64) -> tuple[list[str], int]:
        """Character-preserving chunks from the actual model tokenizer.

        Max pooling over overlapping chunks gives dense retrieval access to
        every field, including dependency IDs near the end of long receipts.
        """
        encoded = self.tokenizer.encode(text, add_special_tokens=False)
        count = len(encoded.ids)
        if count <= size:
            return [text], count
        chunks = []
        for start in range(0, count, size - overlap):
            end = min(count, start + size)
            chunks.append(text[encoded.offsets[start][0]:encoded.offsets[end - 1][1]])
            if end == count:
                break
        return chunks, count

    def passages(self, texts: Sequence[str]):
        import numpy as np
        missing = [text for text in dict.fromkeys(texts) if ("passage", text) not in self.memo]
        if missing:
            method = getattr(self.model, "passage_embed", self.model.embed)
            for text, vector in zip(missing, method(missing)):
                self.memo[("passage", text)] = np.asarray(vector, dtype=np.float32)
        return np.asarray([self.memo[("passage", text)] for text in texts], dtype=np.float32)

    def query(self, text: str):
        import numpy as np
        key = ("query", text)
        if key not in self.memo:
            generated = self.model.query_embed(text) if hasattr(self.model, "query_embed") else self.model.embed([text])
            self.memo[key] = np.asarray(next(iter(generated)), dtype=np.float32)
        return self.memo[key]

    def metadata(self) -> dict[str, Any]:
        return {
            "model": self.model_name,
            "implementation": "fastembed.TextEmbedding (ONNX, CPU)",
            "fastembed_version": importlib.metadata.version("fastembed"),
            "numpy_version": importlib.metadata.version("numpy"),
            "cache_dir": str(self.cache_dir),
            "model_directory": str(self.model_dir),
            "model_file_sha256": self.file_hashes,
            "chunking": {"model_tokens": 384, "overlap": 64, "document_score": "max cosine over chunks", "truncation": "none"},
        }


class DenseIndex:
    def __init__(self, records: Sequence[EvidenceRecord], encoder: DenseEncoder) -> None:
        import numpy as np
        self.records = list(records)
        self.encoder = encoder
        chunks = []
        self.owners = []
        lengths = []
        for index, record in enumerate(records):
            parts, length = encoder.chunk(record.render())
            lengths.append(length)
            chunks.extend(parts)
            self.owners.extend([index] * len(parts))
        self.document_model_token_lengths = lengths
        self.chunk_count = len(chunks)
        self.matrix = encoder.passages(chunks)
        self.matrix /= np.maximum(np.linalg.norm(self.matrix, axis=1, keepdims=True), 1e-12)

    def rank(self, query: str) -> list[str]:
        import numpy as np
        parts, _ = self.encoder.chunk(query)
        queries = np.asarray([self.encoder.query(part) for part in parts])
        queries /= np.maximum(np.linalg.norm(queries, axis=1, keepdims=True), 1e-12)
        chunk_scores = (self.matrix @ queries.T).max(axis=1)
        scores = [-float("inf")] * len(self.records)
        for owner, score in zip(self.owners, chunk_scores):
            scores[owner] = max(scores[owner], float(score))
        return _ordered(scores, self.records)


def reciprocal_rank_fusion(rankings: Sequence[Sequence[str]], *, constant: int = 60) -> list[str]:
    scores: dict[str, float] = {}
    for ranking in rankings:
        for i, record_id in enumerate(ranking, 1):
            scores[record_id] = scores.get(record_id, 0.0) + 1.0 / (constant + i)
    return sorted(scores, key=lambda rid: (-scores[rid], rid))


def direct_ids(records: Sequence[EvidenceRecord], changed_ids: Iterable[str]) -> list[str]:
    changed = set(changed_ids)
    return sorted(record.id for record in records if changed.intersection(record.dependencies))


def exact_seed(ranking: Sequence[str], records: Sequence[EvidenceRecord], changed_ids: Iterable[str]) -> list[str]:
    """Free ranking rule, not free context: seeded records still consume tokens."""
    direct = direct_ids(records, changed_ids)
    return list(dict.fromkeys([*direct, *ranking]))


def read_affected(records: Sequence[EvidenceRecord], changed_ids: Iterable[str]) -> dict[str, int]:
    """Reachability reader restricted to the context records actually returned.

    Missing intermediate receipts cannot be recovered by consulting an index.
    Each result includes the shortest witnessed dependency depth.
    """
    children: dict[str, list[str]] = defaultdict(list)
    for record in records:
        for dependency in record.dependencies:
            children[dependency].append(record.id)
    depths = {root: 0 for root in changed_ids}
    queue = deque(depths)
    affected: dict[str, int] = {}
    while queue:
        parent = queue.popleft()
        for child in children[parent]:
            depth = depths[parent] + 1
            if child not in depths or depth < depths[child]:
                depths[child] = depth
                affected[child] = depth
                queue.append(child)
    return affected


def rank_exact_closure(records: Sequence[EvidenceRecord], changed_ids: Iterable[str]) -> list[str]:
    depths = read_affected(records, changed_ids)
    return sorted(depths, key=lambda rid: (depths[rid], rid))


def iterative_hybrid(
    records: Sequence[EvidenceRecord], query: RetrievalQuery, bm25: BM25Index,
    dense: DenseIndex, budget: int | None, counter: TokenCounter,
    *, rounds: int | None = None, round_width: int = 3, constant: int = 60,
) -> PackedContext:
    """Iterative search with exact-ID seeding, sharing the same final budget.

    New output IDs enter the next query only after the returned evidence
    reader witnesses their connection to the change. Intermediate search
    rankings are index work; every returned record is counted in context.
    """
    by_id = {record.id: record for record in records}
    selected: list[EvidenceRecord] = []
    selected_ids: set[str] = set()
    skipped: set[str] = set()
    calls = 0
    for _ in range(len(records) if rounds is None else rounds):
        known = read_affected(selected, query.changed_ids)
        frontier = tuple(dict.fromkeys([*query.changed_ids, *known]))
        text = query.render() + "\nObserved connected output identifiers: " + " ".join(known)
        ranking = reciprocal_rank_fusion([bm25.rank(text), dense.rank(text)], constant=constant)
        ranking = exact_seed(ranking, records, frontier)
        calls += 2
        added = 0
        for record_id in ranking:
            if record_id in selected_ids:
                continue
            record = by_id[record_id]
            trial = pack_records([*selected, record], budget, counter)
            if record_id not in {r.id for r in trial.records}:
                skipped.add(record_id)
                continue
            selected = trial.records
            selected_ids.add(record_id)
            added += 1
            if added >= round_width:
                break
        if not added:
            break
    return PackedContext(selected, counter(render_context(selected)), sorted(skipped), calls)


def corpus_digest(records: Sequence[EvidenceRecord]) -> str:
    return hashlib.sha256(render_context(sorted(records, key=lambda record: record.id)).encode()).hexdigest()


def score_sets(expected: Iterable[str], predicted: Iterable[str]) -> dict[str, Any]:
    gold, pred = set(expected), set(predicted)
    tp, fp, fn = len(gold & pred), len(pred - gold), len(gold - pred)
    precision = tp / len(pred) if pred else (1.0 if not gold else 0.0)
    recall = tp / len(gold) if gold else (1.0 if not pred else 0.0)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall,
            "f1": f1, "exact_match": pred == gold,
            "missing_ids": sorted(gold - pred), "extra_ids": sorted(pred - gold)}
