from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.db.models import Min, Max

from revenue.models import DataUpload, RevenueRecord
from revenue.services.category_rules import CATEGORY_ORDER, sync_existing_record_categories
from revenue.services.analytics import (
    category_breakdown,
    calendar_heatmap,
    descriptive_stats,
    detect_anomalies,
    eda as eda_service,
    filter_records,
    forecast_4_weeks,
    package_breakdown,
    overview_charts as overview_charts_service,
    advanced_dashboard as advanced_dashboard_service,
    detail_dashboard as detail_dashboard_service,
    summary,
    time_series,
    weekly_revenue_percentage,
    package_weekly_revenue_percentage,
    weekly_marketing_report,
    daily_marketing_report,
    demand_dashboard,
    ml_dashboard,
    monthly_marketing_report,
)


@api_view(["GET"])
def meta(request):
    sync_existing_record_categories()
    uploads = DataUpload.objects.all()[:20]
    bounds = RevenueRecord.objects.aggregate(date_min=Min("date"), date_max=Max("date"))
    return Response({
        "uploads": [
            {
                "id": u.id,
                "filename": u.original_filename,
                "status": u.status,
                "rows_imported": u.rows_imported,
                "uploaded_at": u.uploaded_at.isoformat(),
            }
            for u in uploads
        ],
        "categories": CATEGORY_ORDER,
        "packages": list(RevenueRecord.objects.order_by("package").values_list("package", flat=True).distinct()[:500]),
        "date_min": bounds["date_min"].isoformat() if bounds["date_min"] else None,
        "date_max": bounds["date_max"].isoformat() if bounds["date_max"] else None,
    })


@api_view(["GET"])
def kpis(request):
    qs = filter_records(request.GET)
    data = summary(qs)
    data["stats"] = descriptive_stats(qs)
    return Response(data)


@api_view(["GET"])
def series(request):
    qs = filter_records(request.GET)
    granularity = request.GET.get("granularity", "day")
    return Response(time_series(qs, granularity))


@api_view(["GET"])
def weekly_percent(request):
    qs = filter_records(request.GET)
    return Response(weekly_revenue_percentage(qs))


@api_view(["GET"])
def package_weekly_percent(request):
    qs = filter_records(request.GET)
    package_group = request.GET.get("package_group", "MauriNet")
    return Response(package_weekly_revenue_percentage(qs, package_group))


@api_view(["GET"])
def packages(request):
    qs = filter_records(request.GET)
    return Response({
        "packages": package_breakdown(qs, 15),
        "categories": category_breakdown(qs),
    })


@api_view(["GET"])
def heatmap(request):
    qs = filter_records(request.GET)
    return Response(calendar_heatmap(qs))


@api_view(["GET"])
def forecast(request):
    qs = filter_records(request.GET)
    return Response(forecast_4_weeks(qs))


@api_view(["GET"])
def anomalies(request):
    qs = filter_records(request.GET)
    return Response(detect_anomalies(qs))


@api_view(["GET"])
def eda(request):
    qs = filter_records(request.GET)
    return Response(eda_service(qs))


@api_view(["GET"])
def overview_charts(request):
    qs = filter_records(request.GET)
    return Response(overview_charts_service(qs))


@api_view(["GET"])
def advanced_dashboard(request):
    qs = filter_records(request.GET)
    return Response(advanced_dashboard_service(qs, request.GET.get("granularity", "week")))


@api_view(["GET"])
def detail_dashboard(request):
    qs = filter_records(request.GET)
    return Response(detail_dashboard_service(qs, request.GET.get("granularity", "week")))


@api_view(["GET"])
def weekly_report(request):
    qs = filter_records(request.GET)
    return Response(weekly_marketing_report(qs, request.GET.get("week_id")))


@api_view(["GET"])
def daily_report(request):
    qs = filter_records(request.GET)
    return Response(daily_marketing_report(qs, request.GET.get("week_id")))


@api_view(["GET"])
def demand_report(request):
    qs = filter_records(request.GET)
    return Response(demand_dashboard(qs, request.GET.get("granularity", "week")))


@api_view(["GET"])
def ml_report(request):
    qs = filter_records(request.GET)
    return Response(ml_dashboard(qs))


@api_view(["GET"])
def monthly_report(request):
    qs = filter_records(request.GET)
    return Response(monthly_marketing_report(qs, request.GET.get("month_id")))
