"""
Created by Takahiro Kajino
Creation Date: May 15, 2018
Changed Date: Febrary 22, 2019

Lambda function that would be triggered from CloudWatch Events.
This function is for starting the EC2.

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

    instance_id = os.environ['INSTANCE_ID']

    # Start the instance
    start_ec2_instances(instance_id)
    custom_print('[FINISH] Finished running script')

    return 0

def start_ec2_instances(instance_id):
    """
    Start all instances and wait until they are started.
    NOTE: the wait method can only wait for one instance at a time
    This script is not expected to start multiple instances at once
    therefore will not loop all instances to wait.
    """
    try:
        custom_print('[INFO] Starting Instance: ' + str(instance_id))
        region = os.environ['AWS_REGION']
        ec2_client = boto3.client('ec2', region_name=region)
        ec2_resource = boto3.resource('ec2').Instance(instance_id)

        status_response = ec2_client.describe_instances(instance_ids=[instance_id])

        if status_response['Reservations'][0]['Instances'][0]['State']['Name'] == "running":
            custom_print('[INFO] Instance is already running: ' + str(instance_id))
        else:
            custom_print('[INFO] Instance was not running so called to start: ' + str(instance_id))
            response = ec2_client.start_instances(instance_ids=[instance_id])
            custom_print(response)
            ec2_resource.wait_until_running()
            custom_print('[INFO] Waiting for Instance to be ready: ' + str(instance_id))
            cont = 1
            total = 0

            while cont:
                status_response = ec2_client.describe_instance_status(instance_ids=[instance_id])
                if(status_response['InstanceStatuses'][0]['InstanceStatus']['Status'] == "ok" and status_response['InstanceStatuses'][0]['SystemStatus']['Status'] == "ok"):
                    cont = 0
                else:
                    time.sleep(10)
                    total += 10
            custom_print('[INFO] Successfully Started Instance: ' + str(instance_id) + ' wait time was roughly: ' + str(total) + 'seconds.')

    except Exception as error:
        custom_print('[ERROR] ' + str(error))
        call_sns(str(error))
        return error


def call_sns(msg):
    """
    Nortify via E-mail if Exception arised.
    """
    topic_arn = os.environ["TOPIC_ARN"]
    subject = os.environ["SUBJECT"]
    client = boto3.client("sns")
    request = {
        'TopicArn': topic_arn,
        'Message': msg,
        'Subject': subject
        }

    response = client.publish(**request)

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
