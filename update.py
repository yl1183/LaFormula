from config.config import *
import requests
import pandas as pd
from extract import *
from service import *
from load import *
from sqlalchemy import create_engine, Column, Integer, String, MetaData,Table,select,DateTime,text,update

engine = create_engine(database_url)
metadata = MetaData()

def update_circuits_data():
    circuits_rows_db = get_table_length('circuits')
    print("there are {} rows in circuits table in database".format(str(circuits_rows_db)))
    circuits_rows_api = int(get_api_json(circuits_api,params={'limit':1})['MRData']['total'])
    print("there are {} rows in circuits data in Ergast".format(str(circuits_rows_api)))
    if circuits_rows_api != circuits_rows_db:
        delete_table('circuits')
        load_circuits_data_to_db()

def update_drivers_data():
    drivers_rows_db = get_table_length('drivers')
    print("there are {} rows in drivers table in database".format(str(drivers_rows_db)))
    drivers_rows_api = int(get_api_json(drivers_api,params={'limit':1})['MRData']['total'])
    print("there are {} rows in drivers data in Ergast".format(str(drivers_rows_api)))
    if drivers_rows_db != drivers_rows_api:
        delete_table('drivers')
        load_drivers_data_to_db()

def update_constructors_data():
    constructors_rows_db = get_table_length('constructors')
    print("there are {} rows in constructors table in database".format(str(constructors_rows_db)))
    constructors_rows_api = int(get_api_json(constructor_api,params={'limit':1})['MRData']['total'])
    print("there are {} rows in constructors data in Ergast".format(str(constructors_rows_api)))
    if constructors_rows_db != constructors_rows_api:
        delete_table('constructors')
        load_contructors_data_to_db()

def update_races_data():
    races_rows_db = get_table_length('races')
    print("there are {} rows in races table in database".format(str(races_rows_db)))
    races_rows_api = int(get_api_json(races_api,params={'limit':1})['MRData']['total'])
    print("there are {} rows in races data in Ergast".format(str(races_rows_api)))
    if races_rows_db != races_rows_api:
        delete_table('races')
        load_races_data_to_db()

def update_results_data():
    results_rows_db = get_table_length('results')
    print("there are {} rows in races table in database".format(str(results_rows_db)))
    results_rows_api = int(get_api_json(results_api,params={'limit':1})['MRData']['total'])
    print("there are {} rows in races data in Ergast".format(str(results_rows_api)))
    if results_rows_db < results_rows_api:
        print('start updating values from api offset {}'.format(results_rows_db))
        load_results_data_to_db(offset=results_rows_db)
    
def update_laptime_data():
    most_recent_season,most_recent_round = get_most_recent_year_round()
    existing_recent_season,existing_recent_round = get_most_recent_year_round_laptime()
    if most_recent_season == existing_recent_season and most_recent_round > existing_recent_round:
        total = int(get_api_json(laptimes_api.format(year=existing_recent_season,round=existing_recent_round+1),params={'limit':1})['MRData']['total'])
        if total == 0:
            print('data not updated in api yet')
        else:
            print('start updating laptime data from season {} round {} to the latest in results table'.format(existing_recent_season,existing_recent_round+1))
            load_laptime_data_to_db(existing_recent_season,existing_recent_round+1)
    elif most_recent_season > existing_recent_season:
        total = int(get_api_json(laptimes_api.format(year=existing_recent_season+1,round=1),params={'limit':1})['MRData']['total'])
        if total == 0:
            print('data not updated in api yet')
        else:
            print('start updating laptime data from season {} round {} to the latest in results table'.format(existing_recent_season+1,1))
            load_laptime_data_to_db(existing_recent_season+1,1)
    else:
        print('Laformula has the latest laptime data')

    
def update_pitstops_data():
    most_recent_season,most_recent_round = get_most_recent_year_round()
    existing_recent_season,existing_recent_round = get_most_recent_year_round_pitstops()
    if most_recent_season == existing_recent_season and most_recent_round > existing_recent_round:
        total = int(get_api_json(pitstops_api.format(year=existing_recent_season,round=existing_recent_round+1),params={'limit':1})['MRData']['total'])
        if total == 0:
            print('data not updated in api yet')
        else:
            print('start updating pitstops data from season {} round {} to the latest in results table'.format(existing_recent_season,existing_recent_round+1))
            load_pitstops_data_to_db(existing_recent_season,existing_recent_round+1)            
    elif most_recent_season > existing_recent_season:
        total = int(get_api_json(pitstops_api.format(year=existing_recent_season+1,round=1),params={'limit':1})['MRData']['total'])
        if total == 0:
            print('data not updated in api yet')
        else:
            print('start updating pitstops data from season {} round {} to the latest in results table'.format(existing_recent_season+1,1))
            load_pitstops_data_to_db(existing_recent_season+1,1)            
    else:
        print('Laformula has the latest pitstops data')

def update_qualifying_data():
    most_recent_season,most_recent_round = get_most_recent_year_round()
    existing_recent_season,existing_recent_round = get_most_recent_year_round_qualifying()
    if most_recent_season == existing_recent_season and most_recent_round > existing_recent_round:
        total = int(get_api_json(qualifying_api.format(year=existing_recent_season,round=existing_recent_round+1),params={'limit':1})['MRData']['total'])
        if total == 0:
            print('data not updated in api yet')
        else:
            print('start updating qualifying data from season {} round {} to the latest in results table'.format(existing_recent_season,existing_recent_round+1))
            load_qualifying_data_to_db(existing_recent_season,existing_recent_round+1)            
    elif most_recent_season > existing_recent_season:
        total = int(get_api_json(qualifying_api.format(year=existing_recent_season+1,round=1),params={'limit':1})['MRData']['total'])
        if total == 0:
            print('data not updated in api yet')
        else:
            print('start updating qualifying data from season {} round {} to the latest in results table'.format(existing_recent_season+1,1))
            load_qualifying_data_to_db(existing_recent_season+1,1)            
    else:
        print('Laformula has the latest qualifying data')

