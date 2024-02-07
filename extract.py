

import requests
import pandas as pd
import sqlalchemy
from google.cloud.sql.connector import Connector

# Replace 'your_connection_name', 'your_database_user', 'your_database_password',
# 'your_database_host', 'your_database_name' with your actual connection details
connection_name = connection_name
database_user = 'sqlserver'
database_password = 'sqlserver'
database_host = database_host
database_name = 'laformula'

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

# Use the to_sql method to write the DataFrame to the SQL Server table
response = requests.get('http://ergast.com/api/f1/circuits.json', params={'limit': '999'})
raw_data = response.json()
circuits = raw_data['MRData']['CircuitTable']['Circuits']

data = pd.DataFrame(circuits)

data['locality'] = data['Location'].apply(lambda x: x['locality'])
data['latitude'] = data['Location'].apply(lambda x: round(float(x['lat']), 2))
data['longitude'] = data['Location'].apply(lambda x: round(float(x['long']), 2))
data['country'] = data['Location'].apply(lambda x: x['country'])
data.drop(['Location', 'circuitId'], axis=1, inplace=True)
data.rename(columns={'circuitName': 'circuit_name'}, inplace=True)
print(data['url'][1])

# data = data.astype({})
# data.to_sql(name=table_name, con=engine, if_exists='replace', index=False)

# # Close the connection when done
# connection.close()

# html/body/div[2]/div/div[3]/main/div[3]/div[3]/div[1]/table[1]/tbody/tr[12]/td
/html/body/div[2]/div/div[3]/main/div[3]/div[3]/div[1]/table[1]/tbody/tr[16]/th
