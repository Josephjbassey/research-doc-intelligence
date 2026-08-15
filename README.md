# Research Doc Intelligence

Affordable qualitative research analysis for students and independent researchers. Upload interview transcripts, survey free-text, or field notes and get structured thematic analysis with cross-document synthesis — no enterprise software required.

Built for **Impact Forge Summer 2026 — Computational Research Track**.

---

## What It Does

1. **Upload** 1+ documents (`.txt` or `.docx`)
2. **Per-document analysis**: extracted themes, supporting quotes, stance/sentiment, notable flags
3. **Cross-document synthesis**: recurring themes across sources, contradictions/tensions, overall summary
4. **Export** the full analysis as a formatted `.docx` report

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
| Aggregation | `analysis/views.py` (`run_analysis`) | Merge chunk extractions into per-document summary |
| Synthesis | `analysis/llm_client.py` + `analysis/prompts.py` | Cross-document LLM call → recurring themes + contradictions |
| Export | `analysis/export.py` | Generate formatted `.docx` report |

### Tech Stack

- **Backend:** Django 5+, Python 3.11+
- **Frontend:** Django templates + Tailwind CSS (CDN)
- **LLM:** `zai-org/GLM-5.2` via Featherless.ai (OpenAI-compatible API)
- **Document parsing/export:** `python-docx`
- **Database:** SQLite
- **Caching:** Filesystem cache (`responses/{sha256}.json`) — avoids re-spending tokens on repeated dev runs

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

1. On the home page, enter an analysis title and select 1+ `.txt` or `.docx` files
2. Click **Upload & Prepare** — documents are parsed and chunked
3. Click **Run Full Analysis** — the pipeline runs per-chunk extraction, aggregation, and synthesis
4. View results: per-document themes/quotes, cross-document recurring themes, contradictions
5. Click **Download .docx Report** for a formatted export

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
├── core/
│   ├── settings.py          # Django settings + env config
│   ├── urls.py              # Root URL config
│   └── wsgi.py
├── analysis/
│   ├── models.py            # Session, Document, Chunk, Extraction, DocSummary, Synthesis
│   ├── views.py             # Upload, run_analysis, results, export
│   ├── ingestion.py         # File parsing + chunking
│   ├── llm_client.py        # Featherless API calls + filesystem caching
│   ├── export.py            # .docx report generation
│   ├── prompts.py           # Prompt A (extraction) + Prompt B (synthesis)
│   ├── urls.py              # App URL routes
│   └── templates/
│       └── analysis/
│           ├── base.html     # Layout shell (Tailwind CDN)
│           ├── index.html    # Upload form + session list
│           ├── detail.html   # Session overview + run analysis
│           └── results.html  # Full results display
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

## Author

Joseph Bassey — Impact Forge Summer 2026