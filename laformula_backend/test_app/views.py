# from django.shortcuts import render

# # Create your views here.
# from .models import *
# from rest_framework import viewsets

# class BlogPostViewSet(viewsets.ModelViewSet):
# 	queryset = Constructors.objects.all()
# 	serializer_class = BlogPostSerializer
     

from django.contrib.auth.models import Group, User
from test_app.models import *
from rest_framework import permissions, viewsets

from test_app.serializers import *


class CircuitsViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """
    queryset = Circuits.objects.all()[:10]
    serializer_class = CircuitsSerializer
    permission_classes = [permissions.IsAuthenticated]


class ConstructorsViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows groups to be viewed or edited.
    """
    queryset = Constructors.objects.all()[:10]
    serializer_class = ConstructorsSerializer
    permission_classes = [permissions.IsAuthenticated]

class DriversViewSet(viewsets.ModelViewSet):
    queryset = Drivers.objects.all()
    serializer_class = DriverSerializer
    permission_classes = [permissions.IsAuthenticated]

class DriverSeasonRoundView(viewsets.ModelViewSet):
    serializer_class = DriverSeasonRoundSerializer
    queryset = Results.objects.none()

    def get_queryset(self):
        # Optionally filter by season and year
        season = self.request.query_params.get('season')
        round = self.request.query_params.get('round')

        queryset = Results.objects.all()

        if season is not None:
            queryset = queryset.filter(season=season)
        if round is not None:
            queryset = queryset.filter(round=round)

        return queryset
    
class RaceSeasonRoundView(viewsets.ModelViewSet):
    serializer_class = RaceSeasonRoundSerializer
    queryset = Races.objects.none()
    def get_queryset(self):
        # Optionally filter by season and year
        season = self.request.query_params.get('season')
        round = self.request.query_params.get('round')
        queryset = Races.objects.all()
        if season is not None:
            queryset = queryset.filter(season=season)
        if round is not None:
            queryset = queryset.filter(round=round)

        return queryset
    
class ResultsSeasonRoundView(viewsets.ModelViewSet):
    serializer_class = ResultsSerializer
    queryset = Results.objects.none()
    def get_queryset(self):
        # Optionally filter by season and year
        season = self.request.query_params.get('season')
        round = self.request.query_params.get('round')
        queryset = Results.objects.all()
        if season is not None:
            queryset = queryset.filter(season=season)
        if round is not None:
            queryset = queryset.filter(round=round)

        return queryset
    

class ResultsSeasonView(viewsets.ModelViewSet):
    serializer_class = ResultsSerializer
    queryset = Results.objects.none()
    def get_queryset(self):
        # Optionally filter by season and year
        season = self.request.query_params.get('season')
        queryset = Results.objects.all()
        if season is not None:
            queryset = queryset.filter(season=season)
        return queryset


class LastUpdateView(viewsets.ModelViewSet):
    serializer_class = LastUpdateSerializer
    queryset = LastUpdate.objects.none()
    def get_queryset(self):
        table_name = self.request.query_params.get('table_name')
        queryset = LastUpdate.objects.all()
        if table_name is not None:
            queryset = queryset.filter(table_name=table_name)

        return queryset