# Generated by Django 3.1.10 on 2023-12-26 22:43

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('recommendations', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='CollaborativelyFilteredRecommendation',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ],
        ),
    ]
