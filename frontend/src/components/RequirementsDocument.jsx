import { useState } from "react";
import MermaidViewer from "./MermaidViewer";
import { formatAgentName } from "./agentNames";

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

  return (
    <button
      type="button"
      className={`brd-line requirements-document__finding ${selected ? "is-selected" : ""}`}
      title="Open source evidence"
      aria-label={`Open evidence for: ${finding.statement}`}
      aria-pressed={selected}
      onClick={() => onOpenEvidence(finding.id)}
    >
      <span className="requirements-document__finding-text">{finding.statement}</span>
      <span className="requirements-document__finding-meta">
        {finding.type && <span>{finding.type.replace(/_/g, " ")}</span>}
        {finding.priority && <span>{finding.priority} priority</span>}
        {finding.agent && <span>{formatAgentName(finding.agent)}</span>}
        {(source?.file_name || finding.source_id) && (
          <span className="requirements-document__source">
            Evidence · {source?.file_name || finding.source_id}
            {source?.page_or_ts && ` · ${source.page_or_ts}`}
          </span>
        )}
        {confidence && <span>Confidence · {confidence}</span>}
        {finding.review_status && <span>{finding.review_status}</span>}
      </span>
    </button>
  );
}

function ConflictReview({ conflict, onResolve }) {
  return (
    <div className={`conflict requirements-document__conflict ${conflict.status !== "open" ? "is-resolved" : ""}`} key={conflict.id}>
      <div className="requirements-document__conflict-heading">
        <span className={`requirements-document__conflict-status ${conflict.status === "open" ? "is-open" : ""}`}>
          {conflict.status === "open" ? "Needs review" : "Resolved"}
        </span>
        <strong>{conflict.topic}</strong>
      </div>
      <p>{conflict.disagreement}</p>
      <div className="split">
        <div>
          <em className="metadata-italic text-secondary">Source A</em>
          <blockquote className="citation font-citation italic text-sm my-2">“{conflict.left.statement}”</blockquote>
        </div>
        <div>
          <em className="metadata-italic text-secondary">Source B</em>
          <blockquote className="citation font-citation italic text-sm my-2">“{conflict.right.statement}”</blockquote>
        </div>
      </div>
      {conflict.suggested_question && <p className="muted">{conflict.suggested_question}</p>}
      {conflict.status === "open" && (
        <div className="row">
          <button type="button" className="btn" onClick={() => onResolve(conflict.id, "left")}>
            Keep Source A
          </button>
          <button type="button" className="btn primary" onClick={() => onResolve(conflict.id, "right")}>
            Keep Source B
          </button>
        </div>
      )}
      {conflict.resolution && <p className="requirements-document__resolution">{conflict.resolution}</p>}
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
                      <ConflictReview key={conflict.id} conflict={conflict} onResolve={onResolveConflict} />
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
