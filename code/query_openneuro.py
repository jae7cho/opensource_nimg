from selenium import webdriver
from selenium.webdriver.support import wait
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
import numpy as np
import re
from datetime import datetime
import requests
import configparser
from requests.auth import HTTPBasicAuth
import pandas as pd
import json
import sys

# Query for Open Neuro API
# Might be able to change to get all info from this query instead of using selenium
query =  """
query {
  dataset(id:"ds_placeholder") {
	id
	name
	metadata {
		  datasetId
		  datasetUrl
		  datasetName
		  firstSnapshotCreatedAt
		  latestSnapshotCreatedAt
		  dxStatus
		  tasksCompleted
		  trialCount
		  studyDesign
		  studyDomain
		  studyLongitudinal
		  dataProcessed
		  species
		  associatedPaperDOI
		  openneuroPaperDOI
		  seniorAuthor
		  adminUsers
		  ages
		  modalities
		  grantFunderName
		  grantIdentifier
		  affirmedDefaced
		  affirmedConsent
		}
	latestSnapshot {
	  id
	}
  }
}
"""

def get_metainfo(url):
	"""
	Function to get species, study type, Population type (Healthy, Clinical), tasks, citation block
	"""
	options = Options()
	options.add_argument("--headless")
	driver = webdriver.Firefox(options=options)
	driver.get(f'{url}/metadata')
	element = WebDriverWait(driver, 30).until(
		EC.presence_of_element_located((By.TAG_NAME, 'form'))
	)
	species = driver.find_elements(By.XPATH, f"//*[contains(@class, 'css-1y7plm6')]")[0].text
	studytype = driver.find_elements(By.XPATH, f"//*[contains(@class, 'css-1y7plm6')]")[1].text
	dx = driver.find_elements(By.XPATH, f"//*[contains(@class, 'css-1y7plm6')]")[2].text
	tasks = driver.find_elements(By.CSS_SELECTOR,"input[name='tasksCompleted'][class='css-1v4xkzy']")[0].get_attribute('value')
	cite = driver.find_elements(By.XPATH, f"//*[contains(@class, 'cite-content-block')]")[0].text
	driver.close()
	return species, studytype, dx, tasks, cite

def scrapeON(url):
	"""
	Function to get sidebar metadata info
	"""
	options = Options()
	options.add_argument("--headless")
	driver = webdriver.Firefox(options=options)
	driver.get(f'{url}/metadata')
	# Set variable dict and list:
	metavars = {}
	varlist = ['Tasks','Available Modalities','Participants','Dataset DOI','How To Cite','References and Links','Uploaded by']
	blocks = ['dmb-inline-list','dmb-modalities','undefined','dmb-list']
	# Wait for site to fully load:
	try:
		element = WebDriverWait(driver, 30).until(
			EC.presence_of_element_located((By.XPATH, "//*[contains(@class, 'col') and contains(@class, 'sidebar')]"))
		)
		# Get Sidebar:
		direct = driver.find_element(By.XPATH, "//*[contains(@class, 'col') and contains(@class, 'sidebar')]")
		# Get list of site blocks:
		for block in blocks:
			dmb_blocks = direct.find_elements(By.XPATH, f"//*[contains(@class, 'dataset-meta-block') and contains(@class, '{block}')]")
			# Loop through site blocks:
			for dmb in dmb_blocks:
				# Check for variable in each block:
				for v in varlist:
					if dmb.text.split('\n')[0] == v:
						try:
							if v == 'How To Cite':
								metavars[v] = dmb.text.split('\n')[2]
							elif v == 'Uploaded by':
								match = re.search(r'\d{4}-\d{2}-\d{2}', dmb.text.split('\n')[1])
								pubyear = datetime.strptime(match.group(), '%Y-%m-%d').date().year
								metavars['Published Year'] = pubyear
							else:
								metavars[v] = dmb.text.split('\n')[1]
						except:
							print(f"{v} missing on site for {url.split('/')[4]}")
		# Get metadata field:
		metavars['species'] = driver.find_elements(By.XPATH, f"//*[contains(@class, 'css-1y7plm6')]")[0].text
		metavars['studytype'] = driver.find_elements(By.XPATH, f"//*[contains(@class, 'css-1y7plm6')]")[1].text
		metavars['dx'] = driver.find_elements(By.XPATH, f"//*[contains(@class, 'css-1y7plm6')]")[2].text
		metavars['tasks'] = driver.find_elements(By.CSS_SELECTOR,"input[name='tasksCompleted'][class='css-1v4xkzy']")[0].get_attribute('value')
		metavars['cite'] = driver.find_elements(By.XPATH, f"//*[contains(@class, 'cite-content-block')]")[0].text

		driver.quit()
	finally:
		driver.quit()
	return metavars

