from django.db import models


class DataUpload(models.Model):
    STATUS_CHOICES = [
        ("pending", "En attente"),
        ("processed", "Traité"),
        ("failed", "Échec"),
    ]

    file = models.FileField(upload_to="uploads/%Y/%m/%d/")
    original_filename = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    rows_imported = models.PositiveIntegerField(default=0)
    rows_rejected = models.PositiveIntegerField(default=0)
    date_column = models.CharField(max_length=255, blank=True)
    package_column = models.CharField(max_length=255, blank=True)
    revenue_column = models.CharField(max_length=255, blank=True)
    errors = models.JSONField(default=list, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.original_filename} — {self.status}"


class RevenueRecord(models.Model):
    upload = models.ForeignKey(DataUpload, on_delete=models.CASCADE, related_name="records")
    date = models.DateField(db_index=True)
    package = models.CharField(max_length=255, db_index=True)
    category = models.CharField(max_length=100, default="Non classé", db_index=True)
    revenue = models.DecimalField(max_digits=18, decimal_places=2)
    raw_payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["date", "package"]),
            models.Index(fields=["category", "date"]),
        ]
        ordering = ["date", "package"]

    def __str__(self):
        return f"{self.date} — {self.package} — {self.revenue}"


class PowerPointReport(models.Model):
    upload = models.ForeignKey(DataUpload, on_delete=models.SET_NULL, null=True, blank=True)
    file = models.FileField(upload_to="reports/%Y/%m/%d/")
    filters = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    generated_by_task = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Rapport PowerPoint — {self.created_at:%Y-%m-%d %H:%M}"
