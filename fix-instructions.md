# Step-by-Step Instructions to Fix KVS Notification Setup

## Problem
The current CloudFormation template is trying to use a Kinesis Data Stream as the destination for Kinesis Video Stream notifications, but KVS only supports SNS topics as notification destinations.

## Solution
We need to:
1. Add an SNS topic
2. Configure KVS to send notifications to the SNS topic
3. Create a Lambda function to forward messages from SNS to Kinesis Data Stream

## Step 1: Add SNS Topic and Policy
Add these resources after the KVSNotificationStream resource:

```yaml
  # SNS Topic for KVS Notifications
  KVSNotificationTopic:
    Type: AWS::SNS::Topic
    Properties:
      TopicName: !Sub "${ProjectName}-kvs-notifications-topic"
    
  # Policy to allow KVS to publish to SNS
  KVSNotificationTopicPolicy:
    Type: AWS::SNS::TopicPolicy
    Properties:
      Topics:
        - !Ref KVSNotificationTopic
      PolicyDocument:
        Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Principal:
              Service: kinesisvideo.amazonaws.com
            Action: 'sns:Publish'
            Resource: !Ref KVSNotificationTopic
```

## Step 2: Update the KVSNotificationIAMPolicy
Add SNS permissions to the KVSNotificationIAMPolicy:

```yaml
  KVSNotificationIAMPolicy:
    Type: AWS::IAM::Policy
    Properties:
      PolicyName: !Sub "${ProjectName}-kvs-notification-policy"
      PolicyDocument:
        Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Action:
              - 'kinesis:PutRecord'
              - 'kinesis:PutRecords'
              - 'kinesis:GetRecords'
              - 'kinesis:GetShardIterator'
              - 'kinesis:DescribeStream'
              - 'kinesis:ListShards'
              - 'kinesis:DescribeStreamSummary'
              - 'kinesis:SubscribeToShard'
              - 'kinesis:ListStreams'
            Resource: !GetAtt KVSNotificationStream.Arn
          - Effect: Allow
            Action:
              - 'kinesisvideo:UpdateNotificationConfiguration'
              - 'kinesisvideo:DescribeNotificationConfiguration'
              - 'kinesisvideo:DescribeStream'
            Resource: !GetAtt VideoStream.Arn
          - Effect: Allow
            Action:
              - 'sns:Publish'
            Resource: !Ref KVSNotificationTopic
      Roles:
        - !Ref LambdaExecutionRole
```

## Step 3: Update the KVSNotificationSetupFunction
Replace the existing KVSNotificationSetupFunction with:

```yaml
  KVSNotificationSetupFunction:
    Type: AWS::Lambda::Function
    DependsOn: KVSNotificationIAMPolicy
    Properties:
      FunctionName: !Sub "${ProjectName}-kvs-notification-setup"
      Handler: index.lambda_handler
      Role: !GetAtt LambdaExecutionRole.Arn
      Runtime: python3.9
      Timeout: 60
      MemorySize: 256
      Code:
        ZipFile: |
          import boto3
          import json
          import cfnresponse
          import time
          import logging

          # Configure logging
          logger = logging.getLogger()
          logger.setLevel(logging.INFO)

          def lambda_handler(event, context):
              """
              Set up KVS stream notification to SNS Topic
              
              This function is used as a CloudFormation custom resource to create
              a notification configuration for a Kinesis Video Stream that sends
              notifications to an SNS Topic.
              """
              logger.info(f"Received event: {json.dumps(event)}")
              
              try:
                  # Handle DELETE request
                  if event['RequestType'] == 'Delete':
                      logger.info("Delete request - sending success response")
                      cfnresponse.send(event, context, cfnresponse.SUCCESS, {})
                      return
                  
                  # Get parameters from the event
                  stream_name = event['ResourceProperties']['VideoStreamName']
                  sns_topic_arn = event['ResourceProperties']['SNSTopicArn']
                  
                  logger.info(f"Setting up notification for stream {stream_name} to {sns_topic_arn}")
                  
                  # Configure KVS stream notification
                  kvs_client = boto3.client('kinesisvideo')
                  
                  # Wait for the stream to be active
                  max_retries = 10
                  retries = 0
                  while retries < max_retries:
                      try:
                          logger.info(f"Checking stream status (attempt {retries+1}/{max_retries})")
                          response = kvs_client.describe_stream(StreamName=stream_name)
                          
                          if response['StreamInfo']['Status'] == 'ACTIVE':
                              logger.info("Stream is active, proceeding with notification setup")
                              break
                              
                          logger.info(f"Stream status is {response['StreamInfo']['Status']}, waiting...")
                          retries += 1
                          time.sleep(5)
                          
                      except Exception as e:
                          logger.error(f"Error checking stream status: {str(e)}")
                          retries += 1
                          time.sleep(5)
                  
                  if retries >= max_retries:
                      logger.warning("Max retries reached waiting for stream to be active")
                  
                  # Configure notification using the correct method name and parameter structure
                  logger.info("Creating stream notification configuration")
                  response = kvs_client.update_notification_configuration(
                      StreamName=stream_name,
                      NotificationConfiguration={
                          'Status': 'ENABLED',
                          'DestinationConfig': {
                              'Uri': sns_topic_arn
                          }
                      }
                  )
                  
                  logger.info(f"Notification configuration created successfully: {json.dumps(response)}")
                  
                  # Send success response
                  cfnresponse.send(event, context, cfnresponse.SUCCESS, {
                      'Status': 'Notification configuration created successfully'
                  })
                  
              except Exception as e:
                  logger.error(f"Error: {str(e)}")
                  cfnresponse.send(event, context, cfnresponse.FAILED, {
                      'Error': str(e)
                  })
```