def gather_meta(ds,api_key,wd):

	ondf = {
		'OpenNeuro Code':[],
		'Dataset':[],
		'Published year':[],
		'Species':[],
		'Population':[],
		'Study Type':[],
		'Use Case':[],
		'Age range':[],
		'Sample Size':[],
		'Modality':[],
		'Citation_block':[],
		'Reference':[],
		'OpenNeuro Data Link':[],
		'How to cite':[],
		'Tasks':[]
	}
	try:
		response = requests.post('https://openneuro.org/crn/graphql',
								json={"query":query.replace('ds_placeholder',ds)},
								auth = HTTPBasicAuth('apikey', api_key))
		query_output = json.loads(response.text)['data']['dataset']
		dataset = query_output['name']
		snapshot = query_output['latestSnapshot']['id'].split(':')
		on_meta = f'https://openneuro.org/datasets/{snapshot[0]}/versions/{snapshot[1]}'
		metavars = scrapeON(on_meta)
		# species, studytype, dx, tasks, cite = get_metainfo(on_meta)

		# Published year:
		try:
			if 'Published Year' in metavars.keys():
				published_year = metavars['Published Year']
			else:
				published_year = pd.to_datetime(query_output['metadata']['firstSnapshotCreatedAt']).year
		except:
			published_year = 'None'
		# Population:
		try:
			pop = query_output['metadata']['studyDomain']
		except:
			pop = 'None'
		# Ages:
		try:
			agemin = np.min(query_output["metadata"]["ages"])
			agemax = np.max(query_output["metadata"]["ages"])
			age_range = f'{agemin}-{agemax}'
		except:
			age_range = 'None'
		# Sample size:
		try:
			if 'Participants' in metavars.keys():
				sample_size = metavars['Participants']
			else:
				sample_size = len(query_output["metadata"]["ages"])
		except:
			sample_size = 'None'
		# Dataset modalities:
		mods = query_output['metadata']['modalities']
		print(mods)
		if (('mri' in mods) & (len(query_output['metadata']['tasksCompleted'])>0)):
			mods.append('fMRI')
		mods = ', '.join(mods)
		# Get paper/citation info:	
		try:
			target_url = f"https://raw.github.com/OpenNeuroDatasets/{ds}/master/dataset_description.json"
			response = requests.get(target_url).json()
			try:
				ref = response['ReferencesAndLinks']
			except:
				if ( ('References and Links' in metavars.keys()) & (len(metavars['References and Links'])>1) ):
					ref = metavars['References and Links']
				else:
					ref = query_output['metadata']['associatedPaperDOI']
			try:
				cit = response['HowToAcknowledge']
			except:
				if 'How To Cite' in metavars.keys():
					cit = metavars['How To Cite']
				else:
					cit = 'No acknowlegement info'
		except:
			ref = query_output['metadata']['associatedPaperDOI']
			cit = 'No acknowlegement info'
		if isinstance(ref, list):
			ref = ', '.join(ref) # Fix this repetition.

		# Data:
		if 'Dataset DOI' in metavars.keys():
			datadoi = metavars['Dataset DOI']
		else:
			datadoi = f'https://github.com/OpenNeuroDatasets/{ds}'


		# Fill dataframe:
		ondf['OpenNeuro Code'].append(ds)
		ondf['Dataset'].append(query_output['name'])
		ondf['Published year'].append(published_year)
		ondf['Species'].append(metavars['species'])
		ondf['Population'].append(metavars['dx'])
		ondf['Study Type'].append(metavars['studytype'])
		ondf['Use Case'].append(pop)
		ondf['Age range'].append(age_range)
		ondf['Sample Size'].append(sample_size)
		ondf['Modality'].append(str(mods).replace('[','').replace(']',''))
		ondf['Citation_block'].append(metavars['cite'])
		ondf['Reference'].append(ref)
		ondf['OpenNeuro Data Link'].append(datadoi)
		ondf['How to cite'].append(cit)
		ondf['Tasks'].append(metavars['tasks'])

		# Fill missing:
		for c in ondf.keys():
			if len(ondf[c])<np.max([len(ondf[cc]) for cc in ondf.keys()]):
				ondf[c].append('None')
		return pd.DataFrame(ondf)
	except:
		print(ds, ' not available or private')

def main():
	"""
	Run query and metadata scrape for all open neuro ascension numbers
	"""
	ds_list = np.loadtxt(f'{wd}/lists/ds_list.txt',dtype='str')
	# api key for Open Neuro API queries
	config = configparser.SafeConfigParser()
	config.read([r'{wd}/conf/queries.ini'])
	api_key = config.get('openneuro','api_key')
	wd = config.get('openneuro','workingdir')
	results = []
	for ds in ds_list:
		results.append(gather_meta(ds,api_key,wd))
	return results

if __name__=="__main__":
	results = main()
	if len(results)>1:
		pd.concat(results).to_csv(f'{wd}/output/open_neuro_all.csv')
