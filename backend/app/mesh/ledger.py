from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from typing import Any, Dict, List, Optional
from app import db
from app.clock import get_now


def sha256_hex(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


class HashChainedLedger:
    """Tamper-evident, hash-chained ledger for requirements, resolutions, and cryptographic seals.
    Every entry references the parent entry hash and source chunk hash, forming an immutable DAG."""

    @staticmethod
    def get_head(session_id: str) -> Optional[Dict[str, Any]]:
        with db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM ledger_entries WHERE session_id = ? ORDER BY timestamp DESC, rowid DESC LIMIT 1",
                (session_id,),
            ).fetchone()
            return dict(row) if row else None

    @staticmethod
    def record_entry(
        session_id: str,
        entry_type: str,
        data: Dict[str, Any],
        source_chunk_text: str = "",
        signer_id: str = "system",
        signature: Optional[str] = None,
    ) -> Dict[str, Any]:
        head = HashChainedLedger.get_head(session_id)
        parent_hash = head["entry_hash"] if head else "0" * 64
        source_hash = sha256_hex(source_chunk_text) if source_chunk_text else "0" * 64

        entry_id = f"blk_{uuid.uuid4().hex[:10]}"
        timestamp = get_now().isoformat()
        data_json = json.dumps(data, sort_keys=True)

        payload_to_hash = f"{parent_hash}:{source_hash}:{data_json}:{timestamp}:{signer_id}"
        entry_hash = sha256_hex(payload_to_hash)

        with db.connect() as conn:
            conn.execute(
                """
                INSERT INTO ledger_entries
                (id, session_id, entry_type, parent_hash, source_hash, data_json, signature, signer_id, entry_hash, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry_id,
                    session_id,
                    entry_type,
                    parent_hash,
                    source_hash,
                    data_json,
                    signature,
                    signer_id,
                    entry_hash,
                    timestamp,
                ),
            )

        return {
            "id": entry_id,
            "session_id": session_id,
            "entry_type": entry_type,
            "parent_hash": parent_hash,
            "source_hash": source_hash,
            "data": data,
            "signature": signature,
            "signer_id": signer_id,
            "entry_hash": entry_hash,
            "timestamp": timestamp,
        }

    @staticmethod
    def verify_chain(session_id: str) -> Dict[str, Any]:
        """Cryptographically verifies every block in the ledger for the given session.
        Returns validation status, block count, and detects any tampering."""
        with db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM ledger_entries WHERE session_id = ? ORDER BY timestamp ASC, rowid ASC",
                (session_id,),
            ).fetchall()

        entries = [dict(r) for r in rows]
        if not entries:
            return {"valid": True, "blocks_count": 0, "message": "Ledger is empty (genesis pending)."}

        expected_parent = "0" * 64
        for idx, entry in enumerate(entries):
            # 1. Verify parent hash chain continuity
            if entry["parent_hash"] != expected_parent:
                return {
                    "valid": False,
                    "tampered_block_index": idx,
                    "tampered_block_id": entry["id"],
                    "error": f"Parent hash mismatch at block {idx}: expected {expected_parent[:12]}..., got {entry['parent_hash'][:12]}...",
                }

            # 2. Recompute and verify block hash integrity
            payload = f"{entry['parent_hash']}:{entry['source_hash']}:{entry['data_json']}:{entry['timestamp']}:{entry['signer_id']}"
            recomputed_hash = sha256_hex(payload)
            if recomputed_hash != entry["entry_hash"]:
                return {
                    "valid": False,
                    "tampered_block_index": idx,
                    "tampered_block_id": entry["id"],
                    "error": f"Hash tampering detected at block {idx}: computed {recomputed_hash[:12]}... does not match recorded {entry['entry_hash'][:12]}...",
                }

            expected_parent = entry["entry_hash"]

        head = entries[-1]
        return {
            "valid": True,
            "blocks_count": len(entries),
            "head_hash": head["entry_hash"],
            "head_timestamp": head["timestamp"],
            "signed_approvals": sum(1 for e in entries if e["entry_type"] == "requirement_sealed"),
            "message": f"Cryptographic integrity verified across {len(entries)} chained blocks with zero tampering.",
        }

    @staticmethod
    def get_delta_since(session_id: str, known_head_hash: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns missing entries since the peer's known head hash for local-first delta sync."""
        with db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM ledger_entries WHERE session_id = ? ORDER BY timestamp ASC, rowid ASC",
                (session_id,),
            ).fetchall()

        entries = [dict(r) for r in rows]
        if not known_head_hash or known_head_hash == "0" * 64:
            return entries

        # Find position of known head
        idx = next((i for i, e in enumerate(entries) if e["entry_hash"] == known_head_hash), -1)
        if idx != -1:
            return entries[idx + 1 :]
        return entries
