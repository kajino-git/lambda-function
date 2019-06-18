"""
Created by Takahiro Kajino
Creation Date: August 22, 2018
Changed Date: Febrary 30, 2019

Lambda function that would be triggered from CloudWatch Events and CodeCommit.
This function is for nortificating Chatwork.

Change Detail: Change python version from 2.7 to 3.7 and local variables to environment variables
"""

import json
import os
import time

from botocore.vendored import requests
import boto3

def lambda_handler(event, context):
    """
    lambda main
    """
    custom_print('[START] Starting Script')
    custom_print(event)

    # Developers Env
    url = os.environ['URL']
    chatwork_token = os.environ['TOKEN']
    chatwork_room = os.environ['ROOM']

    chatwork_url = '{0}/rooms/{1}/messages'.format(url, chatwork_room)
    headers = {'X-ChatWorkToken': chatwork_token}

    # deploy nortification
    found = 0
    # deployment trigger
    for key in event:
        if key == 'CodePipeline.job':
            found = 1

    # if key is found, trigger is from CodePipeline
    if found:
        check_enviornment(chatwork_url, headers, event)

    custom_print('[FINISH] Finished running script')
    return 0

def check_enviornment(chatwork_url, headers, event):
    """
    Notify deployment which environment is deployed and succsess or failure.
    Staging, Production, Approval.

    Parameters
    chatwork_url: str
    headers: dict {TOKEN}
    event: dict {codepipeline event}
    """
    try:
        env = event['CodePipeline.job']['data']['actionConfiguration']['configuration']['UserParameters']
        pipelineclient = boto3.client('codepipeline')
        job_id = event['CodePipeline.job']['id']

        # For Developers enviornment
        if env == 'Dev':
            custom_print('[INFO] Retrieving CodeDeploy Status for ' + str(env) + ' enviornment')
            cont = 1
            total = 0

            while cont:

                web_response = get_codedeploy_details(os.environ['APP'], os.environ['GROUP_DEV'])
                web_status = web_response['deploymentGroupInfo']['lastAttemptedDeployment']['status']
                web_id = web_response['deploymentGroupInfo']['lastAttemptedDeployment']['deploymentId']

                # If Deployment Successful, report as success
                if web_status == 'Succeeded':
                    custom_print('[INFO] Deployment was successful for ' + str(env) + ' enviornment')

                    cont = 0

                    # Send notification to Typetalk
                    requests.post(chatwork_url, headers=headers, params={
                        'body': '開発環境への反映が終わりました。問題ありませんでした。' +
                        '\nBATCHサーバ: ' + web_status + ' ('+ web_id + ')'
                        })

                    # Tell CodePipeline success
                    response = pipelineclient.put_job_success_result(jobId=job_id)
                    custom_print('[INFO] Sent CodePipeline success result')

                else:
                    # Increase the timer
                    time.sleep(15)
                    total += 15

                    #if more than 240 seconds then fail as timeout
                    if total > 240:
                        # Send notification to Typetalk
                        requests.post(chatwork_url, headers=headers, params={
                            'body': '開発環境への自動デプロイが失敗しました。' +
                            '\nWEBサーバ: ' + web_status  + ' ('+ web_id + ')'
                        })

                        # Tell CodePipeline Fail
                        response = pipelineclient.put_job_failure_result(jobId=job_id, failureDetails={
                            'message': 'Deployment has failed because it took more than 4 minutes to finish', 'type': 'JobFailed'
                        })
                        custom_print('[WARNING] Sent CodePipeline fail result')
                        return 1

        # For Production Result
        elif env == 'Prod':

            custom_print('[INFO] Retrieving CodeDeploy Status for ' + str(env) + ' enviornment')
            cont = 1
            total = 0

            while cont:

                web_response = get_codedeploy_details(os.environ['APP'], os.environ['GROUP_PROD'])
                web_status = web_response['deploymentGroupInfo']['lastAttemptedDeployment']['status']
                web_id = web_response['deploymentGroupInfo']['lastAttemptedDeployment']['deploymentId']

                # If Deployment Successful, report as success
                if web_status == 'Succeeded':
                    custom_print('[INFO] Deployment was successful for ' + str(env) + ' enviornment')

                    cont = 0

                    # Send notification to Typetalk
                    requests.post(chatwork_url, headers=headers, params={
                        'body': '本番環境への反映が終わりました。問題ありませんでした。' +
                        '\nBATCHサーバ: ' + web_status + ' ('+ web_id + ')'
                    })

                    # Tell CodePipeline success
                    response = pipelineclient.put_job_success_result(jobId=job_id)
                    custom_print('[INFO] Sent CodePipeline success result')

                else:
                    # Increase the timer
                    time.sleep(15)
                    total += 15

                    #if more than 240 seconds then fail as timeout
                    if total > 240:
                        # Send notification to Typetalk
                        requests.post(chatwork_url, headers=headers, params={
                            'body': '本番環境への自動デプロイが失敗しました。' +
                            '\nWEBサーバ: ' + web_status  + ' ('+ web_id + ')'
                        })

                        # Tell CodePipeline Fail
                        response = pipelineclient.put_job_failure_result(jobId=job_id, failureDetails={
                            'message': 'Deployment has failed because it took more than 4 minutes to finish', 'type': 'JobFailed'
                        })
                        custom_print('[WARNING] Sent CodePipeline fail result')
                        return 1

        # For Production Trigger
        elif env == 'PROD_START':
            response = pipelineclient.get_pipeline_state(name=os.environ['PIPELINE'])
            approval_stage = response['stageStates'][3]['actionStates'][0]['latestExecution']

            user = approval_stage['lastUpdatedBy']
            user = user.split(":")

            summary = approval_stage['summary']

            custom_print('[INFO] ' + str(user[5]) + ' has pushed to prod enviornment')
            requests.post(chatwork_url, headers=headers, params={
                'body': str(user[5]) + '　が本番環境への承認を行いました。:runner: :dash:' +
                '\n\nメッセージ内容: ' + str(summary)
            })

            response = pipelineclient.put_job_success_result(jobId=job_id)
            custom_print('[INFO] Sent CodePipeline success result')

    except Exception as error:
        response = pipelineclient.put_job_failure_result(jobId=job_id, failureDetails={'message': error, 'type': 'JobFailed'})
        custom_print('[INFO] Sent CodePipeline fail result\n' + str(error))
        requests.post(chatwork_url, headers=headers, params={
            'body': '自動デプロイが失敗しました。' +
            '\n\nエラーメッセージ内容: ' + str(error)
        })
        custom_print(response)
        return 1

def get_codedeploy_details(app_name, group_name):
    """
    Retrieve CodeDeploy status.

    Parameters
    app_name: str codedeploy application name
    group_name: str codedeploy deploy group name
    """
    try:
        codedeploy_client = boto3.client('codedeploy')

        return codedeploy_client.get_deployment_group(
            applicationName=app_name,
            deploymenGroupName=group_name
        )

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
