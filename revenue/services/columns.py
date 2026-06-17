import re
import unicodedata
from difflib import SequenceMatcher
import pandas as pd

DATE_ALIASES = {
    "date", "jour", "jours", "day", "periode", "period", "week", "semaine", "mois", "month",
    "transactiondate", "eventdate", "usage_date", "dt"
}
PACKAGE_ALIASES = {
    "package", "packages", "pack", "offre", "offer", "bundle", "plan", "produit", "product",
    "service", "service_name", "nom_package", "forfait"
}
REVENUE_ALIASES = {
    "revenue", "revenu", "revenus", "ca", "chiffreaffaires", "chiffredaffaires", "amount",
    "montant", "value", "valeur", "sales", "recette", "recettes", "turnover"
}


def normalize_name(value: str) -> str:
    value = str(value).strip().lower()
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "", value)


def _alias_score(column_name: str, aliases: set[str]) -> float:
    name = normalize_name(column_name)
    if name in aliases:
        return 1.0
    return max(SequenceMatcher(None, name, alias).ratio() for alias in aliases)


def _date_quality(series: pd.Series) -> float:
    parsed = pd.to_datetime(series, errors="coerce", dayfirst=True)
    return float(parsed.notna().mean())


def _numeric_quality(series: pd.Series) -> float:
    s = series.astype(str).str.replace(" ", "", regex=False).str.replace(",", ".", regex=False)
    numeric = pd.to_numeric(s, errors="coerce")
    return float(numeric.notna().mean())


def detect_columns(df: pd.DataFrame) -> dict[str, str]:
    if df.empty:
        raise ValueError("Le fichier Excel est vide.")

    scores = {"date": [], "package": [], "revenue": []}
    for col in df.columns:
        sample = df[col].dropna().head(200)
        if sample.empty:
            continue

        date_score = 0.65 * _alias_score(col, DATE_ALIASES) + 0.35 * _date_quality(sample)
        revenue_score = 0.65 * _alias_score(col, REVENUE_ALIASES) + 0.35 * _numeric_quality(sample)
        package_score = 0.80 * _alias_score(col, PACKAGE_ALIASES) + 0.20 * (1 - _numeric_quality(sample))

        scores["date"].append((date_score, col))
        scores["package"].append((package_score, col))
        scores["revenue"].append((revenue_score, col))

    selected: dict[str, str] = {}
    used: set[str] = set()
    for key in ["date", "revenue", "package"]:
        ordered = sorted(scores[key], reverse=True, key=lambda x: x[0])
        for score, col in ordered:
            if col not in used and score >= 0.45:
                selected[key] = col
                used.add(col)
                break

    missing = [k for k in ["date", "package", "revenue"] if k not in selected]
    if missing:
        details = ", ".join(missing)
        raise ValueError(f"Colonnes non détectées automatiquement : {details}. Renomme-les ou vérifie le fichier.")

    return selected
