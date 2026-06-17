from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
import math
import numpy as np
from datetime import date
import pandas as pd
from django.db.models import Sum, Count, Min, Max
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth
from sklearn.ensemble import IsolationForest
from scipy import stats

from revenue.models import RevenueRecord


def _iso_date(value) -> str:
    """Return YYYY-MM-DD for datetime.date, datetime.datetime, pandas Timestamp or strings."""
    if value is None:
        return ""
    if hasattr(value, "date") and callable(value.date):
        return value.date().isoformat()
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def qs_to_frame(qs) -> pd.DataFrame:
    rows = list(qs.values("date", "package", "category", "revenue"))
    if not rows:
        return pd.DataFrame(columns=["date", "package", "category", "revenue"])
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    df["revenue"] = pd.to_numeric(df["revenue"], errors="coerce").fillna(0.0)
    return df


def filter_records(params):
    qs = RevenueRecord.objects.all()
    upload_id = params.get("upload_id")
    if upload_id:
        qs = qs.filter(upload_id=upload_id)
    date_from = params.get("date_from")
    date_to = params.get("date_to")
    category = params.get("category")
    package = params.get("package")
    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)
    if category:
        qs = qs.filter(category=category)
    if package:
        qs = qs.filter(package=package)
    return qs


def _money(value) -> float:
    if isinstance(value, Decimal):
        return float(value)
    return float(value or 0)


def summary(qs) -> dict:
    agg = qs.aggregate(
        total=Sum("revenue"),
        rows=Count("id"),
        packages=Count("package", distinct=True),
        date_min=Min("date"),
        date_max=Max("date"),
    )
    total = _money(agg["total"])
    rows = agg["rows"] or 0
    date_min = agg["date_min"]
    date_max = agg["date_max"]
    days = (date_max - date_min).days + 1 if date_min and date_max else 0
    daily_avg = total / days if days else 0

    wow = None
    if date_max:
        current_start = date_max - timedelta(days=6)
        previous_start = current_start - timedelta(days=7)
        previous_end = current_start - timedelta(days=1)
        current_total = _money(qs.filter(date__gte=current_start, date__lte=date_max).aggregate(v=Sum("revenue"))["v"])
        previous_total = _money(qs.filter(date__gte=previous_start, date__lte=previous_end).aggregate(v=Sum("revenue"))["v"])
        if previous_total > 0:
            wow = ((current_total - previous_total) / previous_total) * 100

    return {
        "total_revenue": round(total, 2),
        "rows": rows,
        "packages": agg["packages"] or 0,
        "date_min": date_min.isoformat() if date_min else None,
        "date_max": date_max.isoformat() if date_max else None,
        "days": days,
        "daily_average": round(daily_avg, 2),
        "wow_percent": round(wow, 2) if wow is not None else None,
    }


def descriptive_stats(qs) -> dict:
    df = qs_to_frame(qs)
    if df.empty:
        return {}
    daily = df.groupby("date", as_index=False)["revenue"].sum()
    values = daily["revenue"].to_numpy(dtype=float)
    return {
        "mean": round(float(np.mean(values)), 2),
        "median": round(float(np.median(values)), 2),
        "std": round(float(np.std(values, ddof=1)), 2) if len(values) > 1 else 0,
        "min": round(float(np.min(values)), 2),
        "max": round(float(np.max(values)), 2),
        "p25": round(float(np.percentile(values, 25)), 2),
        "p75": round(float(np.percentile(values, 75)), 2),
        "p90": round(float(np.percentile(values, 90)), 2),
        "p95": round(float(np.percentile(values, 95)), 2),
    }


def time_series(qs, granularity="day") -> dict:
    trunc = {"day": TruncDay, "week": TruncWeek, "month": TruncMonth}.get(granularity, TruncDay)
    data = (
        qs.annotate(period=trunc("date"))
        .values("period")
        .annotate(revenue=Sum("revenue"), rows=Count("id"))
        .order_by("period")
    )
    df = pd.DataFrame(list(data))
    if df.empty:
        return {"labels": [], "revenue": [], "ma7": []}
    df["revenue"] = pd.to_numeric(df["revenue"], errors="coerce").fillna(0)
    if granularity == "day":
        df["ma7"] = df["revenue"].rolling(7, min_periods=1).mean()
    else:
        df["ma7"] = np.nan
    return {
        "labels": [_iso_date(p) for p in df["period"]],
        "revenue": [round(float(v), 2) for v in df["revenue"]],
        "ma7": [None if math.isnan(v) else round(float(v), 2) for v in df["ma7"]],
    }


def package_breakdown(qs, limit=12) -> dict:
    data = (
        qs.values("package", "category")
        .annotate(revenue=Sum("revenue"), rows=Count("id"))
        .order_by("-revenue")[:limit]
    )
    rows = list(data)
    return {
        "labels": [r["package"] for r in rows],
        "categories": [r["category"] for r in rows],
        "revenue": [round(_money(r["revenue"]), 2) for r in rows],
        "rows": [r["rows"] for r in rows],
    }


def category_breakdown(qs) -> dict:
    data = qs.values("category").annotate(revenue=Sum("revenue")).order_by("-revenue")
    rows = list(data)
    return {
        "labels": [r["category"] for r in rows],
        "revenue": [round(_money(r["revenue"]), 2) for r in rows],
    }


def calendar_heatmap(qs) -> dict:
    df = qs_to_frame(qs)
    if df.empty:
        return {"days": []}
    daily = df.groupby("date", as_index=False)["revenue"].sum()
    max_value = daily["revenue"].max() or 1
    daily["level"] = np.ceil((daily["revenue"] / max_value) * 5).astype(int).clip(1, 5)
    return {
        "days": [
            {
                "date": _iso_date(row.date),
                "revenue": round(float(row.revenue), 2),
                "level": int(row.level),
            }
            for row in daily.itertuples(index=False)
        ]
    }


def forecast_4_weeks(qs) -> dict:
    """Forecast the next 3 weeks of revenue with an econometric ARIMA model.

    The function name is kept for backward compatibility with the existing API,
    but the application displays a 3-week forecast in the Machine Learning tab.
    The target variable is weekly total revenue: Y_t = sum(ORDER_FEES) by week.
    """
    df = qs_to_frame(qs)
    if df.empty:
        return {"method": "none", "points": [], "history": []}

    # Build the weekly time series required by ARIMA.
    weekly = (
        df.set_index("date")[["revenue"]]
        .resample("W-MON")
        .sum()
        .rename(columns={"revenue": "y"})
        .sort_index()
    )
    weekly["y"] = pd.to_numeric(weekly["y"], errors="coerce").fillna(0.0)

    # A very short time series cannot be estimated reliably with ARIMA.
    if len(weekly) < 8:
        return _naive_weekly_forecast(weekly, reason="historique insuffisant pour estimer un modèle ARIMA")

    try:
        from statsmodels.tsa.arima.model import ARIMA
        from statsmodels.tsa.stattools import adfuller

        y = weekly["y"].astype(float)

        # In this project we use a parsimonious ARIMA(1,1,1), adapted to about 51 weeks of data.
        # d=1 means that the model works on weekly changes to reduce non-stationarity.
        order = (1, 1, 1)
        model = ARIMA(y, order=order, enforce_stationarity=False, enforce_invertibility=False)
        fitted = model.fit()
        forecast_res = fitted.get_forecast(steps=3)
        mean = forecast_res.predicted_mean
        conf = forecast_res.conf_int(alpha=0.10)  # 90% confidence interval

        last_week = weekly.index.max()
        future_dates = pd.date_range(last_week + pd.Timedelta(weeks=1), periods=3, freq="W-MON")

        # ADF test is included for documentation/reporting. If it fails, keep the app working.
        adf_pvalue = None
        try:
            adf_pvalue = float(adfuller(y.dropna(), autolag="AIC")[1])
        except Exception:
            adf_pvalue = None

        points = []
        lower_col, upper_col = conf.columns[0], conf.columns[1]
        for i, d in enumerate(future_dates):
            yhat = float(mean.iloc[i])
            lo = float(conf.iloc[i][lower_col])
            hi = float(conf.iloc[i][upper_col])
            points.append({
                "date": _iso_date(d),
                "yhat": round(max(yhat, 0), 2),
                "yhat_lower": round(max(lo, 0), 2),
                "yhat_upper": round(max(hi, 0), 2),
            })

        fitted_values = fitted.fittedvalues.reindex(weekly.index).fillna(method="bfill").fillna(0)
        errors = y - fitted_values
        rmse = float(np.sqrt(np.mean(np.square(errors)))) if len(errors) else 0.0
        mae = float(np.mean(np.abs(errors))) if len(errors) else 0.0

        return {
            "method": "ARIMA(1,1,1)",
            "order": {"p": 1, "d": 1, "q": 1},
            "target": "Weekly total revenue",
            "adf_pvalue": round(adf_pvalue, 4) if adf_pvalue is not None else None,
            "aic": round(float(fitted.aic), 2) if fitted.aic is not None else None,
            "bic": round(float(fitted.bic), 2) if fitted.bic is not None else None,
            "rmse": round(rmse, 2),
            "mae": round(mae, 2),
            "history": [
                {"date": _iso_date(idx), "y": round(float(val), 2)}
                for idx, val in weekly["y"].tail(20).items()
            ],
            "points": points,
        }
    except Exception as exc:
        return _naive_weekly_forecast(weekly, reason=f"fallback après erreur ARIMA: {exc}")


