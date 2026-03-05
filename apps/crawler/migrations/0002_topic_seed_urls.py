from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crawler', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='topic',
            name='seed_urls',
            field=models.JSONField(blank=True, default=list, help_text='List of seed URLs to crawl and extract links from'),
        ),
        migrations.AlterField(
            model_name='topic',
            name='keywords',
            field=models.JSONField(blank=True, default=list, help_text='List of keywords to search for'),
        ),
    ]
