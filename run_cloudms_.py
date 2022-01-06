import csv
import json
import requests
import re
import time
import pandas
import operator

class authWorkspace:
    api_token = ""

    auth_url = "https://eu-svc.leanix.net/services/mtm/v1/oauth2/token"
    # request_url = "https://eu.leanix.net/services/pathfinder/v1/graphql"
    request_url = "https://eu.leanix.net/services/integration-api/v1/"

    response = requests.post(auth_url, auth=('apitoken', api_token),data={'grant_type': 'client_credentials'})
    response.raise_for_status()

    access_token = response.json()['access_token']
    auth_header = 'Bearer ' + access_token
    header = {'Authorization': auth_header, 'Content-Type': 'application/json'}

class transform_local_data:
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

        for a_r6 in r6:
            mins = data.groupby(['Technical Name Question'])[a_r6].min()
            maxs = data.groupby(['Technical Name Question'])[a_r6].max()
            all_sminimums[a_r6] = mins.to_dict()
            all_smaximums[a_r6] = maxs.to_dict()

        return all_sminimums, all_smaximums



class get_cloudms_data():
    api_token = "5cSrH3sV5YWGTxnyTdN94jX4TSQjqrUGMA4vfOP5"
    auth_url = "https://eu-svc.leanix.net/services/mtm/v1/oauth2/token"
    # request_url = "https://zf.leanix.net//services/pathfinder/v1/graphql"
    request_url = "https://eu.leanix.net//services/pathfinder/v1/graphql"

    response = requests.post(auth_url, auth=('apitoken', api_token),data={'grant_type': 'client_credentials'})
    response.raise_for_status()
    access_token = response.json()['access_token']
    auth_header = 'Bearer ' + access_token
    header = {'Authorization': auth_header}

    r6 = ['Rehost','Rearchitect','Rebuild','Replace','Retain','Retire']

    r_precendence = {
        "Rehost": 1,
        "Rearchitect": 3,
        "Rebuild": 4,
        "Replace": 2,
        "Retain": 6,
        "Retire": 5
    }
        
    def run_graphql(self):
        # , tags: ["In scope for CVCS App Assessment"]
        # allFactSheets(first: 1, filter: {externalIds: ["externalId/{{lix_external_id}}"]})
        # allFactSheets(first: 10, filter: {facetFilters: [{facetKey: "FactSheetTypes", keys: ["Application"]}]})
        # allFactSheets(first: 10, filter: {quickSearch: "{{SEARCH_TERM}}", facetFilters: [{facetKey: "FactSheetTypes", keys: ["Application"]}]})
        # allFactSheets(first: 10, filter: {quickSearch: "APIS IQ-RM PRO 7.0", facetFilters: [{facetKey: "FactSheetTypes", keys: ["Application"]}]})
        # allFactSheets(filter: {facetFilters: [{facetKey: "FactSheetTypes", keys: ["Application"]}, {facetKey: "6f1036cd-91b7-429e-86a7-1cc8239a78d2", "operator": "OR", keys: ["8d390bef-1980-44b7-86ec-54912474170c"]}]}) {
        # allFactSheets(first: 1, filter: {quickSearch: \""""+input_app+"""\",facetFilters: [{facetKey: "FactSheetTypes", keys: ["Application"]}]}) {

        query = """
        {
            allFactSheets(filter: {ids: ["38c5757a-2222-4bcd-89ef-e6a4d364c13b","1ec06442-6327-46fd-be0e-57a1c86e9025","8034d96b-d40f-4423-a2ec-e7aaf84d8ab4","dc838233-addc-4ac2-812c-af3836ddc51c","672ab7f5-ce3c-4697-a153-fa73baa680ba","ec608daa-b438-4778-8ac2-9eb2e6464a68"]}) {
                    totalCount
                    edges {
                        node {
                            ... on Application {
                            id
                            displayName
                            externalId {
                                externalId
                            }
                            CMLifecycle
                            CMUpToDate
                            CMBusinessNeed
                            rangeOfUsers
                            CMBusinessBenefit
                            businessCriticality
                            CMTimeCritical
                            functionalSuitability
                            CRT_CloudVersion
                            CRT_CodeAccess
                            CMCloudReadyOrganization
                            CRT_RunningLicense
                            FIAR_API_Documentation
                            FIAR_API_CRUD
                            FIAR_API_CoreFunction
                            FIAR_Cloud_ScaleUp
                            CMResourceAvailability
                            CRT_Workload
                            CMMaintenanceEffort
                            CMChangeCloudNative
                            CRT_ComplexTechnical
                            CMInterfaces
                            technicalSuitability
                            CMSecurityRisks
                        }
                    }
                }
            }
        }
        """

        data = {"query" : query}
        json_data = json.dumps(data)
        response = requests.post(url=self.request_url, headers=self.header, data=json_data)
        response.raise_for_status()
        response = response.json()

        return response


    def transform_scores(self, app_data, cms_score_map, all_sminimums, all_smaximums):
        map_keys = []
        default_keys = ['id','displayName','externalId','']

        for a_key in cms_score_map.keys():
            if a_key not in default_keys:
                map_keys.append(a_key)

        all_app_scores = {}

        for app in app_data['data']['allFactSheets']['edges']:
            app_score, app_min, app_max = {}, {}, {}

            for x_score in [app_score, app_min, app_max]:
                for a_6r in self.r6:
                    x_score[a_6r] = 0

            for cloud_measure in map_keys:
                try:
                    for a_6r in self.r6:
                        app_score[a_6r] += int(cms_score_map[cloud_measure][app['node'][cloud_measure]][a_6r])
                        app_min[a_6r] += all_sminimums[a_6r][cloud_measure]
                        app_max[a_6r] += all_smaximums[a_6r][cloud_measure]

                except KeyError:
                    pass 

            all_app_scores[app['node']['id']] = {}
            all_app_scores[app['node']['id']]['score'] = app_score
            all_app_scores[app['node']['id']]['sminimum'] = app_min
            all_app_scores[app['node']['id']]['smaximum'] = app_max

        return all_app_scores


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
            app_decision[an_app] = max(indexed_scores[an_app], key = indexed_scores[an_app].get) 

        ## using app_scores
        # for an_app in indexed_scores:
        #     app_decision[an_app] = max(indexed_scores[an_app]['score'], key = indexed_scores[an_app]['score'].get) 

        with open('r_decision_20220106.json','w') as json_out:
            json_out.write(str(app_decision))

        return app_decision



