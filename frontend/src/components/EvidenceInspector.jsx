import { useEffect, useRef } from "react";
import { formatAgentName } from "./agentNames";

export default function EvidenceInspector({ evidence, onClose }) {
  const closeButtonRef = useRef(null);
  const onCloseRef = useRef(onClose);
  const isOpen = Boolean(evidence);

  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    if (!isOpen) return undefined;
    const previouslyFocused = document.activeElement;
    closeButtonRef.current?.focus();
    const handleKeyDown = (event) => {
      if (event.key === "Escape") onCloseRef.current();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      previouslyFocused?.focus?.();
    };
  }, [isOpen]);

  if (!evidence) return null;

  const finding = evidence.finding;
  const chunk = evidence.chunk;
  const location = [
    chunk?.file_name || chunk?.source_id,
    chunk?.page_or_ts,
  ].filter(Boolean).join(" · ");
  const excerpt = finding?.source_span || chunk?.text;

  return (
    <aside className="drawer evidence-drawer" aria-label="Evidence and source excerpt" aria-live="polite">
      <div className="evidence-drawer__header">
        <div>
          <span className="requirements-document__eyebrow">{evidence.citation ? "COPILOT REFERENCE" : "SOURCE TRACE"}</span>
          <h2 tabIndex={-1}>Evidence inspector</h2>
        </div>
        <button
          ref={closeButtonRef}
          type="button"
          className="btn ghost"
          onClick={onClose}
          aria-label="Close evidence inspector"
        >
          Close
        </button>
      </div>
      {finding?.statement && (
        <section className="evidence-drawer__relationship" aria-label="Requirement linked to source">
          <span className="evidence-drawer__section-label">GENERATED CLAIM</span>
          <p className="evidence-drawer__claim">{finding.statement}</p>
        </section>
      )}
      {finding?.agent && <p className="muted">{formatAgentName(finding.agent)}</p>}
      {typeof finding?.confidence === "number" && Number.isFinite(finding.confidence) && (
        <p className="muted">Confidence · {Math.round(finding.confidence * 100)}%</p>
      )}
      {!finding && typeof evidence.confidence === "number" && Number.isFinite(evidence.confidence) && (
        <p className="muted">Copilot-reported confidence · {Math.round(evidence.confidence * 100)}%</p>
      )}
      {location && <p className="evidence-location">{location}</p>}
      {evidence.citationUnverified && (
        <p className="evidence-unverified-note">
          This source is present in the workspace, but its relevance to the Copilot answer has not been verified.
        </p>
      )}
      {excerpt && (
        <section className="evidence-drawer__relationship">
          <span className="evidence-drawer__section-label">
            {finding ? "SOURCE EXCERPT" : "CITED SOURCE EXCERPT"}
          </span>
          <blockquote className="evidence-source-excerpt">{excerpt}</blockquote>
        </section>
      )}
      {!location && !excerpt && (
        <p className="muted">No source excerpt was returned for this item.</p>
      )}
    </aside>
  );
}
