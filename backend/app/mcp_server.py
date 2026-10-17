from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class MCPTool(BaseModel):
    name: str
    description: str
    inputSchema: Dict[str, Any]


class MCPJsonRpcRequest(BaseModel):
    jsonrpc: str = "2.0"
    method: str
    params: Optional[Dict[str, Any]] = None
    id: Optional[Any] = 1


class MCPJsonRpcResponse(BaseModel):
    jsonrpc: str = "2.0"
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None
    id: Optional[Any] = 1


AVAILABLE_MCP_TOOLS = [
    MCPTool(
        name="orbius_get_brd",
        description="Retrieve complete Business Requirements Document specifications, sections, and metadata for a session.",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "Session ID (e.g. 'demo')",
                    "default": "demo"
                }
            }
        }
    ),
    MCPTool(
        name="orbius_vector_search",
        description="Execute semantic vector search over all ingested documents, diagrams, PDFs, and voice notes.",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "default": "demo"},
                "query": {"type": "string", "description": "Search query or natural language question"},
                "top_k": {"type": "integer", "default": 5}
            },
            "required": ["query"]
        }
    ),
    MCPTool(
        name="orbius_get_action_items",
        description="Retrieve all cross-document conflicts, pending tasks, and deadline alerts.",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "default": "demo"}
            }
        }
    ),
    MCPTool(
        name="orbius_get_knowledge_graph",
        description="Extract the interactive knowledge graph of entities, components, requirements, and conflict relationships.",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "default": "demo"}
            }
        }
    ),
    MCPTool(
        name="orbius_run_pipeline",
        description="Trigger autonomous multi-agent analysis and specification generation for current workspace session.",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "default": "demo"},
                "description": {"type": "string", "default": ""}
            }
        }
    ),
]


async def execute_mcp_tool(name: str, arguments: Dict[str, Any], session_store: Any, run_pipeline_fn: Any) -> Any:
    """Execute an MCP tool call."""
    session_id = arguments.get("session_id", "demo")

    if name == "orbius_get_brd":
        sess = session_store.get(session_id)
        if not sess:
            return {"error": f"Session {session_id} not found", "sections": []}
        return {
            "session_id": session_id,
            "sections_count": len(sess.sections),
            "sections": [s.model_dump() for s in sess.sections],
            "quality_score": getattr(sess, "quality_score", None)
        }

    elif name == "orbius_vector_search":
        from app.vector_store import vector_store
        query = arguments.get("query", "")
        top_k = arguments.get("top_k", 5)
        results = vector_store.search(session_id, query, top_k=top_k)
        return {"query": query, "results": results}

    elif name == "orbius_get_action_items":
        sess = session_store.get(session_id)
        if not sess:
            return {"conflicts": [], "tasks": [], "alerts": []}
        return {
            "conflicts": [c.model_dump() for c in sess.conflicts],
            "tasks": [t.model_dump() for t in sess.tasks],
            "alerts": [a.model_dump() for a in sess.alerts],
        }

    elif name == "orbius_get_knowledge_graph":
        from app.graph_generator import generate_knowledge_graph
        sess = session_store.get(session_id)
        return generate_knowledge_graph(sess)

    elif name == "orbius_run_pipeline":
        desc = arguments.get("description", "")
        sess = await run_pipeline_fn(session_id, desc)
        return {
            "status": "completed",
            "session_id": session_id,
            "sections_count": len(sess.sections),
            "conflicts_count": len(sess.conflicts),
        }

    else:
        raise ValueError(f"Unknown MCP tool: {name}")


async def handle_mcp_rpc(request: MCPJsonRpcRequest, session_store: Any, run_pipeline_fn: Any) -> MCPJsonRpcResponse:
    """Handle standard MCP JSON-RPC protocol requests."""
    method = request.method
    params = request.params or {}

    try:
        if method == "tools/list":
            return MCPJsonRpcResponse(
                id=request.id,
                result={"tools": [t.model_dump() for t in AVAILABLE_MCP_TOOLS]}
            )

        elif method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            if not tool_name:
                return MCPJsonRpcResponse(
                    id=request.id,
                    error={"code": -32602, "message": "Missing tool name in tools/call"}
                )
            result = await execute_mcp_tool(tool_name, tool_args, session_store, run_pipeline_fn)
            return MCPJsonRpcResponse(
                id=request.id,
                result={"content": [{"type": "text", "text": str(result)}], "structured": result}
            )

        elif method == "resources/list":
            return MCPJsonRpcResponse(
                id=request.id,
                result={
                    "resources": [
                        {
                            "uri": "orbius://session/demo/brd",
                            "name": "Orbius Business Requirements Document",
                            "mimeType": "application/json"
                        },
                        {
                            "uri": "orbius://session/demo/graph",
                            "name": "Orbius Knowledge Graph",
                            "mimeType": "application/json"
                        }
                    ]
                }
            )

        elif method in ("initialize", "ping"):
            return MCPJsonRpcResponse(
                id=request.id,
                result={
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {"name": "Orbius-MCP-Server", "version": "1.0.0"},
                    "capabilities": {"tools": {}, "resources": {}}
                }
            )

        else:
            return MCPJsonRpcResponse(
                id=request.id,
                error={"code": -32601, "message": f"Method not found: {method}"}
            )
    except Exception as e:
        logger.exception("MCP RPC execution error")
        return MCPJsonRpcResponse(
            id=request.id,
            error={"code": -32000, "message": str(e)}
        )
