from django.contrib.auth.models import Group, User
from test_app.models import *
from rest_framework import serializers


class CircuitsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Circuits
        fields = ['circuit_name', 'circuit_id', 'country', 'locality']


class ConstructorsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Constructors
        fields = ['constructor_id', 'constructor_name']

class DriverSerializer(serializers.ModelSerializer):
    class Meta:
        model = Drivers
        fields = ['url','driver_id','given_name', 'family_name','date_of_birth','nationality']

class DriverNameSerializer(DriverSerializer):
    class Meta(DriverSerializer.Meta):
        fields = ['given_name', 'family_name']

class ConstructorNameSerializer(DriverSerializer):
    class Meta(ConstructorsSerializer.Meta):
        fields = ['constructor_name']

class ResultsSerializer(serializers.ModelSerializer):
    driver = DriverNameSerializer()
    constructor = ConstructorNameSerializer()
    class Meta:
        model = Results
        fields = ['season', 'round','driver','constructor','number','finished_position','points','grid','laps','status','time_in_ms','fastest_lap_rank','fastest_lap_lap','fastest_lap_time','average_speed_kph']

class DriverSeasonRoundSerializer(serializers.ModelSerializer):
    driver = DriverSerializer()
    class Meta:
        model = Results
        fields = ['season', 'round','driver']

class RaceSeasonRoundSerializer(serializers.ModelSerializer):
    class Meta:
        model = Races
        fields = ['season', 'round','race_name']

class LastUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = LastUpdate
        fields = ['table_name', 'last_updated']

