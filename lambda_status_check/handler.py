import json
import os

import boto3
from botocore.exceptions import ClientError

# Initialize the DynamoDB resource outside of the handler for better performance.
# This allows the connection to be reused across multiple Lambda invocations.
dynamodb = boto3.resource('dynamodb')

def lambda_handler(event, context):
    """
    Handles API Gateway requests to check the processing status of a file.

    This function supports three main operations:
    1.  CORS preflight (OPTIONS): Responds to browser preflight requests.
    2.  Health Check (GET /status): A simple, unauthenticated check to verify
        that the API and Lambda are operational. Triggered by a GET request
        with no query string parameters.
    3.  Status Lookup (GET /status?userId=...&fileId=...): Fetches and returns
        the status of a specific file for a given user from DynamoDB.

    Args:
        event (dict): The event dict from API Gateway, containing the HTTP method,
                      headers, and query string parameters.
        context (object): The Lambda context object (not used in this function).

    Returns:
        dict: A valid API Gateway proxy response object.
    """
    table = dynamodb.Table(os.environ['TABLE_NAME'])

    # Define standard CORS headers for all responses to ensure browser compatibility.
    cors_headers = {
        'Access-Control-Allow-Origin': '*',  # Best practice: Restrict to your frontend's domain in production.
        'Access-Control-Allow-Headers': 'Content-Type,Authorization',
        'Access-Control-Allow-Methods': 'GET,OPTIONS',
        'Content-Type': 'application/json'
    }

    # Immediately handle the OPTIONS preflight request required by browsers for CORS.
    if event.get('httpMethod') == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': cors_headers,
            'body': json.dumps({'message': 'CORS preflight successful'})
        }

    params = event.get('queryStringParameters')

    # If no query parameters are provided, treat it as a simple health check.
    # This provides a basic, public endpoint for monitoring and smoke tests.
    if not params:
        return {
            'statusCode': 200,
            'headers': cors_headers,
            'body': json.dumps({'status': 'ok'})
        }

    # Main logic for handling a specific status lookup request.
    try:
        # Validate that the required parameters are present in the request.
        user_id = params.get('userId')
        file_id = params.get('fileId')
        if not user_id or not file_id:
            return {
                'statusCode': 400,
                'headers': cors_headers,
                'body': json.dumps({'error': 'Missing required query parameters: userId and fileId'})
            }

        # Fetch the item from the DynamoDB table using the provided keys.
        response = table.get_item(
            Key={
                'userId': user_id,
                'fileId': file_id
            }
        )

        print(f"Successfully fetched status for userId: {user_id}, fileId: {file_id}")

        # Return the DynamoDB item, or an empty object if not found.
        return {
            'statusCode': 200,
            'headers': cors_headers,
            'body': json.dumps(response.get('Item', {}))
        }

    except ClientError as e:
        # Handle potential errors from the DynamoDB service itself.
        error_message = e.response['Error']['Message']
        print(f"DynamoDB ClientError: {error_message}")
        return {
            'statusCode': 500,
            'headers': cors_headers,
            'body': json.dumps({'error': f'A database error occurred: {error_message}'})
        }
    except Exception as e:  # noqa: BLE001 - Lambda boundary must return a generic 500 response
        # Catch any other unexpected errors during execution.
        print(f"An unexpected error occurred: {e!s}")
        return {
            'statusCode': 500,
            'headers': cors_headers,
            'body': json.dumps({'error': 'An internal server error occurred.'})
        }
