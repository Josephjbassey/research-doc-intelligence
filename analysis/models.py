"""
Django models for Research Doc Intelligence.
Document → Chunk → Extraction (per-chunk LLM output)
Document → DocSummary (aggregated per-doc)
Session → Synthesis (cross-document)
"""

import json
from django.db import models


class Session(models.Model):
    """A single analysis session — groups uploaded documents and their synthesis."""
    created_at = models.DateTimeField(auto_now_add=True)
    title = models.CharField(max_length=255, default="Untitled Analysis")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} ({self.created_at:%Y-%m-%d %H:%M})"

    @property
    def document_count(self):
        return self.documents.count()

    @property
    def is_analyzed(self):
        return hasattr(self, "synthesis")


class Document(models.Model):
    """An uploaded document (.txt or .docx)."""
    session = models.ForeignKey(Session, related_name="documents", on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    file_type = models.CharField(max_length=10, default="txt")
    raw_text = models.TextField()
    word_count = models.IntegerField(default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["uploaded_at"]

    def __str__(self):
        return self.title

    @property
    def filename(self):
        return self.title

    @property
    def extraction(self):
        """Aggregated extraction data for template rendering."""
        summary = getattr(self, "summary", None)
        if summary:
            return {
                "themes": summary.all_themes,
                "stance": summary.stance,
                "flags": summary.all_flags,
            }
        return {"themes": [], "stance": "", "flags": []}


class Chunk(models.Model):
    """A text chunk split from a document for LLM processing."""
    document = models.ForeignKey(Document, related_name="chunks", on_delete=models.CASCADE)
    index = models.IntegerField()
    text = models.TextField()
    word_count = models.IntegerField(default=0)

    class Meta:
        ordering = ["index"]
        unique_together = ("document", "index")

    def __str__(self):
        return f"{self.document.title} — chunk {self.index}"


class Extraction(models.Model):
    """LLM extraction result for a single chunk."""
    chunk = models.OneToOneField(Chunk, related_name="extraction", on_delete=models.CASCADE)
    themes_json = models.TextField(default="[]")
    stance = models.TextField(default="")
    flags_json = models.TextField(default="[]")
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def themes(self) -> list:
        return json.loads(self.themes_json) if self.themes_json else []

    @themes.setter
    def themes(self, value):
        self.themes_json = json.dumps(value)

    @property
    def flags(self) -> list:
        return json.loads(self.flags_json) if self.flags_json else []

    @flags.setter
    def flags(self, value):
        self.flags_json = json.dumps(value)

    def __str__(self):
        return f"Extraction for {self.chunk}"


class DocSummary(models.Model):
    """Aggregated summary for a single document (merged from chunk extractions)."""
    document = models.OneToOneField(Document, related_name="summary", on_delete=models.CASCADE)
    summary_text = models.TextField(default="")
    all_themes_json = models.TextField(default="[]")
    all_flags_json = models.TextField(default="[]")
    stance = models.TextField(default="")
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def all_themes(self) -> list:
        return json.loads(self.all_themes_json) if self.all_themes_json else []

    @property
    def all_flags(self) -> list:
        return json.loads(self.all_flags_json) if self.all_flags_json else []


class Synthesis(models.Model):
    """Cross-document synthesis result for a session."""
    session = models.OneToOneField(Session, related_name="synthesis", on_delete=models.CASCADE)
    recurring_themes_json = models.TextField(default="[]")
    contradictions_json = models.TextField(default="[]")
    overall_summary = models.TextField(default="")
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def recurring_themes(self) -> list:
        return json.loads(self.recurring_themes_json) if self.recurring_themes_json else []

    @property
    def contradictions(self) -> list:
        return json.loads(self.contradictions_json) if self.contradictions_json else []