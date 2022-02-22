import csv
import json
from select import select
import requests
import re
import pandas
import operator
import time
import logging

logging.basicConfig(format='%(asctime)s %(message)s',filename='cms_log.txt', level=logging.INFO)

## authorization class to initialize necessary tokens and urls
class authWorkspace:
    ## replace with key vault code in production
    api_token = ""

    auth_url = "https://eu-svc.leanix.net/services/mtm/v1/oauth2/token"
    request_url = "https://eu.leanix.net/services/integration-api/v1/"

    response = requests.post(auth_url, auth=('apitoken', api_token),data={'grant_type': 'client_credentials'})
    response.raise_for_status()

    access_token = response.json()['access_token']
    logging.info('Access token granted.')
    auth_header = 'Bearer ' + access_token
    header = {'Authorization': auth_header, 'Content-Type': 'application/json'}


## transforms csv to dict, creates minimums and maximums dictionaries for each 6r 
class transform_local_data:
    ## ingests csv, transforms question-scores to mapping dict
    ## needs to be moved to an inbound iAPI processor
    def transform_schema_to_dict(self):
        cloud_ms_schema = {}

        with open('schema2.csv','r',encoding='utf-8') as csv_file:
            schema_data = csv.DictReader(csv_file)
            
            for data in schema_data:
                if data['\ufeffTechnical Name Question'] not in cloud_ms_schema:
                    cloud_ms_schema[data['\ufeffTechnical Name Question']] = {}

                if data['Technical Name'] not in cloud_ms_schema[data['\ufeffTechnical Name Question']]:
                    new_answer = {}
                    new_answer['Rehost'] = data['Rehost']
                    new_answer['Rearchitect'] = data['Rearchitect']
                    new_answer['Rebuild'] = data['Rebuild']
                    new_answer['Replace'] = data['Replace']
                    new_answer['Retain'] = data['Retain']
                    new_answer['Retire'] = data['Retire']
                    cloud_ms_schema[data['\ufeffTechnical Name Question']][data['Technical Name']] = new_answer
            
            return cloud_ms_schema


    def transform_schema_index(self):
        data = pandas.read_csv("schema3.csv")
        r6 = ['Rehost','Rearchitect','Rebuild','Replace','Retain','Retire']
        all_sminimums = {}
        all_smaximums = {}

        ## for each question, get the max and min score of all answers for each 6R
        ## SQL example:
        ## select
        ##     question
        ##     ,6R
        ##     ,max(scores)
        ##     ,min(scores)
        ## from schema2
        ## group by question, 6R

        for a_r6 in r6:
            mins = data.groupby(['Technical Name Question'])[a_r6].min()
            maxs = data.groupby(['Technical Name Question'])[a_r6].max()
            all_sminimums[a_r6] = mins.to_dict()
            all_smaximums[a_r6] = maxs.to_dict()

        return all_sminimums, all_smaximums


