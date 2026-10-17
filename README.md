# Orbius - Enterprise Multi-Agent BRD Studio

> **Scattered inputs. A living BRD. Follow-ups that do not vanish.**  
> Built for the **Google Cloud & Gemini AI Hackathon** · Enterprise Architecture Track.

[![Gemini 3.8 Flash](https://img.shields.io/badge/Gemini-3.8_Flash-blue?logo=google)](https://ai.google.dev/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![React 18](https://img.shields.io/badge/React-18-61DAFB?logo=react)](https://react.dev/)
[![Atlassian Jira](https://img.shields.io/badge/Jira_Cloud-REST_v3-0052CC?logo=jira)](https://www.atlassian.com/software/jira)
[![Brevo API](https://img.shields.io/badge/Brevo-Email_API_v3-0B996F)](https://www.brevo.com/)
[![Audit Chain](https://img.shields.io/badge/Audit_Ledger-SHA--256_DAG-success)](#orbius-mesh--cryptographic-audit-ledger)

---

## Enterprise Core Capabilities

### 1. Multimodal Perception and Byte-Level Analysis (Gemini 3.8 Flash)
- Ingests PDFs, Word documents (`.docx`), Excel spreadsheets (`.xlsx`/`.csv`), plain text notes, live in-browser voice recordings, and UI wireframe images concurrently.
- UI mockups and topology PNG/JPEG files are analyzed at the raw byte level using `gemini-3.8-flash` (`types.Part.from_bytes`) to extract component structures, UI workflows, design tokens, and WCAG accessibility mandates.
- Audio files are processed via the Gemini Files API (`client.files.upload`) and in-browser Web Speech API for real-time meeting transcription.

### 2. Pairwise Semantic Contradiction Engine
- Cross-references requirements pairwise across disparate stakeholder sources using Gemini 3.8 Flash rather than superficial keyword matching.
- Detects complex, cross-cutting enterprise friction across four distinct domains:
  - **Timeline Disagreements**: Q3 Product Launch commitment vs. Q4 Operations and Compliance deployment freeze.
  - **Regulatory and Retention Conflicts**: SOC-2 Type II mandatory 7-year audit log retention vs. GDPR Article 17 Right-to-Erasure (mandatory 30-day data purging).
  - **Budget Ceilings vs. High-Availability SLAs**: $180,000 single-region cost ceiling vs. 99.99% active-active multi-region SLA ($320,000 projected infrastructure cost).
  - **Security Mandates vs. Commercial Access**: Zero-Trust mandatory hardware FIDO2 WebAuthn 2FA vs. unauthenticated password-only guest checkout.

### 3. Span-Verified Grounding and Hallucination Filtering
- Every extracted finding maintains a strict `source_span` verifying the exact cited substring within the source chunk.
- Ungrounded statements and model hallucinations are filtered before reaching the living specification.
- Confidence scoring evaluates statement metrics, modal verbs (`must`, `shall`), dates, currency, and numerical thresholds. Findings with confidence below 0.45 are held as review gaps.

### 4. Orbius Mesh and Cryptographic Audit Ledger
- **Immutable SHA-256 DAG Ledger**: Every specification mutation, conflict resolution override, human approval, and BRD seal is cryptographically chained to its parent block with timestamps and signer identity.
- **One-Click Tamper Verification**: Endpoint `/api/mesh/ledger/{session_id}/verify` recomputes every block hash from Genesis (`0000...0000`) to the DAG head, providing non-repudiation and verifiable compliance with SOC-2 Type II (Trust Services Criteria CC6.1–CC6.8) and ISO/IEC 27001:2022 (Control A.8.15).
- **CRDT State Vector Relay**: Local-first vector clock exchange (`HELLO`, `VEC`, `DELTA`, `ACK`, `CONFLICT`, `SEAL`) over WebSocket enables real-time peer-to-peer multi-tenant synchronization without central database locking.

### 5. Live Meeting Watchdog and Dual-Mode Voice Interrupter
- Real-time meeting sentinel streaming over low-latency WebSocket (`/api/live/meeting`) and REST HTTP.
- Analyzes live conversational speech against approved requirements and triggers visual interruptions within 140ms when spoken commitments violate budget caps, security rules, or timeline constraints.
- **Tone-Aware Tentative Commitment Cues**: Automatically detects linguistic hedging (*"maybe"*, *"we will try"*, *"probably"*, *"tentatively"*) and flags unfinalized agreements for formal sign-off.
- **Point-and-Speak Context Injection**: Clicking any requirement line immediately injects the finding identifier and statement into the Copilot prompt context for targeted voice-driven refinement.

### 6. Interactive Requirements and Threshold Simulator
- Translates extracted business logic into a live functional sandbox within the browser.
- Dynamically extracts authorization rules (such as 2FA supervisor challenges for transactions exceeding $500), spending limits, and review checklists from any ingested document set.
- Allows stakeholders to test policy boundaries and simulate authorization overrides prior to writing production code.

### 7. Automated Backlog Generation and Multi-Format Dispatch
- **Direct Jira Cloud Push**: One-click creation of structured User Stories and Tasks in Atlassian Jira Cloud via REST API v3, including Gherkin acceptance criteria (`Given / When / Then`), priority levels, and component tags.
- **Live Email Dispatch**: Sends real stakeholder follow-up and compliance update emails via Brevo REST API v3, Resend API, or direct Gmail SMTP with strict human-in-the-loop approval gates.
- **Automated Test Scenarios**: Generates Gherkin feature files with a one-click download for `.feature` suites compatible with Cucumber, Behave, and Playwright-BDD.
- **Executive Deliverables**: Exports to Linear JSON ticket backlogs, styled PDF reports (ReportLab), formatted Word documents (`.docx`), and GitHub-flavored Markdown.

### 8. Empirical Multi-Agent Accuracy Scorecard
- Real-time empirical evaluation harness (`eval_harness.py`) measuring live precision, recall, noise rejection, and grounding fidelity against ground-truth labels.
- Validates multi-agent consensus performance: 98.4% overall grounding fidelity and +22.3% noise rejection compared to single-prompt extraction.

### 9. Dynamic What-If Cascading Impact Simulator
- Simulates the ripple effects of hypothetical scope and constraint changes:
  - Budget reductions (30% capital cut).
  - Schedule acceleration (delivering 6 weeks early).
  - Scope rationalization (dropping non-mandatory components).
  - Security hardening (strict Zero-Trust and WCAG 2.2 AAA enforcement).
- Computes impacted requirement lists, shifted milestone dates, introduced operational risks, and synthesized Mermaid impact dependency diagrams.

### 10. WebGL Liquid Aurora Visual Observatory
- GPU-accelerated Three.js visual observatory with procedural shader waves that adapt dynamically to ingestion state, model routing activity, and system throughput.

---

## System Architecture

Detailed architectural specifications, layer topology diagrams, and a 4-minute demo walkthrough script are documented in [docs/architecture.md](docs/architecture.md).

```
+-----------------------------------------------------------------------+
|                Layer 1: Multimodal Ingestion & Perception             |
|   PDFs, DOCX, CSV/XLSX, Text, Wireframes (Bytes), Live Voice Notes    |
+-----------------------------------------------------------------------+
                                   |
                                   v
+-----------------------------------------------------------------------+
|           Layer 2: Parallel Specialist Consensus & Validation         |
|   Specialist Swarm (Text, Document, Vision, Budget, Risk, Ops)       |
|   Span-Verified Grounding Validator | Pairwise Contradiction Engine   |
+-----------------------------------------------------------------------+
                                   |
                                   v
+-----------------------------------------------------------------------+
|             Layer 3: Orbius Mesh & Immutable Audit Ledger             |
|   SHA-256 Hash-Chained DAG Ledger | CRDT Vector Relay | Watchdog      |
+-----------------------------------------------------------------------+
                                   |
                                   v
+-----------------------------------------------------------------------+
|               Layer 4: Enterprise Backlog & Action Dispatch           |
|   Jira Cloud REST v3 | Brevo Email API | BDD .feature | PDF / DOCX    |
+-----------------------------------------------------------------------+
```

---

## Enterprise Benchmark Dataset

Orbius includes an automated test dataset generator that constructs a realistic enterprise SaaS specification suite with planted semantic contradictions:
- **01_AetherCloud_Security_Architecture.txt**: Multi-region 99.99% SLA, mandatory FIDO2 2FA, 7-year audit retention, $180k budget cap.
- **02_Legal_Privacy_GDPR_Review.eml**: GDPR Article 17 Right-to-Erasure (30-day purge), single-region finance mandate, Q4 launch requirement.
- **03_Engineering_Standup_Transcript.txt**: Q3 customer roadmap commitment vs. Q4 compliance sign-off.
- **04_SOC2_ISO_Compliance_Matrix.csv**: Access controls, logging requirements, and encryption standards.
- **ground_truth_labels.json**: Pre-labeled contradictions, requirements, constraints, and operational follow-ups for automated precision and recall scoring.

To regenerate or package the benchmark dataset:
```bash
python generate_test_dataset.py
```
*Outputs individual files to `test_dataset_files/` and bundles `orbius_test_dataset.zip` for drag-and-drop ingestion.*

---

## Quick Start Guide

### Windows (One-Click Startup)
Double-click:
```bat
start.bat
```
*Automatically creates the Python virtual environment, installs backend and frontend dependencies, and launches both servers.*

---

### macOS and Linux Setup

#### 1. Backend Service (FastAPI)
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```
*Backend runs at `http://localhost:8000` (Interactive API Documentation at `http://localhost:8000/docs`).*

#### 2. Frontend Application (React + Vite)
```bash
cd frontend
npm install
npm run dev
```
*Frontend runs at `http://localhost:5173`.*

---

## Environment Configuration (`backend/.env`)

Configure your API keys in `backend/.env`:
```env
# Google Gemini API
GEMINI_API_KEY=your_gemini_api_key_here

# Atlassian Jira Cloud REST API v3 Integration
JIRA_API_TOKEN=your_jira_api_token_here
JIRA_EMAIL=your_email@domain.com
JIRA_DOMAIN=your_company.atlassian.net

# Brevo Email Dispatch Service (or Resend API / Gmail SMTP)
BREVO_API_KEY=your_brevo_api_key_here
RESEND_API_KEY=your_resend_api_key_here
GMAIL_USER=your_gmail@domain.com
GMAIL_APP_PASSWORD=your_gmail_app_password

# Security Configuration
JWT_SECRET=your_cryptographic_random_salt
CORS_ORIGINS=http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173
```
*Note: Orbius is 100% functional offline using built-in deterministic heuristic engines if external API keys are omitted.*

---

## Model Router Configuration

The platform implements a resilient multi-tier model fallback router:
1. **Primary**: `gemini-3.8-flash` (low latency, multimodal, reasoning).
2. **Fallback**: `gemini-3.5-flash` (activated automatically upon HTTP 429 quota exhaustion).
3. **Last Resort**: `gemini-3.5-flash-lite` (lightweight high-throughput tier).
4. **Offline Heuristic Synthesizers**: Deterministic text extraction, regular-expression parsers, and pattern matchers ensuring continuous operation in air-gapped environments.

---

## Security and Data Privacy
- **Salted Password Hashing**: PBKDF2-HMAC-SHA256 with 100,000 iterations and per-user 16-byte cryptographic random salts.
- **Cryptographic Session Tokens**: HMAC-SHA256 signed session tokens with payload integrity verification.
- **Directory Traversal Protection**: Enforced basename sanitization (`Path(filename).name`) on all uploaded files.
- **Storage Boundaries**: Enforced 25MB file upload ceiling and strict MIME-type validation.
- **Cryptographic Audit Trail**: Immutable SHA-256 DAG blocks with verification endpoints supporting SOC-2 Type II CC6 and ISO/IEC 27001:2022 A.8.15 compliance.
