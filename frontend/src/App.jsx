import { useEffect, useMemo, useRef, useState } from "react";
import mermaid from "mermaid";
import ActionCenter from "./components/ActionCenter";
import AnalysisTrace from "./components/AnalysisTrace";
import EvidenceInspector from "./components/EvidenceInspector";
import FragmentConvergence from "./components/FragmentConvergence";
import Icon from "./components/Icon";
import RequirementsDocument from "./components/RequirementsDocument";
import SourceVault from "./components/SourceVault";
import { formatAgentName } from "./components/agentNames";

const SESSION = "demo";

mermaid.initialize({
  startOnLoad: false,
  theme: "dark",
  securityLevel: "loose",
  flowchart: { useMaxWidth: true, htmlLabels: true, curve: "basis" },
  sequence: { useMaxWidth: true, showSequenceNumbers: true },
});

function useTheme() {
  const [theme, setTheme] = useState(() => localStorage.getItem("orbius-theme") || "dark");
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("orbius-theme", theme);
    mermaid.initialize({
      startOnLoad: false,
      theme: theme === "dark" ? "dark" : "default",
    });
  }, [theme]);
  return [theme, setTheme];
}

function routingStatusLabel(router) {
  const latestEvent = router?.log?.at(-1)?.event;
  if (latestEvent === "offline_demo") return "Offline heuristic";
  if (!router?.active_model) return "Route not reported";
  return router.fallback ? "Fallback route" : "Reported route";
}

function ScrollReveal({ as: Element = "div", className = "", children, ...props }) {
  const revealRef = useRef(null);

  useEffect(() => {
    const element = revealRef.current;
    if (!element) return undefined;
    if (!("IntersectionObserver" in window)) {
      element.classList.add("is-visible");
      return undefined;
    }

    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) {
        element.classList.add("is-visible");
        observer.unobserve(element);
      }
    }, { threshold: 0.16, rootMargin: "0px 0px -32px 0px" });

    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  return (
    <Element ref={revealRef} className={`story-reveal ${className}`.trim()} {...props}>
      {children}
    </Element>
  );
}

async function jsonFetch(url, options = {}) {
  const token = localStorage.getItem("orbius_token");
  const headers = {
    ...(options.headers || {}),
    ...(token ? { "x-user-id": token } : {}),
  };
  try {
    const res = await fetch(url, { ...options, headers });
    const text = await res.text();
    let data;
    try {
      data = text ? JSON.parse(text) : {};
    } catch {
      if (res.status === 502 || res.status === 503 || res.status === 504 || text.includes("The page")) {
        throw new Error("Backend server is waking up or temporarily unreachable. Please wait ~30 seconds and try again.");
      }
      throw new Error(`Invalid response from server (${res.status}). Please verify the backend is running.`);
    }

    if (!res.ok) {
      throw new Error(data.error || data.detail || `Server error (${res.status})`);
    }
    return data;
  } catch (err) {
    if (err.message && (err.message.includes("Failed to fetch") || err.message.includes("NetworkError"))) {
      throw new Error("Unable to connect to the backend server. Please verify backend is running on port 8000.");
    }
    throw err;
  }
}

