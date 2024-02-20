from google.cloud.sql.connector import Connector
import sqlalchemy
from config.config import connection_name,database_host,circuits_api,database_user,database_password,database_name
from extract import get_circuits_data
from transform import clean_circuits_data

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

engine = sqlalchemy.create_engine(
    "mssql+pytds://",
    creator=getconn,
)

table_name = 'circuits'

data = get_circuits_data()
data = clean_circuits_data(data)
data.to_sql(name=table_name, con=engine, if_exists='replace', index=False)

connector.close()