def _naive_weekly_forecast(weekly: pd.DataFrame, reason: str) -> dict:
    weekly = weekly.copy()
    if weekly.empty:
        return {"method": "none", "reason": reason, "points": [], "history": []}
    last_date = pd.to_datetime(weekly.index.max())
    base = float(weekly["y"].tail(4).mean()) if len(weekly) else 0.0
    std = float(weekly["y"].tail(4).std()) if len(weekly) > 1 else 0.0
    points = []
    for i in range(1, 4):
        d = last_date + pd.Timedelta(weeks=i)
        points.append({
            "date": _iso_date(d),
            "yhat": round(max(base, 0), 2),
            "yhat_lower": round(max(base - 1.64 * std, 0), 2),
            "yhat_upper": round(max(base + 1.64 * std, 0), 2),
        })
    return {
        "method": "Naive MA4",
        "reason": reason,
        "history": [
            {"date": _iso_date(idx), "y": round(float(val), 2)}
            for idx, val in weekly["y"].tail(20).items()
        ],
        "points": points,
    }


def detect_anomalies(qs) -> dict:
    df = qs_to_frame(qs)
    if df.empty:
        return {"rows": []}
    grouped = df.groupby(["date", "package", "category"], as_index=False)["revenue"].sum()
    grouped["z_score"] = grouped.groupby("package")["revenue"].transform(
        lambda x: stats.zscore(x, nan_policy="omit") if len(x) > 2 and x.std() > 0 else np.zeros(len(x))
    )
    grouped["z_anomaly"] = grouped["z_score"].abs() >= 3

    if len(grouped) >= 20:
        features = grouped[["revenue"]].to_numpy(dtype=float)
        model = IsolationForest(contamination=0.05, random_state=42)
        grouped["iforest"] = model.fit_predict(features) == -1
    else:
        grouped["iforest"] = False

    anomalies = grouped[grouped["z_anomaly"] | grouped["iforest"]].sort_values("revenue", ascending=False)
    return {
        "rows": [
            {
                "date": _iso_date(r.date),
                "package": r.package,
                "category": r.category,
                "revenue": round(float(r.revenue), 2),
                "z_score": round(float(r.z_score), 2),
                "method": "IsolationForest + Z-score" if r.iforest and r.z_anomaly else "IsolationForest" if r.iforest else "Z-score",
            }
            for r in anomalies.head(100).itertuples(index=False)
        ]
    }


