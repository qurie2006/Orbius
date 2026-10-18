import { useState } from "react";
import MermaidViewer from "./MermaidViewer";
import { formatAgentName } from "./agentNames";
import { getCleanFileName, stripQuotes } from "./sourceUtils";

const WORKSPACE_TABS = [
  ["brd", "Requirements"],
  ["prototype", "Prototype"],
  ["tests", "Tests"],
  ["ripple", "Impact"],
  ["meeting", "Meeting"],
  ["trace", "Decision trace"],
];

function FindingRow({ finding, source, selected, onOpenEvidence }) {
  const confidence = typeof finding.confidence === "number" && Number.isFinite(finding.confidence)
    ? `${Math.round(finding.confidence * 100)}%`
    : null;
  const fileName = source?.file_name || getCleanFileName(finding.source_id);

  return (
    <button
      type="button"
      className={`w-full text-left py-2.5 px-3 rounded-lg hover:bg-white/[0.03] transition-colors flex flex-col gap-1 ${selected ? "bg-[#7DD3FC]/10" : ""}`}
      title="Open source evidence"
      aria-label={`Open evidence for: ${finding.statement}`}
      aria-pressed={selected}
      onClick={() => onOpenEvidence(finding.id)}
    >
      <span className="text-xs text-[#F4F5F7] font-medium leading-relaxed">{finding.statement}</span>
      <span className="flex flex-wrap items-center gap-2 text-[11px] font-mono text-[#929BA8]">
        {finding.type && <span>{finding.type.replace(/_/g, " ")}</span>}
        {finding.priority && <span>· {finding.priority} priority</span>}
        {finding.agent && <span>· {formatAgentName(finding.agent)}</span>}
        {fileName && (
          <span className="text-[#7DD3FC]">
            · Evidence: {fileName}
            {source?.page_or_ts && ` (${source.page_or_ts})`}
          </span>
        )}
        {confidence && <span className="text-[#6ED6A0]">· {confidence}</span>}
      </span>
    </button>
  );
}

function ConflictReview({ conflict, onResolve, chunks = [] }) {
  const leftFileName = getCleanFileName(conflict.left?.source_id || conflict.left?.statement, chunks);
  const rightFileName = getCleanFileName(conflict.right?.source_id || conflict.right?.statement, chunks);
  const isResolved = conflict.status !== "open";

  return (
    <div className="py-5 border-b border-[#292D34] space-y-3" key={conflict.id}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className={`w-1.5 h-1.5 rounded-full ${isResolved ? "bg-[#6ED6A0]" : "bg-amber-400 animate-pulse"}`} />
          <strong className="text-sm font-semibold text-[#F4F5F7]">{conflict.topic}</strong>
        </div>
        <span className={`font-mono text-[11px] ${isResolved ? "text-[#6ED6A0]" : "text-amber-300"}`}>
          {isResolved ? "Resolved" : "Requires Decision"}
        </span>
      </div>
      <p className="text-xs text-[#929BA8] leading-relaxed">{conflict.disagreement}</p>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-1">
        <div className="p-3.5 rounded-xl bg-[#15181E] border border-[#292D34] space-y-2">
          <div className="text-[11px] font-mono text-[#7DD3FC] flex items-center gap-1 font-semibold">
            <span className="material-symbols-outlined text-[13px]">description</span>
            <span>Source: <strong className="text-[#F4F5F7]">{leftFileName}</strong></span>
          </div>
          <div className="pl-3 py-1 border-l-2 border-[#7DD3FC]/50 text-xs italic text-[#929BA8] leading-relaxed">
            "{stripQuotes(conflict.left.statement)}"
          </div>
          {conflict.status === "open" && (
            <button
              type="button"
              className="mt-2 px-3 py-1.5 rounded-md bg-[#7DD3FC] text-black font-semibold text-xs hover:bg-[#7DD3FC]/90 transition-colors"
              onClick={() => onResolve(conflict.id, "left")}
            >
              Adopt Option A ({leftFileName})
            </button>
          )}
        </div>
        <div className="p-3.5 rounded-xl bg-[#15181E] border border-[#292D34] space-y-2">
          <div className="text-[11px] font-mono text-[#7DD3FC] flex items-center gap-1 font-semibold">
            <span className="material-symbols-outlined text-[13px]">description</span>
            <span>Source: <strong className="text-[#F4F5F7]">{rightFileName}</strong></span>
          </div>
          <div className="pl-3 py-1 border-l-2 border-[#7DD3FC]/50 text-xs italic text-[#929BA8] leading-relaxed">
            "{stripQuotes(conflict.right.statement)}"
          </div>
          {conflict.status === "open" && (
            <button
              type="button"
              className="mt-2 px-3 py-1.5 rounded-md bg-[#181B22] text-[#F4F5F7] border border-[#292D34] hover:bg-[#292D34] font-semibold text-xs transition-colors"
              onClick={() => onResolve(conflict.id, "right")}
            >
              Adopt Option B ({rightFileName})
            </button>
          )}
        </div>
      </div>
      {conflict.suggested_question && (
        <p className="text-xs text-[#929BA8] italic pl-3 border-l-2 border-[#292D34] my-2">{conflict.suggested_question}</p>
      )}
      {conflict.resolution && (
        <p className="text-xs text-[#6ED6A0] font-mono">Decision: {conflict.resolution}</p>
      )}
    </div>
  );
}

