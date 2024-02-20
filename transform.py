import pandas as pd




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

    data['length'] = data['length'].apply(clean_circuits_length)
    data['turns'] = data['turns'].apply(clean_circuits_turns)
    return data

def clean_drivers_data(data):
    data.rename(columns={i:i.lower() for i in [*data.columns]})
    data['dateofbirth'] = pd.to_datetime(data['dateofbirth'],format = '%Y-%m-%d')
    return data

def clean_constructors_data(data):
    data.rename(columns={i:i.lower() for i in [*data.columns]})
    return data

def form_