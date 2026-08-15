# Technical Writeup — Research Doc Intelligence

## Problem

Students and independent researchers doing qualitative analysis (interview transcripts, survey free-text, field notes) have no affordable way to extract structured findings from messy text. Enterprise tools like NVivo and Atlas.ti cost hundreds of dollars and have steep learning curves. Most students end up manually highlighting PDFs and building spreadsheets by hand — slow, error-prone, and impossible to redo when the coding scheme changes.

## Solution

A web app that lets a user upload 1+ documents (.txt / .docx), runs them through a multi-step LLM pipeline, and produces:
- Per-document analysis: extracted themes, supporting quotes, stance/sentiment, notable flags
- Cross-document synthesis: recurring themes across sources, contradictions/tensions, overall summary
- A formatted .docx report export

## Stack

- **Backend:** Django 6.1, Python 3.11+
- **Frontend:** Django templates + Tailwind CSS (CDN, no build step)
- **LLM:** `zai-org/GLM-5.2` via Featherless.ai (OpenAI-compatible API)
- **Document parsing/export:** `python-docx` (one library for both directions)
- **Database:** SQLite
- **Caching:** Filesystem cache (`responses/{sha256}.json`) — avoids re-spending tokens on repeated dev runs

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

The pipeline has clean separation: `ingestion.py` (parsing + chunking) -> `llm_client.py` (API calls + caching) + `prompts.py` (Prompt A / Prompt B constants) -> `views.py` (orchestration: extraction -> aggregation -> synthesis) -> `export.py` (docx generation). No god-functions — each module has a single responsibility.

## What Was Hard

### 1. Token limit truncation breaking JSON parsing

The PRD specified `max_tokens=800` for extraction and `max_tokens=1200` for synthesis. In practice, GLM-5.2 produces verbose JSON with rich theme descriptions and supporting quotes. At 800 tokens, the JSON was being cut off mid-sentence — the closing braces never arrived, so `json.loads()` failed silently and the fallback returned an empty themes array.

**Fix:** Increased to `max_tokens=3000` for extraction and `max_tokens=4000` for synthesis. The PRD's token budget was calibrated for "compact JSON" but the model produces detailed, high-quality output that needs room to breathe.

**Lesson:** Always test prompt token budgets against real data before trusting them. A truncated JSON response is worse than no response because it looks like it worked (the API call succeeded) but produces empty results downstream.

### 2. Synthesis prompt input size causing empty responses

The initial synthesis prompt sent the full per-document extraction JSON — all theme fields (label, description, supporting_quote, confidence), all flags, and stance text. For 3 documents with 5 themes each, this was ~9KB of input. The model's response was either empty or truncated.

**Fix:** Compacted the extraction JSON sent to the synthesis prompt. Only sent `label`, `description`, and `quote` per theme — dropped `confidence` and `flags`. This reduced the input from ~9KB to ~6KB and the model started producing complete, well-structured synthesis JSON.

**Lesson:** LLMs have a finite attention budget. When the input is bloated, the model spends capacity processing it rather than generating output. Send only what the synthesis step actually needs — theme labels and descriptions are enough to identify patterns; confidence levels and flags are per-document concerns that don't help cross-document reasoning.

### 3. Markdown code fences in LLM responses

The system prompts explicitly say "return ONLY valid JSON, no preamble, no markdown fences" but GLM-5.2 still wraps responses in ` ```json ... ``` ` fences. The initial fence-stripping logic handled the opening fence but had an edge case where the closing fence wasn't stripped correctly if there was trailing whitespace.

**Fix:** Made the fence-stripping more robust — strip leading ```json or ```, strip trailing ```, then strip whitespace. Added a fallback that returns a structured error object (with `parse_error: true` and the raw response) instead of crashing, so the pipeline continues even if one chunk fails to parse.

**Lesson:** Never trust an LLM to follow formatting instructions perfectly. Always have a parser that can handle the most common violations (markdown fences, leading/trailing whitespace, preamble text) and a graceful fallback that doesn't kill the entire pipeline.

### 4. Django INSTALLED_APPS ordering

The initial settings.py omitted `django.contrib.admin`, `django.contrib.sessions`, and `django.contrib.messages` from INSTALLED_APPS (trying to keep it minimal), but `core/urls.py` referenced `admin.site.urls` and the middleware stack required sessions and messages. This caused a `LookupError: No installed app with label 'admin'` on first run.

**Fix:** Added the missing apps to INSTALLED_APPS in the correct order.

**Lesson:** Django's default project template includes those apps for a reason. Stripping them to be "minimal" without understanding the dependency graph costs more time than it saves.

### 5. Caching stale bad responses

When the synthesis API call returned an empty string (due to the input size issue above), that empty response got cached. On the next run, the pipeline pulled the empty cached response and produced empty synthesis results — even after the underlying issue was fixed.

**Fix:** Had to manually clear the cache (`rm responses/*.json`) after fixing the prompt. The caching layer now works correctly (it caches good responses), but during development, bad responses can get stuck in cache.

**Lesson:** Cache invalidation is still one of the two hard problems in computer science. During development, always have a quick way to blow away the cache. In production, consider a TTL or a "force refresh" mechanism.

## Innovation: Cross-Document Synthesis + Contradiction Detection

Most similar tools (including AI-powered summarizers) stop at per-document summary. The key innovation here is the two-stage LLM pipeline:

1. **Per-chunk extraction** identifies themes, quotes, and stance from each document independently
2. **Cross-document synthesis** takes all per-document extractions and identifies patterns that only emerge when looking across sources — recurring themes (appearing in 2+ docs) and contradictions/tensions between sources

This mirrors how a human qualitative researcher works: code each document independently, then look across the corpus for patterns. The contradiction detection is particularly valuable — it surfaces tensions that a per-document summary would miss entirely.

In the demo run with 3 interview transcripts about remote work, the pipeline correctly identified:
- 4 recurring themes (productivity/flexibility, cross-team disconnection, career visibility, communication overload)
- 1 contradiction (doc 1 values spontaneous office interactions; doc 3 argues the office only enables shallow work)

## What I'd Build Next (Post-Hackathon)

- PDF support (text-based PDFs, not OCR)
- User accounts + saved analyses
- Interactive theme editing (let the researcher rename, merge, or reject LLM-suggested themes)
- Inter-rater reliability metrics when the same document is coded multiple times
- Streaming UI (show results as each chunk completes, not batch)
- Custom prompt templates (let researchers define their own coding scheme)