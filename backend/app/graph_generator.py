from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


def generate_knowledge_graph(session: Optional[Any]) -> Dict[str, Any]:
    """Extract interactive knowledge graph nodes and edges from current session state."""
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []
    node_ids = set()

    def add_node(nid: str, label: str, node_type: str, color: str, details: str = "", radius: int = 24):
        if nid not in node_ids:
            node_ids.add(nid)
            nodes.append({
                "id": nid,
                "label": label,
                "type": node_type,
                "color": color,
                "details": details,
                "radius": radius
            })

    def add_edge(source: str, target: str, label: str, edge_type: str = "relates_to"):
        if source in node_ids and target in node_ids:
            edges.append({
                "source": source,
                "target": target,
                "label": label,
                "type": edge_type
            })

    # Root System Node
    add_node("root_orbius", "Orbius Core System", "system", "#38bdf8", "Central multi-agent architecture and requirements context", 30)

    if not session:
        # Default starter graph if session is empty
        add_node("doc_brief", "Project Brief (PDF)", "document", "#a78bfa", "Initial business and architecture requirements", 22)
        add_node("spec_auth", "OAuth2 / JWT Security", "requirement", "#34d399", "Token-based secure API authentication", 20)
        add_node("spec_data", "Vector Database RAG", "component", "#fbbf24", "ChromaDB semantic indexing and chunk search", 20)
        add_node("spec_multi", "Multi-Region Cloud", "component", "#60a5fa", "High-availability geo-replicated deployment", 20)
        add_node("conf_lat", "Latency vs Strong Consistency", "conflict", "#f87171", "Replication delay exceeds 100ms threshold", 22)
        add_node("task_audit", "Security Audit Milestone", "task", "#f472b6", "Review end-to-end encryption keys", 18)

        add_edge("root_orbius", "doc_brief", "ingests", "ingest")
        add_edge("doc_brief", "spec_auth", "specifies", "specifies")
        add_edge("doc_brief", "spec_data", "specifies", "specifies")
        add_edge("doc_brief", "spec_multi", "specifies", "specifies")
        add_edge("spec_multi", "conf_lat", "triggers", "conflicts_with")
        add_edge("conf_lat", "task_audit", "requires", "resolves")

        return {
            "nodes": nodes,
            "edges": edges,
            "metrics": {
                "total_nodes": len(nodes),
                "total_edges": len(edges),
                "node_types": {"system": 1, "document": 1, "component": 2, "requirement": 1, "conflict": 1, "task": 1}
            }
        }

    # 1. Documents & Chunks
    chunks = getattr(session, "chunks", []) or []
    files_seen = {}
    for c in chunks:
        fname = getattr(c, "file_name", "Document")
        mod = getattr(c, "modality", "text")
        if fname not in files_seen:
            nid = f"doc_{len(files_seen)}"
            files_seen[fname] = nid
            color = "#a78bfa" if mod == "pdf" else ("#f472b6" if mod == "audio" else ("#38bdf8" if mod == "image" else "#94a3b8"))
            add_node(nid, fname, "document", color, f"Modality: {mod.upper()} | Ingested source artifact", 22)
            add_edge("root_orbius", nid, "ingests", "ingest")

    # 2. Specifications & Sections
    sections = getattr(session, "sections", []) or []
    for i, s in enumerate(sections):
        s_title = getattr(s, "title", f"Spec {i+1}")
        s_id = f"sec_{i}"
        add_node(s_id, s_title[:32], "specification", "#34d399", getattr(s, "content", "")[:200], 20)
        # Connect to parent document if citations exist
        connected = False
        citations = getattr(s, "citations", []) or []
        for cite in citations:
            c_file = getattr(cite, "file_name", None)
            if c_file and c_file in files_seen:
                add_edge(files_seen[c_file], s_id, "specifies", "specifies")
                connected = True
        if not connected:
            add_edge("root_orbius", s_id, "defines", "defines")

    # 3. Conflicts
    conflicts = getattr(session, "conflicts", []) or []
    for i, conf in enumerate(conflicts):
        c_id = f"conf_{i}"
        desc = getattr(conf, "description", f"Conflict {i+1}")
        sev = getattr(conf, "severity", "medium")
        color = "#ef4444" if sev == "high" else "#f87171"
        add_node(c_id, f"Conflict: {desc[:28]}...", "conflict", color, f"Severity: {sev.upper()}\n{desc}", 22)
        add_edge("root_orbius", c_id, "flags", "conflicts_with")

    # 4. Tasks & Actions
    tasks = getattr(session, "tasks", []) or []
    for i, t in enumerate(tasks):
        t_id = f"task_{i}"
        t_title = getattr(t, "title", f"Task {i+1}")
        prio = getattr(t, "priority", "medium")
        color = "#fbbf24" if prio == "high" else "#60a5fa"
        add_node(t_id, t_title[:28], "task", color, f"Priority: {prio.upper()} | Status: {getattr(t, 'status', 'pending')}", 18)
        # If task mentions conflict or spec, link it
        if conflicts:
            add_edge(f"conf_{i % len(conflicts)}", t_id, "resolves", "resolves")
        else:
            add_edge("root_orbius", t_id, "schedules", "schedules")

    return {
        "nodes": nodes,
        "edges": edges,
        "metrics": {
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "node_types": {
                "system": 1,
                "document": len(files_seen),
                "specification": len(sections),
                "conflict": len(conflicts),
                "task": len(tasks)
            }
        }
    }
