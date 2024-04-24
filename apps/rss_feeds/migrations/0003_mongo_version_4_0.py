# Generated by Django 3.1.10 on 2022-05-17 13:35

from django.conf import settings
from django.db import migrations


def set_mongo_feature_compatibility_version(apps, schema_editor):
    new_version = "4.0"
    db = settings.MONGODB.admin
    doc = db.command({"getParameter": 1, "featureCompatibilityVersion": 1})
    old_version = doc["featureCompatibilityVersion"]["version"]
    print(f"\n ---> Current MongoDB featureCompatibilityVersion: {old_version}")

    if old_version != new_version:
        db.command({"setFeatureCompatibilityVersion": new_version})
        print(f" ---> Updated MongoDB featureCompatibilityVersion: {new_version}")


class Migration(migrations.Migration):
    dependencies = [
        ("rss_feeds", "0002_remove_mongo_types"),
    ]

    operations = [migrations.RunPython(set_mongo_feature_compatibility_version, migrations.RunPython.noop)]
