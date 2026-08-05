"""
Hisobot API.

POST /api/reports/generate
  body: ReportFilter (reportType, groupType, nodeId?, stationId?, period{mode,startDate,endDate,label})
  -> ReportData (report-service.ts bilan bir xil shakl)
"""

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAdmin, section_required

from .services import generate_report


class GenerateReportView(APIView):
    # Hisobot ikkala bo'limdan ham chaqiriladi (Статистика va Ҳисоботлар),
    # shuning uchun ulardan bittasi yetarli.
    permission_classes = [
        IsAuthenticated,
        IsAdmin,
        section_required("hisobotlar", "statistika", writes_only=False),
    ]

    def post(self, request):
        filter_ = request.data or {}
        period = filter_.get("period") or {}
        if period.get("startDate") is None or period.get("endDate") is None:
            return Response(
                {"detail": "period.startDate va period.endDate (ms) majburiy."},
                status=400,
            )
        return Response(generate_report(filter_))
