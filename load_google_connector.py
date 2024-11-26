from google.cloud.sql.connector import Connector
import sqlalchemy
from config.config import connection_name,database_host,circuits_api,database_user,database_password,database_name
from extract import *
from transform import *

connector = Connector()

def getconn():
    conn = connector.connect(
        connection_name,
        "pytds",
        user=database_user,
        host = database_host,
        password=database_password,
        db=database_name
    )
    return conn
# Create an SQLAlchemy engine using the connection
def load_circuits_data_to_db():
    engine = sqlalchemy.create_engine(
        "mssql+pytds://",
        creator=getconn,
    )

    table_name = 'circuits'
    data = get_circuits_data()
    data = clean_circuits_data(data)
    data.to_sql(name=table_name, con=engine, if_exists='replace', index=False)

    connector.close()

def load_drivers_data_to_db():
    engine = sqlalchemy.create_engine(
        "mssql+pytds://",
        creator=getconn,
    )

    table_name = 'drivers'

    data =  get_drivers_data()
    data = clean_drivers_data(data)
    data.to_sql(name=table_name, con=engine, if_exists='replace', index=False)

    connector.close()

def load_constructors_data_to_db():
    engine = sqlalchemy.create_engine(
        "mssql+pytds://",
        creator=getconn,
    )

    table_name = 'constructors'

    data =  get_constructors_data()
    data = clean_constructors_data(data)
    data.to_sql(name=table_name, con=engine, if_exists='replace', index=False)

    connector.close()

def load_races_data_to_db():
    engine = sqlalchemy.create_engine(
        "mssql+pytds://",
        creator=getconn,
    )

    table_name = 'races'

    data =  get_races_data()
    data = clean_races_data(data)
    data.to_sql(name=table_name, con=engine, if_exists='replace', index=False)

    connector.close()