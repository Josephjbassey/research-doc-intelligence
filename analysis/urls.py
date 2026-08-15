from django.urls import path
from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("upload/", views.upload, name="upload"),
    path("session/<int:session_id>/results/", views.results, name="results"),
    path("session/<int:session_id>/export/", views.export_report, name="export_report"),
]