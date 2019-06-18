"""
Created by Takahiro Kajino
Creation Date: August 30, 2018
Changed Date: Febrary 22, 2019

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

    # Chatwork initialize
    url = os.environ['CHAT_URL']
    chatwork_token = os.environ['TOKEN']
    chatwork_room = os.environ['ROOM']

    chatwork_url = '{0}/rooms/{1}/messages'.format(url, chatwork_room)
    headers = {'X-ChatWorkToken': chatwork_token}

    # notify codecommit push nortification
    found = 0

    # Determine if source is Pull Request trigger or deployment trigger
    for key in event:
        if key == 'source':
            found = 1

    if found:
        pull_request_env(event, chatwork_url, headers)

    # Was deployment trigger
    else:
        user = event['Records'][0]['userIdentityARN']
        user = user.split(":")

        source = event['Records'][0]['eventSourceARN']
        source = source.split(":")

        commit_id = event['Records'][0]['codecommit']['references'][0]['commit']
        commit_detail = retrieve_commit(commit_id, source[5])

        branch = event['Records'][0]['codecommit']['references'][0]['ref']
        branch_name = branch.split("/")[2]

        custom_print('[INFO] ' + str(user[5]) + ' has pushed to ' + str(source[5]) + ' repository ' + branch_name + " branch ")
        requests.post(chatwork_url, headers=headers, params={
            'body': branch_name + " ブランチに"
            '\n' + str(user[5]) + ' が自動デプロイを実行しました。' +
            '\n' + str(source[5]) + ' から反映中ですので少々お待ちください。' +
            '\n\n' + 'デプロイ内容: \n' + str(commit_detail['commit']['message'])
        })

    custom_print('[FINISH] Finished running script')
    return 0

def pull_request_env(event, chatwork_url, headers):
    """
    Notify pull request nortification in CodeCommit.
    Create, Close without merge, Merge, Push, Comment.

    Parameters
    chatwork_url: str
    headers: dict {TOKEN}
    """
    try:
        user = event['detail']['callerUserArn']
        user = user.split(':')

        detail_type = event['detail-type']

        pull_event = event['detail']['event']

        base_url = os.environ['BASE_URL']

        # Pull Request General
        if detail_type == "CodeCommit Pull Request State Change":

            pull_id = event['detail']['pullRequestId']
            pull_url = base_url + "pull-requests/" + pull_id + "/commits?region=ap-northeast-1"

            # If description is found
            found = 0
            for key in event['detail']:
                if key == 'description':
                    found = 1
            if found:
                pull_description = event['detail']['description']
            else:
                pull_description = "（未入力）"

            destination_ref = event['detail']['destinationReference']
            destination_ref = destination_ref.split('/')

            source_ref = event['detail']['sourceReference']
            source_ref = source_ref.split('/')

            pull_title = event['detail']['title']

            # New pull request was created
            if pull_event == 'pullRequestCreated':
                custom_print('[INFO] ' + str(user[5]) + ' has created a new pull request. ID: ' + str(pull_id))
                requests.post(chatwork_url, headers=headers, params={
                    'body': str(user[5]) + ' が新規にプルリク (' + str(pull_id) + ') を作成しました。' +
                    '\n\nタイトル: ' + str(pull_title) +
                    '\n内容: ' + str(pull_description) +
                    '\nブランチ: ' + str(source_ref[2]) + ' → '  + str(destination_ref[2]) +
                    '\n\n' + pull_url
                })
            # Pull was closed without merging
            elif pull_event == 'pullRequestStatusChanged':
                custom_print('[INFO] ' + str(user[5]) + ' has closed without merging a pull request. ID: ' + str(pull_id))
                requests.post(chatwork_url, headers=headers, params={
                    'body': str(user[5]) + ' がマージせずにプルリク (' + str(pull_id) + ') をクローズしました。' +
                    '\n\nタイトル: ' + str(pull_title) +
                    '\n内容: ' + str(pull_description) +
                    '\nブランチ: ' + str(source_ref[2]) + ' → '  + str(destination_ref[2]) +
                    '\n\n' + pull_url
                })
            # Closed a pull with merging
            elif pull_event == 'pullRequestMergeStatusUpdated':
                custom_print('[INFO] ' + str(user[5]) + ' has merged a pull request. ID: ' + str(pull_id))
                requests.post(chatwork_url, headers=headers, params={
                    'body': str(user[5]) + ' がマージを行いプルリク (' + str(pull_id) + ') をクローズしました。' +
                    '\n\nタイトル: ' + str(pull_title) +
                    '\n内容: ' + str(pull_description) +
                    '\nブランチ: ' + str(source_ref[2]) + ' → '  + str(destination_ref[2]) +
                    '\n\n' + pull_url
                })
            # Pushed to non master branch
            elif pull_event == 'pullRequestSourceBranchUpdated':
                commit_id = event['detail']['sourceCommit']
                custom_print('[INFO] ' + str(user[5]) + ' has pushed to non master branch. ID: ' + str(pull_id))
                requests.post(chatwork_url, headers=headers, params={
                    'body': str(user[5]) + ' が ' + str(source_ref[2])+' のブランチにコミットしました。プルリク (' + str(pull_id) + ')' +
                    '\n\nタイトル: ' + str(pull_title) +
                    '\n内容: ' + str(pull_description) +
                    '\nブランチ: ' + str(source_ref[2]) + ' → '  + str(destination_ref[2]) +
                    '\nコミットID: ' +str(commit_id) +
                    '\n\n' + pull_url
                })
            # Other events detected not sent
            else:
                custom_print('[INFO] No notification sent. Pull Event: ' + str(pull_event) + ' PullID: ' + str(pull_id))

        # Pull Request Comment
        elif detail_type == "CodeCommit Comment on Pull Request":

            comment_id = event['detail']['commentId']

            pull_id = event['detail']['pullRequestId']
            pull_url = base_url + "pull-requests/" + pull_id + "/activity?region=ap-northeast-1#" + comment_id

            comment_response = retrieve_comment(comment_id)

            # New comments added
            if pull_event == 'commentOnPullRequestCreated':
                custom_print('[INFO] comment added to PullID: ' + str(pull_id))
                requests.post(chatwork_url, headers=headers, params={
                    'body': str(user[5]) + ' がプルリク (' + str(pull_id) + ') にコメントしました。' +
                    '\n\nコメント:\n' + comment_response['comment']['content'] +
                    '\n\n' + pull_url
                })

            else:
                custom_print('[INFO] No notification sent. Pull Event: ' + str(pull_event) + ' PullID: ' + str(pull_id))

        elif detail_type == "CodeCommit Comment on Commit":

            comment_id = event['detail']['commentId']
            after_commit_id = event['detail']['afterCommitId']

            pull_url = base_url + "commit/" + after_commit_id + "?region=ap-northeast-1#" +comment_id

            comment_response = retrieve_comment(comment_id)

            custom_print('[INFO] comment added')
            requests.post(chatwork_url, headers=headers, params={
                'body': str(user[5]) + ' がコミットにコメントしました。' +
                '\n\nコミットID: ' + after_commit_id +
                '\nコメント:\n' + comment_response['comment']['content'] +
                '\n\n' + pull_url
            })

        # Other events detected not sent
        else:
            custom_print('[INFO] No notification sent. Pull Event: ' + str(pull_event) + ' PullID: ' + str(pull_id))

    except Exception as error:
        custom_print('[ERROR] ' + str(error))
        return 2


def retrieve_commit(commit_id, source):
    """
    Retrieve commit description.

    Parameters
    commit_id: str
    source: str "Source ARN"
    """
    try:
        cc_client = boto3.client('codecommit')
        response = cc_client.get_commit(
            commitId=commit_id,
            repositoryName=source
        )
        return response
    except Exception as error:
        custom_print('[ERROR] ' + str(error))
        return 2


def retrieve_comment(comment_id):
    """
    Retrieve comment description

    Parameters
    comment_id: str
    """
    try:
        cc_client = boto3.client('codecommit')
        response = cc_client.get_comment(
            commentId=comment_id
        )
        return response
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