def eda(qs) -> dict:
    df = qs_to_frame(qs)
    if df.empty:
        return {"distribution": [], "concentration": {}, "monthly_matrix": []}
    package_sum = df.groupby("package", as_index=False)["revenue"].sum().sort_values("revenue", ascending=False)
    total = package_sum["revenue"].sum() or 1
    concentration = {
        "top_5_share": round(float(package_sum.head(5)["revenue"].sum() / total * 100), 2),
        "top_10_share": round(float(package_sum.head(10)["revenue"].sum() / total * 100), 2),
        "top_20_share": round(float(package_sum.head(20)["revenue"].sum() / total * 100), 2),
    }
    values = df["revenue"].to_numpy(dtype=float)
    counts, bins = np.histogram(values, bins=min(20, max(5, len(values) // 10)))
    df["month"] = df["date"].dt.to_period("M").astype(str)
    matrix = df.pivot_table(index="package", columns="month", values="revenue", aggfunc="sum", fill_value=0)
    matrix = matrix.loc[matrix.sum(axis=1).sort_values(ascending=False).head(15).index]
    return {
        "distribution": [
            {"bin_start": round(float(bins[i]), 2), "bin_end": round(float(bins[i + 1]), 2), "count": int(counts[i])}
            for i in range(len(counts))
        ],
        "concentration": concentration,
        "monthly_matrix": [
            {"package": idx, **{col: round(float(matrix.loc[idx, col]), 2) for col in matrix.columns}}
            for idx in matrix.index
        ],
    }


def weekly_revenue_percentage(qs) -> dict:
    """Weekly revenue with week-over-week change rate for PPT-style charts."""
    df = qs_to_frame(qs)
    if df.empty:
        return {"title": "TOTAL REVENUE", "labels": [], "revenue": [], "revenue_millions": [], "change_rate": []}
    df = df.sort_values("date")
    df["week"] = df["date"].dt.to_period("W")
    weekly = df.groupby("week", as_index=False)["revenue"].sum().sort_values("week")
    weekly["change_rate"] = weekly["revenue"].pct_change() * 100
    return {
        "title": "TOTAL REVENUE",
        "labels": [f"{p.start_time:%d-%b}" for p in weekly["week"]],
        "revenue": [round(float(v), 2) for v in weekly["revenue"]],
        "revenue_millions": [round(float(v) / 1_000_000, 2) for v in weekly["revenue"]],
        "change_rate": [None if pd.isna(v) else round(float(v), 1) for v in weekly["change_rate"]],
    }



PACKAGE_PERCENT_GROUPS = {
    "MauriNet": ["maurinet", "net", "internet", "internat", "1 year data"],
    "MauriAllo": ["mauriallo", "mauri allo", "allo", "voice"],
    "MauriMix": ["maurimix", "mauri mix", "mauri attay", "mix"],
    "Raha": ["raha"],
}


def _normalize_package_name(value: str) -> str:
    return str(value or "").strip().lower().replace("-", " ").replace("_", " ")


def _package_group_mask(df: pd.DataFrame, package_group: str):
    keywords = PACKAGE_PERCENT_GROUPS.get(package_group, [package_group.lower()])
    names = df["package"].map(_normalize_package_name)
    mask = pd.Series(False, index=df.index)
    for kw in keywords:
        kw = _normalize_package_name(kw)
        if kw == "net":
            mask = mask | names.str.contains(r"(^|\s)net(\s|\d|$)", regex=True, na=False)
        elif kw == "mix":
            mask = mask | names.str.contains(r"(^|\s)mix(\s|\d|$)", regex=True, na=False)
        elif kw == "allo":
            mask = mask | names.str.contains(r"(^|\s)allo(\s|\d|$)", regex=True, na=False)
        else:
            mask = mask | names.str.contains(kw, regex=False, na=False)
    return mask


def package_weekly_revenue_percentage(qs, package_group: str) -> dict:
    """Weekly package-group revenue with week-over-week change rate for PPT-style charts."""
    df = qs_to_frame(qs)
    if df.empty:
        return {"package": package_group, "title": f"{package_group.upper()} REVENUE", "labels": [], "revenue": [], "revenue_millions": [], "change_rate": []}

    df = df.sort_values("date")
    df["week"] = df["date"].dt.to_period("W")
    all_weeks = df.groupby("week", as_index=False)["revenue"].sum()[["week"]]
    selected = df[_package_group_mask(df, package_group)]

    if selected.empty:
        merged = all_weeks.copy()
        merged["package_revenue"] = 0.0
    else:
        weekly_pack = selected.groupby("week", as_index=False)["revenue"].sum().rename(columns={"revenue": "package_revenue"})
        merged = all_weeks.merge(weekly_pack, on="week", how="left").fillna({"package_revenue": 0})

    revenue_for_change = merged["package_revenue"].replace(0, np.nan)
    merged["change_rate"] = revenue_for_change.pct_change() * 100
    return {
        "package": package_group,
        "title": f"{package_group.upper()} REVENUE",
        "labels": [f"{p.start_time:%d-%b}" for p in merged["week"]],
        "revenue": [round(float(v), 2) for v in merged["package_revenue"]],
        "revenue_millions": [round(float(v) / 1_000_000, 2) for v in merged["package_revenue"]],
        "change_rate": [None if pd.isna(v) else round(float(v), 1) for v in merged["change_rate"]],
    }

def overview_charts(qs) -> dict:
    """Dynamic PowerPoint-like overview charts for the currently selected data."""
    df = qs_to_frame(qs)
    if df.empty:
        empty = {"labels": [], "revenue": []}
        return {
            "trend": {"labels": [], "revenue": [], "change_rate": []},
            "category_trend": {"labels": [], "series": []},
            "package_compare": {"labels": [], "previous": [], "current": [], "previous_label": "Période précédente", "current_label": "Période actuelle"},
            "category_weekly_table": {"headers": ["Category", "Previous week", "Current week", "Diff", "Cont."], "rows": []},
            "category_mix": empty,
        }

    df = df.sort_values("date")
    min_date = df["date"].min()
    max_date = df["date"].max()
    span_days = max(1, int((max_date - min_date).days) + 1)
    freq = "W-MON" if span_days > 45 else "D"

    period = df["date"].dt.to_period("W" if freq == "W-MON" else "D")
    df = df.assign(period=period)
    period_sum = df.groupby("period", as_index=False)["revenue"].sum().sort_values("period")
    labels = [str(p) if freq != "W-MON" else f"{p.start_time:%d-%b} / {p.end_time:%d-%b}" for p in period_sum["period"]]
    revenues = [round(float(v), 2) for v in period_sum["revenue"]]
    change = period_sum["revenue"].pct_change().replace([np.inf, -np.inf], np.nan)
    change_rates = [None if pd.isna(v) else round(float(v), 4) for v in change]

    top_categories = (
        df.groupby("category", as_index=False)["revenue"].sum()
        .sort_values("revenue", ascending=False)
        .head(6)["category"].tolist()
    )
    cat_pivot = (
        df[df["category"].isin(top_categories)]
        .pivot_table(index="period", columns="category", values="revenue", aggfunc="sum", fill_value=0)
        .reindex(period_sum["period"])
        .fillna(0)
    )
    cat_series = [
        {"name": str(cat), "data": [round(float(v), 2) for v in cat_pivot[cat].tolist()]}
        for cat in cat_pivot.columns
    ]

    midpoint = min_date + pd.Timedelta(days=max(1, span_days // 2) - 1)
    previous_df = df[df["date"] <= midpoint]
    current_df = df[df["date"] > midpoint]
    if current_df.empty:
        current_df = df
        previous_df = df.iloc[0:0]
    pkg_current = current_df.groupby("package", as_index=False)["revenue"].sum()
    pkg_previous = previous_df.groupby("package", as_index=False)["revenue"].sum()
    top_packages = pkg_current.sort_values("revenue", ascending=False).head(12)["package"].tolist()
    prev_map = dict(zip(pkg_previous["package"], pkg_previous["revenue"]))
    curr_map = dict(zip(pkg_current["package"], pkg_current["revenue"]))

    cat_mix = df.groupby("category", as_index=False)["revenue"].sum().sort_values("revenue", ascending=False)

    week_df = df.assign(week=df["date"].dt.to_period("W"))
    weeks = sorted(week_df["week"].dropna().unique())
    selected_weeks = weeks[-2:] if len(weeks) >= 2 else weeks
    previous_week = selected_weeks[0] if selected_weeks else None
    current_week = selected_weeks[-1] if selected_weeks else None
    weekly_pivot = (
        week_df[week_df["week"].isin(selected_weeks)]
        .pivot_table(index="category", columns="week", values="revenue", aggfunc="sum", fill_value=0)
        if selected_weeks else pd.DataFrame()
    )
    category_order = ["DATA", "VOICE", "MIX", "SMS", "OTHERS"]
    def _cat_value(cat, week):
        if week is None or weekly_pivot.empty:
            return 0.0
        if cat == "OTHERS":
            matches = [idx for idx in weekly_pivot.index if str(idx).strip().upper() in {"OTHERS", "OTHER", "AUTRES", "others"}]
        else:
            matches = [idx for idx in weekly_pivot.index if str(idx).strip().upper() == cat]
        return float(sum(float(weekly_pivot.loc[idx, week]) for idx in matches if week in weekly_pivot.columns))
    previous_total = float(week_df[week_df["week"] == previous_week]["revenue"].sum()) if previous_week is not None else 0.0
    current_total = float(week_df[week_df["week"] == current_week]["revenue"].sum()) if current_week is not None else 0.0
    category_week_rows = []
    for cat in category_order:
        prev = _cat_value(cat, previous_week)
        curr = _cat_value(cat, current_week)
        diff = None if prev == 0 else round(((curr - prev) / prev) * 100, 1)
        cont = None if previous_total == 0 else round(((curr - prev) / previous_total) * 100, 1)
        category_week_rows.append({"category": cat, "previous": round(prev, 0), "current": round(curr, 0), "diff": diff, "cont": cont})
    total_diff = None if previous_total == 0 else round(((current_total - previous_total) / previous_total) * 100, 1)
    category_week_rows.append({"category": "Total subscription", "previous": round(previous_total, 0), "current": round(current_total, 0), "diff": total_diff, "cont": total_diff})
    category_weekly_table = {
        "headers": [
            "Packs Pillars",
            f"{previous_week.start_time:%d-%b} {previous_week.end_time:%d-%b-%y}" if previous_week is not None else "Previous week",
            f"{current_week.start_time:%d-%b} {current_week.end_time:%d-%b-%y}" if current_week is not None else "Current week",
            "Diff",
            "Cont.",
        ],
        "rows": category_week_rows,
    }

    return {
        "trend": {"labels": labels, "revenue": revenues, "change_rate": change_rates},
        "category_trend": {"labels": labels, "series": cat_series},
        "package_compare": {
            "labels": top_packages,
            "previous": [round(float(prev_map.get(p, 0)), 2) for p in top_packages],
            "current": [round(float(curr_map.get(p, 0)), 2) for p in top_packages],
            "previous_label": f"{_iso_date(previous_df['date'].min())} → {_iso_date(previous_df['date'].max())}" if not previous_df.empty else "Période précédente",
            "current_label": f"{_iso_date(current_df['date'].min())} → {_iso_date(current_df['date'].max())}" if not current_df.empty else "Période actuelle",
        },
        "category_weekly_table": category_weekly_table,
        "category_mix": {
            "labels": [str(v) for v in cat_mix["category"].tolist()],
            "revenue": [round(float(v), 2) for v in cat_mix["revenue"].tolist()],
        },
    }



def advanced_dashboard(qs, granularity: str = "week") -> dict:
    """Advanced dashboard modules inspired by the standalone analytics HTML dashboard."""
    df = qs_to_frame(qs)
    empty = {
        "kpis": {}, "daily_ma": {"labels": [], "revenue": [], "ma7": []},
        "monthly_avg": {"labels": [], "avg": [], "global_avg": 0},
        "weekly": {"labels": [], "revenue": [], "wow": []},
        "category_evolution": {"labels": [], "series": []},
        "data_top10": {"labels": [], "revenue": []},
        "data_top5_trend": {"labels": [], "series": []},
        "category_share": {"labels": [], "revenue": []},
        "wow_table": {"headers": ["Category", "Previous Week", "Reference Week", "Change %", "Contribution %"], "rows": []},
        "stacked": {"labels": [], "series": []},
        "top15": {"labels": [], "revenue": [], "share": []},
        "heatmap": {"weeks": [], "days": []},
    }
    if df.empty:
        return empty

    df = df.sort_values("date")
    granularity = (granularity or "week").lower()
    period_code = {"day": "D", "week": "W", "month": "M"}.get(granularity, "W")
    period_name = {"day": "Day", "week": "Week", "month": "Month"}.get(granularity, "Week")
    def _period_label(p):
        if period_code == "D":
            return f"{p.start_time:%d-%b-%Y}"
        if period_code == "M":
            return f"{p.start_time:%b %Y}"
        return f"{p.start_time:%d-%b} → {p.end_time:%d-%b}"
    df["category_norm"] = df["category"].astype(str).str.upper().replace({"OTHERS":"others","OTHER":"others","AUTRES":"others"})
    # keep user-facing categories exactly as requested
    df["category_norm"] = df["category_norm"].replace({"OTHERS":"others"})
    df.loc[~df["category_norm"].isin(["DATA", "VOICE", "MIX", "SMS", "others"]), "category_norm"] = "others"

    daily = df.groupby("date", as_index=False)["revenue"].sum().sort_values("date")
    daily["ma7"] = daily["revenue"].rolling(7, min_periods=1).mean()
    global_avg = float(daily["revenue"].mean()) if len(daily) else 0.0

    by_month_day = daily.copy()
    by_month_day["month"] = by_month_day["date"].dt.to_period("M")
    monthly_avg = by_month_day.groupby("month", as_index=False)["revenue"].mean().sort_values("month")

    df["period"] = df["date"].dt.to_period(period_code)
    weekly = df.groupby("period", as_index=False)["revenue"].sum().sort_values("period")
    weekly["wow"] = weekly["revenue"].pct_change() * 100
    week_labels = [_period_label(p) for p in weekly["period"]]

    cat_order = ["DATA", "VOICE", "MIX", "SMS", "others"]
    cat_week = df.pivot_table(index="period", columns="category_norm", values="revenue", aggfunc="sum", fill_value=0).reindex(weekly["period"]).fillna(0)
    for c in cat_order:
        if c not in cat_week.columns:
            cat_week[c] = 0
    cat_series = [{"name": c if c != "others" else "OTHERS", "data": [round(float(v), 2) for v in cat_week[c].tolist()]} for c in cat_order]

    ref_week = weekly["period"].iloc[-1] if len(weekly) else None
    prev_week = weekly["period"].iloc[-2] if len(weekly) > 1 else None
    ref_df = df[df["period"] == ref_week] if ref_week is not None else df.iloc[0:0]
    prev_df = df[df["period"] == prev_week] if prev_week is not None else df.iloc[0:0]

    data_ref = ref_df[ref_df["category_norm"] == "DATA"]
    data_top = data_ref.groupby("package", as_index=False)["revenue"].sum().sort_values("revenue", ascending=False).head(10)

    top5_names = (df[df["category_norm"] == "DATA"].groupby("package", as_index=False)["revenue"].sum()
                  .sort_values("revenue", ascending=False).head(5)["package"].tolist())
    data_top5_trend = []
    if top5_names:
        data_pkg_week = (df[(df["category_norm"] == "DATA") & (df["package"].isin(top5_names))]
                         .pivot_table(index="period", columns="package", values="revenue", aggfunc="sum", fill_value=0)
                         .reindex(weekly["period"]).fillna(0))
        data_top5_trend = [{"name": p, "data": [round(float(v), 2) for v in data_pkg_week[p].tolist()]} for p in top5_names if p in data_pkg_week.columns]

    cat_ref = ref_df.groupby("category_norm", as_index=False)["revenue"].sum()
    cat_ref_map = dict(zip(cat_ref["category_norm"], cat_ref["revenue"]))
    cat_labels = [c if c != "others" else "OTHERS" for c in cat_order]
    cat_values = [round(float(cat_ref_map.get(c, 0)), 2) for c in cat_order]

    prev_cat = dict(zip(prev_df.groupby("category_norm", as_index=False)["revenue"].sum()["category_norm"], prev_df.groupby("category_norm", as_index=False)["revenue"].sum()["revenue"])) if not prev_df.empty else {}
    ref_total = float(ref_df["revenue"].sum()) or 1.0
    wow_rows = []
    for c in cat_order:
        prev = float(prev_cat.get(c, 0) or 0)
        cur = float(cat_ref_map.get(c, 0) or 0)
        change = None if prev == 0 else round((cur - prev) / prev * 100, 1)
        share = round((cur / ref_total) * 100, 1) if ref_total else 0.0
        wow_rows.append({"category": c if c != "others" else "OTHERS", "previous": round(prev, 0), "current": round(cur, 0), "change": change, "share": share})

    top15 = ref_df.groupby("package", as_index=False)["revenue"].sum().sort_values("revenue", ascending=False).head(15)

    # Last 12 calendar weeks heatmap by day-of-week (kept weekly because it is a heatmap).
    heat_base = df.copy()
    heat_base["heat_week"] = heat_base["date"].dt.to_period("W")
    heat_weeks = sorted(heat_base["heat_week"].dropna().unique())
    last_weeks = list(heat_weeks[-12:])
    heat_rows = []
    if last_weeks:
        heat_df = heat_base[heat_base["heat_week"].isin(last_weeks)].copy()
        heat_df["dow"] = heat_df["date"].dt.day_name().str[:3]
        heat = heat_df.groupby(["heat_week", "dow"], as_index=False)["revenue"].sum()
        max_heat = float(heat["revenue"].max()) if not heat.empty else 1.0
        dow_order = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        for w in last_weeks:
            for d in dow_order:
                v = float(heat[(heat["heat_week"] == w) & (heat["dow"] == d)]["revenue"].sum())
                heat_rows.append({"week": f"{w.start_time:%d-%b}", "day": d, "revenue": round(v, 2), "level": int(math.ceil((v / max_heat) * 5)) if max_heat else 0})

    return {
        "kpis": {
            "reference_week": (_period_label(ref_week) if ref_week is not None else ""),
            "reference_period_label": period_name,
            "total_revenue": round(float(df["revenue"].sum()), 2),
            "reference_revenue": round(float(ref_df["revenue"].sum()), 2),
            "daily_average": round(global_avg, 2),
            "packages": int(df["package"].nunique()),
            "last_wow": None if len(weekly) < 2 or pd.isna(weekly["wow"].iloc[-1]) else round(float(weekly["wow"].iloc[-1]), 1),
        },
        "daily_ma": {"labels": [_iso_date(d) for d in daily["date"]], "revenue": [round(float(v), 2) for v in daily["revenue"]], "ma7": [round(float(v), 2) for v in daily["ma7"]]},
        "monthly_avg": {"labels": [str(p) for p in monthly_avg["month"]], "avg": [round(float(v), 2) for v in monthly_avg["revenue"]], "global_avg": round(global_avg, 2)},
        "weekly": {"labels": week_labels, "revenue": [round(float(v), 2) for v in weekly["revenue"]], "wow": [None if pd.isna(v) else round(float(v), 1) for v in weekly["wow"]]},
        "category_evolution": {"labels": week_labels, "series": cat_series},
        "data_top10": {"labels": data_top["package"].tolist(), "revenue": [round(float(v), 2) for v in data_top["revenue"]]},
        "data_top5_trend": {"labels": week_labels, "series": data_top5_trend},
        "category_share": {"labels": cat_labels, "revenue": cat_values},
        "wow_table": {"headers": ["Category", "Previous "+period_name, "Reference "+period_name, "Change %", "Contribution %"], "rows": wow_rows},
        "stacked": {"labels": week_labels, "series": cat_series},
        "top15": {"labels": top15["package"].tolist(), "revenue": [round(float(v), 2) for v in top15["revenue"]], "share": [round(float(v) / ref_total * 100, 1) for v in top15["revenue"]]},
        "heatmap": {"weeks": [f"{w.start_time:%d-%b}" for w in last_weeks], "days": heat_rows},
    }



def detail_dashboard(qs, granularity: str = "week") -> dict:
    """Category detail screen for DATA, VOICE and MIX, matching the standalone dashboard detail pages."""
    df = qs_to_frame(qs)
    empty = {
        "kpis": {},
        "weekly": {"labels": [], "revenue": [], "wow": [], "average": []},
        "top10": {"labels": [], "revenue": []},
        "stat_rows": [],
        "subcategories": [],
    }
    if df.empty:
        return empty

    df = df.sort_values("date")
    granularity = (granularity or "week").lower()
    period_code = {"day": "D", "week": "W", "month": "M"}.get(granularity, "W")
    def _period_label(p):
        if period_code == "D":
            return f"{p.start_time:%d-%b-%Y}"
        if period_code == "M":
            return f"{p.start_time:%b %Y}"
        return f"{p.start_time:%d-%b} → {p.end_time:%d-%b}"
    df["week"] = df["date"].dt.to_period(period_code)
    weekly = df.groupby("week", as_index=False).agg(revenue=("revenue", "sum"), rows=("revenue", "count"), packages=("package", "nunique"))
    weekly = weekly.sort_values("week")
    weekly["wow"] = weekly["revenue"].pct_change() * 100
    weekly["average"] = weekly["revenue"] / weekly["rows"].replace(0, np.nan)
    week_labels = [_period_label(p) for p in weekly["week"]]

    top10 = df.groupby("package", as_index=False)["revenue"].sum().sort_values("revenue", ascending=False).head(10)
    total = float(df["revenue"].sum()) or 1.0

    stat_rows = []
    for i, row in enumerate(weekly.itertuples(index=False), start=1):
        wdf = df[df["week"] == row.week]
        top_pkg = wdf.groupby("package", as_index=False)["revenue"].sum().sort_values("revenue", ascending=False).head(1)
        stat_rows.append({
            "rank": i,
            "period": _period_label(row.week),
            "revenue": round(float(row.revenue), 2),
            "wow": None if pd.isna(row.wow) else round(float(row.wow), 1),
            "packages": int(row.packages),
            "top_package": top_pkg["package"].iloc[0] if not top_pkg.empty else "—",
            "top_package_revenue": round(float(top_pkg["revenue"].iloc[0]), 2) if not top_pkg.empty else 0,
        })

    pkg_week = df.pivot_table(index="week", columns="package", values="revenue", aggfunc="sum", fill_value=0)
    subcats = []
    pkg_sum = df.groupby("package", as_index=False)["revenue"].sum().sort_values("revenue", ascending=False)
    for i, row in enumerate(pkg_sum.itertuples(index=False), start=1):
        series = pkg_week[row.package].tolist() if row.package in pkg_week.columns else []
        first = float(series[0]) if series else 0
        last = float(series[-1]) if series else 0
        trend = None if first == 0 else round((last - first) / first * 100, 1)
        periods = int(sum(1 for v in series if v > 0))
        subcats.append({
            "rank": i,
            "package": row.package,
            "revenue": round(float(row.revenue), 2),
            "share": round(float(row.revenue) / total * 100, 1),
            "periods": periods,
            "average": round(float(row.revenue) / periods, 2) if periods else 0,
            "trend": trend,
        })

    return {
        "kpis": {
            "total_revenue": round(total, 2),
            "packages": int(df["package"].nunique()),
            "rows": int(len(df)),
            "daily_average": round(float(df.groupby("date")["revenue"].sum().mean()), 2),
            "last_wow": None if len(weekly) < 2 or pd.isna(weekly["wow"].iloc[-1]) else round(float(weekly["wow"].iloc[-1]), 1),
        },
        "weekly": {
            "labels": week_labels,
            "revenue": [round(float(v), 2) for v in weekly["revenue"]],
            "wow": [None if pd.isna(v) else round(float(v), 1) for v in weekly["wow"]],
            "average": [0 if pd.isna(v) else round(float(v), 2) for v in weekly["average"]],
        },
        "top10": {"labels": top10["package"].tolist(), "revenue": [round(float(v), 2) for v in top10["revenue"]]},
        "stat_rows": stat_rows,
        "subcategories": subcats,
    }


def weekly_marketing_report(qs, week_id: str | None = None) -> dict:
    """Interactive weekly report matching the marketing PPT logic.

    Default reference period is the last complete imported week. The user can choose
    any other week from the returned weeks list.
    """
    df = qs_to_frame(qs)
    empty = {
        "weeks": [], "selected_week": None, "previous_week": None, "kpis": {},
        "total_revenue": {"labels": [], "revenue": [], "change_rate": []},
        "total_recharge": {"labels": [], "revenue": [], "change_rate": []},
        "report_date": date.today().strftime("%d/%m/%Y"),
        "title_period": None,
        "avg_daily": {"labels": [], "total": [], "change_rate": []},
        "category_avg_daily": {"labels": [], "series": []},
        "category_compare": {"headers": ["Category", "Previous Week", "Selected Week", "Change %"], "rows": []},
        "groups": [], "data_packs_combo": {"labels": [], "series": []},
    }
    if df.empty:
        return empty

    df = df.sort_values("date")
    df["week"] = df["date"].dt.to_period("W")
    weeks = sorted(df["week"].dropna().unique())
    if not weeks:
        return empty

    # Weekly Report charts must stay readable in the dashboard and in PowerPoint.
    # Use only the last 3 months of the imported time series for every trend chart.
    max_date = df["date"].max()
    chart_start = max_date - pd.DateOffset(months=3)
    chart_weeks = [p for p in weeks if p.end_time >= chart_start]
    if not chart_weeks:
        chart_weeks = weeks[-13:]

    def _week_id(p):
        return f"{p.start_time:%Y-%m-%d}_{p.end_time:%Y-%m-%d}"

    def _week_label(p):
        return f"{p.start_time:%d-%b-%Y} → {p.end_time:%d-%b-%Y}"

    selected = weeks[-1]
    if week_id:
        for p in weeks:
            if _week_id(p) == week_id or str(p) == week_id:
                selected = p
                break
    selected_index = weeks.index(selected)
    previous = weeks[selected_index - 1] if selected_index > 0 else None
    selected_df = df[df["week"] == selected]
    previous_df = df[df["week"] == previous] if previous is not None else df.iloc[0:0]

    def _values_for_weeks(frame, value_col, selected_weeks):
        mp = {r.week: float(getattr(r, value_col)) for r in frame.itertuples(index=False)}
        return [round(float(mp.get(p, 0.0)), 2) for p in selected_weeks]

    # Weekly total revenue + change rate
    weekly = df.groupby("week", as_index=False)["revenue"].sum().sort_values("week")
    weekly["change_rate"] = weekly["revenue"].pct_change() * 100

    # Average daily revenue by week, total and by category
    daily = df.groupby(["week", "date"], as_index=False)["revenue"].sum()
    avg_daily = daily.groupby("week", as_index=False)["revenue"].mean().sort_values("week")
    avg_daily["change_rate"] = avg_daily["revenue"].pct_change() * 100

    cat_daily = df.groupby(["week", "date", "category"], as_index=False)["revenue"].sum()
    cat_avg = cat_daily.groupby(["week", "category"], as_index=False)["revenue"].mean()
    categories = ["DATA", "VOICE", "MIX", "SMS", "OTHERS"]
    cat_series = []
    for cat in categories:
        sub = cat_avg[cat_avg["category"].astype(str).str.upper() == cat]
        vals = []
        mp = {r.week: float(r.revenue) for r in sub.itertuples(index=False)}
        for p in chart_weeks:
            vals.append(round(float(mp.get(p, 0.0)), 2))
        cat_series.append({"name": cat, "data": vals})

    def _pct_change(cur, prev):
        if not prev:
            return None
        return round(((cur - prev) / prev) * 100, 1)

    selected_total = float(selected_df["revenue"].sum())
    previous_total = float(previous_df["revenue"].sum()) if previous is not None else 0.0
    selected_days = max(1, selected_df["date"].nunique())
    previous_days = max(1, previous_df["date"].nunique()) if not previous_df.empty else 1

    compare_rows = []
    for cat in categories:
        cur = float(selected_df[selected_df["category"].astype(str).str.upper() == cat]["revenue"].sum())
        prev = float(previous_df[previous_df["category"].astype(str).str.upper() == cat]["revenue"].sum()) if not previous_df.empty else 0.0
        compare_rows.append({"category": cat, "previous": round(prev, 2), "current": round(cur, 2), "change": _pct_change(cur, prev)})
    compare_rows.append({"category": "TOTAL", "previous": round(previous_total, 2), "current": round(selected_total, 2), "change": _pct_change(selected_total, previous_total)})

    def _contains_any(series, keywords):
        names = series.astype(str).str.lower().str.replace("-", " ", regex=False).str.replace("_", " ", regex=False)
        mask = pd.Series(False, index=series.index)
        for kw in keywords:
            kw = kw.lower().replace("-", " ").replace("_", " ")
            if kw in {"net", "mix", "allo"}:
                mask = mask | names.str.contains(rf"(^|\s){kw}(\s|\d|$)", regex=True, na=False)
            else:
                mask = mask | names.str.contains(kw, regex=False, na=False)
        return mask

    group_defs = [
        ("MauriNet", ["maurinet", "internet", "net", "1 year data"]),
        ("MauriAllo", ["mauri allo", "mauriallo", "allo", "voice"]),
        ("MauriMix", ["mauri attay", "mauri mix", "maurimix", "mix"]),
        ("Raha", ["raha"]),
        ("Beinatna", ["beinatna"]),
    ]

    def _top_packages(source_df, keywords, limit=20):
        sub = source_df[_contains_any(source_df["package"], keywords)]
        if sub.empty:
            return []
        pack = sub.groupby("package", as_index=False)["revenue"].sum().sort_values("revenue", ascending=False).head(limit)
        return [{"package": str(r.package), "revenue": round(float(r.revenue), 2)} for r in pack.itertuples(index=False)]

    groups = []
    for name, keywords in group_defs:
        sub = df[_contains_any(df["package"], keywords)]
        if sub.empty:
            trend_vals = [0.0 for _ in chart_weeks]
        else:
            trend = sub.groupby("week", as_index=False)["revenue"].sum()
            mp = {r.week: float(r.revenue) for r in trend.itertuples(index=False)}
            trend_vals = [round(float(mp.get(p, 0.0)), 2) for p in chart_weeks]
        cr = pd.Series(trend_vals).replace(0, np.nan).pct_change() * 100
        groups.append({
            "name": name,
            "labels": [_week_label(p) for p in chart_weeks],
            "revenue": trend_vals,
            "revenue_millions": [round(v / 1_000_000, 3) for v in trend_vals],
            "change_rate": [None if pd.isna(v) else round(float(v), 1) for v in cr],
            "previous_top": _top_packages(previous_df, keywords) if previous is not None else [],
            "current_top": _top_packages(selected_df, keywords),
        })

    # MauriNet + Raha + Beinatna combo like the PPT data-packs slide
    combo_names = ["MauriNet", "MauriNet + Raha + Beinatna"]
    combo_series = []
    for label, keywords in [
        (combo_names[0], ["maurinet", "internet", "net", "1 year data"]),
        (combo_names[1], ["maurinet", "internet", "net", "1 year data", "raha", "beinatna"]),
    ]:
        sub = df[_contains_any(df["package"], keywords)]
        mp = {}
        if not sub.empty:
            trend = sub.groupby("week", as_index=False)["revenue"].sum()
            mp = {r.week: float(r.revenue) for r in trend.itertuples(index=False)}
        combo_series.append({"name": label, "data": [round(float(mp.get(p, 0.0)), 2) for p in chart_weeks]})

    return {
        "weeks": [{"id": _week_id(p), "label": _week_label(p)} for p in weeks],
        "selected_week": {"id": _week_id(selected), "label": _week_label(selected)},
        "previous_week": {"id": _week_id(previous), "label": _week_label(previous)} if previous is not None else None,
        "report_date": date.today().strftime("%d/%m/%Y"),
        "title_period": f"{selected.start_time:%d} to {selected.end_time:%d %b}",
        "kpis": {
            "selected_revenue": round(selected_total, 2),
            "previous_revenue": round(previous_total, 2),
            "change": _pct_change(selected_total, previous_total),
            "avg_daily": round(selected_total / selected_days, 2),
            "previous_avg_daily": round(previous_total / previous_days, 2) if previous is not None else 0,
            "days": selected_days,
            "packages": int(selected_df["package"].nunique()),
        },
        "total_revenue": {
            "labels": [_week_label(p) for p in chart_weeks],
            "revenue": _values_for_weeks(weekly, "revenue", chart_weeks),
            "revenue_millions": [round(v / 1_000_000, 3) for v in _values_for_weeks(weekly, "revenue", chart_weeks)],
            "change_rate": _values_for_weeks(weekly.fillna({"change_rate": 0}), "change_rate", chart_weeks),
        },
        # The imported file contains ORDER_FEES revenue only; this mirrors the PPT recharge panel with the same imported measure unless a recharge column is added later.
        "total_recharge": {
            "labels": [_week_label(p) for p in chart_weeks],
            "revenue": _values_for_weeks(weekly, "revenue", chart_weeks),
            "revenue_millions": [round(v / 1_000_000, 3) for v in _values_for_weeks(weekly, "revenue", chart_weeks)],
            "change_rate": _values_for_weeks(weekly.fillna({"change_rate": 0}), "change_rate", chart_weeks),
        },
        "avg_daily": {
            "labels": [_week_label(p) for p in chart_weeks],
            "total": _values_for_weeks(avg_daily, "revenue", chart_weeks),
            "change_rate": _values_for_weeks(avg_daily.fillna({"change_rate": 0}), "change_rate", chart_weeks),
        },
        "category_avg_daily": {"labels": [_week_label(p) for p in chart_weeks], "series": cat_series},
        "category_compare": {"headers": ["Category", "Previous Week", "Selected Week", "Change %"], "rows": compare_rows},
        "groups": groups,
        "data_packs_combo": {"labels": [_week_label(p) for p in chart_weeks], "series": combo_series},
    }



def daily_marketing_report(qs, week_id: str | None = None) -> dict:
    """Daily report for the 7 days of a selected week, using the Weekly Report style.

    The selected week defaults to the last imported week. The report exposes
    Monday → Sunday daily analyses: KPI, revenue, change rate, category mix,
    package groups, top packs and day-by-day comparison.
    """
    df = qs_to_frame(qs)
    empty = {
        "weeks": [], "selected_week": None, "report_date": date.today().strftime("%d/%m/%Y"),
        "title_period": None, "kpis": {}, "daily_revenue": {"labels": [], "revenue": [], "change_rate": []},
        "category_daily": {"labels": [], "series": []},
        "category_compare": {"headers": [], "rows": []},
        "day_kpis": [], "groups": [], "day_package_tables": [],
    }
    if df.empty:
        return empty

    df = df.sort_values("date")
    df["week"] = df["date"].dt.to_period("W")
    weeks = sorted(df["week"].dropna().unique())
    if not weeks:
        return empty

    def _week_id(p):
        return f"{p.start_time:%Y-%m-%d}_{p.end_time:%Y-%m-%d}"

    def _week_label(p):
        return f"{p.start_time:%d-%b-%Y} → {p.end_time:%d-%b-%Y}"

    selected = weeks[-1]
    if week_id:
        for p in weeks:
            if _week_id(p) == week_id or str(p) == week_id:
                selected = p
                break

    week_start = selected.start_time.normalize()
    day_dates = [week_start + pd.Timedelta(days=i) for i in range(7)]
    day_names_fr = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
    day_labels = [f"{name} {d:%d-%b}" for name, d in zip(day_names_fr, day_dates)]
    selected_df = df[df["week"] == selected].copy()
    selected_idx = weeks.index(selected)
    previous = weeks[selected_idx - 1] if selected_idx > 0 else None
    previous_df = df[df["week"] == previous].copy() if previous is not None else df.iloc[0:0].copy()

    daily_sum = selected_df.groupby("date", as_index=False)["revenue"].sum()
    daily_map = {pd.Timestamp(r.date).normalize(): float(r.revenue) for r in daily_sum.itertuples(index=False)}
    daily_values = [round(float(daily_map.get(d.normalize(), 0.0)), 2) for d in day_dates]
    daily_change = []
    prev_val = None
    for v in daily_values:
        if prev_val is None or prev_val == 0:
            daily_change.append(None)
        else:
            daily_change.append(round(((v - prev_val) / prev_val) * 100, 1))
        prev_val = v

    categories = ["DATA", "VOICE", "MIX", "SMS", "OTHERS"]
    df_cat = selected_df.copy()
    df_cat["category_norm"] = df_cat["category"].astype(str).str.upper()
    df_cat.loc[~df_cat["category_norm"].isin(categories), "category_norm"] = "OTHERS"
    cat_day = df_cat.groupby(["date", "category_norm"], as_index=False)["revenue"].sum()
    category_series = []
    for cat in categories:
        sub = cat_day[cat_day["category_norm"] == cat]
        mp = {pd.Timestamp(r.date).normalize(): float(r.revenue) for r in sub.itertuples(index=False)}
        category_series.append({"name": cat, "data": [round(float(mp.get(d.normalize(), 0.0)), 2) for d in day_dates]})

    def _pct_change(cur, prev):
        if prev is None or prev == 0:
            return None
        return round(((cur - prev) / prev) * 100, 1)

    # Category comparison table: each category compares selected week with previous week.
    comp_rows = []
    for cat, serie in zip(categories, category_series):
        vals = serie["data"]
        cur_total = round(sum(vals), 2)
        prev_total = 0.0
        if not previous_df.empty:
            prev_total = float(previous_df[previous_df["category"].astype(str).str.upper() == cat]["revenue"].sum())
        comp_rows.append({
            "category": cat,
            **{f"d{i}": vals[i] for i in range(7)},
            "change": _pct_change(cur_total, prev_total),
            "total": cur_total,
            "previous_total": round(prev_total, 2),
        })
    prev_all_total = float(previous_df["revenue"].sum()) if not previous_df.empty else 0.0
    comp_rows.append({
        "category": "TOTAL",
        **{f"d{i}": daily_values[i] for i in range(7)},
        "change": _pct_change(sum(daily_values), prev_all_total),
        "total": round(sum(daily_values), 2),
        "previous_total": round(prev_all_total, 2),
    })

    day_kpis = []
    for i, d in enumerate(day_dates):
        day_df = selected_df[selected_df["date"].dt.normalize() == d.normalize()]
        day_kpis.append({
            "day": day_names_fr[i],
            "date": _iso_date(d),
            "label": day_labels[i],
            "revenue": daily_values[i],
            "change": daily_change[i],
            "packages": int(day_df["package"].nunique()) if not day_df.empty else 0,
            "transactions": int(len(day_df)),
            "top_category": (day_df.groupby("category")["revenue"].sum().sort_values(ascending=False).index[0] if not day_df.empty else "—"),
        })

    def _contains_any(series, keywords):
        names = series.astype(str).str.lower().str.replace("-", " ", regex=False).str.replace("_", " ", regex=False)
        mask = pd.Series(False, index=series.index)
        for kw in keywords:
            kw = kw.lower().replace("-", " ").replace("_", " ")
            if kw in {"net", "mix", "allo"}:
                mask = mask | names.str.contains(rf"(^|\s){kw}(\s|\d|$)", regex=True, na=False)
            else:
                mask = mask | names.str.contains(kw, regex=False, na=False)
        return mask

    group_defs = [
        ("MauriNet", ["maurinet", "internet", "net", "1 year data"]),
        ("MauriAllo", ["mauri allo", "mauriallo", "allo", "voice"]),
        ("MauriMix", ["mauri attay", "mauri mix", "maurimix", "mix"]),
        ("Raha", ["raha"]),
        ("Beinatna", ["beinatna"]),
    ]

    def _top_packages(source_df, keywords=None, limit=10):
        sub = source_df
        if keywords is not None:
            sub = source_df[_contains_any(source_df["package"], keywords)]
        if sub.empty:
            return []
        pack = sub.groupby("package", as_index=False)["revenue"].sum().sort_values("revenue", ascending=False).head(limit)
        return [{"package": str(r.package), "revenue": round(float(r.revenue), 2)} for r in pack.itertuples(index=False)]

    groups = []
    for name, keywords in group_defs:
        sub = selected_df[_contains_any(selected_df["package"], keywords)]
        mp = {}
        if not sub.empty:
            trend = sub.groupby("date", as_index=False)["revenue"].sum()
            mp = {pd.Timestamp(r.date).normalize(): float(r.revenue) for r in trend.itertuples(index=False)}
        vals = [round(float(mp.get(d.normalize(), 0.0)), 2) for d in day_dates]
        cr = []
        pv = None
        for v in vals:
            cr.append(None if pv is None or pv == 0 else round(((v - pv) / pv) * 100, 1))
            pv = v
        groups.append({
            "name": name,
            "labels": day_labels,
            "revenue": vals,
            "revenue_millions": [round(v / 1_000_000, 3) for v in vals],
            "change_rate": cr,
            "previous_top": _top_packages(previous_df, keywords, limit=20) if not previous_df.empty else [],
            "top_week": _top_packages(selected_df, keywords, limit=20),
        })

    day_package_tables = []
    for i, d in enumerate(day_dates):
        day_df = selected_df[selected_df["date"].dt.normalize() == d.normalize()]
        day_package_tables.append({"label": day_labels[i], "rows": _top_packages(day_df, None, limit=10)})

    return {
        "weeks": [{"id": _week_id(p), "label": _week_label(p)} for p in weeks],
        "selected_week": {"id": _week_id(selected), "label": _week_label(selected)},
        "report_date": date.today().strftime("%d/%m/%Y"),
        "title_period": f"{selected.start_time:%d} to {selected.end_time:%d %b}",
        "kpis": {
            "selected_revenue": round(float(sum(daily_values)), 2),
            "avg_daily": round(float(np.mean(daily_values)), 2) if daily_values else 0,
            "best_day": day_kpis[int(np.argmax(daily_values))]["label"] if daily_values else "—",
            "best_day_revenue": round(float(max(daily_values)), 2) if daily_values else 0,
            "change_monday_sunday": _pct_change(daily_values[-1], daily_values[0]) if daily_values else None,
            "packages": int(selected_df["package"].nunique()) if not selected_df.empty else 0,
        },
        "daily_revenue": {"labels": day_labels, "revenue": daily_values, "revenue_millions": [round(v/1_000_000, 3) for v in daily_values], "change_rate": daily_change},
        "category_daily": {"labels": day_labels, "series": category_series},
        "category_compare": {"headers": ["Category", *day_names_fr, "Total", "Sun vs Mon %"], "rows": comp_rows},
        "day_kpis": day_kpis,
        "groups": groups,
        "day_package_tables": day_package_tables,
    }




def _robust_series_trend(values, min_base: float = 1.0) -> dict:
    """Return a stable trend using early vs recent active-period averages.

    The previous implementation compared the very first period with the very last
    period. That made the dashboard show unrealistic values such as -95% or
    +12000% when the first/last imported week was incomplete or very small.
    This helper ignores zero inactive periods and compares small windows of
    active periods, which is safer for weekly/monthly package dashboards.
    """
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    active = arr[arr > 0]
    if len(active) < 2:
        return {"trend": None, "slope": 0.0, "status": "Stable"}
    window = max(1, min(4, len(active) // 4 if len(active) >= 8 else 2))
    first_avg = float(np.mean(active[:window]))
    last_avg = float(np.mean(active[-window:]))
    if first_avg <= min_base:
        trend = None
    else:
        trend = round(((last_avg - first_avg) / first_avg) * 100, 1)
    x = np.arange(len(active), dtype=float)
    slope = float(np.polyfit(x, active, 1)[0]) if len(active) > 1 else 0.0
    if trend is None:
        status = "Growing" if slope > 0 else "Declining" if slope < 0 else "Stable"
    elif trend >= 5 and slope >= 0:
        status = "Growing"
    elif trend <= -5 and slope <= 0:
        status = "Declining"
    else:
        status = "Stable"
    return {"trend": trend, "slope": round(slope, 2), "status": status}


def _segment_package(share: float, trend) -> str:
    """Classify packages into the four segments used by the dashboard."""
    share = float(share or 0)
    if share < 1:
        return "Low profitability"
    if trend is not None and trend >= 15 and share >= 3:
        return "Star"
    if share >= 8 and (trend is None or trend >= -15):
        return "Cash cow"
    return "Core product"

def _period_code_for(granularity: str) -> str:
    return {"day": "D", "week": "W", "month": "M"}.get((granularity or "week").lower(), "W")


def _period_label_any(period, code: str) -> str:
    if code == "D":
        return f"{period.start_time:%d-%b-%Y}"
    if code == "M":
        return f"{period.start_time:%b %Y}"
    return f"{period.start_time:%d-%b} → {period.end_time:%d-%b}"


def demand_dashboard(qs, granularity: str = "week") -> dict:
    """Main dashboard in percentages: demand popularity, revenue, Pareto, cash cows and stats."""
    df = qs_to_frame(qs)
    empty = {
        "demand_ranking": {"labels": [], "share": [], "revenue": []},
        "popularity_evolution": {"labels": [], "series": []},
        "cannibalization": {"labels": [], "series": []},
        "performance_segments": [],
        "revenue_avg": {"labels": [], "avg": []},
        "period_revenue": {"labels": [], "revenue": [], "share": []},
        "pareto": {"labels": [], "revenue": [], "cum_share": []},
        "cash_cows": [],
        "low_profit": [],
        "stats": {},
    }
    if df.empty:
        return empty
    df = df.sort_values("date")
    total = float(df["revenue"].sum()) or 1.0
    pkg = df.groupby("package", as_index=False).agg(revenue=("revenue", "sum"), transactions=("revenue", "count"))
    pkg["share"] = pkg["revenue"] / total * 100
    pkg["avg"] = pkg["revenue"] / pkg["transactions"].replace(0, np.nan)
    pkg = pkg.sort_values("revenue", ascending=False)

    code = _period_code_for(granularity)
    df["period"] = df["date"].dt.to_period(code)
    period_tot = df.groupby("period", as_index=False)["revenue"].sum().sort_values("period")
    labels = [_period_label_any(p, code) for p in period_tot["period"]]

    top_names = pkg.head(8)["package"].tolist()
    piv = df[df["package"].isin(top_names)].pivot_table(index="period", columns="package", values="revenue", aggfunc="sum", fill_value=0).reindex(period_tot["period"]).fillna(0)
    per_tot_map = dict(zip(period_tot["period"], period_tot["revenue"]))
    pop_series = []
    for name in top_names:
        vals = []
        for period in period_tot["period"]:
            base = float(per_tot_map.get(period, 0) or 0)
            vals.append(round(float(piv.loc[period, name]) / base * 100, 2) if base else 0)
        pop_series.append({"name": name, "data": vals})

    # Automatic cannibalization examples: compare closest packages sharing a keyword and different prices.
    mix_candidates = [x for x in pkg["package"].tolist() if "mix" in str(x).lower()]
    cannibal_names = mix_candidates[:4] if len(mix_candidates) >= 2 else top_names[:4]
    cann_piv = df[df["package"].isin(cannibal_names)].pivot_table(index="period", columns="package", values="revenue", aggfunc="sum", fill_value=0).reindex(period_tot["period"]).fillna(0)
    cann_series = []
    for name in cannibal_names:
        cann_series.append({"name": name, "data": [round(float(v), 2) for v in cann_piv[name].tolist()]}) if name in cann_piv.columns else None

    # Performance segmentation: use a robust trend (early active-period average vs recent
    # active-period average). This prevents incomplete first/last periods from creating
    # unrealistic trend values and wrong segments.
    pkg_period = df.pivot_table(index="package", columns="period", values="revenue", aggfunc="sum", fill_value=0).reindex(columns=period_tot["period"]).fillna(0)
    seg_rows = []
    for row in pkg.itertuples(index=False):
        series = pkg_period.loc[row.package].to_numpy(dtype=float) if row.package in pkg_period.index else np.array([], dtype=float)
        t = _robust_series_trend(series)
        trend = t["trend"]
        segment = _segment_package(float(row.share), trend)
        seg_rows.append({"package": str(row.package), "share": round(float(row.share), 2), "revenue": round(float(row.revenue), 2), "avg": round(float(row.avg or 0), 2), "trend": trend, "segment": segment})

    pareto = pkg.copy()
    pareto["cum_share"] = pareto["revenue"].cumsum() / total * 100
    period_revenue = period_tot.copy()
    period_total_all = float(period_revenue["revenue"].sum()) or 1.0
    values = df.groupby("date")["revenue"].sum().to_numpy(dtype=float)
    return {
        "demand_ranking": {"labels": pkg.head(15)["package"].tolist(), "share": [round(float(v), 2) for v in pkg.head(15)["share"]], "revenue": [round(float(v), 2) for v in pkg.head(15)["revenue"]]},
        "popularity_evolution": {"labels": labels, "series": pop_series},
        "cannibalization": {"labels": labels, "series": cann_series},
        "performance_segments": seg_rows[:50],
        "revenue_avg": {"labels": pkg.head(15)["package"].tolist(), "avg": [round(float(v or 0), 2) for v in pkg.head(15)["avg"]]},
        "period_revenue": {"labels": labels, "revenue": [round(float(v), 2) for v in period_revenue["revenue"]], "share": [round(float(v) / period_total_all * 100, 2) for v in period_revenue["revenue"]]},
        "pareto": {"labels": pareto.head(25)["package"].tolist(), "revenue": [round(float(v), 2) for v in pareto.head(25)["revenue"]], "cum_share": [round(float(v), 2) for v in pareto.head(25)["cum_share"]]},
        "cash_cows": [r for r in seg_rows if r["segment"] in {"Cash cow", "Star"}][:15],
        "low_profit": [r for r in seg_rows if r["segment"] == "Low profitability"][:15],
        "stats": descriptive_stats(qs),
    }


def ml_dashboard(qs) -> dict:
    """Machine learning tab: anomalies, 3-week forecast, clustering and trend analysis."""
    df = qs_to_frame(qs)
    empty = {"anomalies": {"rows": []}, "forecast": {"method": "none", "points": []}, "clusters": [], "trends": []}
    if df.empty:
        return empty
    anomalies = detect_anomalies(qs)
    fc = forecast_4_weeks(qs)
    fc["points"] = fc.get("points", [])[:21]
    pkg = df.groupby("package", as_index=False).agg(total=("revenue", "sum"), avg=("revenue", "mean"), transactions=("revenue", "count"))
    if len(pkg) >= 3:
        from sklearn.cluster import KMeans
        features = pkg[["total", "avg", "transactions"]].to_numpy(dtype=float)
        features = (features - features.mean(axis=0)) / (features.std(axis=0) + 1e-9)
        k = min(4, len(pkg))
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        pkg["cluster"] = km.fit_predict(features)
    else:
        pkg["cluster"] = 0
    cluster_rows = []
    for c, sub in pkg.groupby("cluster"):
        cluster_rows.append({
            "cluster": int(c) + 1,
            "packages": int(len(sub)),
            "total": round(float(sub["total"].sum()), 2),
            "avg": round(float(sub["avg"].mean()), 2),
            "top_packages": sub.sort_values("total", ascending=False).head(8)["package"].tolist(),
        })
    # Trend by package using robust active-week averages + linear slope.
    # This avoids false extreme values when the imported last week is incomplete.
    df["week"] = df["date"].dt.to_period("W")
    all_weeks = sorted(df["week"].dropna().unique())
    trends = []
    for name, sub in df.groupby("package"):
        weekly = sub.groupby("week", as_index=False)["revenue"].sum().sort_values("week")
        if len(weekly) < 2:
            continue
        wk_map = {r.week: float(r.revenue) for r in weekly.itertuples(index=False)}
        y = np.array([wk_map.get(w, 0.0) for w in all_weeks], dtype=float)
        t = _robust_series_trend(y)
        active = y[y > 0]
        last_revenue = float(active[-1]) if len(active) else 0.0
        trends.append({"package": str(name), "trend": t["trend"], "slope": t["slope"], "status": t["status"], "last_revenue": round(last_revenue, 2)})
    trends = sorted(trends, key=lambda r: abs(r["trend"] if r["trend"] is not None else r["slope"]), reverse=True)[:50]
    return {"anomalies": anomalies, "forecast": fc, "clusters": sorted(cluster_rows, key=lambda r: r["total"], reverse=True), "trends": trends}


def monthly_marketing_report(qs, month_id: str | None = None) -> dict:
    """Monthly report similar to weekly report, aggregated by month."""
    df = qs_to_frame(qs)
    if df.empty:
        return {"months": [], "selected_month": None, "previous_month": None, "kpis": {}, "monthly_revenue": {"labels": [], "revenue": [], "change_rate": []}, "category_compare": {"headers": [], "rows": []}, "groups": []}
    df = df.sort_values("date")
    df["month"] = df["date"].dt.to_period("M")
    months = sorted(df["month"].dropna().unique())
    def _id(p): return f"{p.start_time:%Y-%m}"
    def _lab(p): return f"{p.start_time:%B %Y}"
    selected = months[-1]
    if month_id:
        for p in months:
            if _id(p) == month_id or str(p) == month_id:
                selected = p; break
    idx = months.index(selected)
    prev = months[idx-1] if idx > 0 else None
    monthly = df.groupby("month", as_index=False)["revenue"].sum().sort_values("month")
    monthly["change_rate"] = monthly["revenue"].pct_change() * 100
    sel_df = df[df["month"] == selected]
    prev_df = df[df["month"] == prev] if prev is not None else df.iloc[0:0]
    sel_total = float(sel_df["revenue"].sum()); prev_total=float(prev_df["revenue"].sum()) if not prev_df.empty else 0
    def _pct(cur, old): return None if not old else round((cur-old)/old*100,1)
    categories=["DATA","VOICE","MIX","SMS","OTHERS"]
    def _catnorm(x):
        x=str(x).upper(); return x if x in categories else "OTHERS"
    rows=[]
    for cat in categories:
        cur=float(sel_df[sel_df["category"].map(_catnorm)==cat]["revenue"].sum())
        old=float(prev_df[prev_df["category"].map(_catnorm)==cat]["revenue"].sum()) if not prev_df.empty else 0
        rows.append({"category":cat,"previous":round(old,2),"current":round(cur,2),"change":_pct(cur,old),"share":round(cur/(sel_total or 1)*100,2)})
    group_defs=[("MauriNet", ["maurinet","internet","net","1 year data"]),("MauriAllo", ["mauri allo","mauriallo","allo","voice"]),("MauriMix", ["mauri attay","mauri mix","maurimix","mix"]),("Raha", ["raha"]),("Beinatna", ["beinatna"])]
    def contains(series, kws):
        names=series.astype(str).str.lower().str.replace('-', ' ', regex=False).str.replace('_',' ', regex=False)
        mask=pd.Series(False,index=series.index)
        for kw in kws: mask=mask|names.str.contains(kw.lower(), regex=False, na=False)
        return mask
    groups=[]
    for name,kws in group_defs:
        sub=df[contains(df["package"],kws)]
        mp=sub.groupby("month",as_index=False)["revenue"].sum() if not sub.empty else pd.DataFrame(columns=["month","revenue"])
        m=dict(zip(mp["month"],mp["revenue"])) if not mp.empty else {}
        vals=[round(float(m.get(p,0)),2) for p in months]
        rates=[]
        for i,v in enumerate(vals): rates.append(None if i==0 or vals[i-1]==0 else round((v-vals[i-1])/vals[i-1]*100,1))
        top=sel_df[contains(sel_df["package"],kws)].groupby("package",as_index=False)["revenue"].sum().sort_values("revenue",ascending=False).head(20)
        prev_top=prev_df[contains(prev_df["package"],kws)].groupby("package",as_index=False)["revenue"].sum().sort_values("revenue",ascending=False).head(20) if not prev_df.empty else pd.DataFrame(columns=["package","revenue"])
        groups.append({"name":name,"labels":[_lab(p) for p in months],"revenue":vals,"change_rate":rates,"top_month":[{"package":r.package,"revenue":round(float(r.revenue),2)} for r in top.itertuples(index=False)],"previous_month_top":[{"package":r.package,"revenue":round(float(r.revenue),2)} for r in prev_top.itertuples(index=False)]})
    return {"months":[{"id":_id(p),"label":_lab(p)} for p in months],"selected_month":{"id":_id(selected),"label":_lab(selected)},"previous_month":{"id":_id(prev),"label":_lab(prev)} if prev is not None else None,"report_date":date.today().strftime("%d/%m/%Y"),"kpis":{"selected_revenue":round(sel_total,2),"previous_revenue":round(prev_total,2),"change":_pct(sel_total,prev_total),"days":int(sel_df["date"].nunique()),"packages":int(sel_df["package"].nunique()),"avg_daily":round(sel_total/(int(sel_df["date"].nunique()) or 1),2)},"monthly_revenue":{"labels":[_lab(p) for p in monthly["month"]],"revenue":[round(float(v),2) for v in monthly["revenue"]],"change_rate":[None if pd.isna(v) else round(float(v),1) for v in monthly["change_rate"]]},"category_compare":{"headers":["Category","Previous Month","Selected Month","Change %","Share %"],"rows":rows},"groups":groups}
