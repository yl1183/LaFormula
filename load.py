from sqlalchemy import create_engine, Column, Integer, String, MetaData, Table,select,DateTime,text,insert
from datamodels import *
from extract import *
from transform import *
from config.config import *

engine = create_engine(database_url)
metadata = MetaData()

def load_drivers_data_to_db():
    with engine.connect() as connection:
        data =  get_drivers_data()
        data = clean_drivers_data(data)
        sql = text('''INSERT INTO drivers (driver_id, url, given_name, family_name, date_of_birth, nationality)
                      VALUES (:driver_id, :url, :given_name, :family_name, :date_of_birth, :nationality)''')
        # data = [row.to_dict() for _,row in data.iterrows()]
        data = data.to_dict(orient='records')
        # insert_statement = insert(drivers).values(data)
        connection.execute(sql,data)
        connection.commit()


def load_circuits_data_to_db():
        with engine.connect() as connection:
            data =  get_circuits_data()
            data = clean_circuits_data(data)
            sql = text('''INSERT INTO circuits (url,circuit_name, locality, latitude, longitude, country, length, turns,circuit_id) 
                          VALUES (:url, :circuit_name, :locality, :latitude, :longitude, :country, :length, :turns, :circuit_id)''')
            # data = [row.to_dict() for _,row in data.iterrows()]
            data = data.to_dict(orient='records')
            # insert_statement = insert(drivers).values(data)
            connection.execute(sql,data)
            connection.commit()

def load_contructors_data_to_db():
        with engine.connect() as connection:
            data =  get_constructors_data()
            data = clean_constructors_data(data)
            sql = text('''INSERT INTO constructors (constructor_id, url, constructor_name, nationality) 
                          VALUES (:constructor_id, :url, :constructor_name, :nationality)''')
            # data = [row.to_dict() for _,row in data.iterrows()]
            data = data.to_dict(orient='records')
            # insert_statement = insert(drivers).values(data)
            connection.execute(sql,data)
            connection.commit()

def load_races_data_to_db():
        with engine.connect() as connection:
            data =  get_races_data()
            data = clean_races_data(data)
            sql = text('''INSERT INTO races (season, round, url, race_name, date, time, first_practice_datetime, second_practice_datetime, third_practice_datetime, qualifying_datetime, sprint_datetime, circuit_id, datetime) 
                          VALUES (:season, :round, :url, :race_name, :date, :time, :first_practice_datetime, :second_practice_datetime, :third_practice_datetime, :qualifying_datetime, :sprint_datetime, :circuit_id, :datetime)''')
            # data = [row.to_dict() for _,row in data.iterrows()]
            data = data.to_dict(orient='records')
            # insert_statement = insert(drivers).values(data)
            connection.execute(sql,data)
            connection.commit()


def load_results_data_to_db(offset = 0):
        with engine.connect() as connection:
            data =  get_results_data(offset)
            data = clean_results_data(data)
            next_id = connection.execute(text(f"SELECT COUNT(*) + 1 FROM results")).scalar()
            connection.execute(text(f"DBCC CHECKIDENT ('results', RESEED, :next_id)"), {'next_id': next_id - 1})
            sql = text('''INSERT INTO results (season,round,driver_id,constructor_id,number,finished_position,points,grid,laps,status,time_in_ms,fastest_lap_rank,fastest_lap_lap,fastest_lap_time,average_speed_kph) 
                          VALUES (:season,:round,:driver_id,:constructor_id,:number,:finished_position,:points,:grid,:laps,:status,:time_in_ms,:fastest_lap_rank,:fastest_lap_lap,:fastest_lap_time,:average_speed_kph)''')
            # data = [row.to_dict() for _,row in data.iterrows()]
            data = data.to_dict(orient='records')          
            # insert_statement = insert(drivers).values(data)
            connection.execute(sql,data)
            connection.commit()


def load_laptime_data_to_db(starting_season=1996,starting_round=1):
        with engine.connect() as connection:
            data =  get_laptime_data(starting_season,starting_round)
            print('starting pulling laptime')
            data = clean_laptime_data(data)
            next_id = connection.execute(text(f"SELECT COUNT(*) + 1 FROM laptime")).scalar()
            connection.execute(text(f"DBCC CHECKIDENT ('laptime', RESEED, :next_id)"), {'next_id': next_id}) #since laptime_id is starting from 2!!
            sql = text('''INSERT INTO laptime (position,time_in_ms,season,round,lap,driver_id) 
                              VALUES (:position,:time_in_ms,:season,:round,:lap,:driver_id)''')
            data = data.to_dict(orient='records')  
            connection.execute(sql,data)
            connection.commit() 
        #     data.to_sql(name='laptime', con=connection, if_exists='append',chunksize=2000,index=False)

def load_pitstops_data_to_db(starting_season=2011,starting_round=1):
        with engine.connect() as connection:
                data =  get_pitstops_data(starting_season,starting_round)
                data = clean_pitstops_data(data)
                next_id = connection.execute(text(f"SELECT COUNT(*) + 1 FROM pitstops")).scalar()
                connection.execute(text(f"DBCC CHECKIDENT ('pitstops', RESEED, :next_id)"), {'next_id': next_id - 1})
                sql = text('''INSERT INTO pitstops (season,round,driver_id,lap,stop,time,duration_in_ms) 
                              VALUES (:season,:round,:driver_id,:lap,:stop,:time,:duration_in_ms)''')
                # data = [row.to_dict() for _,row in data.iterrows()]
                data = data.to_dict(orient='records')          
                # insert_statement = insert(drivers).values(data)
                connection.execute(sql,data)
                connection.commit()

def load_qualifying_data_to_db(starting_season=2003,starting_round=1):
        with engine.connect() as connection:
                data =  get_qualifying_data(starting_season,starting_round)
                data = clean_qualifying_data(data)
                next_id = connection.execute(text(f"SELECT COUNT(*) + 1 FROM qualifying")).scalar()
                connection.execute(text(f"DBCC CHECKIDENT ('qualifying', RESEED, :next_id)"), {'next_id': next_id - 1})
                sql = text('''INSERT INTO qualifying (season,round,driver_id,qualifying_position,q1_in_ms,q2_in_ms,q3_in_ms) 
                              VALUES (:season,:round,:driver_id,:qualifying_position,:q1_in_ms,:q2_in_ms,:q3_in_ms)''')
                # data = [row.to_dict() for _,row in data.iterrows()]
                data = data.to_dict(orient='records')          
                # insert_statement = insert(drivers).values(data)
                connection.execute(sql,data)
                connection.commit()
  
#insert statement to insert
# def load_races_data_to_db():
#         with engine.connect() as connection:
#             data =  get_races_data()
#             data = clean_races_data(data)
#             data = [row.to_dict() for _,row in data.iterrows()]
#             for i in range(0,len(data),20):
#             #
#             # data = data.to_dict(orient='list')
#                 insert_statement = insert(drivers).values(data[i:i+20])
#                 connection.execute(insert_statement)
#                 connection.commit()