# Research Doc Intelligence

Affordable qualitative research analysis for students and independent researchers. Upload interview transcripts, survey free-text, or field notes and get structured thematic analysis with cross-document synthesis — no enterprise software required.

Built for **Impact Forge Summer 2026 — Computational Research Track**.

---

## What It Does

1. **Upload** 1+ documents (`.txt` or `.docx`) — drag-and-drop or browse
2. **Per-document analysis**: extracted themes, supporting quotes, stance/sentiment, notable flags
3. **Cross-document synthesis**: recurring themes across sources, contradictions/tensions, overall summary
4. **Export** the full analysis as a formatted `.docx` report

The entire pipeline runs in one step — upload your files and the analysis completes automatically, no intermediate steps.

## Architecture

```
[Upload .txt/.docx]
      │
      ▼
[Ingestion & Chunking]  (~1800-word chunks, split on paragraph/sentence boundaries)
      │
      ▼
[Per-Chunk Extraction]  → GLM-5.2 via Featherless.ai → structured JSON (themes, quotes, stance)
      │
      ▼
[Per-Document Aggregation]  → merge chunk results into one doc-level summary
      │
      ▼
[Cross-Document Synthesis]  → GLM-5.2 → recurring themes + contradictions across all docs
      │
      ▼
[Report Renderer]  → HTML view (Django templates) + .docx export (python-docx)
```

### Pipeline Stages

| Stage | Module | Responsibility |
|-------|--------|----------------|
| Ingestion | `analysis/ingestion.py` | Parse `.txt`/`.docx`, split into ~1800-word chunks |
| Extraction | `analysis/llm_client.py` + `analysis/prompts.py` | Per-chunk LLM call → structured JSON (themes, quotes, stance) |
| Aggregation | `analysis/views.py` (`_run_analysis_pipeline`) | Merge chunk extractions into per-document summary |
| Synthesis | `analysis/llm_client.py` + `analysis/prompts.py` | Cross-document LLM call → recurring themes + contradictions |
| Export | `analysis/export.py` | Generate formatted `.docx` report |

### Tech Stack

- **Backend:** Django, Python 3.11+
- **Frontend:** Django templates + Tailwind CSS (Play CDN) + HTMX
- **LLM:** `zai-org/GLM-5.2` via Featherless.ai (OpenAI-compatible API)
- **Document parsing/export:** `python-docx`
- **Database:** SQLite
- **Caching:** Filesystem cache (`responses/{sha256}.json`) — avoids re-spending tokens on repeated dev runs

### Design Language

The UI follows an editorial/manuscript aesthetic — a research paper, not a SaaS dashboard.

- **Typography:** Fraunces (display/headings), IBM Plex Sans (body), IBM Plex Mono (source labels, doc IDs, citations)
- **Palette:** Paper (`#EFEEE7`) background, Ink (`#1C2230`) text, Highlight (`#F4C542`) for the signature highlighter mark, Flag (`#B8433A`) for contradictions only, Rule (`#DAD7CC`) for hairlines/borders
- **Signature element:** Extracted evidence quotes get a literal highlighter mark — an amber swipe behind the text, the way a researcher would mark up a printed transcript. This is the one bold visual move, directly justified by what the tool does (surfacing evidence).
- **Micro-animations:** Staggered entrance fades, scroll-triggered section reveals (IntersectionObserver), highlighter-mark sweep-in on quotes, card hover lifts, pulsing contradiction badge, loading overlay with spinner during analysis, drag-over state on the upload zone. All animations respect `prefers-reduced-motion`.

## Setup

### Prerequisites

- Python 3.11+
- A Featherless.ai API key (get one at https://featherless.ai)

### Installation

```bash
git clone https://github.com/josephjbassey/research-doc-intelligence.git
cd research-doc-intelligence

python -m venv venv
source venv/bin/activate    # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

### Configuration

```bash
cp .env.example .env
# Edit .env and add your Featherless API key:
# FEATHERLESS_API_KEY=feather-sk-your-key-here
```

### Database Setup

```bash
python manage.py migrate
```

### Run the Server

```bash
python manage.py runserver
```

Open http://127.0.0.1:8000 in your browser.

## Usage

1. On the home page, select 1+ `.txt` or `.docx` files (drag-and-drop or browse)
2. Click **Analyze documents** — the full pipeline runs automatically (extraction → aggregation → synthesis)
3. View results: overall summary, cross-document recurring themes, contradictions, per-document evidence with highlighted quotes
4. Click **Export report** to download a formatted `.docx` report

### Sample Data

Three sample interview transcripts about remote work experiences are included in `sample_data/`. Upload all three to see the cross-document synthesis and contradiction detection in action.

## Project Structure

```
research-doc-intelligence/
├── manage.py
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
├── TECHNICAL_WRITEUP.md
├── core/
│   ├── settings.py          # Django settings + env config
│   ├── urls.py              # Root URL config
│   └── wsgi.py
├── analysis/
│   ├── models.py            # Session, Document, Chunk, Extraction, DocSummary, Synthesis
│   ├── views.py             # Upload+analyze, results, export
│   ├── ingestion.py         # File parsing + chunking
│   ├── llm_client.py        # Featherless API calls + filesystem caching + IPv4 fix
│   ├── export.py            # .docx report generation
│   ├── prompts.py           # Prompt A (extraction) + Prompt B (synthesis)
│   ├── urls.py              # App URL routes
│   └── templates/
│       ├── base.html         # Layout shell, Tailwind config, fonts, animations, loading overlay
│       ├── upload.html       # Upload form with drag-drop + file list
│       └── results.html      # Synthesis results with themes, contradictions, evidence
├── responses/                # Gitignored — LLM response cache
└── sample_data/              # 3 demo transcripts
    ├── interview_01_remote_work.txt
    ├── interview_02_remote_work.txt
    └── interview_03_remote_work.txt
```

## LLM Integration

The app uses two prompts:

- **Prompt A (Per-chunk extraction):** Extracts themes, supporting quotes, stance, and notable flags from each text chunk. Returns structured JSON. Max 5 themes per chunk.
- **Prompt B (Cross-document synthesis):** Takes all per-document extractions and identifies recurring themes (appearing in 2+ docs), contradictions, and produces an overall summary.

All LLM responses are cached by SHA256 hash of (system prompt + user prompt) in `responses/`. Re-running analysis on the same text returns instantly without API calls — essential for iterative development without burning tokens.

### Networking Note

The LLM client forces IPv4 via a `urllib3.util.connection.allowed_gai_family` monkey-patch. This machine has no IPv6 route, and without the fix `requests`/`urllib3` tries IPv6 addresses first (which hang until timeout) instead of falling back to IPv4. The fix is in `analysis/llm_client.py` at the top of the file.

## Author

Joseph Bassey — Impact Forge Summer 2026