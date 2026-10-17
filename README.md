# 🌌 Orbius - Enterprise Multi-Agent BRD Studio

> **Scattered inputs. A living BRD. Follow-ups that do not vanish.**  
> Built for the **Google Cloud & Gemini AI Hackathon** · Enterprise Architecture Track.

[![Gemini 3.8 Flash](https://img.shields.io/badge/Gemini-3.8_Flash-blue?logo=google)](https://ai.google.dev/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![React 18](https://img.shields.io/badge/React-18-61DAFB?logo=react)](https://react.dev/)
[![Atlassian Jira](https://img.shields.io/badge/Jira_Cloud-REST_v3-0052CC?logo=jira)](https://www.atlassian.com/software/jira)
[![Brevo API](https://img.shields.io/badge/Brevo-Email_API_v3-0B996F)](https://www.brevo.com/)
[![Audit Chain](https://img.shields.io/badge/Audit_Ledger-SHA--256_DAG-success)](#-orbius-mesh--cryptographic-audit-ledger)

---

## 🌟 S-Tier Enterprise Capabilities

### 1. 🖼️ True Multimodal Perception (Gemini 3.8 Flash)
- Upload PDFs, Word documents (`.docx`), Excel spreadsheets (`.xlsx`/`.csv`), text notes, and UI wireframe images simultaneously.
- UI mockups and topology PNGs are analyzed at the byte level with `gemini-3.8-flash` (`types.Part.from_bytes`) to extract component structures, design tokens, and accessibility constraints.

### 2. ⚖️ Pairwise Semantic Contradiction Engine
- Cross-references requirements pairwise across disparate stakeholder sources using Gemini 3.8 Flash to catch subtle, cross-cutting disagreements.
- Detects non-trivial enterprise friction: **Timeline mismatches** (Q3 vs. Q4), **Legal vs. Policy conflicts** (7-year audit retention vs. GDPR Article 17 right-to-erasure), and **Budget caps vs. High-Availability SLAs** (single-region cap vs. 99.99% multi-region requirement).

### 3. 🎯 Span-Verified Grounding & Noise Rejection
- Every generated requirement is cryptographically grounded in a verified `source_span` matching the source text.
- Hallucinations and ungrounded statements are automatically flagged and filtered before entering the final specification.

### 4. 🛡️ Orbius Mesh & Cryptographic Audit Ledger
- **Immutable SHA-256 DAG Ledger**: Every specification mutation, conflict override, and human approval is cryptographically chained to its parent block.
- **Instant Tamper Verification**: 1-click verification recomputes all block hashes from genesis to DAG head, guaranteeing SOC-2 Type II (CC6.1–CC6.8) and ISO/IEC 27001:2022 (A.8.15) compliance.
- **CRDT Delta Sync Relay**: Local-first vector clock exchange (`HELLO`, `VEC`, `DELTA`, `ACK`, `SEAL`) enables seamless peer-to-peer synchronization.

### 5. 🎙️ Live Meeting Watchdog & Dual-Mode Interrupter
- Real-time meeting sentinel streaming over WebSocket (`/api/live/meeting`) or REST HTTP.
- Dynamically interrupts spoken statements that attempt to skip security mandates, violate budget limits, or contradict approved specifications.
- **Tone-Aware Tentative Commitment Cues**: Automatically detects hedging language (*"maybe"*, *"we'll try"*, *"probably"*) and flags unfinalized agreements.
- **Point-and-Speak**: Click any requirement line to focus its context directly in the Copilot prompt for instant voice-driven refinement.

### 6. 🚀 Enterprise Action & Backlog Dispatch
- **Direct Jira Cloud Push**: 1-click creation of structured User Stories and Tasks in Atlassian Jira Cloud via REST API v3 with Gherkin acceptance criteria (`Given / When / Then`).
- **Live Email Dispatch**: Sends real stakeholder follow-up and compliance update emails via Brevo REST API v3.
- **Multi-Format Deliverables**: Export to Jira CSV, Linear JSON, formatted Word (`.docx`), PDF, and Markdown.

### 7. 📊 Empirical Multi-Agent Accuracy Scorecard
- Real-time empirical evaluation harness replacing static estimations with live measured precision, recall, and grounding metrics across actual session data.

---

## 🏛️ System Architecture

Detailed architectural specifications, data flow diagrams, and a 4-minute demo walkthrough script are available in [docs/architecture.md](docs/architecture.md).

---

## 📁 Enterprise Benchmark Dataset

Orbius includes an automated test dataset generator reproducing realistic enterprise SaaS requirements:
- **01_Priya_Mehta_VP_Product.txt**: Executive kickoff memo proposing a Q3 launch.
- **02_Marcus_Chen_Finance_Head.csv**: Strict budget allocations and $180k cap.
- **03_Elena_Rostova_Lead_Architect.txt**: Multi-region 99.99% HA architecture & FIDO2 2FA mandates.
- **04_David_Kim_Field_Operations.txt**: Chicago deployment constraints mandating a Q4 launch window.
- **05_Amina_Zaid_Compliance_Officer.txt**: GDPR Article 17 Right-to-Erasure vs. 7-year audit retention.

To regenerate the benchmark dataset:
```bash
python generate_test_dataset.py
```
*Generates individual files in `test_dataset_files/` and bundles `orbius_test_dataset.zip` for instant drag-and-drop ingestion.*

---

## 🚀 Quick Start Guide

### 🪟 Windows (1-Click Startup)
Double-click:
```bat
start.bat
```
*Automatically configures virtual environments, installs dependencies, and launches both backend and frontend.*

---

### 💻 macOS & Linux Setup

#### 1. Backend Service (FastAPI)
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```
*Runs at `http://localhost:8000` (Interactive API Documentation at `http://localhost:8000/docs`).*

#### 2. Frontend Application (React + Vite)
```bash
cd frontend
npm install
npm run dev
```
*Runs at `http://localhost:5173`.*

---

## 🔑 Environment Configuration (`backend/.env`)

Configure your API keys in `backend/.env`:
```env
# Google Gemini API
GEMINI_API_KEY=your_gemini_api_key_here

# Atlassian Jira Cloud Integration
JIRA_API_TOKEN=your_jira_api_token_here
JIRA_EMAIL=your_email@domain.com
JIRA_DOMAIN=your_company.atlassian.net

# Brevo Email Dispatch Service
BREVO_API_KEY=your_brevo_api_key_here

# Security Settings
JWT_SECRET=your_cryptographic_random_salt
CORS_ORIGINS=http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173
```
*Note: Orbius is 100% functional offline with built-in heuristic fallbacks if external API keys are omitted.*

---

## 🔒 Security & Data Privacy
- **Salted Password Hashing**: PBKDF2-HMAC-SHA256 with 100,000 iterations and per-user 16-byte cryptographic random salts.
- **Cryptographic Session Tokens**: HMAC-SHA256 signed session tokens with payload integrity checks.
- **Directory Traversal Protection**: Enforced basename sanitization on all uploaded files.
- **Storage Boundaries**: 25MB file upload ceiling and strict MIME-type validation.
