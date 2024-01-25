from datetime import datetime
from datetime import timedelta
import json
import logging as log
import sys
import time
import os

from airflow import models
from airflow.operators.python_operator import PythonOperator
from airflow.utils import dates
from google.cloud import bigquery
from google.api_core.exceptions import BadRequest

import requests as r
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

from parse_ada_data import parse_api_data

from commons.vault import Vault


conf = json.loads(models.Variable.get("ada_data_etl_config"))
conf.update({"ada_api_key": (models.Variable.get("ada_api_key", None))})

default_dag_args = {
    "depends_on_past": False,
    "email_on_failure": conf["email_on_failure"],
    "email_on_retry": False,
    "email": conf["notification_email"],
    "retries": 0,
    "retry_delay": timedelta(minutes=5),
}


def parse_iso_string(date_time_str):
    """
    parse_iso_string(date_time_str)

    Parses a string in iso format into a DateTime object.

    Parameters
    ----------
    date_time_str : str
        A datetime string in the format of "%Y-%m-%dT%H:%M:%S.%f" or "%Y-%m-%dT%H:%M:%S".

    Returns
    -------
    datetime

    Notes
    -----
    In Python>==3.7, the datetime library has the function datetime.fromisoformat(date_time_str),
    which parses a string the follows any ISO compliant datetime format. Since our cloud composer
    instance uses Python 3.6, I wrote this custom function that parses all of the possible formats
    I've seen when running this pipeline.
    """

    # TODO: When Airflow uses Python >==3.7, replace with datetime.fromisoformat(date_time_str)
    stripped_dt_string = date_time_str.split("+")[0]
    iso_formats = ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S")
    for fmt in iso_formats:
        try:
            return datetime.strptime(stripped_dt_string, fmt)
        except ValueError:
            pass
    raise ValueError(f'Issue with datetime {stripped_dt_string}: No valid date format found')


def convert_to_iso_string(datetime_obj):
    """
    convert_to_iso_string(datetime_obj)

    Converts a DateTime object into iso format.

    Parameters
    ----------
    datetime_obj : datetime

    Returns
    -------
    str
        A string in iso format: "%Y-%m-%dT%H:%M:%S.%f"

    Notes
    -----
    In Python>==3.7, the datetime library has the function datetime.isoformat(), which converts a
    datetime into a string in ISO compliant format. Since our cloud composer instance uses Python
    3.6, I wrote this custom function that parses a DateTime into iso format.
    """

    # TODO: When Airflow uses Python >==3.7, replace with datetime.isoformat()
    iso_format = "%Y-%m-%dT%H:%M:%S.%f"
    return datetime_obj.strftime(iso_format)


