from celery import shared_task
from .models import DataUpload
from .services.pptx_export import generate_pptx


@shared_task(name="revenue.tasks.generate_weekly_powerpoint")
def generate_weekly_powerpoint():
    latest = DataUpload.objects.filter(status="processed").first()
    if not latest:
        return {"status": "skipped", "reason": "Aucun fichier traité disponible"}
    report = generate_pptx(filters={"upload_id": str(latest.id)}, upload=latest, generated_by_task=True)
    return {"status": "ok", "report_id": report.id, "file": report.file.name}
