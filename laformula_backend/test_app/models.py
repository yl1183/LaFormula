from django.db import models

# Create your models here.


class Circuits(models.Model):
    url = models.CharField(max_length=120, db_collation='SQL_Latin1_General_CP1_CI_AS', blank=True, null=True)
    circuit_name = models.CharField(max_length=60, db_collation='SQL_Latin1_General_CP1_CI_AS')
    locality = models.CharField(max_length=50, db_collation='SQL_Latin1_General_CP1_CI_AS', blank=True, null=True)
    latitude = models.FloatField(blank=True, null=True)
    longitude = models.FloatField(blank=True, null=True)
    country = models.CharField(max_length=50, db_collation='SQL_Latin1_General_CP1_CI_AS', blank=True, null=True)
    length = models.FloatField(blank=True, null=True)
    turns = models.IntegerField(blank=True, null=True)
    circuit_id = models.CharField(primary_key=True, max_length=50, db_collation='SQL_Latin1_General_CP1_CI_AS')

    class Meta:
        managed = False
        db_table = 'circuits'


class Constructors(models.Model):
    constructor_id = models.CharField(primary_key=True, max_length=30, db_collation='SQL_Latin1_General_CP1_CI_AS')
    url = models.CharField(max_length=120, db_collation='SQL_Latin1_General_CP1_CI_AS', blank=True, null=True)
    constructor_name = models.CharField(max_length=50, db_collation='SQL_Latin1_General_CP1_CI_AS', blank=True, null=True)
    nationality = models.CharField(max_length=50, db_collation='SQL_Latin1_General_CP1_CI_AS', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'constructors'


class Drivers(models.Model):
    driver_id = models.CharField(primary_key=True, max_length=30, db_collation='SQL_Latin1_General_CP1_CI_AS')
    url = models.CharField(max_length=120, db_collation='SQL_Latin1_General_CP1_CI_AS', blank=True, null=True)
    given_name = models.CharField(max_length=50, db_collation='SQL_Latin1_General_CP1_CI_AS', blank=True, null=True)
    family_name = models.CharField(max_length=50, db_collation='SQL_Latin1_General_CP1_CI_AS', blank=True, null=True)
    date_of_birth = models.DateTimeField(blank=True, null=True)
    nationality = models.CharField(max_length=50, db_collation='SQL_Latin1_General_CP1_CI_AS', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'drivers'


class Laptime(models.Model):
    laptime_id = models.AutoField(primary_key=True)
    position = models.IntegerField(blank=True, null=True)
    time_in_ms = models.BigIntegerField(blank=True, null=True)
    season = models.IntegerField(blank=True, null=True)
    round = models.IntegerField(blank=True, null=True)
    lap = models.IntegerField(blank=True, null=True)
    driver_id = models.CharField(max_length=30, db_collation='SQL_Latin1_General_CP1_CI_AS', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'laptime'


class Pitstops(models.Model):
    pitstop_id = models.AutoField(primary_key=True)
    season = models.IntegerField(blank=True, null=True)
    round = models.IntegerField(blank=True, null=True)
    driver_id = models.CharField(max_length=30, db_collation='SQL_Latin1_General_CP1_CI_AS', blank=True, null=True)
    lap = models.IntegerField(blank=True, null=True)
    stop = models.IntegerField(blank=True, null=True)
    time = models.CharField(max_length=30, db_collation='SQL_Latin1_General_CP1_CI_AS', blank=True, null=True)
    duration_in_ms = models.BigIntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'pitstops'


class Qualifying(models.Model):
    qualifying_id = models.AutoField(primary_key=True)
    season = models.IntegerField(blank=True, null=True)
    round = models.IntegerField(blank=True, null=True)
    driver_id = models.CharField(max_length=30, db_collation='SQL_Latin1_General_CP1_CI_AS', blank=True, null=True)
    qualifying_position = models.IntegerField(blank=True, null=True)
    q1_in_ms = models.BigIntegerField(blank=True, null=True)
    q2_in_ms = models.BigIntegerField(blank=True, null=True)
    q3_in_ms = models.BigIntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'qualifying'


class Races(models.Model):
    season = models.IntegerField(primary_key=True)  # The composite primary key (season, round) found, that is not supported. The first column is selected.     
    round = models.IntegerField()
    url = models.CharField(max_length=120, db_collation='SQL_Latin1_General_CP1_CI_AS', blank=True, null=True)
    race_name = models.CharField(max_length=50, db_collation='SQL_Latin1_General_CP1_CI_AS', blank=True, null=True)
    date = models.DateTimeField(blank=True, null=True)
    time = models.CharField(max_length=20, db_collation='SQL_Latin1_General_CP1_CI_AS', blank=True, null=True)
    first_practice_datetime = models.DateTimeField(blank=True, null=True)
    second_practice_datetime = models.DateTimeField(blank=True, null=True)
    third_practice_datetime = models.DateTimeField(blank=True, null=True)
    qualifying_datetime = models.DateTimeField(blank=True, null=True)
    sprint_datetime = models.DateTimeField(blank=True, null=True)
    circuit_id = models.CharField(max_length=50, db_collation='SQL_Latin1_General_CP1_CI_AS', blank=True, null=True)
    datetime = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'races'
        unique_together = (('season', 'round'),)


class Results(models.Model):
    result_id = models.AutoField(primary_key=True)
    season = models.IntegerField(blank=True, null=True)
    round = models.IntegerField(blank=True, null=True)
    driver = models.ForeignKey(Drivers, on_delete=models.CASCADE, related_name='results')
    constructor = models.ForeignKey(Constructors, on_delete=models.CASCADE, related_name='results')
    number = models.CharField(max_length=10, db_collation='SQL_Latin1_General_CP1_CI_AS', blank=True, null=True)
    finished_position = models.IntegerField(blank=True, null=True)
    points = models.FloatField(blank=True, null=True)
    grid = models.IntegerField(blank=True, null=True)
    laps = models.IntegerField(blank=True, null=True)
    status = models.CharField(max_length=50, db_collation='SQL_Latin1_General_CP1_CI_AS', blank=True, null=True)
    time_in_ms = models.BigIntegerField(blank=True, null=True)
    fastest_lap_rank = models.IntegerField(blank=True, null=True)
    fastest_lap_lap = models.IntegerField(blank=True, null=True)
    fastest_lap_time = models.BigIntegerField(blank=True, null=True)
    average_speed_kph = models.FloatField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'results'


class SeasonDrivingStanding(models.Model):
    season = models.IntegerField(blank=True, null=True)
    driver_id = models.CharField(max_length=30, db_collation='SQL_Latin1_General_CP1_CI_AS', blank=True, null=True)
    points = models.FloatField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'season_driving_standing'


class LastUpdate(models.Model):
    table_name = models.CharField(unique=True, max_length=255, db_collation='SQL_Latin1_General_CP1_CI_AS', blank=True, null=True)
    last_updated = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'last_update'