class ldifWorkspace:
    ## Load inbound processor to variable
    with open("CloudMS_Outbound.json") as json_file:
        ldif_out_processor = json.load(json_file)
    with open("cms_inbound.json") as json_file2:
        ldif_in_processor = json.load(json_file2)

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


    ## Create connector processor if it does not exists
    def createProcessorRun(self, request_url, header, api_token):
        self.data = {
            "connectorType": "inboundFactSheet",
            "connectorId": "update-cms-data",
            "connectorVersion": "1.0.0",
            "processingDirection": "inbound",
            "processingMode": "partial",
            "credentials": {
                "apiToken": api_token
            },
            "processors": self.ldif_in_processor['processors']
        }
        self.data = json.dumps(self.data)
        new_data = re.sub(r': True', ': true', self.data)
        response = requests.put(url=request_url + "configurations/", headers=header, data=new_data)

    ## Create connector with LDIF content
    def createRun(self, content, request_url, header):
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
        
        self.response = requests.post(url=request_url + "synchronizationRuns/", headers=header, data=json.dumps(data))
        with open('test_ldif.json','w') as json_out2:
            json_out2.write(json.dumps(data))
        return (self.response.json())

    ## Process data / load into LeanIX workspace
    def startRun(self, run, request_url, header):
        response = requests.post(url=request_url + "synchronizationRuns/" + run["id"] + "/start?test=false", headers=header)




if __name__ == '__main__':
    wkspcAuth = authWorkspace()

    tld = transform_local_data()
    cms_score_map = tld.transform_schema_to_dict()
    all_sminimums, all_smaximums = tld.transform_schema_index()

    cms_data = get_cloudms_data()
    all_app_data = cms_data.run_graphql()
    app_scores = cms_data.transform_scores(all_app_data, cms_score_map, all_sminimums, all_smaximums)
    indexed_scores = cms_data.apply_index(app_scores)
    r_decision = cms_data.max_6r(indexed_scores)

    iAPI = ldifWorkspace()
    content = iAPI.buildLdif(app_scores, r_decision)
    iAPI.createProcessorRun(wkspcAuth.request_url, wkspcAuth.header, wkspcAuth.api_token)
    run = iAPI.createRun(content, wkspcAuth.request_url, wkspcAuth.header)
    iAPI.startRun(run, wkspcAuth.request_url, wkspcAuth.header)
