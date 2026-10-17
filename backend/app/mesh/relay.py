from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
from fastapi import WebSocket
from app.clock import get_now
from app.mesh.ledger import HashChainedLedger


class MeshRelayManager:
    """Manages WebSocket connections and protocol frames for Orbius Mesh local-first sync.
    Implements the HELLO, VEC, DELTA, ACK, CONFLICT, SEAL protocol state machine."""

    def __init__(self):
        # session_id -> list of active client WebSockets
        self.active_connections: Dict[str, List[WebSocket]] = {}
        # session_id -> peer_id -> state
        self.peer_states: Dict[str, Dict[str, Any]] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections.setdefault(session_id, []).append(websocket)

    def disconnect(self, websocket: WebSocket, session_id: str):
        if session_id in self.active_connections:
            self.active_connections[session_id] = [
                ws for ws in self.active_connections[session_id] if ws != websocket
            ]

    async def handle_frame(self, websocket: WebSocket, session_id: str, frame: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        frame_type = frame.get("type", "").upper()
        payload = frame.get("payload", {})
        peer_id = frame.get("peer_id", "anonymous_peer")

        head = HashChainedLedger.get_head(session_id)
        current_head_hash = head["entry_hash"] if head else "0" * 64

        # 1. HELLO Frame: Identify peer, exchange public keys & ledger head
        if frame_type == "HELLO":
            self.peer_states.setdefault(session_id, {})[peer_id] = {
                "public_key": payload.get("public_key"),
                "protocol_version": payload.get("protocol_version", "1.0"),
                "known_head": payload.get("ledger_head", "0" * 64),
                "connected_at": get_now().isoformat(),
            }
            # Respond with HELLO ACK & server ledger head
            return {
                "type": "HELLO_ACK",
                "session_id": session_id,
                "server_head_hash": current_head_hash,
                "protocol_version": "1.0-mesh",
                "mesh_nodes_online": len(self.active_connections.get(session_id, [])),
            }

        # 2. VEC Frame: Vector Clock / State comparison
        elif frame_type == "VEC":
            known_head = payload.get("head_hash")
            deltas = HashChainedLedger.get_delta_since(session_id, known_head)
            return {
                "type": "DELTA",
                "session_id": session_id,
                "head_hash": current_head_hash,
                "entries": deltas,
                "count": len(deltas),
                "byte_size": len(json.dumps(deltas)),
            }

        # 3. DELTA Frame: Ingest offline or peer updates into the local ledger
        elif frame_type == "DELTA":
            incoming_entries = payload.get("entries", [])
            saved = []
            for entry in incoming_entries:
                new_entry = HashChainedLedger.record_entry(
                    session_id=session_id,
                    entry_type=entry.get("entry_type", "crdt_delta"),
                    data=entry.get("data", {}),
                    source_chunk_text=entry.get("source_text", ""),
                    signer_id=peer_id,
                    signature=entry.get("signature"),
                )
                saved.append(new_entry["id"])

            # Broadcast update to other connected peers in session
            await self.broadcast(
                session_id,
                {
                    "type": "DELTA_BROADCAST",
                    "origin_peer": peer_id,
                    "new_head_hash": HashChainedLedger.get_head(session_id)["entry_hash"],
                    "count": len(saved),
                },
                exclude_ws=websocket,
            )

            return {
                "type": "ACK",
                "session_id": session_id,
                "saved_count": len(saved),
                "current_head": HashChainedLedger.get_head(session_id)["entry_hash"],
            }

        # 4. SEAL Frame: Submit cryptographic approval of BRD version
        elif frame_type == "SEAL":
            version_hash = payload.get("version_hash")
            signature = payload.get("signature")
            signer_id = payload.get("signer_id", peer_id)

            sealed_block = HashChainedLedger.record_entry(
                session_id=session_id,
                entry_type="requirement_sealed",
                data={
                    "version_hash": version_hash,
                    "summary": payload.get("summary", "Approved BRD release candidate"),
                    "version": payload.get("version", 1),
                },
                signer_id=signer_id,
                signature=signature,
            )

            # Broadcast SEAL to all peers
            await self.broadcast(
                session_id,
                {
                    "type": "SEAL_COMMITTED",
                    "session_id": session_id,
                    "block": sealed_block,
                    "signer_id": signer_id,
                },
            )

            return {
                "type": "ACK",
                "status": "sealed",
                "block_id": sealed_block["id"],
                "entry_hash": sealed_block["entry_hash"],
            }

        # 5. CONFLICT Frame: Broadcast real-time contradiction to all peers
        elif frame_type == "CONFLICT":
            await self.broadcast(session_id, frame, exclude_ws=websocket)
            return {"type": "ACK", "status": "conflict_broadcasted"}

        return {"type": "ACK", "status": "received"}

    async def broadcast(self, session_id: str, message: Dict[str, Any], exclude_ws: Optional[WebSocket] = None):
        conns = self.active_connections.get(session_id, [])
        dead = []
        for ws in conns:
            if ws != exclude_ws:
                try:
                    await ws.send_text(json.dumps(message))
                except Exception:
                    dead.append(ws)
        for d in dead:
            self.disconnect(d, session_id)


mesh_manager = MeshRelayManager()
