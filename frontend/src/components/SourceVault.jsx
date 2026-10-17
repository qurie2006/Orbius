import { useEffect, useRef, useState } from "react";

export default function SourceVault({
  files,
  uploading,
  onUpload,
  onPreviewFile,
  onRemoveFile,
  onClearFiles,
  description,
  onDescriptionChange,
  running,
  onGenerate,
  VoiceRecorder,
}) {
  const fileInputRef = useRef(null);
  const previewCloseRef = useRef(null);
  const [preview, setPreview] = useState(null);
  const [previewing, setPreviewing] = useState(null);
  const previewOpen = Boolean(preview);

  useEffect(() => {
    if (!previewOpen) return undefined;
    const previouslyFocused = document.activeElement;
    previewCloseRef.current?.focus({ preventScroll: true });
    const handleKeyDown = (event) => {
      if (event.key === "Escape") {
        setPreview(null);
        return;
      }
      if (event.key !== "Tab") return;
      const dialog = previewCloseRef.current?.closest("[role='dialog']");
      const focusable = dialog && [...dialog.querySelectorAll(
        "button:not(:disabled), a[href], input:not(:disabled), textarea:not(:disabled), select:not(:disabled), [tabindex]:not([tabindex='-1'])",
      )].filter((element) => element.getClientRects().length > 0);
      if (!focusable?.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      previouslyFocused?.focus?.();
    };
  }, [previewOpen]);

  async function previewFile(fileName) {
    setPreviewing(fileName);
    try {
      const data = await onPreviewFile(fileName);
      if (data) setPreview(data);
    } finally {
      setPreviewing(null);
    }
  }

  async function removePreviewedFile() {
    if (await onRemoveFile(preview.filename)) setPreview(null);
  }

  return (
    <section className="panel panel-sources source-vault">
      <header className="source-vault__header">
        <div>
          <span className="source-vault__eyebrow">01 / INPUTS</span>
          <h2>Source vault</h2>
        </div>
        <span className="source-vault__count" aria-label={`${files.length} sources`}>
          {String(files.length).padStart(2, "0")}
        </span>
      </header>

      <button
        type="button"
        className={`source-vault__drop ${uploading ? "is-uploading" : ""}`}
        onDragOver={(event) => {
          event.preventDefault();
          event.stopPropagation();
        }}
        onDrop={(event) => {
          event.preventDefault();
          event.stopPropagation();
          if (event.dataTransfer.files?.length) onUpload(event.dataTransfer.files);
        }}
        onClick={() => fileInputRef.current?.click()}
        disabled={uploading}
      >
        <span className="source-vault__upload-mark" aria-hidden="true">↥</span>
        <span className="source-vault__drop-title">
          {uploading ? "Reading source material…" : "Add project sources"}
        </span>
        <span className="source-vault__drop-hint">Drop files here or browse · PDF, DOCX, sheets, images, audio</span>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          hidden
          aria-label="Choose project source files"
          onChange={(event) => {
            if (event.target.files?.length) onUpload(event.target.files);
            event.target.value = "";
          }}
        />
      </button>

      <div className="source-vault__section-heading">
        <div>
          <span className="source-vault__eyebrow">PROJECT MATERIAL</span>
          <strong>Sources</strong>
        </div>
        {files.length > 0 && (
          <button type="button" className="btn ghost source-vault__clear" onClick={onClearFiles}>
            Clear list
          </button>
        )}
      </div>

      {files.length > 0 ? (
        <ul className="source-vault__list">
          {files.map((file) => {
            const modality = file.modality || "document";
            return (
              <li className="source-vault__file" key={file.name}>
                <span className="source-vault__file-type" aria-hidden="true">
                  {modality === "audio" ? "AUD" : modality === "image" ? "IMG" : modality === "sheet" ? "TAB" : "DOC"}
                </span>
                <button
                  type="button"
                  className="source-vault__preview-button"
                  onClick={() => previewFile(file.name)}
                  disabled={previewing === file.name}
                  aria-label={`Preview ${file.name}`}
                >
                  <span className="source-vault__file-name">{file.name}</span>
                  <span className="source-vault__file-modality">{modality}</span>
                </button>
                <button
                  type="button"
                  className="source-vault__remove"
                  title={`Remove ${file.name} from the active source list`}
                  aria-label={`Remove ${file.name} from the active source list`}
                  onClick={() => onRemoveFile(file.name)}
                >
                  ×
                </button>
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="source-vault__empty">Sources added to this session will appear here.</p>
      )}

      <p className="source-vault__storage-note">
        Removing a source clears it from the active session list. Server-side file cleanup is not confirmed.
      </p>

      <div className="source-vault__recorder">
        <span className="source-vault__eyebrow">CAPTURE A CONVERSATION</span>
        <VoiceRecorder onAudioRecorded={onUpload} />
      </div>

      <div className="source-vault__context">
        <label className="source-vault__eyebrow" htmlFor="project-context">
          PROJECT CONTEXT
        </label>
        <div className="prompt-starter-row">
          <button
            type="button"
            className="prompt-starter-chip"
            onClick={() => onDescriptionChange((previous) => `${previous}${previous ? "\n" : ""}Objective: Reduce checkout flow latency by 30%.`)}
          >
            + Checkout SLA
          </button>
          <button
            type="button"
            className="prompt-starter-chip"
            onClick={() => onDescriptionChange((previous) => `${previous}${previous ? "\n" : ""}Mandate: Require PCI-DSS Compliance & 2FA.`)}
          >
            + PCI & 2FA
          </button>
          <button
            type="button"
            className="prompt-starter-chip"
            onClick={() => onDescriptionChange((previous) => `${previous}${previous ? "\n" : ""}Scope: Multi-currency payments and automatic tax calculations.`)}
          >
            + Multi-Currency
          </button>
        </div>
        <textarea
          id="project-context"
          className="studio-textarea"
          rows={4}
          value={description}
          placeholder="Add goals, constraints, and technical context…"
          onChange={(event) => onDescriptionChange(event.target.value)}
        />
        <button className="launch-swarm-btn" disabled={running || uploading} onClick={onGenerate}>
          {running ? (
            <>
              <span className="vault-pulse" aria-hidden="true" />
              Analysis in progress
            </>
          ) : (
            "Generate requirements"
          )}
        </button>
      </div>

      {preview && (
        <div className="auth-overlay" onClick={() => setPreview(null)}>
          <section
            className="auth-card source-vault__preview"
            role="dialog"
            aria-modal="true"
            aria-labelledby="source-preview-title"
            onClick={(event) => event.stopPropagation()}
          >
            <header className="source-vault__preview-header">
              <div>
                <span className="source-vault__eyebrow">SOURCE PREVIEW</span>
                <h2 id="source-preview-title">{preview.filename}</h2>
              </div>
              <button
                ref={previewCloseRef}
                type="button"
                className="file-remove-btn"
                data-modal-initial-focus
                aria-label="Close preview"
                onClick={() => setPreview(null)}
              >
                ×
              </button>
            </header>
            <div className="source-vault__preview-meta">
              <span className={`file-modality-badge ${preview.modality || "document"}`}>
                {preview.modality || "document"}
              </span>
              {preview.chunk_count != null && (
                <span className="chip">{preview.chunk_count} extracted chunk{preview.chunk_count === 1 ? "" : "s"}</span>
              )}
            </div>
            <pre className="source-vault__preview-content">
              {preview.full_text || "No extracted text is available for this source."}
            </pre>
            <footer className="source-vault__preview-actions">
              <button type="button" className="btn ghost" onClick={removePreviewedFile}>
                Remove from source list
              </button>
              <button type="button" className="btn primary" onClick={() => setPreview(null)}>
                Close
              </button>
            </footer>
          </section>
        </div>
      )}
    </section>
  );
}
