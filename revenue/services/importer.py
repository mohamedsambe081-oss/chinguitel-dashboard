from __future__ import annotations

from decimal import Decimal, InvalidOperation
from django.utils import timezone
import pandas as pd

from revenue.models import DataUpload, RevenueRecord
from .columns import detect_columns

from .category_rules import infer_category, standardize_package_name


def _clean_revenue(value) -> Decimal | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).replace(" ", "").replace("\u00a0", "").replace(",", ".")
    try:
        amount = Decimal(text)
    except InvalidOperation:
        return None
    if amount < 0:
        return None
    return amount.quantize(Decimal("0.01"))


def process_upload(upload: DataUpload) -> DataUpload:
    errors: list[str] = []
    try:
        df = pd.read_excel(upload.file.path)
        detected = detect_columns(df)
        date_col = detected["date"]
        package_col = detected["package"]
        revenue_col = detected["revenue"]

        clean = pd.DataFrame()
        clean["date"] = pd.to_datetime(df[date_col], errors="coerce", dayfirst=True).dt.date
        clean["package"] = df[package_col].astype(str).str.strip().map(standardize_package_name)
        clean["revenue"] = df[revenue_col].map(_clean_revenue)

        valid = clean.dropna(subset=["date", "package", "revenue"])
        valid = valid[valid["package"].str.lower().ne("nan")]
        valid = valid[valid["package"].str.len() > 0]

        rejected = len(df) - len(valid)

        RevenueRecord.objects.filter(upload=upload).delete()
        records = [
            RevenueRecord(
                upload=upload,
                date=row.date,
                package=row.package,
                category=infer_category(row.package),
                revenue=row.revenue,
                raw_payload={
                    "source_date_col": str(date_col),
                    "source_package_col": str(package_col),
                    "source_revenue_col": str(revenue_col),
                },
            )
            for row in valid.itertuples(index=False)
        ]
        RevenueRecord.objects.bulk_create(records, batch_size=1000)

        upload.status = "processed"
        upload.rows_imported = len(records)
        upload.rows_rejected = rejected
        upload.date_column = str(date_col)
        upload.package_column = str(package_col)
        upload.revenue_column = str(revenue_col)
        upload.errors = errors
        upload.processed_at = timezone.now()
        upload.save()
        return upload
    except Exception as exc:
        upload.status = "failed"
        upload.errors = [str(exc)]
        upload.processed_at = timezone.now()
        upload.save()
        return upload
