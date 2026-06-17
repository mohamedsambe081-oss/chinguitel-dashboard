from django.contrib import admin
from .models import DataUpload, RevenueRecord, PowerPointReport


@admin.register(DataUpload)
class DataUploadAdmin(admin.ModelAdmin):
    list_display = ("original_filename", "status", "rows_imported", "rows_rejected", "uploaded_at", "processed_at")
    search_fields = ("original_filename", "date_column", "package_column", "revenue_column")
    list_filter = ("status", "uploaded_at")
    readonly_fields = ("uploaded_at", "processed_at", "rows_imported", "rows_rejected", "errors")


@admin.register(RevenueRecord)
class RevenueRecordAdmin(admin.ModelAdmin):
    list_display = ("date", "package", "category", "revenue", "upload")
    list_filter = ("category", "date")
    search_fields = ("package",)
    date_hierarchy = "date"


@admin.register(PowerPointReport)
class PowerPointReportAdmin(admin.ModelAdmin):
    list_display = ("created_at", "upload", "generated_by_task", "file")
    list_filter = ("generated_by_task", "created_at")
