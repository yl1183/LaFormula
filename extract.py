from config.config import circuits_api,drivers_api,constructor_api

import requests
import pandas as pd
from bs4 import BeautifulSoup
from web_scrape import get_length_data_scrape,get_turns_data_scrape





def get_api_json(url,params):
    response = requests.get(url, params=params)
    raw_data = response.json()
    return raw_data

def get_circuits_data():
    raw_data = get_api_json(circuits_api,{'limit': '999'})
    circuits = raw_data['MRData']['CircuitTable']['Circuits']
    data = pd.DataFrame(circuits)
    data['locality'] = data['Location'].apply(lambda x: x['locality'])
    data['latitude'] = data['Location'].apply(lambda x: round(float(x['lat']), 2))
    data['longitude'] = data['Location'].apply(lambda x: round(float(x['long']), 2))
    data['country'] = data['Location'].apply(lambda x: x['country'])
    data.drop(['Location', 'circuitId'], axis=1, inplace=True)
    data.rename(columns={'circuitName': 'circuit_name'}, inplace=True)
    data.loc[data['circuit_name'] == 'Long Beach', 'url'] = 'https://en.wikipedia.org/wiki/Grand_Prix_of_Long_Beach'
    data = data[data['circuit_name'] != 'Las Vegas Strip Street Circuit']
    data['length'] = data['url'].apply(get_length_data_scrape)
    data['turns'] = data['url'].apply(get_turns_data_scrape)
    
    return data

def get_drivers_data():
    raw_data = get_api_json(drivers_api,{'limit': '999'})
    drivers = raw_data['MRData']['DriverTable']['Drivers']
    data = pd.DataFrame(drivers)
    data.drop(['permanentNumber', 'code'], axis=1, inplace=True)

    return data
    
def get_constructors_data():
    raw_data = get_api_json(constructor_api,{'limit': '999'})
    constructors = raw_data['MRData']['ConstructorTable']['Constructors']
    data =  pd.DataFrame(constructors)

    return data









