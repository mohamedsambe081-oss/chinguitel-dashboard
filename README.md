# Chinguitel Revenue Analytics — Django

Application web Django pour importer un fichier Excel `date / package / revenue`, nettoyer les données, générer un dashboard interactif et exporter un rapport PowerPoint.

## Couleurs imposées

- Blanc : `#ffffff`
- Bleu : `#0d47a1`
- Violet : `#6a1b9a`

## Fonctionnalités incluses

- Upload Excel `.xlsx` / `.xls`
- Détection automatique des colonnes date, package et revenue
- Nettoyage : dates, packages, revenus numériques, suppression des lignes invalides
- Stockage en base Django
- Dashboard avec filtres : date, catégorie, package
- APIs JSON pour Chart.js
- KPIs, séries temporelles, MA7, agrégations jour/semaine/mois
- Forecast 4 semaines avec Prophet si disponible, fallback naïf sinon
- Détection anomalies : IsolationForest + Z-score
- EDA : distribution, concentration top packages, matrice package x mois
- Export PowerPoint à la demande
- Tâche Celery hebdomadaire chaque lundi

## Installation locale

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Ouvrir : `http://127.0.0.1:8000/`

## Chart.js hors ligne

L'application ne dépend pas d'un CDN dans les templates. Place le fichier local :

```text
static/vendor/chart.umd.min.js
```

Pendant l'installation initiale seulement, télécharge Chart.js depuis le site officiel ou installe-le via npm, puis copie `chart.umd.min.js` dans ce dossier. Après cela, l'application fonctionne sans internet.

## Celery / Redis

Lancer Redis, puis dans deux terminaux séparés :

```bash
celery -A telecom_revenue worker -l info
celery -A telecom_revenue beat -l info
```

La tâche `generate_weekly_powerpoint` est programmée chaque lundi à 07:00.

## PostgreSQL

En développement, SQLite est utilisé par défaut. Pour PostgreSQL, configure `.env` :

```env
DB_ENGINE=postgres
DB_NAME=chinguitel_revenue
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=localhost
DB_PORT=5432
```

## Format Excel accepté

Le fichier doit contenir l'équivalent de ces trois colonnes :

| Date | Package | Revenue |
|---|---|---|
| 2026-05-01 | DATA_1GB | 120000 |

Les noms peuvent varier : `jour`, `day`, `periode`, `offre`, `bundle`, `revenu`, `ca`, `amount`, etc. Le détecteur essaie de reconnaître automatiquement les colonnes.

## Limite importante

Prophet donne des résultats utiles seulement si l'historique est suffisant et stable. Avec peu de semaines de données, l'application utilise un fallback prudent au lieu de fabriquer une précision inexistante.
