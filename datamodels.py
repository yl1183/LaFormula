from sqlalchemy import create_engine, Column, Integer, String, MetaData, Table,select,DateTime,text
from config.config import database_url

engine = create_engine(database_url)
metadata = MetaData()


# drivers = Table(
#     'drivers',
#     metadata,
#     Column('driver_id', String, primary_key=True),
#     Column('url', String),
#     Column('given_name', String),
#     Column('family_name', String),
#     Column('date_of_birth', DateTime),
#     Column('nationality', String)
# )

#reflected
drivers = Table('drivers', metadata, autoload_with=engine)
circuits = Table('circuits',metadata,autoload_with=engine)
races = Table('races',metadata,autoload_with=engine)
constructors = Table('constructors',metadata,autoload_with=engine)


