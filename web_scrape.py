from bs4 import BeautifulSoup
import requests

def get_length_data_scrape(url):
    response = requests.get(url, params={'limit': 999})
    soup = BeautifulSoup(response.content,'html.parser')
    selected = soup.select('th:-soup-contains("Length")')
    if selected:
        length_data = selected[0].find_next().get_text(strip=True)
        if 'km' in length_data:
            return length_data
        else:
            length_data = selected[1].find_next().get_text(strip=True)
    else:
        length_data = 'NA'
    
    return length_data

def get_turns_data_scrape(url):
    response = requests.get(url, params={'limit': 999})
    soup = BeautifulSoup(response.content,'html.parser')
    selected = soup.select('th:-soup-contains("Turns")')
    if selected:
        turns_data = selected[0].find_next().get_text(strip=True)
    else:
        turns_data = 'NA'
    return turns_data
