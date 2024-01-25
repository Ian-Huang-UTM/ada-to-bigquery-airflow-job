# Ada Chatbot to BigQuery Airflow DAG project

This project reads data from the Ada chatbot endpoint to our own storage in BigQuery. This read occurs in a batch process once a day around 4 am EST. This will allow our teams to use NLP on the data and analyze it to identify common user issues.

## Data Types to be extracted

* [Messages](https://console.cloud.google.com/bigquery?ws=!1m5!1m4!4m3!1sds-bi-analytics-dev!2sada_chatbot!3smessages&project=ds-services-dev&d=ada_chatbot&p=ds-bi-analytics-dev&t=messages&page=table)
* [Conversations](https://console.cloud.google.com/bigquery?ws=!1m5!1m4!4m3!1sds-bi-analytics-dev!2sada_chatbot!3sconversations&project=ds-services-dev&d=ada_chatbot&p=ds-bi-analytics-dev&t=conversations&page=table)

## API Docs

* Not publicly available yet!

## API Key

The Data API key for our chatbot is stored in Google Secret Manager:

* [dev secret](https://console.cloud.google.com/security/secret-manager/secret/airflow-variables-ada_api_key/versions?project=ds-services-dev)
* [prod secret](https://console.cloud.google.com/security/secret-manager/secret/airflow-variables-ada_api_key/versions?project=ds-services-prod&folder=&organizationId=)

## API Limits

The API can currently only support 1 request per api key per second, which means we have to space out our queries artificially by at least one second.
