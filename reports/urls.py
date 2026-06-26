from django.urls import path

from . import views

urlpatterns = [
    path("reports/generate/", views.GenerateReportView.as_view(), name="report-generate"),
]
