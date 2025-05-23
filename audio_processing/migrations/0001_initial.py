# Generated by Django 5.2 on 2025-04-28 16:43

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='AudioProcessingTask',
            fields=[
                ('file_id', models.CharField(max_length=36, primary_key=True, serialize=False)),
                ('status', models.CharField(choices=[('uploaded', 'Uploaded'), ('transcribing', 'Transcribing'), ('translating', 'Translating'), ('completed', 'Completed')], default='uploaded', max_length=20)),
                ('translation', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