// ==========================================
// FEATURE 4: In-Browser Voice Notes Recorder
// ==========================================
function VoiceRecorder({ onAudioRecorded }) {
  const [isRecording, setIsRecording] = useState(false);
  const [duration, setDuration] = useState(0);
  const [liveTranscript, setLiveTranscript] = useState("");
  const mediaRecorderRef = useRef(null);
  const recognitionRef = useRef(null);
  const audioChunksRef = useRef([]);
  const timerRef = useRef(null);
  const canvasRef = useRef(null);
  const animationFrameRef = useRef(null);
  const audioContextRef = useRef(null);
  const analyserRef = useRef(null);
  const transcriptRef = useRef("");

  async function startRecording() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioChunksRef.current = [];
      transcriptRef.current = "";
      setLiveTranscript("");

      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;

      // Real-time Speech Recognition
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (SpeechRecognition) {
        try {
          const recognition = new SpeechRecognition();
          recognition.continuous = true;
          recognition.interimResults = true;
          recognition.lang = "en-US";
          recognition.onresult = (event) => {
            let current = "";
            for (let i = 0; i < event.results.length; i++) {
              current += event.results[i][0].transcript + " ";
            }
            const clean = current.trim();
            transcriptRef.current = clean;
            setLiveTranscript(clean);
          };
          recognition.onerror = (e) => console.log("Speech recognition notice:", e.error);
          recognition.start();
          recognitionRef.current = recognition;
        } catch (e) {
          console.log("SpeechRecognition not initialized:", e);
        }
      }

      // Audio frequency visualizer
      const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      audioContextRef.current = audioCtx;
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 64;
      analyserRef.current = analyser;
      const source = audioCtx.createMediaStreamSource(stream);
      source.connect(analyser);

      drawVisualizer();

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data);
      };

      mediaRecorder.onstop = () => {
        const nowStr = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
        const filesToUpload = [];

        // Attach text transcription
        const finalTranscript = transcriptRef.current.trim() || liveTranscript.trim();
        if (finalTranscript) {
          const txtFile = new File([finalTranscript], `voice_brief_${nowStr}.txt`, { type: "text/plain" });
          filesToUpload.push(txtFile);
        }

        // Attach audio file
        const audioBlob = new Blob(audioChunksRef.current, { type: "audio/webm" });
        const audioFile = new File([audioBlob], `voice_recording_${nowStr}.webm`, { type: "audio/webm" });
        filesToUpload.push(audioFile);

        onAudioRecorded(filesToUpload);

        stream.getTracks().forEach((track) => track.stop());
        if (audioCtx.state !== "closed") audioCtx.close();
        cancelAnimationFrame(animationFrameRef.current);
      };

      mediaRecorder.start(250);
      setIsRecording(true);
      setDuration(0);
      timerRef.current = setInterval(() => {
        setDuration((d) => d + 1);
      }, 1000);
    } catch (err) {
      alert(`Microphone access error: ${err.message}. Please allow mic access in your browser.`);
    }
  }

  function stopRecording() {
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch (e) { }
    }
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      clearInterval(timerRef.current);
    }
  }

  function drawVisualizer() {
    const canvas = canvasRef.current;
    if (!canvas || !analyserRef.current) return;
    const ctx = canvas.getContext("2d");
    const bufferLength = analyserRef.current.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);

    function render() {
      animationFrameRef.current = requestAnimationFrame(render);
      analyserRef.current.getByteFrequencyData(dataArray);
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      const barWidth = (canvas.width / 16) - 2;
      const accentColor = getComputedStyle(document.documentElement).getPropertyValue("--accent").trim();
      let x = 0;
      for (let i = 0; i < 16; i++) {
        const barHeight = (dataArray[i * 2] / 255) * canvas.height * 0.9 + 2;
        ctx.fillStyle = accentColor;
        ctx.beginPath();
        ctx.roundRect(x, canvas.height - barHeight, barWidth, barHeight, 3);
        ctx.fill();
        x += barWidth + 2;
      }
    }
    render();
  }

  const formatDuration = (s) => {
    const mins = Math.floor(s / 60);
    const secs = s % 60;
    return `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
  };

  return (
    <div className="voice-recorder-widget">
      {!isRecording ? (
        <button
          type="button"
          className="btn voice-btn"
          onClick={startRecording}
          title="Record a live meeting or voice note to extract requirements"
        >
          <Icon name="microphone" size={16} />
          <span>Record voice note / meeting</span>
        </button>
      ) : (
        <div>
          <div className="recording-active-bar">
            <div className="recording-pill">
              <span className="rec-dot" />
              <span>REC {formatDuration(duration)}</span>
            </div>
            <canvas ref={canvasRef} width={80} height={24} className="rec-canvas" />
            <button type="button" className="btn primary small" onClick={stopRecording}>
              Done & Attach
            </button>
          </div>
          {liveTranscript && (
            <div className="live-transcript-box">
              <span className="muted" style={{ fontSize: "0.72rem", display: "block" }}>Live Transcribing:</span>
              <p style={{ margin: "2px 0 0", fontSize: "0.8rem", fontStyle: "italic" }}>"{liveTranscript}"</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ==========================================
// FEATURE 2: Chat with BRD Copilot Drawer
// ==========================================
function CopilotDrawer({ isOpen, onClose, onOpenEvidence, sourceChunks = [] }) {
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      content: "Hello! I am your **Orbius BRD Copilot**. Ask about project requirements, scope trade-offs, budget constraints, or stakeholder updates.",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [suggestions, setSuggestions] = useState([
    "What are the main requirements?",
    "Summarize all budget constraints",
    "What deadlines or action items are there?",
    "Draft a reply email to the sender",
  ]);
  const chatEndRef = useRef(null);
  const chatInputRef = useRef(null);
  const closeHandlerRef = useRef(onClose);

  useEffect(() => {
    closeHandlerRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    chatEndRef.current?.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth" });
  }, [messages, loading]);

  useEffect(() => {
    if (!isOpen) return undefined;
    const previouslyFocused = document.activeElement;
    chatInputRef.current?.focus({ preventScroll: true });
    const handleKeyDown = (event) => {
      if (event.key === "Escape") closeHandlerRef.current();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      previouslyFocused?.focus?.();
    };
  }, [isOpen]);

  async function handleSend(textToSend) {
    const text = textToSend || input;
    if (!text.trim() || loading) return;

    const userMsg = { role: "user", content: text };
    const nextHistory = [...messages, userMsg];
    setMessages(nextHistory);
    setInput("");
    setLoading(true);

    try {
      const res = await jsonFetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: SESSION,
          message: text,
          history: nextHistory.map((m) => ({ role: m.role, content: m.content })),
        }),
      });

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: res.reply,
          citations: res.citations || [],
        },
      ]);
      if (res.suggested_followups) setSuggestions(res.suggested_followups);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `Error fetching answer: ${err.message}`,
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  if (!isOpen) return null;

  return (
    <section className="copilot-drawer" role="dialog" aria-label="BRD Copilot">
      <div className="copilot-header">
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Icon name="message" size={19} />
          <strong>BRD Copilot</strong>
          <span className="chip" style={{ fontSize: "0.7rem", padding: "2px 6px" }}>Project assistant</span>
        </div>
        <button type="button" className="btn ghost" style={{ padding: "4px 8px" }} onClick={onClose} aria-label="Close Copilot">
          ✕
        </button>
      </div>

      <div className="copilot-messages">
        {messages.map((m, idx) => (
          <div key={idx} className={`copilot-bubble ${m.role}`}>
            <div style={{ whiteSpace: "pre-wrap", lineHeight: 1.5 }}>{m.content}</div>
            {m.citations && m.citations.length > 0 && (
              <div className="citations-container">
                <span className="muted copilot-reference-note">
                  Copilot references · source match does not verify relevance
                </span>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                  {m.citations.map((citation, i) => {
                    const source = sourceChunks.find((chunk) =>
                      (citation?.source_id && chunk.source_id === citation.source_id) ||
                      (citation?.file_name && chunk.file_name === citation.file_name),
                    );
                    const label = source?.file_name || source?.source_id ||
                      citation?.file_name || citation?.source_id || "Reference without source details";

                    return (
                      <button
                        key={`${citation?.source_id || citation?.file_name || "reference"}-${i}`}
                        type="button"
                        className="citation-chip"
                        disabled={!source}
                        title={source
                          ? "Matched to a source in this workspace; relevance to the answer is unverified."
                          : "This reference does not match a source currently loaded in this workspace."}
                        onClick={() => source && onOpenEvidence(citation, source)}
                      >
                        {label}{!source && " · unmatched"}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        ))}
        {loading && (
          <div className="copilot-bubble assistant">
            <span className="live-dot" /> Analyzing project findings & evidence...
          </div>
        )}
        <div ref={chatEndRef} />
      </div>

      <div className="copilot-suggestions">
        {suggestions.map((s, i) => (
          <button key={i} type="button" className="suggestion-pill" onClick={() => handleSend(s)}>
            {s}
          </button>
        ))}
      </div>

      <form
        className="copilot-input-bar"
        onSubmit={(e) => {
          e.preventDefault();
          handleSend();
        }}
      >
        <input
          ref={chatInputRef}
          type="text"
          placeholder="Ask a question about your project..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
        />
        <button type="submit" className="btn primary" disabled={loading || !input.trim()}>
          Send
        </button>
      </form>
    </section>
  );
}

// ==========================================
// FEATURE 5: Live What-If Scenario Simulator
// ==========================================
function ScenarioSimulatorModal({ isOpen, onClose }) {
  const [activeScenario, setActiveScenario] = useState("budget_cut_30");
  const [customPrompt, setCustomPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [diffSvg, setDiffSvg] = useState("");

  const presets = [
    { id: "budget_cut_30", label: "Budget cut 30%", desc: "What if the budget shrinks?" },
    { id: "launch_accelerated", label: "Deliver 6 weeks early", desc: "What if deadlines move earlier?" },
    { id: "drop_tablet_scope", label: "Must-haves only", desc: "Keep only mandatory items" },
    { id: "strict_security_wcag", label: "Stricter security", desc: "Raise security & compliance rules" },
  ];

  async function runSimulation(type) {
    const scType = type || activeScenario;
    setLoading(true);
    try {
      const res = await jsonFetch("/api/scenario/simulate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: SESSION,
          scenario_type: scType,
          custom_prompt: scType === "custom" ? customPrompt : "",
        }),
      });
      setResult(res);

      if (res.diagram_diff_mermaid) {
        const id = `diff-mermaid-${Date.now()}`;
        const { svg } = await mermaid.render(id, res.diagram_diff_mermaid);
        setDiffSvg(svg);
      }
    } catch (err) {
      alert(`Simulation error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }

  if (!isOpen) return null;

  return (
    <div className="auth-overlay">
      <div className="auth-card scenario-modal" role="dialog" aria-modal="true" aria-labelledby="scenario-modal-title">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
          <div>
            <h3 id="scenario-modal-title" style={{ margin: "0 0 4px" }}>What-if scenario simulator</h3>
            <p className="muted" style={{ margin: 0, fontSize: "0.85rem" }}>
              Explore cascading downstream impacts on requirements, milestones, and risks.
            </p>
          </div>
          <button type="button" className="btn ghost" data-modal-initial-focus onClick={onClose} aria-label="Close scenario simulator">✕</button>
        </div>

        <div className="scenario-presets">
          {presets.map((p) => (
            <button
              key={p.id}
              type="button"
              className={`preset-card ${activeScenario === p.id ? "active" : ""}`}
              onClick={() => {
                setActiveScenario(p.id);
                runSimulation(p.id);
              }}
            >
              <strong>{p.label}</strong>
              <span>{p.desc}</span>
            </button>
          ))}
        </div>

        <div style={{ marginTop: 14, marginBottom: 16 }}>
          <label className="muted" style={{ fontSize: "0.8rem", display: "block", marginBottom: 4 }}>
            Or enter custom hypothetical constraint:
          </label>
          <div style={{ display: "flex", gap: 8 }}>
            <input
              type="text"
              placeholder="e.g. What if the deadline moves to next Friday?"
              value={customPrompt}
              onChange={(e) => setCustomPrompt(e.target.value)}
            />
            <button
              type="button"
              className="btn primary"
              disabled={loading || !customPrompt.trim()}
              onClick={() => {
                setActiveScenario("custom");
                runSimulation("custom");
              }}
            >
              Simulate
            </button>
          </div>
        </div>

        {loading ? (
          <div className="card" style={{ textAlign: "center", padding: 30 }}>
            <span className="live-dot" /> Calculating downstream requirement ripple effects...
          </div>
        ) : result ? (
          <div className="scenario-results">
            <h4>{result.scenario_title}</h4>
            <div className="impact-box" dangerouslySetInnerHTML={{ __html: result.impact_summary }} />

            {result.affected_items && result.affected_items.length > 0 && (
              <div style={{ marginTop: 14 }}>
                <strong style={{ fontSize: "0.88rem" }}>Impacted Requirements:</strong>
                <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 6 }}>
                  {result.affected_items.map((item, i) => (
                    <div key={i} className="affected-item-row">
                      <span className={`status-tag ${item.status}`}>{item.status.toUpperCase()}</span>
                      <div>
                        <strong>{item.statement}</strong>
                        <p className="muted" style={{ margin: "2px 0 0", fontSize: "0.8rem" }}>{item.impact}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {diffSvg && (
              <div style={{ marginTop: 16 }}>
                <strong style={{ fontSize: "0.88rem" }}>Cascading Dependency Path:</strong>
                <div className="mermaid-viewport" dangerouslySetInnerHTML={{ __html: diffSvg }} />
              </div>
            )}
          </div>
        ) : (
          <div className="card" style={{ textAlign: "center", padding: 24 }}>
            <p className="muted" style={{ margin: 0 }}>Select a preset above to calculate live trade-offs.</p>
          </div>
        )}
      </div>
    </div>
  );
}

// ==========================================
// FEATURE: BRD -> Clickable Interactive Prototype
// ==========================================
function InteractivePrototype({ findings, chunks }) {
  const reqItems = useMemo(
    () => (findings || []).filter((f) => f.type !== "stakeholder" && f.section !== "stakeholders"),
    [findings]
  );
  const stakeholders = useMemo(
    () => (findings || []).filter((f) => f.type === "stakeholder" || f.section === "stakeholders"),
    [findings]
  );

  // Detect rules from findings
  const thresholdRule = useMemo(() => {
    return reqItems.find((f) => /\$\s?[\d,]+/.test(f.statement) && /above|over|exceed|threshold|2fa|override/i.test(f.statement));
  }, [reqItems]);

  const thresholdAmount = useMemo(() => {
    if (!thresholdRule) return 500;
    const match = thresholdRule.statement.match(/\$\s?([\d,]+)/);
    return match ? parseFloat(match[1].replace(/,/g, "")) : 500;
  }, [thresholdRule]);

  const budgetRule = useMemo(() => {
    return reqItems.find((f) => f.section === "budget" || /budget|ceiling|cap|allocation/i.test(f.statement));
  }, [reqItems]);

  const budgetCap = useMemo(() => {
    if (!budgetRule) return null;
    const match = budgetRule.statement.match(/\$\s?([\d,]+(?:\.\d+)?)\s*(k|m)?/i);
    if (!match) return null;
    let val = parseFloat(match[1].replace(/,/g, ""));
    if (match[2]?.toLowerCase() === "k") val *= 1000;
    if (match[2]?.toLowerCase() === "m") val *= 1000000;
    return val;
  }, [budgetRule]);

  // State
  const [testAmount, setTestAmount] = useState(thresholdAmount ? thresholdAmount + 150 : 650);
  const [testSpend, setTestSpend] = useState(budgetCap ? budgetCap * 0.75 : 120000);
  const [overrideModal, setOverrideModal] = useState(false);
  const [overridePin, setOverridePin] = useState("");
  const [overrideMessage, setOverrideMessage] = useState(null);
  const [verifiedList, setVerifiedList] = useState({});
  const [actionDispatched, setActionDispatched] = useState(false);
  const [auditLogs, setAuditLogs] = useState(() => [
    { ts: new Date().toISOString().slice(11, 19) + " UTC", event: "Prototype initialized from current BRD findings; not independently verified" },
  ]);

  if (!findings || findings.length === 0) {
    return (
      <div className="card" style={{ textAlign: "center", padding: 36 }}>
        <p className="muted" style={{ margin: 0 }}>
          Generate a BRD first — the interactive prototype will be built dynamically from your project's findings.
        </p>
      </div>
    );
  }

  const requires2FA = thresholdRule ? testAmount > thresholdAmount : false;
  const exceedsBudget = budgetCap ? testSpend > budgetCap : false;

  function handleVerifyOverride() {
    if (overridePin.length >= 4) {
      setOverrideMessage({ ok: true, text: "✓ Prototype simulation passed. No real authentication was performed." });
      setAuditLogs((prev) => [
        { ts: new Date().toISOString().slice(11, 19) + " UTC", event: `2FA simulation passed for $${testAmount.toLocaleString()}` },
        ...prev,
      ]);
      setTimeout(() => {
        setOverrideModal(false);
        setOverridePin("");
        setOverrideMessage(null);
      }, 1000);
    } else {
      setOverrideMessage({ ok: false, text: "✕ Invalid PIN. Enter at least 4 digits." });
    }
  }

  function toggleVerified(id, stmt) {
    setVerifiedList((prev) => {
      const next = !prev[id];
      setAuditLogs((logs) => [
        { ts: new Date().toISOString().slice(11, 19) + " UTC", event: `${next ? "Marked reviewed" : "Unchecked review"}: ${stmt.slice(0, 45)}...` },
        ...logs,
      ]);
      return { ...prev, [id]: next };
    });
  }

  function handleDispatchAction() {
    setActionDispatched(true);
    setAuditLogs((prev) => [
        { ts: new Date().toISOString().slice(11, 19) + " UTC", event: "Proposal dispatch simulation recorded" },
      ...prev,
    ]);
  }

  return (
    <div className="prototype-container">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16, flexWrap: "wrap", gap: 10 }}>
        <div>
          <h3 style={{ margin: "0 0 2px", color: "var(--accent-text)" }}>Interactive Requirements Simulator</h3>
          <p className="muted" style={{ margin: 0, fontSize: "0.82rem" }}>
            Local prototype simulation based on extracted findings. Actions here do not process transactions, authenticate users, or send deliverables.
          </p>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          {stakeholders.map((s, idx) => (
            <span key={idx} className="chip" style={{ background: "color-mix(in srgb, var(--accent) 10%, var(--elev))", color: "var(--accent-text)", fontSize: "0.75rem" }}>
              {s.statement}
            </span>
          ))}
        </div>
      </div>

      <div className="prototype-screen">
        {/* Left Column: Interactive Rule Testing */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16, minWidth: 0, width: "100%" }}>
          {/* Threshold / 2FA Simulator */}
          <div style={{ background: "var(--elev-2)", border: "1px solid var(--line)", borderRadius: 14, padding: 18, minWidth: 0 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8, flexWrap: "wrap", gap: 8 }}>
              <strong style={{ fontSize: "0.92rem", display: "flex", alignItems: "center", gap: 6 }}>
                Security & threshold evaluation
              </strong>
              <span className="chip" style={{ fontSize: "0.72rem", background: requires2FA ? "color-mix(in srgb, var(--danger) 12%, var(--elev))" : "color-mix(in srgb, var(--good) 12%, var(--elev))", color: requires2FA ? "var(--danger)" : "var(--good)", border: `1px solid ${requires2FA ? "var(--danger)" : "var(--good)"}` }}>
                {requires2FA ? "Would require 2FA" : "Standard flow"}
              </span>
            </div>
            <p className="muted" style={{ fontSize: "0.8rem", margin: "0 0 14px", lineHeight: 1.4, wordBreak: "break-word", overflowWrap: "anywhere" }}>
              {thresholdRule ? thresholdRule.statement : "Test transaction authorization rules against stated criteria."}
            </p>

            <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12, flexWrap: "wrap" }}>
              <label style={{ fontSize: "0.82rem", color: "var(--muted)" }}>Transaction Value:</label>
              <div style={{ position: "relative", display: "inline-flex", alignItems: "center" }}>
                <span style={{ position: "absolute", left: 10, color: "var(--muted)", fontWeight: 700 }}>$</span>
                <input
                  type="number"
                  value={testAmount}
                  onChange={(e) => setTestAmount(parseFloat(e.target.value) || 0)}
                  style={{ width: 140, padding: "7px 10px 7px 22px", fontSize: "0.95rem", fontWeight: 700, borderRadius: 8, border: "1px solid var(--line)", background: "var(--bg)" }}
                />
              </div>
              <span style={{ fontSize: "0.78rem", color: "var(--muted)" }}>Threshold: <strong>${thresholdAmount.toLocaleString()}</strong></span>
            </div>

            {/* Quick Presets */}
            <div style={{ display: "flex", gap: 6, marginBottom: 14, flexWrap: "wrap" }}>
              <button
                type="button"
                className="chip"
                style={{ cursor: "pointer", fontSize: "0.72rem", background: testAmount === thresholdAmount - 100 ? "color-mix(in srgb, var(--accent) 12%, var(--elev))" : "var(--elev)" }}
                onClick={() => setTestAmount(Math.max(0, thresholdAmount - 100))}
              >
                ${Math.max(0, thresholdAmount - 100).toLocaleString()} (Below)
              </button>
              <button
                type="button"
                className="chip"
                style={{ cursor: "pointer", fontSize: "0.72rem", background: testAmount === thresholdAmount ? "color-mix(in srgb, var(--accent) 12%, var(--elev))" : "var(--elev)" }}
                onClick={() => setTestAmount(thresholdAmount)}
              >
                ${thresholdAmount.toLocaleString()} (Limit)
              </button>
              <button
                type="button"
                className="chip"
                style={{ cursor: "pointer", fontSize: "0.72rem", background: testAmount === thresholdAmount + 250 ? "color-mix(in srgb, var(--accent) 12%, var(--elev))" : "var(--elev)" }}
                onClick={() => setTestAmount(thresholdAmount + 250)}
              >
                ${(thresholdAmount + 250).toLocaleString()} (Elevated)
              </button>
            </div>

            {requires2FA ? (
              <div style={{ background: "color-mix(in srgb, var(--danger) 10%, var(--elev))", border: "1px solid var(--danger)", borderRadius: 10, padding: 12 }}>
                <p style={{ margin: "0 0 8px", fontSize: "0.82rem", color: "var(--ink)", lineHeight: 1.4, wordBreak: "break-word" }}>
                  Simulated amount (${testAmount.toLocaleString()}) exceeds the ${thresholdAmount.toLocaleString()} ceiling; this rule would require 2FA.
                </p>
                <button
                  type="button"
                  className="btn primary"
                  style={{ fontSize: "0.82rem", padding: "6px 14px", cursor: "pointer" }}
                  onClick={() => setOverrideModal(true)}
                >
                  Simulate 2FA step
                </button>
              </div>
            ) : (
              <div style={{ background: "color-mix(in srgb, var(--good) 10%, var(--elev))", border: "1px solid var(--good)", borderRadius: 10, padding: 12 }}>
                <p style={{ margin: 0, fontSize: "0.82rem", color: "var(--good)", lineHeight: 1.4, wordBreak: "break-word" }}>
                  Simulation: value (${testAmount.toLocaleString()}) is at or below the threshold.
                </p>
              </div>
            )}
          </div>

          {/* Budget Guardrail Simulator */}
          {budgetCap && (
            <div style={{ background: "var(--elev-2)", border: "1px solid var(--line)", borderRadius: 14, padding: 18, minWidth: 0 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8, flexWrap: "wrap", gap: 8 }}>
                <strong style={{ fontSize: "0.92rem", display: "flex", alignItems: "center", gap: 6 }}>
                  Budget guardrail tracker
                </strong>
                <span className="chip" style={{ fontSize: "0.72rem", background: exceedsBudget ? "color-mix(in srgb, var(--danger) 12%, var(--elev))" : "color-mix(in srgb, var(--warn) 12%, var(--elev))", color: exceedsBudget ? "var(--danger)" : "var(--warn)", border: `1px solid ${exceedsBudget ? "var(--danger)" : "var(--warn)"}` }}>
                  Limit: ${budgetCap.toLocaleString()}
                </span>
              </div>
              <p className="muted" style={{ fontSize: "0.78rem", margin: "0 0 12px", lineHeight: 1.4, wordBreak: "break-word", overflowWrap: "anywhere" }}>
                {budgetRule?.statement}
              </p>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.82rem", marginBottom: 6, flexWrap: "wrap", gap: 6 }}>
                <span>Simulated Spend: <strong>${testSpend.toLocaleString()}</strong> ({Math.round((testSpend / budgetCap) * 100)}%)</span>
                <span style={{ color: exceedsBudget ? "var(--danger)" : "var(--good)", fontWeight: 600 }}>
                  {exceedsBudget ? `Over by $${(testSpend - budgetCap).toLocaleString()}` : `Remaining: $${(budgetCap - testSpend).toLocaleString()}`}
                </span>
              </div>
              <input
                type="range"
                min={budgetCap * 0.3}
                max={budgetCap * 1.5}
                step={Math.max(1000, Math.round(budgetCap * 0.05))}
                value={testSpend}
                onChange={(e) => setTestSpend(parseFloat(e.target.value))}
                style={{ width: "100%", accentColor: exceedsBudget ? "var(--danger)" : "var(--accent)", cursor: "pointer" }}
              />
            </div>
          )}

          {/* Action Item / Proposal Dispatch Simulator */}
          <div style={{ background: "var(--elev-2)", border: "1px solid var(--line)", borderRadius: 14, padding: 18, minWidth: 0 }}>
            <strong style={{ fontSize: "0.92rem", display: "flex", alignItems: "center", gap: 6, marginBottom: 6 }}>
              Stakeholder deliverable dispatch
            </strong>
            <p className="muted" style={{ fontSize: "0.78rem", margin: "0 0 14px", lineHeight: 1.4, wordBreak: "break-word", overflowWrap: "anywhere" }}>
              Simulate dispatching technical architecture deliverables to the recipient requested in the source document.
            </p>
            <button
              type="button"
              className="btn"
              disabled={actionDispatched}
              onClick={handleDispatchAction}
              style={{ fontSize: "0.82rem", padding: "8px 16px", cursor: actionDispatched ? "default" : "pointer" }}
            >
              {actionDispatched ? "Dispatch simulation logged" : "Simulate proposal dispatch"}
            </button>
          </div>
        </div>

        {/* Right Column: Live Requirement Verification & Audit Log */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16, minWidth: 0, width: "100%" }}>
          {/* Requirement Verification Checklist */}
          <div style={{ background: "var(--elev-2)", border: "1px solid var(--line)", borderRadius: 14, padding: 18, flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10, flexWrap: "wrap", gap: 8 }}>
              <div>
                <strong style={{ fontSize: "0.95rem", display: "block" }}>Requirements review checklist</strong>
                <span className="muted" style={{ fontSize: "0.76rem" }}>
                  {Object.values(verifiedList).filter(Boolean).length} of {reqItems.length} marked reviewed ({reqItems.length ? Math.round((Object.values(verifiedList).filter(Boolean).length / reqItems.length) * 100) : 0}%)
                </span>
              </div>
              <div style={{ display: "flex", gap: 6 }}>
                <button
                  type="button"
                  className="chip"
                  style={{ cursor: "pointer", background: "color-mix(in srgb, var(--accent) 10%, var(--elev))", color: "var(--accent-text)", border: "1px solid color-mix(in srgb, var(--accent) 30%, var(--line))", fontSize: "0.72rem" }}
                  onClick={() => {
                    const all = {};
                    reqItems.forEach((r) => { all[r.id] = true; });
                    setVerifiedList(all);
                    setAuditLogs((l) => [{ ts: new Date().toISOString().slice(11, 19) + " UTC", event: `Marked all ${reqItems.length} items reviewed locally` }, ...l]);
                  }}
                >
                  Mark all reviewed
                </button>
                <button
                  type="button"
                  className="chip"
                  style={{ cursor: "pointer", background: "var(--elev)", border: "1px solid var(--line)", fontSize: "0.72rem" }}
                  onClick={() => {
                    setVerifiedList({});
                    setAuditLogs((l) => [{ ts: new Date().toISOString().slice(11, 19) + " UTC", event: "Reset all requirement checks" }, ...l]);
                  }}
                >
                  Reset
                </button>
              </div>
            </div>

            {/* Verification Progress Bar */}
            <div style={{ width: "100%", height: 6, background: "var(--bg)", borderRadius: 999, overflow: "hidden", marginBottom: 14 }}>
              <div
                style={{
                  width: `${reqItems.length ? (Object.values(verifiedList).filter(Boolean).length / reqItems.length) * 100 : 0}%`,
                  height: "100%",
                  background: "var(--accent)",
                  transition: "width 0.3s ease",
                }}
              />
            </div>

            {/* Scrollable list taking full available height */}
            <div style={{ display: "flex", flexDirection: "column", gap: 10, flex: 1, minHeight: 360, maxHeight: 480, overflowY: "auto", paddingRight: 4 }}>
              {reqItems.map((f) => {
                const isChecked = !!verifiedList[f.id];
                return (
                  <div
                    key={f.id}
                    onClick={() => toggleVerified(f.id, f.statement)}
                    style={{
                      display: "flex",
                      alignItems: "flex-start",
                      gap: 12,
                      padding: "12px 14px",
                      borderRadius: 10,
                      background: isChecked ? "color-mix(in srgb, var(--good) 8%, var(--elev))" : "var(--elev)",
                      border: `1px solid ${isChecked ? "color-mix(in srgb, var(--good) 40%, var(--line))" : "var(--line)"}`,
                      cursor: "pointer",
                      transition: "all 0.15s ease",
                      minWidth: 0,
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={isChecked}
                      onChange={() => {}}
                      style={{ marginTop: 2, cursor: "pointer", accentColor: "var(--good)", transform: "scale(1.15)" }}
                    />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <p style={{
                        margin: "0 0 6px",
                        fontSize: "0.84rem",
                        lineHeight: 1.45,
                        color: isChecked ? "var(--good)" : "var(--ink)",
                        wordBreak: "break-word",
                        overflowWrap: "anywhere",
                      }}>
                        {f.statement}
                      </p>
                      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                        <span className="chip" style={{ fontSize: "0.68rem", padding: "2px 8px", background: "var(--bg-2)" }}>
                          {f.section.replace(/_/g, " ")}
                        </span>
                        {typeof f.confidence === "number" && Number.isFinite(f.confidence) && (
                          <span className="muted" style={{ fontSize: "0.7rem" }}>
                            Confidence · {Math.round(f.confidence * 100)}%
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Live Session Audit Stream */}
          <div style={{ background: "var(--bg)", border: "1px solid var(--line)", borderRadius: 12, padding: 14, minWidth: 0 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
              <strong style={{ fontSize: "0.78rem", color: "var(--muted)", display: "flex", alignItems: "center", gap: 6 }}>
                <span style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--good)", display: "inline-block" }} />
                Local review log
              </strong>
              <span className="muted" style={{ fontSize: "0.7rem" }}>{auditLogs.length} events logged</span>
            </div>
            <div style={{ maxHeight: 110, overflowY: "auto", fontSize: "0.75rem", display: "flex", flexDirection: "column", gap: 5 }}>
              {auditLogs.map((log, i) => (
                <div key={i} style={{ color: "var(--accent-text)", wordBreak: "break-word", overflowWrap: "anywhere" }}>
                  <span style={{ color: "var(--muted)" }}>[{log.ts}]</span> {log.event}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {overrideModal && (
        <div className="auth-overlay">
          <div className="auth-card" style={{ maxWidth: 380 }}>
            <h4 style={{ margin: "0 0 6px" }}>Simulated security check</h4>
            <p className="muted" style={{ fontSize: "0.8rem", margin: "0 0 12px" }}>
              {thresholdRule ? thresholdRule.statement : "A local rule simulation for elevated transactions."}
            </p>
            <input
              type="password"
              placeholder="Enter PIN (e.g. 1234)"
              value={overridePin}
              onChange={(e) => setOverridePin(e.target.value)}
              style={{ marginBottom: 10 }}
            />
            {overrideMessage && (
              <p style={{ color: overrideMessage.ok ? "var(--good)" : "var(--danger)", fontSize: "0.82rem", margin: "0 0 10px" }}>
                {overrideMessage.text}
              </p>
            )}
            <div style={{ display: "flex", gap: 8 }}>
              <button type="button" className="btn primary" style={{ flex: 1 }} onClick={handleVerifyOverride}>
                Simulate 2FA
              </button>
              <button type="button" className="btn ghost" onClick={() => setOverrideModal(false)}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ==========================================
// FEATURE: Gherkin Test Suite & Backlog Viewer
// ==========================================
function GherkinTestCases({ sessionId }) {
  const [testCases, setTestCases] = useState([]);
  const [loading, setLoading] = useState(false);
  const [runningSim, setRunningSim] = useState(false);
  const [activeTab, setActiveTab] = useState(0);

  useEffect(() => {
    fetchTests();
  }, [sessionId]);

  async function fetchTests() {
    setLoading(true);
    try {
      const data = await jsonFetch(`/api/session/${sessionId}/test-suite`);
      setTestCases(data.test_cases || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  // Download the scenarios as a real .feature file that QA tools (Cucumber, Behave, Playwright-BDD) can run
  function downloadFeatureFile() {
    const content = testCases.map((tc) => `# ${tc.id} — source: ${tc.requirement_statement}\n${tc.gherkin}`).join("\n\n");
    const blob = new Blob([content], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "orbius-acceptance-tests.feature";
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="gherkin-container">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14, gap: 10, flexWrap: "wrap" }}>
        <div>
          <h3 style={{ margin: "0 0 2px" }}>Acceptance tests (Gherkin)</h3>
          <p className="muted" style={{ margin: 0, fontSize: "0.82rem" }}>
            Plain-English Given / When / Then checks, one for each requirement found in your files.
          </p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button
            type="button"
            className="btn primary"
            disabled={testCases.length === 0}
            onClick={downloadFeatureFile}
          >
            Download .feature file
          </button>
        </div>
      </div>

      {loading ? (
        <div className="card" style={{ textAlign: "center", padding: 30 }}>
          <span className="live-dot" /> Generating executable test cases...
        </div>
      ) : testCases.length === 0 ? (
        <div className="card" style={{ textAlign: "center", padding: 24 }}>
          <p className="muted" style={{ margin: 0 }}>Generate a BRD first to compile downstream Gherkin test scenarios.</p>
        </div>
      ) : (
        <div>
          <div style={{ display: "flex", gap: 6, overflowX: "auto", marginBottom: 12 }}>
            {testCases.map((tc, idx) => (
              <button
                key={tc.id}
                type="button"
                className={`studio-nav-btn ${activeTab === idx ? "active" : ""}`}
                onClick={() => setActiveTab(idx)}
              >
                <span>{tc.id}</span>
                <span style={{ fontSize: "0.7rem", opacity: 0.8 }}>({tc.coverage})</span>
              </button>
            ))}
          </div>

          {testCases[activeTab] && (
            <div className="gherkin-card">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                <div>
                  <strong style={{ fontSize: "0.95rem" }}>{testCases[activeTab].feature}</strong>
                  <p className="muted" style={{ margin: "2px 0 0", fontSize: "0.8rem" }}>
                    {testCases[activeTab].name}
                  </p>
                </div>
                <span className="chip" style={{ background: "color-mix(in srgb, var(--accent) 10%, var(--elev))", color: "var(--accent-text)" }}>
                  Ready to run · {testCases[activeTab].coverage}
                </span>
              </div>

              <div className="gherkin-code">{testCases[activeTab].gherkin}</div>

              <div style={{ marginTop: 10, fontSize: "0.78rem", color: "var(--muted)" }}>
                Linked Finding: <em>{testCases[activeTab].requirement_statement}</em>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ==========================================
// FEATURE: Impact Ripple Dependency Graph
// ==========================================
function ImpactRippleGraph({ sessionId }) {
  const [graphData, setGraphData] = useState(null);
  const [selectedSim, setSelectedSim] = useState(null);
  const [pulsingNodes, setPulsingNodes] = useState([]);

  useEffect(() => {
    jsonFetch(`/api/session/${sessionId}/ripple-graph`)
      .then((data) => {
        setGraphData(data);
      })
      .catch(console.error);
  }, [sessionId]);

  function triggerSimulation(sim) {
    setSelectedSim(sim.id);
    setPulsingNodes(sim.affected_nodes);
  }

  const currentSim = graphData?.simulations?.find((s) => s.id === selectedSim);

  return (
    <div className="ripple-graph-panel">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
        <div>
          <h3 style={{ margin: "0 0 2px", color: "var(--accent-text)" }}>Interactive Impact Ripple Graph</h3>
          <p className="muted" style={{ margin: 0, fontSize: "0.82rem" }}>
            Visualizes cross-cutting dependencies between Requirements, Stakeholders, Budgets, and Deadlines.
          </p>
        </div>
      </div>

      <div style={{ display: "flex", gap: 8, marginBottom: 16, flexWrap: "wrap" }}>
        {graphData?.simulations?.map((sim) => (
          <button
            key={sim.id}
            type="button"
            className={`preset-card ${selectedSim === sim.id ? "active" : ""}`}
            style={{ padding: "8px 14px", flex: 1, minWidth: 200 }}
            onClick={() => triggerSimulation(sim)}
          >
            <strong>{sim.title}</strong>
          </button>
        ))}
      </div>

      {currentSim && (
        <div style={{ background: "color-mix(in srgb, var(--accent) 8%, var(--elev))", border: "1px solid color-mix(in srgb, var(--accent) 35%, var(--line))", borderRadius: 12, padding: 14, marginBottom: 18 }}>
          <strong style={{ color: "var(--accent-text)", fontSize: "0.88rem" }}>Cascading ripple impact:</strong>
          <p style={{ margin: "4px 0 0", fontSize: "0.85rem", color: "var(--ink)" }}>{currentSim.impact_summary}</p>
        </div>
      )}

      {graphData && (graphData.nodes || []).length === 0 && (
        <div className="card" style={{ textAlign: "center", padding: 24 }}>
          <p className="muted" style={{ margin: 0 }}>Generate a BRD first — the graph is built only from your uploaded files.</p>
        </div>
      )}

      <div style={{ display: "flex", flexWrap: "wrap", gap: 10, padding: 18, background: "var(--bg-2)", borderRadius: 14, border: "1px solid var(--line)" }}>
        {graphData?.nodes?.map((node) => {
          const isPulsing = pulsingNodes.includes(node.id);
          const nodeColor = {
            project: "var(--accent-2)",
            stakeholder: "var(--accent-2)",
            budget: "var(--warn)",
            deadline: "var(--danger)",
            requirement: "var(--good)",
            task: "var(--muted)",
          }[node.type] || "var(--muted)";
          return (
            <div
              key={node.id}
              className={`ripple-node-badge ${isPulsing ? "pulsing" : ""}`}
              style={{
                background: isPulsing ? "color-mix(in srgb, var(--accent) 12%, var(--elev-2))" : "var(--elev-2)",
                color: isPulsing ? "var(--accent)" : node.color,
                borderColor: isPulsing ? "var(--accent)" : "var(--line)",
              }}
            >
              <span>{isPulsing ? "!" : "●"}</span>
              <span>{node.label}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ==========================================
// FEATURE: Replayable Multi-Agent Decision Trace
// ==========================================
function DecisionTraceTimeline({ events, router, state }) {
  const [activeStep, setActiveStep] = useState(0);
  const findings = state?.findings || [];
  const steps = (events || []).map((event, index) => ({
    name: `L${event.level} · ${formatAgentName(event.agent)}`,
    model: router?.active_model || "Route not reported",
    status: event.status === "running" ? "Recorded as running" : event.status || "Status not reported",
    detail: event.detail || event.task || "No event detail was returned.",
    id: `${event.agent}-${event.task}-${index}`,
  }));
  if (state) {
    steps.push({
      name: "Session snapshot",
      model: router?.active_model || "Route not reported",
      status: "Recorded",
      detail: `${findings.length} findings and ${(state.conflicts || []).length} conflicts are present in the saved session.`,
      id: "session-snapshot",
    });
  }
  const selectedStep = steps[Math.min(activeStep, Math.max(steps.length - 1, 0))];

  return (
    <div className="trace-timeline-container">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
        <div>
          <h3 style={{ margin: "0 0 2px" }}>Recorded activity trace</h3>
          <p className="muted" style={{ margin: 0, fontSize: "0.82rem" }}>
            Review the delegation events returned by the processing pipeline.
          </p>
        </div>
        {steps.length > 0 && (
          <span className="chip">
            Event {Math.min(activeStep + 1, steps.length)} of {steps.length}
          </span>
        )}
      </div>

      {router?.active_model && (
        <p className="muted">{routingStatusLabel(router)} · {router.active_model}</p>
      )}

      {selectedStep ? (
        <>
          {steps.length > 1 && (
            <input
              type="range"
              aria-label="Select recorded activity event"
              min="0"
              max={steps.length - 1}
              value={Math.min(activeStep, steps.length - 1)}
              onChange={(e) => setActiveStep(Number(e.target.value))}
              style={{ width: "100%", margin: "8px 0 16px" }}
            />
          )}
          <div className="trace-step-card">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
              <strong style={{ fontSize: "1rem" }}>{selectedStep.name}</strong>
              <span className="chip">{selectedStep.status}</span>
            </div>
            <p style={{ margin: "4px 0 0", fontSize: "0.88rem" }}>{selectedStep.detail}</p>
          </div>
        </>
      ) : (
        <p className="muted">No delegation events or saved session details have been reported yet.</p>
      )}
    </div>
  );
}

// ==========================================
// FEATURE: Live Meeting Mode & Conflict Interrupter
// ==========================================
function LiveMeetingMode({ sessionId, onNewFinding }) {
  const [meetingTranscript, setMeetingTranscript] = useState("");
  const [isListening, setIsListening] = useState(false);
  const [interruptAlert, setInterruptAlert] = useState(null);
  const recognitionRef = useRef(null);
  const [sampleTriggers, setSampleTriggers] = useState([]);

  // Test phrases are generated from YOUR findings (no demo data)
  useEffect(() => {
    jsonFetch(`/api/session/${sessionId}/meeting-triggers`)
      .then((d) => setSampleTriggers(d.triggers || []))
      .catch(() => setSampleTriggers([]));
  }, [sessionId]);

  async function checkInterruption(text) {
    try {
      const res = await jsonFetch("/api/meeting/interrupter", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ speech: text, session_id: sessionId }),
      });
      if (res.interrupted) {
        setInterruptAlert(res);
      }
    } catch (e) {
      console.error(e);
    }
  }

  function simulatePhrase(phrase) {
    setMeetingTranscript((prev) => (prev ? prev + "\n" + phrase : phrase));
    checkInterruption(phrase);
  }

  return (
    <div className="meeting-panel">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
        <div>
          <h3 style={{ margin: "0 0 2px", color: "var(--accent-text)" }}>Meeting conflict check</h3>
          <p className="muted" style={{ margin: 0, fontSize: "0.82rem" }}>
            Check typed meeting notes or sample phrases against established requirements, budgets, and deadlines.
          </p>
        </div>
      </div>

      <div style={{ display: "flex", gap: 8, marginBottom: 14, flexWrap: "wrap" }}>
        {sampleTriggers.length === 0 && (
          <p className="muted" style={{ margin: 0, fontSize: "0.8rem" }}>
            Generate a BRD first — test phrases will be created from your own requirements, budget and deadlines.
          </p>
        )}
        {sampleTriggers.map((t, idx) => (
          <button
            key={idx}
            type="button"
            className="btn ghost"
            style={{ fontSize: "0.8rem", border: "1px dashed var(--line)" }}
            onClick={() => simulatePhrase(t.phrase)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {interruptAlert && (
        <div className="interruption-banner">
          <strong style={{ fontSize: "0.95rem" }}>{interruptAlert.interruption_reason}</strong>
          <p style={{ margin: "6px 0 0", fontSize: "0.85rem" }}>{interruptAlert.suggested_correction}</p>
          <button
            type="button"
            className="btn ghost"
            style={{ marginTop: 8, padding: "2px 8px", fontSize: "0.75rem", background: "var(--elev)", color: "var(--ink)" }}
            onClick={() => setInterruptAlert(null)}
          >
            Acknowledge & Dismiss
          </button>
        </div>
      )}

      <div style={{ marginTop: 14 }}>
        <strong style={{ fontSize: "0.85rem" }}>Meeting Notes & Transcript:</strong>
        <textarea
          rows={5}
          value={meetingTranscript}
          placeholder="Type a meeting note or click a sample phrase to check for conflicts..."
          onChange={(e) => {
            setMeetingTranscript(e.target.value);
            checkInterruption(e.target.value);
          }}
          style={{ width: "100%", marginTop: 6 }}
        />
      </div>
    </div>
  );
}

// ==========================================
// FEATURE: Accuracy & Validation Scorecard
// ==========================================
function AccuracyScorecard({ isOpen, onClose }) {
  const [scorecard, setScorecard] = useState(null);

  useEffect(() => {
    if (isOpen) {
      jsonFetch("/api/scorecard").then(setScorecard).catch(console.error);
    }
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div className="auth-overlay">
      <div className="auth-card scorecard-modal">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
          <div>
            <h3 style={{ margin: "0 0 2px" }}>Multi-Agent Accuracy Scorecard</h3>
            <p className="muted" style={{ margin: 0, fontSize: "0.82rem" }}>
              Reference metrics returned by the backend. These are not measurements of the current session.
            </p>
          </div>
          <button type="button" className="btn ghost" onClick={onClose}>✕</button>
        </div>

        {scorecard?.metrics?.length > 0 && (
          <p className="muted" style={{ margin: "0 0 12px", fontSize: "0.8rem" }}>
            Benchmark metrics returned for this scorecard.
          </p>
        )}

        <div className="metric-grid">
          {scorecard?.metrics?.map((m, i) => (
            <div key={i} className="metric-card">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <strong style={{ fontSize: "0.85rem" }}>{m.name}</strong>
                <span style={{ color: "var(--good)", fontWeight: 700, fontSize: "0.85rem" }}>{m.improvement}</span>
              </div>
              <div style={{ display: "flex", gap: 14, margin: "8px 0", fontSize: "0.85rem" }}>
                <div>
                  <span className="muted" style={{ display: "block", fontSize: "0.72rem" }}>With Validator</span>
                  <strong style={{ color: "var(--accent-text)" }}>{m.with_validator}%</strong>
                </div>
                <div>
                  <span className="muted" style={{ display: "block", fontSize: "0.72rem" }}>Without Validator</span>
                  <span className="muted">{m.without_validator}%</span>
                </div>
              </div>
              <p className="muted" style={{ margin: 0, fontSize: "0.75rem" }}>{m.detail}</p>
            </div>
          ))}
        </div>
        {scorecard && !scorecard.metrics?.length && (
          <p className="muted" style={{ margin: 0 }}>No benchmark metrics were returned.</p>
        )}
      </div>
    </div>
  );
}

// ==========================================
// MAIN APPLICATION COMPONENT
// ==========================================
export default function App() {
  const [theme, setTheme] = useTheme();
  const [user, setUser] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem("orbius_user"));
    } catch {
      return null;
    }
  });

  // Modal States
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [authMode, setAuthMode] = useState("login");
  const [authEmail, setAuthEmail] = useState("");
  const [authPassword, setAuthPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [authName, setAuthName] = useState("");
  const [authError, setAuthError] = useState(null);

  const [showCopilot, setShowCopilot] = useState(false);
  const [showScenarioModal, setShowScenarioModal] = useState(false);

  const [view, setView] = useState("landing");
  const [isTransitioning, setIsTransitioning] = useState(false);
  const [files, setFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [description, setDescription] = useState("");
  const [running, setRunning] = useState(false);
  const [sections, setSections] = useState([]);
  const [state, setState] = useState(null);
  const [events, setEvents] = useState([]);
  const [router, setRouter] = useState(null);
  const [tab, setTab] = useState("inbox"); // "inbox" | "timeline" | "calendar"
  const [calendarEvents, setCalendarEvents] = useState([]);
  const [selectedDate, setSelectedDate] = useState(() => new Date().toISOString().slice(0, 10));

  const [evidence, setEvidence] = useState(null);
  const [clock, setClock] = useState(null);
  const [banner, setBanner] = useState(null);
  const [simulate, setSimulate] = useState(false);
  const [toast, setToast] = useState(null);
  const [emailDispatchModal, setEmailDispatchModal] = useState(null);
  const emailDispatchOpen = Boolean(emailDispatchModal);

  useEffect(() => {
    if (!showAuthModal && !showScenarioModal && !emailDispatchOpen) return undefined;
    const previouslyFocused = document.activeElement;
    document.querySelector(".auth-overlay [data-modal-initial-focus]")?.focus({ preventScroll: true });
    const handleKeyDown = (event) => {
      if (event.key === "Escape") {
        if (emailDispatchOpen) setEmailDispatchModal(null);
        else if (showAuthModal) setShowAuthModal(false);
        else if (showScenarioModal) setShowScenarioModal(false);
        return;
      }
      if (event.key !== "Tab") return;
      const dialog = document.querySelector(".auth-overlay [role='dialog']");
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
  }, [showAuthModal, showScenarioModal, emailDispatchOpen]);

  const drafts = useMemo(
    () => (state?.tasks || []).filter((t) => t.type === "draft_email"),
    [state]
  );
  const alerts = state?.alerts || [];

  useEffect(() => {
    jsonFetch("/api/clock").then(setClock).catch(() => { });
    jsonFetch("/api/router").then(setRouter).catch(() => { });
    fetchCalendar();
    fetchUserSession();
  }, [user]);

  function showToast(msg) {
    setToast(msg);
    setTimeout(() => setToast(null), 3200);
  }

  async function fetchCalendar() {
    try {
      const data = await jsonFetch("/api/calendar");
      setCalendarEvents(data);
    } catch (e) {
      console.error(e);
    }
  }

  async function fetchUserSession() {
    try {
      const sess = await jsonFetch(`/api/session/${SESSION}`);
      if (sess && sess.sections && sess.sections.length > 0) {
        setState(sess);
        setSections(sess.sections);
        if (sess.chunks && sess.chunks.length > 0) {
          const unique = Array.from(
            new Map(sess.chunks.map((c) => [c.file_name, { name: c.file_name, modality: c.modality }])).values()
          );
          setFiles(unique);
        }
      }
    } catch (e) { }
  }

  async function resetWorkspace() {
    try {
      await jsonFetch("/api/session/reset", { method: "POST" });
      setFiles([]);
      setState(null);
      setSections([]);
      setEvents([]);
      setDescription("");
      showToast("Studio reset. Ready for your new project.");
    } catch (e) {
      setFiles([]);
      setState(null);
      setSections([]);
      setEvents([]);
      setDescription("");
    }
  }

  async function handleAuthSubmit(e) {
    e.preventDefault();
    setAuthError(null);
    try {
      if (authMode === "signup") {
        const res = await jsonFetch("/api/auth/signup", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email: authEmail, password: authPassword, name: authName }),
        });
        localStorage.setItem("orbius_user", JSON.stringify(res.user));
        localStorage.setItem("orbius_token", res.token);
        setUser(res.user);
        setShowAuthModal(false);
        showToast(`Welcome to Orbius, ${res.user.name}!`);
      } else {
        const res = await jsonFetch("/api/auth/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email: authEmail, password: authPassword }),
        });
        localStorage.setItem("orbius_user", JSON.stringify(res.user));
        localStorage.setItem("orbius_token", res.token);
        setUser(res.user);
        setShowAuthModal(false);
        showToast(`Welcome back, ${res.user.name}!`);
      }
    } catch (err) {
      setAuthError(err.message);
    }
  }

  function handleLogout() {
    setUser(null);
    localStorage.removeItem("orbius_user");
    localStorage.removeItem("orbius_token");
    showToast("Logged out successfully.");
  }

  function enterStudio() {
    if (view === "app") return;
    setIsTransitioning(true);
    setTimeout(() => {
      setView("app");
      setTimeout(() => {
        setIsTransitioning(false);
      }, 400);
    }, 280);
  }

  function goToHome() {
    if (view === "landing") return;
    setIsTransitioning(true);
    setTimeout(() => {
      setView("landing");
      setTimeout(() => {
        setIsTransitioning(false);
      }, 300);
    }, 200);
  }

  async function onUpload(list) {
    if (!list || list.length === 0) return;
    setUploading(true);
    try {
      const body = new FormData();
      body.append("session_id", SESSION);
      [...list].forEach((f) => body.append("files", f));
      const data = await jsonFetch("/api/upload", { method: "POST", body });
      setFiles(data.files || []);
      setState(null);
      setSections([]);
      showToast(`Attached ${data.files.length} document(s). Ready to generate BRD.`);
    } catch (err) {
      console.error(err);
      showToast(`Upload failed: ${err.message}`);
    } finally {
      setUploading(false);
    }
  }

  async function removeFile(fileName) {
    try {
      const data = await jsonFetch(`/api/upload/${SESSION}/${encodeURIComponent(fileName)}`, { method: "DELETE" });
      setFiles(data.files || []);
      showToast(`Removed "${fileName}" from the active source list. Server-side cleanup is not confirmed.`);
      return true;
    } catch (err) {
      showToast(`Unable to remove "${fileName}": ${err.message}`);
      return false;
    }
  }

  async function clearAllFiles() {
    try {
      await jsonFetch(`/api/upload/${SESSION}`, { method: "DELETE" });
      setFiles([]);
      showToast("Cleared the active source list. Server-side cleanup is not confirmed.");
    } catch (err) {
      showToast(`Unable to clear the source list: ${err.message}`);
    }
  }

  async function openFilePreview(fileName) {
    try {
      return await jsonFetch(`/api/upload/${SESSION}/preview/${encodeURIComponent(fileName)}`);
    } catch (err) {
      showToast(`Preview: ${err.message || "File preview unavailable"}`);
      return null;
    }
  }

  async function generate() {
    if (files.length === 0 && !description.trim()) {
      showToast("Please upload project documents or enter a project note first.");
      return;
    }
    setRunning(true);
    setSections([]);
    setEvents([]);
    setView("app");
    const token = localStorage.getItem("orbius_token");
    const headers = token ? { "x-user-id": token } : {};
    const url = `/api/generate?session_id=${SESSION}&project_description=${encodeURIComponent(description)}`;

    const es = new EventSource(url);
    es.addEventListener("section", (e) => {
      const payload = JSON.parse(e.data);
      setSections((prev) => {
        const next = prev.filter((s) => s.id !== payload.section.id);
        return [...next, payload.section];
      });
      if (payload.router) setRouter(payload.router);
    });
    es.addEventListener("delegation", (e) => {
      const payload = JSON.parse(e.data);
      setEvents((prev) => [...prev, payload.event]);
    });
    es.addEventListener("router", (e) => setRouter(JSON.parse(e.data)));
    es.addEventListener("complete", (e) => {
      const payload = JSON.parse(e.data);
      setState(payload.state);
      setSections(payload.state.sections);
      setRunning(false);
      fetchCalendar();
      es.close();
    });
    es.onerror = () => {
      setRunning(false);
      showToast("Generation stream complete.");
      es.close();
    };
  }

  function openEvidence(findingIdOrObj, sourceChunk) {
    if (findingIdOrObj && typeof findingIdOrObj === "object") {
      if (!sourceChunk) return;
      setEvidence({
        citation: true,
        citationUnverified: true,
        confidence: findingIdOrObj.confidence,
        chunk: sourceChunk,
      });
      return;
    }
    const finding = (state?.findings || []).find((f) => f.id === findingIdOrObj);
    if (!finding) return;
    const chunk = (state?.chunks || []).find((c) => c.source_id === finding?.source_id);
    setEvidence({ finding, chunk, findingId: finding.id });
  }

  function openCopilotEvidence(citation, sourceChunk) {
    setShowCopilot(false);
    openEvidence(citation, sourceChunk);
  }

  async function resolveConflict(id, keep) {
    const next = await jsonFetch(`/api/conflicts/resolve?session_id=${SESSION}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ conflict_id: id, keep, note: "Resolved in human review." }),
    });
    setState(next);
    setSections(next.sections);
  }

  async function act(taskObj, action) {
    const taskId = typeof taskObj === "object" ? taskObj.id : taskObj;
    let actionResponse;
    try {
      actionResponse = await jsonFetch(`/api/tasks/${taskId}/${action}`, { method: "POST" });
      if (action === "approved") {
        const recipient = (typeof taskObj === "object" && taskObj.payload?.recipient) || "Client / Team Lead";
        const subject = (typeof taskObj === "object" && taskObj.payload?.subject) || "Requirement Action Item Update";
        const body = (typeof taskObj === "object" && taskObj.payload?.body) || "Action item approved and recorded.";
        const dispatch = actionResponse?.dispatch;
        const sent = dispatch?.sent === true;
        setEmailDispatchModal({
          recipient: dispatch?.target || recipient,
          subject,
          body,
          sent,
          method: dispatch?.method || "unconfirmed",
          actionConfirmed: Boolean(actionResponse) &&
            actionResponse.success !== false &&
            actionResponse.ok !== false &&
            !actionResponse.error,
        });
        showToast(sent
          ? "Task approved and email delivery confirmed."
          : dispatch?.sent === false
            ? "Task approved; email was not sent."
            : "Task approved; email delivery is unconfirmed.");
      }
    } catch (err) {
      showToast(`Could not update task: ${err.message}`);
      return;
    }

    try {
      const next = await jsonFetch(`/api/session/${SESSION}`);
      setState(next);
      fetchCalendar();
    } catch (err) {
      showToast(`Task action completed, but the workspace refresh failed: ${err.message}`);
      return;
    }
    if (action !== "approved") showToast("Task dismissed.");
  }

  async function ff() {
    const data = await jsonFetch("/api/clock/fast-forward?days=30", { method: "POST" });
    setClock(data);
    if (data.fired?.length) {
      setBanner(data.fired[0]);
      showToast("Alert fired. A follow-up draft landed in the Inbox.");
    }
    setState((s) => ({ ...s, tasks: data.tasks, alerts: data.alerts }));
    fetchCalendar();
  }

  async function toggleQuota(on) {
    const data = await jsonFetch(`/api/router/simulate?on=${on}`, { method: "POST" });
    setSimulate(on);
    setRouter(data);
  }

  // Calendar Days computation
  const daysInMonth = useMemo(() => {
    const now = clock?.now ? new Date(clock.now) : new Date();
    const year = now.getFullYear();
    const month = now.getMonth();
    const count = new Date(year, month + 1, 0).getDate();
    return Array.from({ length: count }, (_, i) => {
      const d = i + 1;
      const dateStr = `${year}-${String(month + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
      const evs = calendarEvents.filter((ev) => ev.date === dateStr);
      const hasUrgent = evs.some((e) => e.urgency === "urgent");
      const hasWarning = evs.some((e) => e.urgency === "due_tomorrow");
      const hasNormal = evs.some((e) => e.urgency === "normal");
      return { day: d, dateStr, evs, hasUrgent, hasWarning, hasNormal };
    });
  }, [clock, calendarEvents]);

  const selectedDateEvents = useMemo(() => {
    return calendarEvents.filter((e) => e.date === selectedDate);
  }, [calendarEvents, selectedDate]);

  const [studioCenterTab, setStudioCenterTab] = useState("brd"); // "brd" | "prototype" | "tests" | "ripple" | "meeting" | "trace"
  const [showScorecard, setShowScorecard] = useState(false);

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand" onClick={goToHome} style={{ cursor: "pointer" }}>
          <img src="/orbius-logo.png" alt="Orbius" className="brand-logo-img" />
          <div>
            <b>Orbius</b>
            <span>Evidence-first requirements workspace</span>
          </div>
        </div>
        <div className="top-actions">
          <span className="model-pill">
            <span className={`dot ${router?.fallback ? "warn" : ""}`} />
            {router?.active_model
              ? `${routingStatusLabel(router)} · ${router.active_model}`
              : routingStatusLabel(router)}
          </span>
          <button
            className="icon-btn theme-toggle"
            aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          >
            <Icon name={theme === "dark" ? "sun" : "moon"} size={16} />
            {theme === "dark" ? "Light" : "Dark"}
          </button>

          <button
            type="button"
            className="btn ghost"
            style={{ fontSize: "0.8rem" }}
            onClick={() => setShowScorecard(true)}
            title="View static validation benchmarks"
          >
            Scorecard
          </button>

          {user ? (
            <div className="user-badge">
              <span>{user.name}</span>
              <button className="btn ghost" style={{ padding: "2px 6px", fontSize: "0.75rem" }} onClick={handleLogout}>
                Sign Out
              </button>
            </div>
          ) : (
            <button className="btn primary" onClick={() => setShowAuthModal(true)}>
              Sign In / Sign Up
            </button>
          )}
          {view === "landing" ? (
            <button className="btn primary" onClick={enterStudio}>
              Open workspace
            </button>
          ) : (
            <div style={{ display: "flex", gap: 8 }}>
              <button
                type="button"
                className="btn ghost"
                style={{ color: "var(--accent-text)" }}
                onClick={() => setShowScenarioModal(true)}
                title="Simulate budget cuts, compressed timelines, or scope trade-offs"
              >
                What-if
              </button>
              <button
                type="button"
                className="btn ghost"
                onClick={resetWorkspace}
                title="Clear current session and start a new project"
              >
                New run
              </button>
              <button type="button" className="btn ghost" onClick={goToHome}>
                Home
              </button>
            </div>
          )}
        </div>
      </header>

      {/* Accuracy Scorecard Modal */}
      <AccuracyScorecard isOpen={showScorecard} onClose={() => setShowScorecard(false)} />

      {/* Page Opening / Switching Animation Curtain */}
      <div className={`page-portal-curtain ${isTransitioning ? "active" : ""}`}>
        <div className="curtain-glow" />
      </div>

      {view === "landing" ? (
        <main className={`landing ${isTransitioning ? "transition-exit" : "transition-enter"}`}>
          <section className="landing-hero" aria-labelledby="landing-title">
            <div className="landing-hero__copy">
              <p className="landing-kicker"><span /> OBSERVATORY / INTELLIGENCE IN MOTION</p>
              <h1 id="landing-title" className="landing-title">
                <span className="landing-title__line">Fragmented</span>
                <span className="landing-title__line landing-title__line--accent">information.</span>
                <span className="landing-title__line">Decisions you</span>
                <span className="landing-title__line">can <em>trace.</em></span>
              </h1>
              <p className="landing-hero__lede">
                Orbius turns project signals scattered across documents, conversations, images, and spreadsheets into requirements your team can inspect, challenge, and act on.
              </p>
              <div className="landing-hero__actions">
                <button className="btn primary enter-studio-btn" onClick={enterStudio}>
                  <span>Enter the studio</span>
                  <Icon name="arrowRight" className="btn-arrow" />
                </button>
                <span className="landing-hero__aside">A requirements workspace built around evidence.</span>
              </div>
              <div className="landing-hero__metadata">
                <span>01 <i /> MULTIMODAL SOURCES</span>
                <span>02 <i /> STRUCTURED REQUIREMENTS</span>
                <span>03 <i /> TRACEABLE DECISIONS</span>
              </div>
            </div>
            <aside className="landing-hero__visual" aria-label="Orbius transforms source fragments into traceable decisions">
              <div className="landing-hero__visual-top">
                <span>THE ORBIUS METHOD</span>
                <span>CONCEPTUAL VIEW</span>
              </div>
              <FragmentConvergence />
            </aside>
            <div className="landing-hero__index" aria-hidden="true">ORBIUS / 01</div>
          </section>

          <div className="landing-flow-index" aria-label="From source to decision">
            <span>THE TRANSFORMATION</span>
            <span>Source material <i>→</i></span>
            <span>Requirements <i>→</i></span>
            <span>Evidence <i>→</i></span>
            <span>Decisions</span>
          </div>

          <div className="landing-story">
            <ScrollReveal className="landing-story__section landing-story__section--sources">
              <div className="landing-story__label">
                <span>01</span>
                <span>INGEST / MANY FORMATS</span>
              </div>
              <div className="landing-story__content">
                <p className="landing-story__eyebrow">Start with what you have</p>
                <h2>Project truth rarely arrives in one tidy document.</h2>
                <p>
                  Briefs, call notes, spreadsheets, screenshots, and voice recordings each hold part of the picture. Bring them together without losing where each detail came from.
                </p>
                <div className="story-source-lines" aria-hidden="true">
                  <span><b>DOC</b><i>Product brief · 12 pages</i><small>Scope, goals, constraints</small></span>
                  <span><b>AUD</b><i>Discovery call · 08:42</i><small>Needs, dates, open questions</small></span>
                  <span><b>IMG</b><i>Checkout sketch · 03 screens</i><small>States, handoffs, edge cases</small></span>
                </div>
              </div>
            </ScrollReveal>

            <ScrollReveal className="landing-story__section landing-story__section--requirements">
              <div className="landing-story__label">
                <span>02</span>
                <span>STRUCTURE / REVIEW</span>
              </div>
              <div className="landing-story__content">
                <p className="landing-story__eyebrow">Make the shape of the work visible</p>
                <h2>Turn scattered signals into a document your team can reason about.</h2>
                <p>
                  Organize generated requirements, risks, conflicts, diagrams, tests, and prototypes in one working surface. Keep uncertainty visible so people know what needs review.
                </p>
                <div className="story-document" aria-label="Illustrative requirements excerpt">
                  <div className="story-document__top"><span>REQUIREMENTS / REVIEW COPY</span><span>OPEN QUESTION</span></div>
                  <div className="story-document__row"><b>01</b><span>Customer identity must persist across checkout steps.</span><i>Requirement</i></div>
                  <div className="story-document__row"><b>02</b><span>Delivery timing differs between the brief and call notes.</span><i className="is-review">Needs review</i></div>
                  <div className="story-document__row"><b>03</b><span>Each generated claim remains linked to its evidence.</span><i>Traceable</i></div>
                </div>
                <p className="landing-story__caption">Illustrative content · not generated project data.</p>
              </div>
            </ScrollReveal>

            <ScrollReveal className="landing-story__section landing-story__section--evidence">
              <div className="landing-story__label">
                <span>03</span>
                <span>TRACE / DECIDE</span>
              </div>
              <div className="landing-story__content">
                <p className="landing-story__eyebrow">Make every decision inspectable</p>
                <h2>Follow a requirement back to the words that support it.</h2>
                <p>
                  Inspect source excerpts, surface disagreement, and resolve conflicts with a clear review trail. Decisions should be explainable to the people who have to trust them.
                </p>
                <div className="story-trace">
                  <div className="story-trace__claim">
                    <span>GENERATED REQUIREMENT</span>
                    <strong>Checkout must retain the customer’s selected delivery window.</strong>
                  </div>
                  <div className="story-trace__connector" aria-hidden="true"><span /></div>
                  <blockquote>
                    <span>SOURCE EXCERPT / DISCOVERY NOTES</span>
                    “If someone changes the payment method, keep the delivery slot they already picked.”
                  </blockquote>
                </div>
                <p className="landing-story__caption">Illustrative trace · real workspaces show only evidence returned by the application.</p>
              </div>
            </ScrollReveal>
          </div>

          <section className="landing-capabilities" aria-labelledby="capabilities-title">
            <div>
              <p className="landing-story__eyebrow">ONE WORKSPACE / MANY LENSES</p>
              <h2 id="capabilities-title">Stay with the work from first brief to review.</h2>
            </div>
            <div className="landing-capabilities__list">
              <span>Requirements & conflict review</span>
              <span>Evidence & source previews</span>
              <span>Mermaid diagrams</span>
              <span>Interactive prototype</span>
              <span>Gherkin test suite</span>
              <span>Impact analysis & scenarios</span>
              <span>Meeting signals & decision trace</span>
              <span>Exports & follow-up actions</span>
            </div>
          </section>

          <ScrollReveal as="section" className="landing-endnote">
            <p className="landing-story__eyebrow">A BETTER WAY TO HOLD COMPLEXITY</p>
            <h2>Build decisions with their evidence still attached.</h2>
            <button className="btn primary enter-studio-btn" onClick={enterStudio}>
              <span>Open Orbius studio</span>
              <Icon name="arrowRight" className="btn-arrow" />
            </button>
          </ScrollReveal>
        </main>
      ) : (
        <main className={`workspace ${isTransitioning ? "transition-exit" : "transition-enter"}`}>
          {banner && (
            <div className="banner">
              <strong style={{ color: "var(--danger)" }}>Alert Fired!</strong> {banner.reminder_message}{" "}
              <span className="muted">({banner.original_phrase})</span>
            </div>
          )}
          <aside className="workspace-sidebar">
            <SourceVault
              files={files}
              uploading={uploading}
              onUpload={onUpload}
              onPreviewFile={openFilePreview}
              onRemoveFile={removeFile}
              onClearFiles={clearAllFiles}
              description={description}
              onDescriptionChange={setDescription}
              running={running}
              onGenerate={generate}
              VoiceRecorder={VoiceRecorder}
            />
            <AnalysisTrace
              events={events.length ? events : state?.events || []}
              running={running}
              router={router}
              routerStatus={routingStatusLabel(router)}
              clock={clock}
              simulate={simulate}
              onFastForward={ff}
              onToggleSimulation={() => toggleQuota(!simulate)}
              formatAgentName={formatAgentName}
            />
          </aside>

          <RequirementsDocument
            activeTab={studioCenterTab}
            onTabChange={setStudioCenterTab}
            sections={sections}
            state={state}
            running={running}
            theme={theme}
            views={{
              prototype: <InteractivePrototype findings={state?.findings || []} chunks={state?.chunks || []} />,
              tests: <GherkinTestCases sessionId={SESSION} />,
              ripple: <ImpactRippleGraph sessionId={SESSION} />,
              meeting: <LiveMeetingMode sessionId={SESSION} onNewFinding={() => { }} />,
              trace: <DecisionTraceTimeline events={state?.events || events} router={router} state={state} />,
            }}
            onOpenEvidence={openEvidence}
            onResolveConflict={resolveConflict}
            selectedFindingId={evidence?.findingId}
          />

          <ActionCenter
            tab={tab}
            onTabChange={setTab}
            days={daysInMonth}
            selectedDate={selectedDate}
            onSelectDate={setSelectedDate}
            selectedEvents={selectedDateEvents}
            drafts={drafts}
            alerts={alerts}
            state={state}
            sessionId={SESSION}
            onAct={act}
          />
        </main>
      )}

      {/* FEATURE 2: Floating Button & Copilot Drawer */}
      {view === "app" && (
        <button
          type="button"
          className="copilot-floating-btn"
          onClick={() => setShowCopilot(!showCopilot)}
          title="Open BRD AI Copilot"
        >
          <span><Icon name="message" /> Ask Copilot</span>
          <Icon name="sparkle" className="copilot-sparkle" />
        </button>
      )}

      <CopilotDrawer
        isOpen={showCopilot}
        onClose={() => setShowCopilot(false)}
        onOpenEvidence={openCopilotEvidence}
        sourceChunks={state?.chunks || []}
      />

      {/* FEATURE 5: What-If Scenario Simulator Modal */}
      <ScenarioSimulatorModal
        isOpen={showScenarioModal}
        onClose={() => setShowScenarioModal(false)}
      />

      {/* Email Dispatch Confirmation Modal */}
      {emailDispatchModal && (
        <div className="auth-overlay" onClick={() => setEmailDispatchModal(null)}>
          <div className="auth-card" role="dialog" aria-modal="true" aria-labelledby="draft-approval-title" style={{ width: "min(520px, 94vw)" }} onClick={(e) => e.stopPropagation()}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
              <h3 id="draft-approval-title" style={{ margin: 0, display: "flex", alignItems: "center", gap: 8, color: "var(--ink)" }}>
                Task approval result
              </h3>
              <button className="file-remove-btn" data-modal-initial-focus onClick={() => setEmailDispatchModal(null)} aria-label="Close approval details">✕</button>
            </div>

            <div style={{ background: "color-mix(in srgb, var(--elev-2) 80%, transparent)", padding: 14, borderRadius: 14, border: "1px solid var(--line)", fontSize: "0.85rem", display: "flex", flexDirection: "column", gap: 8 }}>
              <div><strong style={{ color: "var(--muted)" }}>Prepared for:</strong> {emailDispatchModal.recipient}</div>
              <div><strong style={{ color: "var(--muted)" }}>Subject:</strong> {emailDispatchModal.subject}</div>
              <div><strong style={{ color: "var(--muted)" }}>Status:</strong> <span className={emailDispatchModal.sent ? "status-confirmed" : "status-unconfirmed"}>
                {!emailDispatchModal.actionConfirmed
                  ? "Approval not confirmed"
                  : emailDispatchModal.sent
                    ? `Delivery confirmed · ${emailDispatchModal.method}`
                    : emailDispatchModal.method === "simulated"
                      ? "Approved · dispatch simulated · not sent"
                      : "Approved · delivery unconfirmed"}
              </span></div>
              <hr style={{ border: "none", borderTop: "1px solid var(--line)", margin: "4px 0" }} />
              <div style={{ whiteSpace: "pre-wrap", lineHeight: 1.5, background: "var(--bg)", padding: 12, borderRadius: 10, border: "1px solid var(--line)" }}>
                {emailDispatchModal.body}
              </div>
            </div>

            <div className="dispatch-note">
              {!emailDispatchModal.actionConfirmed
                ? "The approval request did not return a confirmation. Refresh the task state before relying on this result."
                : emailDispatchModal.sent
                  ? "The backend confirmed delivery for this task."
                  : emailDispatchModal.method === "simulated"
                    ? "The task was approved, but the backend reports that no email was sent. Configure a dispatch provider to enable delivery."
                    : "The task was approved, but the response did not confirm whether an email was delivered."}
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 16 }}>
              <button className="btn primary" onClick={() => setEmailDispatchModal(null)}>Done</button>
            </div>
          </div>
        </div>
      )}

      {/* Auth Modal */}
      {showAuthModal && (
        <div className="auth-overlay">
          <div className="auth-card" role="dialog" aria-modal="true" aria-label="Account sign in">
            <div className="auth-tabs">
              <button
                data-modal-initial-focus
                className={authMode === "login" ? "active" : ""}
                onClick={() => {
                  setAuthMode("login");
                  setAuthError(null);
                }}
              >
                Log In
              </button>
              <button
                className={authMode === "signup" ? "active" : ""}
                onClick={() => {
                  setAuthMode("signup");
                  setAuthError(null);
                }}
              >
                Sign Up
              </button>
            </div>

            {authError && (
              <div style={{ color: "var(--danger)", fontSize: "0.85rem", marginBottom: 12 }}>
                {authError}
              </div>
            )}

            <form onSubmit={handleAuthSubmit}>
              {authMode === "signup" && (
                <div style={{ marginBottom: 12 }}>
                  <label className="muted" style={{ fontSize: "0.8rem", display: "block", marginBottom: 4 }}>Full Name</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Jane Doe"
                    value={authName}
                    onChange={(e) => setAuthName(e.target.value)}
                  />
                </div>
              )}
              <div style={{ marginBottom: 12 }}>
                <label className="muted" style={{ fontSize: "0.8rem", display: "block", marginBottom: 4 }}>Email Address</label>
                <input
                  type="email"
                  required
                  placeholder="name@company.com"
                  value={authEmail}
                  onChange={(e) => setAuthEmail(e.target.value)}
                />
              </div>
              <div style={{ marginBottom: 20 }}>
                <label className="muted" style={{ fontSize: "0.8rem", display: "block", marginBottom: 4 }}>Password</label>
                <div style={{ position: "relative", display: "flex", alignItems: "center" }}>
                  <input
                    type={showPassword ? "text" : "password"}
                    required
                    placeholder="••••••••"
                    value={authPassword}
                    onChange={(e) => setAuthPassword(e.target.value)}
                    style={{ width: "100%", paddingRight: 40 }}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    style={{
                      position: "absolute",
                      right: 10,
                      background: "transparent",
                      border: "none",
                      cursor: "pointer",
                      fontSize: "1.1rem",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      padding: 4,
                      color: "var(--muted)",
                    }}
                    title={showPassword ? "Hide password" : "Show password"}
                  >
                    {showPassword ? "Hide" : "Show"}
                  </button>
                </div>
              </div>
              <div className="row" style={{ justifyContent: "flex-end" }}>
                <button type="button" className="btn ghost" onClick={() => setShowAuthModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn primary">
                  {authMode === "signup" ? "Create Account" : "Log In"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      <EvidenceInspector evidence={evidence} onClose={() => setEvidence(null)} />
      {toast && <div className="drawer" style={{ left: 16, right: "auto" }}>{toast}</div>}
    </div>
  );
}
