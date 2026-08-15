from django.urls import path
from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("upload/", views.upload, name="upload"),
    path("session/<int:session_id>/", views.analysis_detail, name="analysis_detail"),
    path("session/<int:session_id>/run/", views.run_analysis, name="run_analysis"),
    path("session/<int:session_id>/results/", views.results, name="results"),
    path("session/<int:session_id>/export/", views.export_docx, name="export_docx"),
]