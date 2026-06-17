from django.urls import path
from . import api, views

app_name = "revenue"

urlpatterns = [
    path("logout/", views.logout_view, name="logout"),
    path("register/", views.register_view, name="register"),
    path("login/", views.login_view, name="login"),
    path("", views.login_view, name="root_login"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("upload/", views.upload_excel, name="upload_excel"),
    path("upload/delete/", views.delete_upload, name="delete_upload"),
    path("reports/export/", views.export_powerpoint, name="export_powerpoint"),
    path("api/meta/", api.meta, name="api_meta"),
    path("api/kpis/", api.kpis, name="api_kpis"),
    path("api/series/", api.series, name="api_series"),
    path("api/weekly-percent/", api.weekly_percent, name="api_weekly_percent"),
    path("api/package-weekly-percent/", api.package_weekly_percent, name="api_package_weekly_percent"),
    path("api/packages/", api.packages, name="api_packages"),
    path("api/overview-charts/", api.overview_charts, name="api_overview_charts"),
    path("api/advanced-dashboard/", api.advanced_dashboard, name="api_advanced_dashboard"),
    path("api/detail-dashboard/", api.detail_dashboard, name="api_detail_dashboard"),
    path("api/weekly-report/", api.weekly_report, name="api_weekly_report"),
    path("api/daily-report/", api.daily_report, name="api_daily_report"),
    path("api/heatmap/", api.heatmap, name="api_heatmap"),
    path("api/forecast/", api.forecast, name="api_forecast"),
    path("api/anomalies/", api.anomalies, name="api_anomalies"),
    path("api/eda/", api.eda, name="api_eda"),
    path("api/monthly-report/", api.monthly_report, name="api_monthly_report"),
    path("api/ml-report/", api.ml_report, name="api_ml_report"),
    path("api/demand-dashboard/", api.demand_report, name="api_demand_report"),
]