## run iAPI outbound processor to pull application data, reuse functions to send decision and scores back through iAPI
class iAPI(authWorkspace):
    ## Create connector run with outbound processor
    def createOutboundRun(self):
        data = {
            "connectorType": "outboundFactSheet",
            "connectorId": "get-apps-cms",
            "connectorVersion": "1.0.0",
            "lxVersion": "1.0.0",
            "description": "Outputs Cloud Migration Strategy data",
            "processingDirection": "outbound",
            "processingMode": "partial",
            "customFields": {}
        }
        
        response = requests.post(url=authWorkspace.request_url + "synchronizationRuns/", headers=authWorkspace.header, data=json.dumps(data))
        return (response.json())


    ## Create inbound processor/connector run and LDIF content
    def createInboundRun(self, content):
        data = {
            "connectorType": "inboundFactSheet",
            "connectorId": "update-cms-data",
            "connectorVersion": "1.0.0",
            "lxVersion": "1.0.0",
            "description": "Updates cloud migration strategy data with 6R decision and scores.",
            "processingDirection": "inbound",
            "processingMode": "partial",
            "customFields": {},
            "content": content
        }

        self.response = requests.post(url=authWorkspace.request_url + "synchronizationRuns/", headers=authWorkspace.header, data=json.dumps(data))
        return (self.response.json())

    ## Process data / load into LeanIX workspace
    def startRun(self, run):
        response = requests.post(url=authWorkspace.request_url + "synchronizationRuns/" + run["id"] + "/start?test=false", headers=authWorkspace.header)
        return response


    ## check status of iAPI run 
    def status(self, run):
        response = requests.get(url=authWorkspace.request_url + "synchronizationRuns/" + run["id"] + "/status", headers=authWorkspace.header)
        return (response.json())


    
    def getResults(self, run):
        response = requests.get(url=authWorkspace.request_url + "synchronizationRuns/" + run["id"] + "/results", headers=authWorkspace.header)

        if response.status_code == 204:
            print("No result content available for run: " + run["id"])
        else:
            return (response.json())


    def buildLdif(self, app_scores, r_decision):
        content = []

        try:
            for an_app in r_decision:
                new_content = {}
                new_content["type"] = "Application"
                new_content["id"] = an_app
                new_content["data"] = {}
                new_content["data"]['CMResultRecommendation'] = r_decision[an_app]
                new_content["data"]['CMResultRearchitect'] = app_scores[an_app]['Rearchitect']
                new_content["data"]['CMResultRebuild'] = app_scores[an_app]['Rebuild']
                new_content["data"]['CMResultRehost'] = app_scores[an_app]['Rehost']
                new_content["data"]['CMResultReplace'] = app_scores[an_app]['Replace']
                new_content["data"]['CMResultRetain'] = app_scores[an_app]['Retain']
                new_content["data"]['CMResultRetire'] = app_scores[an_app]['Retire']
                content.append(new_content)
        except KeyError:
            pass

        return content

    ## extracts data from workspace
    def __init__(self):
        ## initialize auth class
        super().__init__()
        run_response = self.createOutboundRun()
        fs_content = self.startRun(run_response)
        logging.info('Begin iAPI outbound run.')
        run_status = self.status(run_response)

        while run_status['status'] in ['PENDING','IN_PROGRESS']:
            logging.info('iAPI outbound run status is: ' + str(run_status['status']))
            time.sleep(5)
            run_status = self.status(run_response)

        if run_status['status'] == 'FINISHED':
            logging.info('iAPI outbound run status is: ' + str(run_status['status']))
            self.ldif = self.getResults(run_response)
            logging.info(str(len(self.ldif['content']))+' applications extracted.')
        else:
            logging.info('Check sync logging in LeanIX UI.')


