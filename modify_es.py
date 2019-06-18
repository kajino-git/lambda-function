"""
Created By: takahiro kajino
Creation Date: January 10, 2018
Changed Date: Febrary 22, 2019

Lambda function that would be triggered from CloudWatch Events
and modify Elasticsearch instance via cron in UTC time.

Change Detail: Change python version from 2.7 to 3.7 and local variables to environment variables
"""

import json
import os
import time

import boto3

def lambda_handler(event, context):
    """
    lambda main
    """
    custom_print('[START] Starting Script')

    try:
        region = os.environ['AWS_REGION']
        env = os.environ['ES_INSTANCE_NAME']

        # Get Elasticsearch domain
        es_domain_list = get_es_domain(region, env)

        # Modify the Elasticsearch Instance Type
        modify_es_instance(region, es_domain_list)

    except Exception as error:
        custom_print('[ERROR] ' + str(error))
        return 2

    custom_print('[FINISH] Finished running script')

    return 0

def get_es_domain(region, env):
    """
    Get all the Elasticsearch Domain names that is associated with the term given by the env.
    Then create an array to be associated for the modification.

    Parameters
    region: str
    env: str
    """
    try:

        es_client = boto3.client('es', region_name=region)

        custom_print('[INFO] Retrieving list of es domains for ' + str(env))
        response = es_client.list_domain_names()
        es_domain_list = []
        for key in response['DomainNames']:
            if env in key['DomainName']:
                es_domain_name = key['DomainName']
                es_domain_list.append(es_domain_name)
        custom_print('[INFO] Found ' + str(es_domain_list))

        return es_domain_list

    except Exception as error:
        custom_print('[ERROR] ' + str(error))
        return 2

def modify_es_instance(region, es_domain_list):
    """
    Modify the instance depending on the condition value.
    NOTE: The instance value is hardcoded and could be changed by reading
    the file information but this script doesn't expect to change between
    the 2 instance type.

    Parameters
    region: str
    es_domain_list: list [domain]
    -----------
    """
    try:
        es_client = boto3.client('es', region_name=region)

        for es_domain in es_domain_list:
            es_domain_name = es_domain
            es_instance_type = os.environ['INSTANCE_TYPE']

            response = es_client.describe_elasticsearch_domain(
                DomainName=es_domain_name
            )
            custom_print('[INFO] Before Modification Detail of ' + str(es_domain_name))
            custom_print(response)

            custom_print('[INFO] Modifying Elasticsearch: ' + str(es_domain_name) + ' to ' + str(es_instance_type))
            response = es_client.update_elasticsearch_domain_config(
                DomainName=es_domain_name,
                ElasticsearchClusterConfig={'InstanceType':es_instance_type}
            )
            custom_print(response)
            custom_print('[INFO] Sucessfully called to modify Elasticsearch: ' + str(es_domain_name) + ' to ' + str(es_instance_type))

    except Exception as error:
        custom_print('[ERROR] ' + str(error))
        return 2

def custom_print(msg):
    """
    AWS Lambda does not put logs in continous matter.
    If you want to have a continous log, you need to create
    your own log and put it inside that log.
    Also, this will determine is the response is JSON
    and print it in JSON format for easier read.

    Parameters
    msg: str
    """
    # If the message is a json format, print the result in json
    # to make it easier to read.
    if isinstance(msg, str):
        msg = msg
        print(msg)
    else:
        msgjson = json.dumps(msg, sort_keys=True, default=str)
        msg = '[RESPONSE]\n' + msgjson
        print('[RESPONSE] ' + msgjson)
    # Time since EPOCH
    time_stamp_milli = int(round(time.time() * 1000))

    # Initialize
    log_group_name = os.environ['CUSTOM_LOG_GROUP']
    log_stream_name = os.environ['CUSTOM_LOG_STREAM']
    region = os.environ['AWS_REGION']
    log_client = boto3.client('logs', region_name=region)

    # Obtain the response and check if token exists
    log_response = log_client.describe_log_streams(
        logGroupName=log_group_name,
        logStreamNamePrefix=log_stream_name)['logStreams'][0]
    found = 0
    for key in log_response.keys():
        if key == 'uploadSequenceToken':
            found = 1

    # If token does exists, the log already has entry; append to the log with token
    if found:
        upload_token = log_client.describe_log_streams(
            logGroupName=log_group_name,
            logStreamNamePrefix=log_stream_name)['logStreams'][0]['uploadSequenceToken']
        response = log_client.put_log_events(
            logGroupName=log_group_name,
            logStreamName=log_stream_name,
            logEvents=[
                {
                    'timestamp': time_stamp_milli,
                    'message': msg
                }
            ],
            sequenceToken=upload_token
        )
    # This log entry is absolutely new, therefore no need of token
    else:
        response = log_client.put_log_events(
            logGroupName=log_group_name,
            logStreamName=log_stream_name,
            logEvents=[
                {
                    'timestamp': time_stamp_milli,
                    'message': msg
                }
            ]
        )
