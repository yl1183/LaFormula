from config.config import *
import requests
import pandas as pd
from bs4 import BeautifulSoup
from web_scrape import get_length_data_scrape,get_turns_data_scrape
from service import get_years_rounds


def get_api_json(url,params):
    response = requests.get(url, params=params)
    raw_data = response.json()
    return raw_data

def get_circuits_data(offset=0):
    total = int(get_api_json(circuits_api,params={'limit':1})['MRData']['total'])
    results = pd.DataFrame(columns=['circuitId','url','circuitName','Location'])
    while offset <= total:
        raw = get_api_json(circuits_api,{'limit': 100,'offset':offset})
        circuits = raw['MRData']['CircuitTable']['Circuits']
        data = pd.DataFrame(circuits)
        results = pd.concat([results,data],ignore_index=True)
        offset += 100
    return results
    

def get_drivers_data(offset=0):
    total = int(get_api_json(drivers_api,params={'limit':1})['MRData']['total'])
    results = pd.DataFrame(columns=['driverId','url','givenName','familyName','dateOfBirth','nationality'])
    while offset <= total:
        raw_data = get_api_json(drivers_api,{'limit': 100,'offset':offset})
        drivers = raw_data['MRData']['DriverTable']['Drivers']
        data = pd.DataFrame(drivers)
        data.drop(['permanentNumber', 'code'], axis=1, inplace=True)
        results = pd.concat([results,data],ignore_index=True)
        offset += 100

    return results
    
def get_constructors_data(offset=0):
    total = int(get_api_json(constructor_api,params={'limit':1})['MRData']['total'])
    results = pd.DataFrame(columns=['constructorId','url','name','nationality'])
    while offset <= total:
        raw_data = get_api_json(constructor_api,{'limit': 100,'offset':offset})
        constructors = raw_data['MRData']['ConstructorTable']['Constructors']
        data = pd.DataFrame(constructors)
        results = pd.concat([results,data],ignore_index=True)
        offset += 100
    return results

def get_races_data(offset=0):
    total = int(get_api_json(races_api,params={'limit':1})['MRData']['total'])
    results = pd.DataFrame(columns=['season','round','url','raceName','Circuit','date','time','FirstPractice','SecondPractice','ThirdPractice','Qualifying','Sprint'])
    while offset <= total:
        raw = get_api_json(races_api,params={'limit':100,'offset':offset})
        race = pd.DataFrame(raw['MRData']['RaceTable']['Races'])
        results = pd.concat([results,race],ignore_index=True)
        offset += 100
    return results

def get_results_data(offset=0):
    total = int(get_api_json(results_api,params={'limit':1})['MRData']['total'])
    results = pd.DataFrame(columns=['season', 'round', 'driver_id', 'constructor_id', 'number', 'finished_position', 'points', 'grid', 'laps', 'status', 'time_in_ms', 'fastest_lap_rank', 'fastest_lap_lap', 'fastest_lap_time', 'average_speed_kph'])
    while offset <= total:
        raw = get_api_json(results_api, params={'limit': 100, 'offset': offset})
        
        rows = [
            {
                'season': race['season'],
                'round': race['round'],
                'driver_id': drivers['Driver']['driverId'],
                'constructor_id': drivers['Constructor']['constructorId'],
                'number': drivers['number'],
                'finished_position': drivers['position'],
                'points': drivers['points'],
                'grid': drivers['grid'],
                'laps': drivers['laps'],
                'status': drivers['status'],
                'time_in_ms': drivers['Time']['millis'] if 'Time' in drivers else None,
                'fastest_lap_rank': drivers['FastestLap']['rank'] if 'FastestLap' in drivers else None,
                'fastest_lap_lap': drivers['FastestLap']['lap'] if 'FastestLap' in drivers else None,
                'fastest_lap_time': drivers['FastestLap']['Time']['time'] if 'FastestLap' in drivers else None,
                'average_speed_kph': drivers['FastestLap']['AverageSpeed']['speed'] if 'FastestLap' in drivers else 0
            }
            for race in raw['MRData']['RaceTable']['Races'] for drivers in race['Results']
        ]
        results = pd.concat([results,pd.DataFrame(rows)],ignore_index=True)
        offset += 100
    return results

def get_laptime_data(starting_season=1996,starting_round=1,offset=0):
    results = pd.DataFrame(columns=['position','time','season','round','lap','driverId'])
    for season,round in get_years_rounds(starting_season,starting_round):
        total = int(get_api_json(laptimes_api.format(year=str(season),round=str(round)),params={'limit':1})['MRData']['total'])
        while offset <= total:
            raw = get_api_json(laptimes_api.format(year=str(season),round=str(round)),params={'limit':100,'offset': offset})
            for laps in raw['MRData']['RaceTable']['Races'][0]['Laps']:
                timing_table = pd.DataFrame(laps['Timings'])
                timing_table[['season','round','lap']] = season,round,int(laps['number'])
                results = pd.concat([results,timing_table],axis=0,ignore_index=True)
            offset += 100
    return results

def get_pitstops_data(starting_season=2011,starting_round=1,offset=0):
    results = pd.DataFrame(columns=['season','round','driverId','lap','stop','time','duration'])
    for season,round in get_years_rounds(starting_season,starting_round):
        total = int(get_api_json(pitstops_api.format(year=str(season),round=str(round)),params={'limit':1})['MRData']['total'])
        while offset <= total:
            raw = get_api_json(pitstops_api.format(year=str(season),round=str(round)),params={'limit':100})
            if raw['MRData']['RaceTable']['Races']:
                stops_table = pd.DataFrame(raw['MRData']['RaceTable']['Races'][0]['PitStops'])
                stops_table[['season','round']] = season,round
                results = pd.concat([results,stops_table],axis=0,ignore_index=True)
            offset += 100
    return results

def get_qualifying_data(starting_season=2003,starting_round=1,offset=0):
    results = pd.DataFrame(columns=['season','round','driverId','q1','q2','q3'])
    for season,round in get_years_rounds(starting_season,starting_round):
        total = int(get_api_json(qualifying_api.format(year=str(season),round=str(round)),params={'limit':1})['MRData']['total'])
        while offset <= total:
            raw = get_api_json(qualifying_api.format(year=str(season),round=str(round)),params={'limit':100})
            if raw['MRData']['RaceTable']['Races']:
                    for qualifying_result in raw['MRData']['RaceTable']['Races'][0]['QualifyingResults']:
                        q1 = qualifying_result['Q1'] if 'Q1' in qualifying_result else None
                        q2 = qualifying_result['Q2'] if 'Q2' in qualifying_result else None
                        q3 = qualifying_result['Q3'] if 'Q3' in qualifying_result else None
                        rows = [{
                                'season': season,
                                'round': round,
                                'driverId': qualifying_result['Driver']['driverId'],
                                'qualifying_position': qualifying_result['position'],
                                'q1' : q1,
                                'q2' : q2,
                                'q3' : q3
                                }]
                        results = pd.concat([results,pd.DataFrame(rows)],axis=0,ignore_index=True)
            offset += 100
    return results