## calculate scores for each application, apply index and utilize predence to set final 6R decision
class calculate6rDecision:
    r6 = ['Rehost','Rearchitect','Rebuild','Replace','Retain','Retire']

    r_precendence = {
        "Rehost": 1,
        "Replace": 2,
        "Rearchitect": 3,
        "Rebuild": 4,
        "Retire": 5,
        "Retain": 6
    }

    def transform_scores(self, app_data, cms_score_map, all_sminimums, all_smaximums):
        map_keys = []
        default_keys = ['id','displayName','externalId','']
        i = 0

        ## create array for questions
        for a_key in cms_score_map.keys():
            if a_key not in default_keys:
                map_keys.append(a_key)

        all_app_scores = {}

        ## loop over all applications form outbound processor
        for app in app_data['content']:
            ## cannot get outbound processor to filter to tags, 
            for a_tag in app['data']['tags']:
                if a_tag['tagName'] == 'Candidate for Cloud Migration Assessment':
                    i += 1
                    ## initialize blank disctionaries to store scores
                    app_score, app_min, app_max = {}, {}, {}

                    ## initialize 6r scores to 0 so we can add scores iteratively 
                    for x_score in [app_score, app_min, app_max]:
                        for a_6r in self.r6:
                            x_score[a_6r] = 0

                    for cloud_measure in map_keys:
                        try:
                            for a_6r in self.r6:
                                app_score[a_6r] += int(cms_score_map[cloud_measure][app['data'][cloud_measure]][a_6r])
                                app_min[a_6r] += all_sminimums[a_6r][cloud_measure]
                                app_max[a_6r] += all_smaximums[a_6r][cloud_measure]

                        except KeyError:
                            pass 

                    all_app_scores[app['id']] = {}
                    all_app_scores[app['id']]['score'] = app_score
                    all_app_scores[app['id']]['sminimum'] = app_min
                    all_app_scores[app['id']]['smaximum'] = app_max

        logging.info(str(i)+' applications are a candidate for Cloud Migration Assessment.')
        return all_app_scores


    ## need to look into statistically sound method
    ## ((sum of application scores) + (minimum of questions answered)) / ((minimum of questions answered) - (maximum of questions answered))
    def apply_index(self,all_app_scores):
        all_indexed_scores = {}

        for app_id in all_app_scores:
            indexed_scores = {}
            indexed_scores['Rehost'] = round(((all_app_scores[app_id]['score']['Rehost'] + abs(all_app_scores[app_id]['sminimum']['Rehost'])) / abs((all_app_scores[app_id]['sminimum']['Rehost'] - all_app_scores[app_id]['smaximum']['Rehost']))) * 100)
            indexed_scores['Rearchitect'] = round(((all_app_scores[app_id]['score']['Rearchitect'] + abs(all_app_scores[app_id]['sminimum']['Rearchitect'])) / abs((all_app_scores[app_id]['sminimum']['Rearchitect'] - all_app_scores[app_id]['smaximum']['Rearchitect']))) * 100)
            indexed_scores['Rebuild'] = round(((all_app_scores[app_id]['score']['Rebuild'] + abs(all_app_scores[app_id]['sminimum']['Rebuild'])) / abs((all_app_scores[app_id]['sminimum']['Rebuild'] - all_app_scores[app_id]['smaximum']['Rebuild']))) * 100)
            indexed_scores['Replace'] = round(((all_app_scores[app_id]['score']['Replace'] + abs(all_app_scores[app_id]['sminimum']['Replace'])) / abs((all_app_scores[app_id]['sminimum']['Replace'] - all_app_scores[app_id]['smaximum']['Replace']))) * 100)
            indexed_scores['Retain'] = round(((all_app_scores[app_id]['score']['Retain'] + abs(all_app_scores[app_id]['sminimum']['Retain'])) / abs((all_app_scores[app_id]['sminimum']['Retain'] - all_app_scores[app_id]['smaximum']['Retain']))) * 100)
            indexed_scores['Retire'] = round(((all_app_scores[app_id]['score']['Retire'] + abs(all_app_scores[app_id]['sminimum']['Retire'])) / abs((all_app_scores[app_id]['sminimum']['Retire'] - all_app_scores[app_id]['smaximum']['Retain']))) * 100)

            all_indexed_scores[app_id] = indexed_scores
        
        return all_indexed_scores


    def max_6r(self,indexed_scores):
        app_decision = {}

        ## using indexed_scores
        for an_app in indexed_scores:
            score_ties = {}
            sorted_scores = dict(sorted(indexed_scores[an_app].items(), key=lambda item:item[1], reverse=True))
            ## loop over sorted scores, if max score is tied create new dict to use against precedence object
            for i, a_score in enumerate(sorted_scores):
                if i == 0:
                    app_max_score = a_score
                    score_ties[a_score] = self.r_precendence[a_score]
                elif a_score == app_max_score:
                    score_ties[a_score] = self.r_precendence[a_score]
                else:
                    break

            if len(score_ties) > 1:
                app_decision[an_app] = min(score_ties, key = score_ties.get) 
            else:
                app_decision[an_app] = app_max_score

            logging.info('Decision for '+an_app+' is '+app_decision[an_app])

        return app_decision


if __name__ == '__main__':
    logging.info('Begin run.')
    tld = transform_local_data()
    cms_score_map = tld.transform_schema_to_dict()
    all_sminimums, all_smaximums = tld.transform_schema_index()

    app_data = iAPI()

    cms_data = calculate6rDecision()
    app_scores = cms_data.transform_scores(app_data.ldif, cms_score_map, all_sminimums, all_smaximums)
    indexed_scores = cms_data.apply_index(app_scores)
    r_decision = cms_data.max_6r(indexed_scores)

    content = app_data.buildLdif(indexed_scores, r_decision)
    logging.info('Begin iAPI inbound run.')
    run = app_data.createInboundRun(content)
    app_data.startRun(run)
    run_status = app_data.status(run)
    while run_status['status'] in ['PENDING','IN_PROGRESS']:
        logging.info('iAPI inbound run status is: ' + str(run_status['status']))
        time.sleep(5)
        run_status = app_data.status(run)
    if run_status['status'] == 'FINISHED':
        logging.info('iAPI inbound run status is: ' + str(run_status['status']))

    logging.info('End run.')
    # with open('test_json.json','w') as g:
    #     g.write(str(all_app_data))