## Step 4: Update the KVSNotificationSetup Custom Resource
Replace the existing KVSNotificationSetup with:

```yaml
  KVSNotificationSetup:
    Type: Custom::KVSNotificationSetup
    DependsOn:
      - VideoStream
      - KVSNotificationTopic
      - KVSNotificationSetupFunction
    Properties:
      ServiceToken: !GetAtt KVSNotificationSetupFunction.Arn
      VideoStreamName: !Ref VideoStream
      SNSTopicArn: !Ref KVSNotificationTopic
```

## Step 5: Add Lambda Function to Forward SNS Messages to Kinesis
Add this new Lambda function:

```yaml
  # Lambda to forward SNS messages to Kinesis
  KVSNotificationForwarder:
    Type: AWS::Lambda::Function
    Properties:
      FunctionName: !Sub "${ProjectName}-sns-to-kinesis"
      Handler: index.lambda_handler
      Role: !GetAtt LambdaExecutionRole.Arn
      Runtime: python3.9
      Timeout: 30
      MemorySize: 256
      Environment:
        Variables:
          KINESIS_STREAM_NAME: !Ref KVSNotificationStream
      Code:
        ZipFile: |
          import os
          import json
          import boto3
          
          def lambda_handler(event, context):
              """Forward SNS notifications to Kinesis Data Stream"""
              try:
                  # Get the Kinesis stream name
                  kinesis_stream_name = os.environ['KINESIS_STREAM_NAME']
                  
                  # Create Kinesis client
                  kinesis_client = boto3.client('kinesis')
                  
                  # Process SNS message
                  message = event['Records'][0]['Sns']['Message']
                  
                  # Put record to Kinesis
                  response = kinesis_client.put_record(
                      StreamName=kinesis_stream_name,
                      Data=message,
                      PartitionKey='kvs-notification'
                  )
                  
                  return {
                      'statusCode': 200,
                      'body': json.dumps('Successfully forwarded notification to Kinesis')
                  }
                  
              except Exception as e:
                  print(f"Error: {str(e)}")
                  return {
                      'statusCode': 500,
                      'body': json.dumps(f'Error: {str(e)}')
                  }
```

## Step 6: Add SNS Subscription and Permission
Add these resources:

```yaml
  # SNS subscription for the Lambda function
  KVSNotificationSNSSubscription:
    Type: AWS::SNS::Subscription
    Properties:
      TopicArn: !Ref KVSNotificationTopic
      Protocol: lambda
      Endpoint: !GetAtt KVSNotificationForwarder.Arn

  # Permission for SNS to invoke the Lambda function
  KVSNotificationSNSPermission:
    Type: AWS::Lambda::Permission
    Properties:
      FunctionName: !Ref KVSNotificationForwarder
      Action: lambda:InvokeFunction
      Principal: sns.amazonaws.com
      SourceArn: !Ref KVSNotificationTopic
```
