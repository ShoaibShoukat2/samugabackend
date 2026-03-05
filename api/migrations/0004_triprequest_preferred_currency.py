# Generated migration

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0003_payment_currency_quote_currency'),
    ]

    operations = [
        migrations.AddField(
            model_name='triprequest',
            name='preferred_currency',
            field=models.CharField(
                choices=[('USD', 'US Dollar'), ('MVR', 'Maldivian Rufiyaa')],
                default='USD',
                max_length=3
            ),
        ),
    ]
