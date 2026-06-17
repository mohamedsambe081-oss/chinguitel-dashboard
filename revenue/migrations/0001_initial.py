# Generated manually for the project scaffold.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='DataUpload',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file', models.FileField(upload_to='uploads/%Y/%m/%d/')),
                ('original_filename', models.CharField(max_length=255)),
                ('status', models.CharField(choices=[('pending', 'En attente'), ('processed', 'Traité'), ('failed', 'Échec')], default='pending', max_length=20)),
                ('rows_imported', models.PositiveIntegerField(default=0)),
                ('rows_rejected', models.PositiveIntegerField(default=0)),
                ('date_column', models.CharField(blank=True, max_length=255)),
                ('package_column', models.CharField(blank=True, max_length=255)),
                ('revenue_column', models.CharField(blank=True, max_length=255)),
                ('errors', models.JSONField(blank=True, default=list)),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('processed_at', models.DateTimeField(blank=True, null=True)),
            ],
            options={'ordering': ['-uploaded_at']},
        ),
        migrations.CreateModel(
            name='PowerPointReport',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file', models.FileField(upload_to='reports/%Y/%m/%d/')),
                ('filters', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('generated_by_task', models.BooleanField(default=False)),
                ('upload', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='revenue.dataupload')),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='RevenueRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(db_index=True)),
                ('package', models.CharField(db_index=True, max_length=255)),
                ('category', models.CharField(db_index=True, default='Non classé', max_length=100)),
                ('revenue', models.DecimalField(decimal_places=2, max_digits=18)),
                ('raw_payload', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('upload', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='records', to='revenue.dataupload')),
            ],
            options={'ordering': ['date', 'package']},
        ),
        migrations.AddIndex(
            model_name='revenuerecord',
            index=models.Index(fields=['date', 'package'], name='revenue_rev_date_f_8d2161_idx'),
        ),
        migrations.AddIndex(
            model_name='revenuerecord',
            index=models.Index(fields=['category', 'date'], name='revenue_rev_categor_805c34_idx'),
        ),
    ]
