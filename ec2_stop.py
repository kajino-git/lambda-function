"""
Created by Takahiro Kajino
Creation Date: May 15, 2018
Changed Date: Febrary 22, 2019

Lambda function that would be triggered from CloudWatch Events.
This function is for stopping the EC2 which sorts files to depending on the enviornment and its purpose is for
cost efficient reasoning.

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

    # Stop the instance
    stop_ec2_instances(instance_id)

    custom_print('[FINISH] Finished running script')

    return 0

def stop_ec2_instances(instance_id):
    """
    Stop all instances and wait until they are stopped.
    NOTE: the wait method can only wait for one instance at a time
    This script is not expected to stop multiple instances at once
    therefore will not loop all instances to wait.
    """
    try:
        region = os.environ['AWS_REGION']
        custom_print('[INFO] Stopping Instance: ' + str(instance_id))
        ec2_client = boto3.client('ec2', region_name=region)
        ec2_resource = boto3.resource('ec2').Instance(instance_id)
        response = ec2_client.stop_instances(instance_ids=[instance_id])
        custom_print(response)
        ec2_resource.wait_until_stopped()
        custom_print('[INFO] Successfully Called to Stop Instance: ' + str(instance_id))

    except Exception as error:
        custom_print('[ERROR] ' + str(error))
        call_sns(str(error))
        return 2

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
