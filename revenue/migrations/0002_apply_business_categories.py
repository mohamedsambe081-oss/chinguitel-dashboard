from django.db import migrations
import re


def norm(value):
    text = str(value or '').strip().lower()
    return re.sub(r'[\s_\-]+', ' ', text)


def infer_category(package):
    text = norm(package)
    compact = text.replace(' ', '')
    if 'maurinet' in compact or '1 year data' in text or 'internet' in text or 'unlimited' in text or re.search(r'(^|\s)net(\s|\d|$)', text):
        return 'DATA'
    if 'mauriallo' in compact or 'mauri allo' in text or 'allo' in text or 'internat' in text or 'voice' in text:
        return 'VOICE'
    if 'mauriattay' in compact or 'mauri attay' in text or 'maurimix' in compact or 'mauri mix' in text:
        return 'MIX'
    if 'maurichat' in compact or 'mauri chat' in text or 'chat' in text:
        return 'SMS'
    return 'others'


def apply_categories(apps, schema_editor):
    RevenueRecord = apps.get_model('revenue', 'RevenueRecord')
    updates = []
    for r in RevenueRecord.objects.only('id', 'package', 'category').iterator(chunk_size=1000):
        new_category = infer_category(r.package)
        if r.category != new_category:
            r.category = new_category
            updates.append(r)
            if len(updates) >= 1000:
                RevenueRecord.objects.bulk_update(updates, ['category'], batch_size=1000)
                updates.clear()
    if updates:
        RevenueRecord.objects.bulk_update(updates, ['category'], batch_size=1000)


class Migration(migrations.Migration):
    dependencies = [
        ('revenue', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(apply_categories, migrations.RunPython.noop),
    ]
