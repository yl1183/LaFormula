import pandas as pd
from datetime import datetime
from web_scrape import *


def clean_circuits_length(raw_length):
    if raw_length == 'NA':
        return None
    temp = str(raw_length).split('(')[-1][:-1]
    q,u = temp.split()
    return float(q) if 'km' == u else float(q)*1.60934

def clean_circuits_turns(raw_turns):
    if raw_turns == 'NA':
        return None
    return int(str(raw_turns).split('[')[0])
    
def clean_circuits_data(data):
    """Clean raw circuits data.

    Args:
      data(pd.DataFrame): raw circuit dataframe.

    Returns:
      Cleaned raw circuits data(pd.DataFrame).

    """
    data['locality'] = data['Location'].apply(lambda x: x['locality'])
    data['latitude'] = data['Location'].apply(lambda x: round(float(x['lat']), 2))
    data['longitude'] = data['Location'].apply(lambda x: round(float(x['long']), 2))
    data['country'] = data['Location'].apply(lambda x: x['country'])
    data['circuit_id'] = data['circuitId']
    data.drop(['Location', 'circuitId'], axis=1, inplace=True)
    data.rename(columns={'circuitName': 'circuit_name'}, inplace=True)
    data.loc[data['circuit_name'] == 'Long Beach', 'url'] = 'https://en.wikipedia.org/wiki/Grand_Prix_of_Long_Beach'
    data = data[data['circuit_name'] != 'Las Vegas Strip Street Circuit']
    data['length'] = data['url'].apply(get_length_data_scrape)
    data['turns'] = data['url'].apply(get_turns_data_scrape)
    data['length'] = data['length'].apply(clean_circuits_length)
    data['turns'] = data['turns'].apply(clean_circuits_turns)
    data['turns'] = data['turns'].astype(pd.Int64Dtype())

    return data

def clean_drivers_data(data):
    data['dateOfBirth'] = pd.to_datetime(data['dateOfBirth'],format = '%Y-%m-%d')
    # data['dateOfBirth'] = data['dateOfBirth'].apply(lambda x: datetime.strptime(x, '%Y-%m-%d'))
    data.columns = ['driver_id','url','given_name','family_name','date_of_birth','nationality']
    return data

def clean_constructors_data(data):
    data.columns = ['constructor_id','url','constructor_name','nationality']
    return data


def get_date(row):
    if row!=row:
        return None
    else:
        if 'date' and 'time' in row: 
            return datetime.strptime(row['date']+' '+row['time'][0:-1],'%Y-%m-%d %H:%M:%S')
        else:
            if 'date' in row:
                return datetime.strptime(row['date']+' '+'00:00:00','%Y-%m-%d %H:%M:%S')

def clean_races_data(data):
    data['circuit_id'] = data['Circuit'].apply(lambda x: x['circuitId'])
    data['season'] = data['season'].apply(int)
    data['round'] = data['round'].apply(int)
    data['time'] = data['time'].apply(lambda x: str(x)[0:-1] if x==x else '00:00:00')
    data['datetime'] = data['date']+" "+data['time']
    data['datetime'] = pd.to_datetime(data['datetime'])
    data['date'] = pd.to_datetime(data['date'],format = '%Y-%m-%d')
    data['FirstPractice'] = data['FirstPractice'].apply(get_date)
    data['SecondPractice'] = data['SecondPractice'].apply(get_date)
    data['ThirdPractice'] = data['ThirdPractice'].apply(get_date)
    data['Qualifying'] = data['Qualifying'].apply(get_date)
    data['Sprint'] = data['Sprint'].apply(get_date)
    data.iloc[:, 7:12] = data.iloc[:, 7:12].apply(pd.to_datetime)
    data.drop(['Circuit'],inplace=True,axis=1)
    data.columns = ['season','round','url','race_name','date','time','first_practice_datetime','second_practice_datetime','third_practice_datetime','qualifying_datetime','sprint_datetime','circuit_id','datetime']
    return data


def time_str_to_ms(row):
    if row:
        if row.count(':') == 2:
            return None
        mins = row.split(':')[0]
        s,ms = row.split(':')[1].split('.')[0],row.split(':')[1].split('.')[1]
        return int(mins)*6000 + int(s)*1000 + int(ms)
    return None

def clean_results_data(data):
    data['fastest_lap_time'] = data['fastest_lap_time'].apply(time_str_to_ms)
    types = {'season':int,
         'round':int,
         'driver_id':str,
         'constructor_id':str,
         'number':str,
         'finished_position':int,
         'points':float,
         'grid':int,
         'laps':int,
         'status':str,
         'time_in_ms':pd.Int64Dtype(),
         'fastest_lap_rank':pd.Int64Dtype(),
         'fastest_lap_lap':pd.Int64Dtype(),
         'fastest_lap_time':pd.Int64Dtype(),
         'average_speed_kph':float}
    data = data.astype(types)
    return data



def clean_laptime_data(data):
    data['time'] = data['time'].apply(time_str_to_ms)
    types = {'position':int,
         'time':pd.Int64Dtype(),
         'season':int,
         'round':int,
         'lap':int,
         'driverId':str}
    data = data.astype(types)
    data = data.rename(columns={'time':'time_in_ms','driverId':'driver_id'})
    return data

def clean_pitstop_duration_ms(row):
    if row:
        if row.count(':') == 1:
            mins = row.split(':')[0]
            s,ms = row.split(':')[1].split('.')[0],row.split(':')[1].split('.')[1]
            return int(mins)*6000 + int(s)*1000 + int(ms)
        else:
            return int(float(row)*1000)
    return None


def clean_pitstops_data(data):
    data['duration'] = data['duration'].apply(clean_pitstop_duration_ms)
    types = {'season':int,
         'round':int,
         'driverId':str,
         'lap':int,
         'stop':int,
         'time':str,
         'duration':int}
    data = data.astype(types)
    data = data.rename(columns={'duration':'duration_in_ms','driverId':'driver_id'})
    return data



def clean_qualifying_data(data):
    data['q1'] = data['q1'].apply(time_str_to_ms)
    data['q2'] = data['q2'].apply(time_str_to_ms)
    data['q3'] = data['q3'].apply(time_str_to_ms)
    types = {'season':int,
         'round':int,
         'driverId':str,
         'qualifying_position':int,
         'q1':pd.Int64Dtype(),
         'q2':pd.Int64Dtype(),
         'q3':pd.Int64Dtype()}
    data = data.astype(types)
    data = data.rename(columns={'driverId':'driver_id','q1':'q1_in_ms','q2':'q2_in_ms','q3':'q3_in_ms'})
    return data



