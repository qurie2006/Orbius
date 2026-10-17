from __future__ import annotations

import io
from typing import Any, Dict, List, Optional
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    HRFlowable,
    KeepTogether
)


def generate_brd_pdf(session: Dict[str, Any]) -> bytes:
    """Generate executive-grade Business Requirements Document (BRD) PDF."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "BRDTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=24,
        leading=28,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=8,
    )

    subtitle_style = ParagraphStyle(
        "BRDSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#475569"),
        spaceAfter=20,
    )

    section_heading = ParagraphStyle(
        "BRDSectionHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=18,
        textColor=colors.HexColor("#1e293b"),
        spaceBefore=14,
        spaceAfter=6,
    )

    body_style = ParagraphStyle(
        "BRDBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=14,
        textColor=colors.HexColor("#334155"),
        spaceAfter=8,
    )

    meta_style = ParagraphStyle(
        "BRDMeta",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#64748b"),
    )

    story = []

    # Title Banner
    story.append(Paragraph("ORBIUS SPECIFICATION SUITE", ParagraphStyle("Banner", fontName="Helvetica-Bold", fontSize=9, textColor=colors.HexColor("#2563eb"), spaceAfter=4)))
    story.append(Paragraph("Autonomous Business Requirements Document (BRD)", title_style))
    story.append(Paragraph("Synthesized multi-agent technical specifications, domain rules, test vectors, and architectural trace.", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#cbd5e1"), spaceAfter=15))

    # Document Metadata Block
    session_id = session.get("session_id", "demo")
    chunks = session.get("chunks", [])
    unique_files = list(set([c.get("file_name", "unknown") for c in chunks])) if chunks else ["Project Brief"]
    
    meta_data = [
        [
            Paragraph(f"<b>Session ID:</b> {session_id}", meta_style),
            Paragraph(f"<b>Status:</b> Verified Specification", meta_style),
        ],
        [
            Paragraph(f"<b>Source Documents:</b> {len(unique_files)} ingested", meta_style),
            Paragraph(f"<b>Sources:</b> {', '.join(unique_files[:3])}", meta_style),
        ],
    ]
    t_meta = Table(meta_data, colWidths=[260, 260])
    t_meta.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ("PADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
    ]))
    story.append(t_meta)
    story.append(Spacer(1, 15))

    # Functional Sections
    sections = session.get("sections", [])
    if sections:
        story.append(Paragraph("1. Technical & Functional Specifications", section_heading))
        for sec in sections:
            title = sec.get("title", "Specification Block")
            content = sec.get("content", "").replace("\r\n", "\n")
            conf = sec.get("confidence", 0.95)
            
            story.append(Paragraph(f"<b>{title}</b> (Confidence: {int(conf * 100)}%)", ParagraphStyle("SecTitle", fontName="Helvetica-Bold", fontSize=11, leading=14, textColor=colors.HexColor("#1e293b"), spaceBefore=6, spaceAfter=4)))
            
            # Format paragraphs cleanly
            for p in content.split("\n\n"):
                if p.strip():
                    clean_p = p.replace("**", "").replace("`", "").strip()
                    story.append(Paragraph(clean_p, body_style))
            story.append(Spacer(1, 6))

    # Action Items & Tasks
    tasks = session.get("tasks", [])
    if tasks:
        story.append(Spacer(1, 10))
        story.append(Paragraph("2. Action Items & Verification Tasks", section_heading))
        task_data = [
            [
                Paragraph("<b>Task ID</b>", meta_style),
                Paragraph("<b>Description</b>", meta_style),
                Paragraph("<b>Priority</b>", meta_style),
                Paragraph("<b>Status</b>", meta_style),
            ]
        ]
        for t in tasks[:15]:
            task_data.append([
                Paragraph(t.get("id", ""), meta_style),
                Paragraph(t.get("description", "") or t.get("title", ""), body_style),
                Paragraph(str(t.get("priority", "medium")), meta_style),
                Paragraph(str(t.get("status", "pending")), meta_style),
            ])
        t_tasks = Table(task_data, colWidths=[80, 280, 70, 90])
        t_tasks.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
            ("PADDING", (0, 0), (-1, -1), 5),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(t_tasks)

    # Conflicts & Resolution
    conflicts = session.get("conflicts", [])
    if conflicts:
        story.append(Spacer(1, 10))
        story.append(Paragraph("3. Cross-Document Conflicts & Architectural Inconsistencies", section_heading))
        conf_data = [
            [
                Paragraph("<b>Conflict ID</b>", meta_style),
                Paragraph("<b>Description</b>", meta_style),
                Paragraph("<b>Severity</b>", meta_style),
                Paragraph("<b>Status</b>", meta_style),
            ]
        ]
        for c in conflicts[:10]:
            conf_data.append([
                Paragraph(c.get("id", ""), meta_style),
                Paragraph(c.get("description", ""), body_style),
                Paragraph(str(c.get("severity", "medium")), meta_style),
                Paragraph(str(c.get("status", "open")), meta_style),
            ])
        t_conf = Table(conf_data, colWidths=[80, 280, 70, 90])
        t_conf.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#fee2e2")),
            ("PADDING", (0, 0), (-1, -1), 5),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#fecaca")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(t_conf)

    # Sign-off Block
    story.append(Spacer(1, 20))
    story.append(Paragraph("4. Stakeholder Approvals & Sign-off", section_heading))
    sign_data = [
        [
            Paragraph("<b>Lead Solutions Architect:</b> ____________________", meta_style),
            Paragraph("<b>Date:</b> ____________", meta_style),
        ],
        [
            Paragraph("<b>Product Operations Director:</b> ____________________", meta_style),
            Paragraph("<b>Date:</b> ____________", meta_style),
        ],
    ]
    t_sign = Table(sign_data, colWidths=[360, 160])
    t_sign.setStyle(TableStyle([
        ("PADDING", (0, 0), (-1, -1), 10),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
    ]))
    story.append(t_sign)

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
