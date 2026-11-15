"""Persistent immutable JSON blobs and a small local manifest.

This store is not the dependency traversal engine. HydraDB owns lineage traversal;
the manifest resolves content and current source/tool heads after that traversal.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import ArtifactRecord, MissingEvidenceError, ProofFlowError


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


class ArtifactStore:
    def __init__(self, directory: str | Path):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.blobs = self.directory / "blobs"
        self.blobs.mkdir(exist_ok=True)
        self.db = sqlite3.connect(self.directory / "manifest.sqlite3", check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS records (
                id TEXT PRIMARY KEY, kind TEXT NOT NULL, logical_id TEXT NOT NULL,
                content_hash TEXT NOT NULL, created_at TEXT NOT NULL, metadata TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS records_kind ON records(kind);
            CREATE TABLE IF NOT EXISTS heads (
                logical_id TEXT PRIMARY KEY, record_id TEXT NOT NULL REFERENCES records(id)
            );
        """)
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('workspace',?)", (uuid.uuid4().hex,))
        self.workspace = self.db.execute("SELECT value FROM settings WHERE key='workspace'").fetchone()[0]

    def prepare(self, kind: str, logical_id: str, value: Any,
                metadata: dict[str, Any] | None = None, identity: Any = None) -> ArtifactRecord:
        content_hash = digest(value)
        identity_hash = digest({"logical_id": logical_id, "content_hash": content_hash, "identity": identity})
        node_id = f"{self.workspace}:{kind}:{identity_hash}"
        existing = self.get(node_id, required=False)
        if existing is not None:
            return existing
        return ArtifactRecord(node_id, kind, logical_id, content_hash,
                              datetime.now(timezone.utc).isoformat(), metadata or {})

    def commit(self, record: ArtifactRecord, value: Any, *, head: bool = False) -> None:
        """Persist only after graph writes succeed; publishing the head is atomic locally."""
        encoded = canonical_json(value).encode("utf-8")
        if hashlib.sha256(encoded).hexdigest() != record.content_hash:
            raise ProofFlowError("Record content does not match its immutable hash")
        destination = self.blobs / f"{record.content_hash}.json"
        if destination.exists():
            if destination.read_bytes() != encoded:
                raise MissingEvidenceError(f"Corrupt immutable blob {record.content_hash}")
        else:
            temporary = destination.with_suffix(f".{uuid.uuid4().hex}.tmp")
            with temporary.open("wb") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, destination)
        with self.db:
            self.db.execute(
                "INSERT OR IGNORE INTO records VALUES(?,?,?,?,?,?)",
                (record.id, record.kind, record.logical_id, record.content_hash,
                 record.created_at, canonical_json(record.metadata)),
            )
            existing = self.get(record.id)
            if existing != record:
                raise ProofFlowError("Immutable record metadata conflict")
            if head:
                self.db.execute(
                    "INSERT INTO heads VALUES(?,?) ON CONFLICT(logical_id) DO UPDATE SET record_id=excluded.record_id",
                    (record.logical_id, record.id),
                )

    @staticmethod
    def _record(row: sqlite3.Row) -> ArtifactRecord:
        return ArtifactRecord(row["id"], row["kind"], row["logical_id"], row["content_hash"],
                              row["created_at"], json.loads(row["metadata"]))

    def get(self, record_id: str, *, required: bool = True) -> ArtifactRecord | None:
        row = self.db.execute("SELECT * FROM records WHERE id=?", (record_id,)).fetchone()
        if row is None:
            if required:
                raise MissingEvidenceError(f"No local evidence for {record_id}")
            return None
        return self._record(row)

    def read(self, record_id: str) -> Any:
        record = self.get(record_id)
        path = self.blobs / f"{record.content_hash}.json"
        try:
            encoded = path.read_bytes()
        except FileNotFoundError as exc:
            raise MissingEvidenceError(f"Artifact content missing for {record_id}") from exc
        if hashlib.sha256(encoded).hexdigest() != record.content_hash:
            raise MissingEvidenceError(f"Artifact content hash mismatch for {record_id}")
        return json.loads(encoded)

    def get_head(self, logical_id: str) -> ArtifactRecord | None:
        row = self.db.execute(
            "SELECT r.* FROM records r JOIN heads h ON r.id=h.record_id WHERE h.logical_id=?", (logical_id,)
        ).fetchone()
        return self._record(row) if row is not None else None

    def heads(self, kind: str | None = None) -> list[ArtifactRecord]:
        query = "SELECT r.* FROM records r JOIN heads h ON r.id=h.record_id"
        rows = self.db.execute(query + (" WHERE r.kind=?" if kind else "") + " ORDER BY r.logical_id",
                               (kind,) if kind else ()).fetchall()
        return [self._record(row) for row in rows]

    def list_records(self, kind: str | None = None) -> list[ArtifactRecord]:
        query = "SELECT * FROM records"
        rows = self.db.execute(query + (" WHERE kind=?" if kind else "") + " ORDER BY created_at,id",
                               (kind,) if kind else ()).fetchall()
        return [self._record(row) for row in rows]

    def close(self) -> None:
        self.db.close()
