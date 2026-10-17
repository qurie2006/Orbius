import { useEffect, useMemo, useRef, useState } from "react";
import mermaid from "mermaid";

export default function MermaidViewer({ section, findings, theme }) {
  const [activeTab, setActiveTab] = useState("architecture");
  const [svgContent, setSvgContent] = useState("");
  const [isFullscreen, setIsFullscreen] = useState(false);
  const containerRef = useRef(null);

  const diagrams = useMemo(() => {
    const palette = theme === "dark"
      ? { surface: "#292620", surfaceAlt: "#211f1b", accent: "#d99766", muted: "#9c9080", text: "#f0e9dd", good: "#35412d" }
      : { surface: "#fbf8f2", surfaceAlt: "#f0e8dc", accent: "#9e5c35", muted: "#a9937c", text: "#2e2922", good: "#e3e8d9" };

    function cleanLabel(value, words = 6) {
      const clean = (value || "").replace(/["'`<>[\]{}()|#;:]/g, " ").replace(/\s+/g, " ").trim();
      const parts = clean.split(" ");
      return parts.slice(0, words).join(" ") + (parts.length > words ? "..." : "");
    }

    const people = (findings || [])
      .filter((finding) => finding.type === "stakeholder" || finding.section === "stakeholders")
      .map((finding) => cleanLabel(finding.statement, 4));
    const items = (findings || [])
      .filter((finding) => finding.type !== "stakeholder" && finding.section !== "stakeholders")
      .slice(0, 6);

    const defaultArch = section.mermaid_code || `graph TD
    classDef primary fill:${palette.surface},stroke:${palette.accent},stroke-width:2px,color:${palette.text};
    classDef person fill:${palette.surfaceAlt},stroke:${palette.muted},stroke-width:1px,color:${palette.text};
    classDef item fill:${palette.surface},stroke:${palette.muted},stroke-width:1px,color:${palette.text};

    P0["Project Scope"]:::primary
    ${people.map((person, index) => `S${index}["${person}"]:::person --> P0`).join("\n    ")}
    ${items.map((item, index) => `P0 --> R${index}["${cleanLabel(item.statement, 5)}"]:::item`).join("\n    ")}`;

    const defaultUserFlow = section.user_flow_code || `flowchart LR
    classDef step fill:${palette.surface},stroke:${palette.accent},stroke-width:2px,color:${palette.text};
    classDef finish fill:${palette.good},stroke:${palette.muted},stroke-width:1px,color:${palette.text};

    Start([Start])
    ${items.length > 0 ? items.map((item, index) => `${index === 0 ? "Start" : `F${index - 1}`} --> F${index}["${cleanLabel(item.statement, 5)}"]:::step`).join("\n    ") : "Start --> Process[Process Requirements]:::step"}
    ${items.length > 0 ? `F${items.length - 1} --> Done([Complete]):::finish` : "Process --> Done([Complete]):::finish"}`;

    const requester = people[0] || "Stakeholder";
    const defaultSeq = section.sequence_code || `sequenceDiagram
    autonumber
    actor User as ${requester}
    participant System as System Gateway
    participant Team as Execution Team

    User->>System: Submit Requirements & Directives
    ${items.slice(0, 3).map((item) => `System->>Team: Enforce: ${cleanLabel(item.statement, 6)}`).join("\n    ")}
    Team-->>User: Verification Complete & Artifacts Generated`;

    return {
      architecture: section.mermaid_code || defaultArch,
      user_flow: section.user_flow_code || defaultUserFlow,
      sequence: section.sequence_code || defaultSeq,
    };
  }, [section, findings, theme]);

  useEffect(() => {
    let isMounted = true;
    async function renderMermaid() {
      const code = diagrams[activeTab] || diagrams.architecture;
      const id = `mermaid-${Date.now()}-${Math.floor(Math.random() * 1000)}`;
      try {
        if (typeof document !== "undefined") {
          document.querySelectorAll("[id^='dmermaid'], [id^='d-']").forEach((el) => el.remove());
        }
        const { svg } = await mermaid.render(id, code);
        if (isMounted) setSvgContent(svg);
      } catch (error) {
        console.warn("Mermaid render error:", error);
        if (typeof document !== "undefined") {
          document.querySelectorAll("[id^='dmermaid'], [id^='d-']").forEach((el) => el.remove());
        }
        if (isMounted) {
          setSvgContent(`<div style="padding: 14px; color: var(--muted); font-size: 0.85rem;">Rendering diagram...</div>`);
        }
      }
    }
    renderMermaid();
    return () => { isMounted = false; };
  }, [activeTab, diagrams]);

  return (
    <div className={`mermaid-card ${isFullscreen ? "fullscreen" : ""}`}>
      <div className="mermaid-header">
        <div className="diagram-tabs" role="tablist" aria-label="Diagram type">
          {[
            ["architecture", "Architecture"],
            ["user_flow", "User flow"],
            ["sequence", "Sequence"],
          ].map(([tab, label]) => (
            <button
              type="button"
              role="tab"
              aria-selected={activeTab === tab}
              className={`tab-btn ${activeTab === tab ? "active" : ""}`}
              key={tab}
              onClick={() => setActiveTab(tab)}
            >
              {label}
            </button>
          ))}
        </div>
        <div className="mermaid-controls">
          <button
            type="button"
            className="btn ghost"
            onClick={() => {
              navigator.clipboard.writeText(diagrams[activeTab]);
              alert("Copied Mermaid code to clipboard!");
            }}
          >
            Copy code
          </button>
          <button type="button" className="btn ghost" onClick={() => setIsFullscreen(!isFullscreen)}>
            {isFullscreen ? "Exit full screen" : "Expand"}
          </button>
        </div>
      </div>
      <div className="mermaid-viewport" ref={containerRef} dangerouslySetInnerHTML={{ __html: svgContent }} />
    </div>
  );
}
