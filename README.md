# Cloud Migration Strategy

## Requirements
- python 3.x  
- pip 3.x
- python packages
  - requests 2.x
  - pandas 1.x


## Abstract
Customers of LeanIX who are approaching cloud migration often wish to do so in a systemic way.  Utilizing the 6R approach, including application scoring and indexing, customers can utilize the integration API to programmitcally apply a customized solution.

The purpose of this script is to extract answers to cloud migration questions from applications in a LeanIX workspace, calculate the 6R decision for each candidate application, and push the decision (along with each 6R score) back to the workspace.  All inbound and outbound integration API processors are also included.

## run_cloudms.py

This code utilizes the integration API and 6R approach to cloud migration.  The API documentation can be found [here](https://docs.leanix.net/docs/integration-api). 

Ensure the API token for the workspace is stored in a key vault; insert the key vault code into the authWorkspace class and return the token to api_token.

The iAPI class inherits the authorization variables from the authWorkspace class.First, it utilizes an outbound processor to extract data from the workspace.

Scores are calculated using the schema in the iAPI processor (currently a csv).  The index applied to the scores is:

>((sum of application scores) + (minimum of questions answered)) / ((minimum of questions answered) - (maximum of questions answered))


After the scores, indexed scores and decision are calculated, an inbound processor is utilized to put the data back into the workspace, on the application factsheets. 

```
python3 run_cloudms.py
```
