import { useEffect, useRef } from "react";
import { formatAgentName } from "./agentNames";
import { getCleanFileName, stripQuotes } from "./sourceUtils";

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
  const rawFile = chunk?.file_name || chunk?.source_id || finding?.source_id;
  const cleanFileName = getCleanFileName(rawFile);
  const location = [
    cleanFileName,
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
      {location && (
        <div className="evidence-location flex items-center gap-1.5 text-xs text-secondary font-mono py-1">
          <span className="material-symbols-outlined text-[14px]">description</span>
          <span>Source File: <strong className="text-white font-semibold">{cleanFileName}</strong>{chunk?.page_or_ts ? ` · ${chunk.page_or_ts}` : ""}</span>
        </div>
      )}
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
          <div className="evidence-source-excerpt citation font-citation text-xs leading-relaxed p-3 bg-surface-container rounded border-l-2 border-secondary">
            <div className="text-[10px] uppercase font-mono text-outline mb-1 font-semibold flex items-center justify-between">
              <span>Cited Text</span>
              <span className="text-secondary font-mono">{cleanFileName}</span>
            </div>
            <p className="m-0 italic text-on-surface-variant">{stripQuotes(excerpt)}</p>
          </div>
        </section>
      )}
      {!location && !excerpt && (
        <p className="muted">No source excerpt was returned for this item.</p>
      )}
    </aside>
  );
}
