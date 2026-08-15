"""
Views for Research Doc Intelligence.
Handles: upload, analysis pipeline, results display, docx export.
"""

import json

from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST

from .models import Session, Document, Chunk, Extraction, DocSummary, Synthesis
from .ingestion import parse_uploaded_file, chunk_text
from .llm_client import chat_completion_json
from .prompts import (
    EXTRACTION_SYSTEM_PROMPT,
    EXTRACTION_USER_TEMPLATE,
    SYNTHESIS_SYSTEM_PROMPT,
    SYNTHESIS_USER_TEMPLATE,
)
from .export import generate_report


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

def index(request):
    """Home page — upload form + list of past sessions."""
    sessions = Session.objects.all()[:10]
    return render(request, "analysis/index.html", {"sessions": sessions})


@require_POST
def upload(request):
    """Handle file uploads, create a session, parse and chunk documents."""
    files = request.FILES.getlist("files")
    if not files:
        return JsonResponse({"error": "No files uploaded."}, status=400)

    session_title = request.POST.get("title", "Untitled Analysis")

    session = Session.objects.create(title=session_title)

    for f in files:
        try:
            text = parse_uploaded_file(f)
        except ValueError as e:
            return JsonResponse({"error": str(e)}, status=400)

        doc = Document.objects.create(
            session=session,
            title=f.name,
            file_type=f.name.split(".")[-1].lower(),
            raw_text=text,
            word_count=len(text.split()),
        )

        # Chunk the document
        chunks = chunk_text(text)
        for c in chunks:
            Chunk.objects.create(
                document=doc,
                index=c.index,
                text=c.text,
                word_count=c.word_count,
            )

    return redirect("analysis_detail", session_id=session.id)


# ---------------------------------------------------------------------------
# Analysis pipeline
# ---------------------------------------------------------------------------

def analysis_detail(request, session_id):
    """Show session overview with documents and trigger analysis."""
    session = get_object_or_404(Session, id=session_id)
    return render(request, "analysis/detail.html", {"session": session})


@require_POST
def run_analysis(request, session_id):
    """Run the full analysis pipeline: per-chunk extraction → per-doc aggregation → synthesis."""
    session = get_object_or_404(Session, id=session_id)

    documents = list(session.documents.all())
    if not documents:
        return JsonResponse({"error": "No documents in session."}, status=400)

    # --- Step 1: Per-chunk extraction ---
    for doc in documents:
        for chunk in doc.chunks.all():
            # Skip if already extracted
            if hasattr(chunk, "extraction"):
                continue

            user_prompt = EXTRACTION_USER_TEMPLATE.format(
                doc_title=doc.title,
                chunk_index=chunk.index + 1,
                total_chunks=doc.chunks.count(),
                chunk_text=chunk.text,
            )

            result = chat_completion_json(
                system_prompt=EXTRACTION_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                max_tokens=3000,
            )

            Extraction.objects.create(
                chunk=chunk,
                themes_json=json.dumps(result.get("themes", [])),
                stance=result.get("stance_or_sentiment", ""),
                flags_json=json.dumps(result.get("notable_flags", [])),
            )

    # --- Step 2: Per-document aggregation ---
    doc_extractions = []
    for doc in documents:
        all_themes = []
        all_flags = []
        stances = []

        for chunk in doc.chunks.all():
            if hasattr(chunk, "extraction"):
                ext = chunk.extraction
                all_themes.extend(ext.themes)
                all_flags.extend(ext.flags)
                if ext.stance:
                    stances.append(ext.stance)

        # Build a simple doc-level summary from themes
        theme_labels = [t.get("label", "") for t in all_themes if t.get("label")]
        summary = f"Document contains {len(all_themes)} themes across {doc.chunks.count()} chunks."
        if theme_labels:
            summary += f" Key themes: {', '.join(theme_labels[:5])}."
        if stances:
            summary += f" Overall stance: {stances[0]}"

        DocSummary.objects.update_or_create(
            document=doc,
            defaults={
                "summary_text": summary,
                "all_themes_json": json.dumps(all_themes),
                "all_flags_json": json.dumps(all_flags),
                "stance": stances[0] if stances else "",
            },
        )

        doc_extractions.append({
            "doc_id": f"doc_{doc.id}",
            "doc_title": doc.title,
            "themes": [
                {"label": t.get("label", ""), "description": t.get("description", ""), "quote": t.get("supporting_quote", "")}
                for t in all_themes
            ],
            "stance": stances[0] if stances else "",
        })

    # --- Step 3: Cross-document synthesis ---
    # Only run if we have 2+ documents
    if len(documents) >= 2:
        user_prompt = SYNTHESIS_USER_TEMPLATE.format(
            num_docs=len(documents),
            extractions_json=json.dumps(doc_extractions, indent=1),
        )

        synth_result = chat_completion_json(
            system_prompt=SYNTHESIS_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            max_tokens=4000,
        )

        Synthesis.objects.update_or_create(
            session=session,
            defaults={
                "recurring_themes_json": json.dumps(synth_result.get("recurring_themes", [])),
                "contradictions_json": json.dumps(synth_result.get("contradictions", [])),
                "overall_summary": synth_result.get("overall_summary", ""),
            },
        )
    else:
        # Single document — create a minimal synthesis
        Synthesis.objects.update_or_create(
            session=session,
            defaults={
                "recurring_themes_json": "[]",
                "contradictions_json": "[]",
                "overall_summary": doc_extractions[0].get("stance", "Single document analysis."),
            },
        )

    return redirect("results", session_id=session.id)


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------

def results(request, session_id):
    """Display full analysis results."""
    session = get_object_or_404(Session, id=session_id)

    # Build per-document data for the template
    docs_data = []
    for doc in session.documents.all():
        doc_summary = getattr(doc, "summary", None)
        docs_data.append({
            "doc": doc,
            "summary": doc_summary,
        })

    synthesis = getattr(session, "synthesis", None)

    return render(request, "analysis/results.html", {
        "session": session,
        "docs_data": docs_data,
        "synthesis": synthesis,
    })


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def export_docx(request, session_id):
    """Generate and download a .docx report."""
    session = get_object_or_404(Session, id=session_id)

    # Build the data structure expected by generate_report
    documents_data = []
    for doc in session.documents.all():
        doc_summary = getattr(doc, "summary", None)
        if doc_summary:
            documents_data.append({
                "title": doc.title,
                "summary": doc_summary.summary_text,
                "themes": doc_summary.all_themes,
                "stance": doc_summary.stance,
                "flags": doc_summary.all_flags,
            })
        else:
            documents_data.append({
                "title": doc.title,
                "summary": "No analysis available.",
                "themes": [],
                "stance": "",
                "flags": [],
            })

    synthesis = getattr(session, "synthesis", None)
    synth_data = {
        "recurring_themes": synthesis.recurring_themes if synthesis else [],
        "contradictions": synthesis.contradictions if synthesis else [],
        "overall_summary": synthesis.overall_summary if synthesis else "",
    }

    report_bytes = generate_report(documents_data, synth_data)

    response = HttpResponse(
        report_bytes,
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    filename = f"research-report-{session.id}.docx"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response