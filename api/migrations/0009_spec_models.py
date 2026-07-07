# Generated migration for spec models

from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0008_platformsettings_quote_commission_zero'),
    ]

    operations = [
        migrations.AddField(
            model_name='platformsettings',
            name='assist_avatar_url',
            field=models.URLField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='platformsettings',
            name='assist_greeting',
            field=models.TextField(blank=True, default="Hi! I'm Samuga Assist. How can I help you today?"),
        ),
        migrations.AddField(
            model_name='platformsettings',
            name='bml_account',
            field=models.CharField(blank=True, default='7730000012345', max_length=100),
        ),
        migrations.AddField(
            model_name='platformsettings',
            name='mib_account',
            field=models.CharField(blank=True, default='7730000012345', max_length=100),
        ),
        migrations.AddField(
            model_name='booking',
            name='status',
            field=models.CharField(
                choices=[
                    ('pending_payment', 'Pending Payment'),
                    ('pending_confirmation', 'Pending Confirmation'),
                    ('confirmed', 'Confirmed'),
                    ('cancelled', 'Cancelled'),
                ],
                default='pending_payment',
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name='booking',
            name='ticket_url',
            field=models.URLField(blank=True, default=''),
        ),
        migrations.CreateModel(
            name='Schedule',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('route_from', models.CharField(max_length=255)),
                ('route_to', models.CharField(max_length=255)),
                ('sched_stops', models.JSONField(blank=True, default=list)),
                ('departure_time', models.TimeField(default='09:00:00')),
                ('price_per_seat', models.DecimalField(decimal_places=2, default=350, max_digits=10)),
                ('available_seats', models.IntegerField(default=20)),
                ('run_days', models.CharField(
                    choices=[('daily', 'Daily'), ('sat-thu', 'Sat-Thu'), ('fri', 'Fridays')],
                    default='daily', max_length=20,
                )),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('boat', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='schedules', to='api.speedboat',
                )),
                ('operator', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='schedules', to='api.speedboatoperator',
                )),
            ],
        ),
        migrations.AddField(
            model_name='booking',
            name='schedule',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name='bookings', to='api.schedule',
            ),
        ),
        migrations.CreateModel(
            name='BoatRequest',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('request_ref', models.CharField(max_length=30, unique=True)),
                ('route_from', models.CharField(max_length=255)),
                ('route_to', models.CharField(max_length=255)),
                ('travel_date', models.DateField()),
                ('preferred_time', models.CharField(blank=True, default='Flexible', max_length=100)),
                ('passenger_count', models.IntegerField(default=1)),
                ('trip_type', models.CharField(
                    choices=[('oneway', 'One-way'), ('return', 'Return')],
                    default='oneway', max_length=20,
                )),
                ('contact_number', models.CharField(max_length=20)),
                ('pickup_jetty', models.CharField(blank=True, max_length=255)),
                ('notes', models.TextField(blank=True)),
                ('customer_price', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('status', models.CharField(
                    choices=[
                        ('open', 'Open'), ('operators_pinged', 'Operators Pinged'),
                        ('offer_received', 'Offer Received'), ('assigned', 'Assigned'),
                        ('confirmed', 'Confirmed'), ('closed', 'Closed'), ('cancelled', 'Cancelled'),
                    ],
                    default='open', max_length=30,
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('assigned_operator', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    to='api.speedboatoperator',
                )),
                ('customer', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='boat_requests', to='api.user',
                )),
                ('linked_trip', models.OneToOneField(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    to='api.triprequest',
                )),
            ],
        ),
        migrations.CreateModel(
            name='Passenger',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=255)),
                ('nationality_id', models.CharField(blank=True, max_length=100)),
                ('order', models.IntegerField(default=0)),
                ('trip_request', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='passengers', to='api.triprequest',
                )),
            ],
            options={'ordering': ['order']},
        ),
    ]
