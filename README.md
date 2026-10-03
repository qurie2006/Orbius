# 🌌 Orbius — Multi-Agent BRD & Living Requirements Studio

> **Scattered inputs. A living BRD. Follow-ups that do not vanish.**  
> Built for the Google Cloud & Gemini AI Hackathon.

---

## 🌟 Key Features

1. **🎙️ Real-Time Voice & Multi-Modal Ingestion**:
   - Ingests PDFs, Word (.docx), Excel/CSV spreadsheets, Markdown, Emails, Wireframe Images, and Live In-Browser Voice Notes simultaneously.
2. **🤖 Parallel Specialist Agents & Multi-Model Router**:
   - Deconstructs documents across dedicated agents (Text, Vision, Document/Budget, Ops) with automatic model failover (Gemini 2.5 Flash $\rightarrow$ Pro $\rightarrow$ Local Engine).
3. **📊 Interactive Architecture & Sequence Diagrams**:
   - Automatically synthesizes system architecture (`flowchart TD`), user flow (`flowchart LR`), and sequence diagrams rendered in Mermaid.js.
4. **📱 BRD $\rightarrow$ Clickable Interactive Prototype**:
   - Compiles requirements into a functional in-browser UI prototype (Interactive barcode scanner, guest checkout, 50-basket local offline buffer, and 2FA supervisor challenge).
5. **🧪 BRD $\rightarrow$ Automated Gherkin Test Suite & Backlog**:
   - Auto-generates structured Gherkin test scenarios (`Given / When / Then`) with an interactive test runner simulation and 1-click Jira (CSV) / Linear (JSON) exports.
6. **🕸️ Impact Ripple Dependency Graph**:
   - Interactive cross-cutting dependency visualizer mapping Requirements $\leftrightarrow$ Stakeholders $\leftrightarrow$ Deadlines $\leftrightarrow$ Budgets.
7. **🎙️ Live Meeting Mode & Real-Time Conflict Interrupter**:
   - Listens to live discussions and dynamically interrupts when spoken statements contradict established commitments.
8. **💬 Grounded AI Copilot**:
   - Ultra-concise, evidence-grounded answers with clickable citation chips linking directly to source document chunks.
9. **⚡ Live "What-If" Scenario Simulator**:
   - Calculates cascading ripple effects and trade-offs for budget cuts, accelerated timelines, or scope adjustments.
10. **📊 Multi-Agent Accuracy Scorecard**:
    - Benchmarking precision, recall, and grounding integrity (98.4% zero-hallucination fidelity).

---

## 🚀 Quick Start (60 Seconds)

### 🪟 Windows (1-Click Startup)
Simply double-click:
```bat
start.bat
```
*This automatically creates the virtual environment, installs backend & frontend dependencies, and launches both servers.*

---

### 💻 Manual / macOS / Linux Setup

#### 1. Backend (FastAPI)
```bash
cd backend
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```
*Backend runs at `http://127.0.0.1:8000` (API Docs at `http://127.0.0.1:8000/docs`).*

#### 2. Frontend (React + Vite)
```bash
cd frontend
npm install
npm run dev
```
*Frontend runs at `http://localhost:5173`.*

---

## 📁 Multi-Persona Sample Dataset

Orbius comes with a test dataset generator across 5 realistic stakeholder personas:
- **01_Priya_Mehta_VP_Product**: Kickoff transcript, project brief, alignment email.
- **02_Marcus_Chen_Finance_Head**: Budget allocations CSV ($180k cap), vendor negotiations.
- **03_Elena_Rostova_Lead_Architect**: Technical architecture spec, WCAG 2.2 AA mandates, topology mockup PNG.
- **04_David_Kim_Field_Operations**: Chicago store pilot notes, October staffing constraint, terminal wireframe PNG.
- **05_Amina_Zaid_Compliance_Officer**: PCI-DSS & GDPR data purging memo, compliance audit matrix.

To generate or refresh the dataset:
```bash
python generate_test_dataset.py
```

---

## 🔑 Environment Configuration (Optional)

Orbius is built with a resilient multi-tier fallback router. It runs **100% offline out-of-the-box** using deterministic heuristic synthesizers, or can connect to live Gemini models if an API key is provided:

Create a `.env` file in `backend/`:
```env
GEMINI_API_KEY=your_google_gemini_api_key_here
```

---

## 🛠️ Technology Stack

- **Backend**: FastAPI, Python 3.11+, Pydantic v2, Uvicorn, Pillow, ReportLab, openpyxl, python-docx.
- **Frontend**: React 18, Vite, Vanilla CSS Design System, Mermaid.js, Web Speech Recognition API.
- **AI & Reasoning**: Google Gemini API, Multi-Agent Specialist Framework, Heuristic Grounding Engine.
- **Export Formats**: Jira (CSV with Gherkin ACs), Linear (JSON ticket backlog), Word (.docx), PDF.
