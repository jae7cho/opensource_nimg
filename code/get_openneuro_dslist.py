import openneuro as on
import pandas as pd
import json
import requests
from datetime import datetime
from bs4 import BeautifulSoup
from requests.auth import HTTPBasicAuth
import pandas as pd
import numpy as np
import configparser

fname = config.get('openneuro','file_name')
api_key = config.get('openneuro','api_key')
wd = config.get('openneuro','workingdir')

def on_ds_list():
	ds_list = []
	counter = 1
	while True:
		try:
			print('Page:', counter)
			url = f'https://github.com/orgs/OpenNeuroDatasets/repositories?page={counter}'
			page = requests.get(url)
			soup = BeautifulSoup(page.text, 'html.parser')
			page_ds = [str(i).split('/OpenNeuroDatasets/')[1].split('">')[0] for i in soup.select('a') if (('href="/OpenNeuroDatasets/' in str(i)) & ('<span>' in str(i)))]
			if len(page_ds) < 1:
				print('No pages left')
				break
			for d in page_ds:
				ds_list.append(d)
			counter = counter + 1
		except Exception as e:
			print('All pages done')
			break
	print(f'Number of datasets: {len(ds_list)}')
	return ds_list

ds_list = on_ds_list()
np.savetxt(f'{wd}/lists/ds_list.txt',ds_list,'%s')
