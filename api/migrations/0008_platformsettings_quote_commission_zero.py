from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0007_quote_bank_details'),
    ]

    operations = [
        # Add PlatformSettings model
        migrations.CreateModel(
            name='PlatformSettings',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('subscription_price', models.DecimalField(decimal_places=2, default=450.0, help_text='Monthly subscription price in MVR', max_digits=10)),
                ('free_trial_days', models.IntegerField(default=30, help_text='Free trial period in days for new operators')),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='api.user')),
            ],
            options={
                'verbose_name': 'Platform Settings',
            },
        ),
        # Set commission_rate default to 0
        migrations.AlterField(
            model_name='quote',
            name='commission_rate',
            field=models.DecimalField(decimal_places=2, default=0.0, max_digits=5),
        ),
    ]
