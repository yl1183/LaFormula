from sqlalchemy import create_engine, Column, Integer, String, MetaData,Table,select,DateTime,text,update
from config.config import database_url
from datamodels import drivers

engine = create_engine(database_url)
metadata = MetaData()

def delete_table(table_name):
    table = Table(table_name, metadata,autoload_with=engine)
    with engine.begin() as connection:
    # Construct the delete statement
        delete_statement = table.delete()
    # Execute the delete statement
        connection.execute(delete_statement)


#query
def get_years_rounds(starting_season,starting_round):
    return_list = []
    with engine.connect() as connection:
        # select_statement = select(drivers.c.family_name).where(drivers.c.nationality == 'British')
        select_statement = text('''select season,round from results
                                   where season >= {} and round >={}
                                   group by season,round
                                   order by season,round;'''.format(starting_season,starting_round))
        result = connection.execute(select_statement)
        rows = result.fetchall()
        for row in rows:
            return_list.append([row[0],row[1]])
    return return_list
def get_most_recent_year_round():
    with engine.connect() as connection:
        select_statement = text('''select season,max(round) from results
                                   where season = (select max(season) from results)
                                   group by season;''')
        result = connection.execute(select_statement)
        rows = result.fetchall()
        return rows[0][0],rows[0][1]

def get_most_recent_year_round_laptime():
    with engine.connect() as connection:
        select_statement = text('''select season,max(round) from laptime
                                   where season = (select max(season) from laptime)
                                   group by season;''')
        result = connection.execute(select_statement)
        rows = result.fetchall()
        return rows[0][0],rows[0][1]
    
def get_most_recent_year_round_pitstops():
    with engine.connect() as connection:
        select_statement = text('''select season,max(round) from pitstops
                                   where season = (select max(season) from pitstops)
                                   group by season;''')
        result = connection.execute(select_statement)
        rows = result.fetchall()
        return rows[0][0],rows[0][1]
    
def get_most_recent_year_round_qualifying():
    with engine.connect() as connection:
        select_statement = text('''select season,max(round) from qualifying
                                   where season = (select max(season) from pitstops)
                                   group by season;''')
        result = connection.execute(select_statement)
        rows = result.fetchall()
        return rows[0][0],rows[0][1]

def get_table_length(table_name):
    with engine.connect() as connection:
        # select_statement = select(drivers.c.family_name).where(drivers.c.nationality == 'British')
        select_statement = text('''select count(1) from {};'''.format(table_name))
        result = connection.execute(select_statement)
        length = result.fetchall()
    return length[0][0]





#update
# with engine.connect() as connection:
#     update_statement = update(drivers).where(drivers.c.family_name == 'Zhou').values(nationality='China')
#     connection.execute(update_statement)