export default function RequirementsDocument({
  activeTab,
  onTabChange,
  sections,
  state,
  running,
  theme,
  views,
  onOpenEvidence,
  onResolveConflict,
  selectedFindingId,
}) {
  const [isArchitectureOpen, setIsArchitectureOpen] = useState(false);
  const findings = state?.findings || [];
  const chunks = state?.chunks || [];
  const conflicts = state?.conflicts || [];
  const reviewQuestions = (state?.questions || []).filter(
    (question) => !conflicts.some(
      (conflict) => conflict.status !== "open" && conflict.suggested_question === question,
    ),
  );
  const documentSections = sections.length ? sections : state?.sections || [];
  const sourceCount = new Set(
    chunks.map((chunk) => chunk.source_id || chunk.file_name).filter(Boolean),
  ).size;

  return (
    <section className="panel panel-brd requirements-document">
      <nav className="studio-nav-bar" aria-label="Workspace views">
        {WORKSPACE_TABS.map(([tab, label]) => (
          <button
            type="button"
            className={`studio-nav-btn ${activeTab === tab ? "active" : ""}`}
            aria-current={activeTab === tab ? "page" : undefined}
            key={tab}
            onClick={() => onTabChange(tab)}
          >
            {label}
          </button>
        ))}
      </nav>

      <div className="requirements-document__view" key={activeTab}>
      {activeTab !== "brd" ? views[activeTab] : (
        <div className="requirements-document__body">
          <header className="requirements-document__header">
            <div>
              <span className="requirements-document__eyebrow">DOCUMENT / BUSINESS REQUIREMENTS</span>
              <h2>Business requirements</h2>
            </div>
            <div className="requirements-document__header-meta">
              {state?.version != null && <span>Version {state.version}</span>}
              <span className={`requirements-document__state ${running ? "is-running" : ""}`} role="status">
                <span aria-hidden="true" />
                {running ? "Generating" : state ? "Saved session" : "Draft workspace"}
              </span>
            </div>
          </header>

          {state && (
            <div className="requirements-document__summary" aria-label="Generated document counts">
              <span><strong>{findings.length}</strong> findings</span>
              <span><strong>{sourceCount}</strong> linked sources</span>
              {conflicts.length > 0 && (
                <span><strong>{conflicts.filter((conflict) => conflict.status === "open").length}</strong> open conflicts</span>
              )}
            </div>
          )}

          {running && (
            <div className="requirements-document__live">
              <span aria-hidden="true" />
              New sections are arriving from the active generation stream.
            </div>
          )}

          {!running && documentSections.length === 0 && (
            <div className="requirements-document__empty">
              <span className="requirements-document__empty-index">READY</span>
              <h3>Start with the source material</h3>
              <p>Add project files or context in the Source Vault. Orbius will turn the available evidence into a structured requirements document.</p>
            </div>
          )}

          <div className="requirements-document__sections">
            {documentSections.map((section, index) => {
              const sectionFindings = findings.filter((finding) => section.finding_ids?.includes(finding.id));
              return (
                <article className="requirements-document__section" key={section.id}>
                  <header>
                    <span className="requirements-document__section-index">{String(index + 1).padStart(2, "0")}</span>
                    <h3>{section.title}</h3>
                  </header>
                  {section.id === "diagrams" ? (
                    <div style={{ marginTop: 6 }}>
                      <button
                        type="button"
                        className="btn ghost"
                        style={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                          width: "100%",
                          padding: "10px 14px",
                          background: "var(--elev-2)",
                          border: "1px solid var(--line)",
                          borderRadius: 8,
                          cursor: "pointer",
                          textAlign: "left",
                        }}
                        onClick={() => setIsArchitectureOpen((prev) => !prev)}
                        aria-expanded={isArchitectureOpen}
                      >
                        <span style={{ fontWeight: 600, display: "flex", alignItems: "center", gap: 8 }}>
                          <span>🏗️</span> Architecture & Sequence Diagram
                        </span>
                        <span style={{ fontSize: "0.82rem", color: "var(--muted)" }}>
                          {isArchitectureOpen ? "Hide Diagram ▲" : "Click to view architecture ▼"}
                        </span>
                      </button>
                      {isArchitectureOpen && (
                        <div style={{ marginTop: 12 }}>
                          <MermaidViewer section={section} findings={findings} theme={theme} />
                        </div>
                      )}
                    </div>
                  ) : section.id === "open_conflicts" ? (
                    conflicts.length > 0 ? conflicts.map((conflict) => (
                      <ConflictReview key={conflict.id} conflict={conflict} onResolve={onResolveConflict} chunks={chunks} />
                    )) : <div className="section-body">{section.body}</div>
                  ) : sectionFindings.length > 0 ? (
                    <div className="requirements-document__findings">
                      {sectionFindings.map((finding) => (
                        <FindingRow
                          key={finding.id}
                          finding={finding}
                          source={chunks.find((chunk) => chunk.source_id === finding.source_id) ||
                            chunks.find((chunk) => chunk.file_name === finding.file_name)}
                          selected={selectedFindingId === finding.id}
                          onOpenEvidence={onOpenEvidence}
                        />
                      ))}
                    </div>
                  ) : (
                    <div className="section-body">{section.body}</div>
                  )}
                </article>
              );
            })}
          </div>

          {reviewQuestions.length > 0 && (
            <section className="requirements-document__questions" aria-labelledby="requirements-questions-title">
              <span className="requirements-document__eyebrow">HUMAN REVIEW</span>
              <h3 id="requirements-questions-title">Questions for the project team</h3>
              {reviewQuestions.map((question, index) => <p key={`${index}-${question}`}>{question}</p>)}
            </section>
          )}
        </div>
      )}
      </div>
    </section>
  );
}