def query_ada_source(url):
    """
    query_ada_source(url)

    Queries the chat source API.

    Parameters
    ----------
    url : str
        A string containing the url that the function will be sending the request to.

    Returns
    -------
    requests.Response
        The response from the api request.
    """

    headers = {'Authorization': f"Bearer {conf.get('ada_api_key')}"}
    retry_strategy = Retry(
        total=5,
        status_forcelist=[429, 500, 502, 503, 504],
        method_whitelist=["GET"],
        backoff_factor=2,
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    http = r.Session()
    http.mount("https://", adapter)

    return http.get(url, headers=headers, timeout=60)


def flatten_2d_array(arr):
    """
    flatten_2d_array(arr)

    Flattens a 2d array of object into a 1d array.

    Parameters
    ----------
    arr : list of list of objects
        A 2-dimensional array containing any objects.

    Returns
    -------
    list of objects
        The flattened list of objects.
    """

    return [datapoint for row in arr for datapoint in row]


def fetch_api_data(endpoint_url, start_time, end_time, api_type):
    """
    fetch_api_data(endpoint_url, start_time, end_time, api_type)

    Gets data from either of the API endpoints between two given times.

    Parameters
    ----------
    endpoint_url : str
        The base url that the function will be sending the request to.
    start_time : datetime
        The datetime that is the start of the range the api queries.
    end_time : datetime
        The datetime that is the end of the range the api queries.
    api_type : str
        The type of data the function will be fetching. Currently can be either `conversations` or
        `messages`.

    Returns
    -------
    list of dicts
        A list containing all of the data in the datetime range queried.
    """

    valid_response_data = []
    # TODO: Once Airflow is updated to Python >==3.7, replace with start_time.isoformat()
    str_start_time = convert_to_iso_string(start_time).replace(":", "%3A")
    str_end_time = convert_to_iso_string(end_time).replace(":", "%3A")
    uri = f"/data_api/v1/{api_type}?created_since={str_start_time}&created_to={str_end_time}"
    num_of_pages = 0
    log.info(
        "Time slice: %s to %s",
        str_start_time,
        str_end_time)
    while True:
        num_of_pages += 1
        log.info("Fetching data. URI: %s.", uri)
        response = query_ada_source(endpoint_url + uri)
        if response.status_code == 200:
            payload = response.json()
            valid_response_data.append(payload["data"])
        else:
            log.error(response.text)
            raise ValueError(f'Error response received: {response.status_code}.')

        if payload["next_page_uri"]:
            uri = payload["next_page_uri"]
            time.sleep(1)
        else:
            log.info("Done fetching this interval's API data. %s pages requested.", num_of_pages)
            flattened_conversations = flatten_2d_array(valid_response_data)
            time.sleep(1)
            return flattened_conversations


def get_bq_client_from_vault():
    """
    get_bq_client_from_vault()

    Returns a bigquery client with credentials pulled from the Loblaws Vault.

    Returns
    ----------
    client : google.cloud.bigquery.Client()
        The BigQuery client that allows the function to update the tables.
    """
    vault_client = Vault(
        temp_path='/tmp',
        role=conf['vault_gcp_role'],
        address=os.environ.get("VAULT_ADDR"),
        secret_path='datascience',
        service_account=conf["composer_service_account"],
        jwt_time_to_live=60
    )
    log.info('Getting secret from vault ...')
    creds = vault_client.get_secret_from_vault(conf['ada_to_bq_sa_vault_key'])
    with open('key-file.json', 'w') as key_file:
        key_file.write(json.dumps(creds))
    log.info('Generating BQ client with special SA ...')
    client = bigquery.Client.from_service_account_json(json_credentials_path='key-file.json',
                                                       project=conf['bq_project'])
    log.info('BQ client with special SA generated.')
    os.remove('key-file.json')
    return client


def load_record_to_bq(record, table_type, client, start_time):
    """
    load_record_to_bq(record, table_type, client, start_time)

    Sends records to BigQuery. Data is loaded into a single day partition of the BQ table.

    Parameters
    ----------
    record : list of dicts
        The list of JSON records to send to BigQuery.
    table_type : str
        The name of the table being sent to. Currently can be `messages` or `conversations`.
    client : google.cloud.bigquery.Client()
        The BigQuery client that allows the function to update the tables.
    start_time : datetime
        The start date of the data. Used to refer to a specific partition.
    """

    bq_project = conf.get("bq_project")
    dataset = conf.get("dataset")
    partition_date_str = start_time.strftime("%Y%m%d")
    table_id = f"{bq_project}.{dataset}.{table_type}${partition_date_str}"
    # Ensures idempotence by deleting old partitions before write
    job_config = bigquery.job.LoadJobConfig(**{"write_disposition": "WRITE_TRUNCATE"})
    log.info("Sending data to bigquery table %s.", table_id)
    try:
        client.load_table_from_json(record, table_id, job_config=job_config).result()
    except BadRequest as err:
        log.debug("BadRequest error: %s", str(err))
        log.debug(repr(record))
        raise err
    log.info("Data load to BigQuery complete.")


def run_ada_to_bq_etl(**kwargs):
    """
    run_ada_to_bq_etl(**kwargs)

    The controller function to fetch data from Ada and store in BigQuery. Run by a PythonOperator
    that takes in the `api_type` from kwargs to know which endpoint it is hitting.

    Parameters
    ----------
    **kwargs : dicts
        Allows the function to take in two important variables through `templates_dict`:

        execution_date : str
            A string containing the execution date in iso format.

        api_type : str
            A string representing the name/type of the api being hit. Currently this type can
            either be "messages" or "conversations".
    """

    python_version = '.'.join(map(str, sys.version_info))
    log.info("Python version %s is in use. datetime.fromisoformat requires >==3.7", python_version)
    # Variable setup
    endpoint_url = conf.get("endpoint_url")
    # TODO: When Airflow uses Python >==3.7, replace parse_iso_string with
    # datetime.fromisoformat(date_time_str).
    # Data is queried from only the day before the run date of the DAG, from midnight to midnight.
    end_time = parse_iso_string(kwargs
                                .get("templates_dict")
                                .get("execution_date")).replace(hour=0,
                                                                minute=0,
                                                                second=0,
                                                                microsecond=0
                                                                )
    start_time = end_time - timedelta(days=1)
    end_time = end_time - timedelta(microseconds=1)
    api_type = kwargs.get("templates_dict").get("api_type")
    bq_client = get_bq_client_from_vault()
    # Run functions
    log.info("Starting requests for data from endpoint '%s'.", endpoint_url)
    valid_request_data = fetch_api_data(endpoint_url, start_time, end_time, api_type)
    parsed_data_dicts = parse_api_data(valid_request_data, api_type, conf.get("bq_project"))
    load_record_to_bq(parsed_data_dicts, api_type, bq_client, start_time)


with models.DAG(
        "ada_chatbot_data_etl",
        schedule_interval=conf.get('schedule_interval'),
        default_args=default_dag_args,
        start_date=dates.days_ago(60),
        catchup=True,
        max_active_runs=1) as dag:

    run_ada_messages_etl = PythonOperator(
        task_id='run_ada_messages_etl',
        python_callable=run_ada_to_bq_etl,
        provide_context=True,
        templates_dict={'execution_date': '{{ ts }}',
                        "api_type": "messages",
                        },
    )
    run_ada_conversations_etl = PythonOperator(
        task_id='run_ada_conversations_etl',
        python_callable=run_ada_to_bq_etl,
        provide_context=True,
        templates_dict={'execution_date': '{{ ts }}',
                        "api_type": "conversations",
                        },
    )
