# Generated by Django 3.1.10 on 2022-01-10 21:05

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("rss_feeds", "0002_remove_mongo_types"),
    ]

    operations = [
        migrations.AlterField(
            model_name="feed",
            name="feed_address_locked",
            field=models.BooleanField(blank=True, default=False, null=True),
        ),
        migrations.AlterField(
            model_name="feed",
            name="is_push",
            field=models.BooleanField(blank=True, default=False, null=True),
        ),
        migrations.AlterField(
            model_name="feed",
            name="s3_icon",
            field=models.BooleanField(blank=True, default=False, null=True),
        ),
        migrations.AlterField(
            model_name="feed",
            name="s3_page",
            field=models.BooleanField(blank=True, default=False, null=True),
        ),
        migrations.AlterField(
            model_name="feed",
            name="search_indexed",
            field=models.BooleanField(blank=True, default=None, null=True),
        ),
    ]
