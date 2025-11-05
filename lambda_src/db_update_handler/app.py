import json
import os
import boto3

ORDERS_TABLE_NAME = os.environ.get('ORDERS_TABLE_NAME')
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(ORDERS_TABLE_NAME) if ORDERS_TABLE_NAME else None


def lambda_handler(event, context):
    if not table:
        print("ERROR: ORDERS_TABLE_NAME environment variable not set.")
        return {'statusCode': 500}

    print(f"Received event: {json.dumps(event)}")
    for record in event.get('Records', []):
        try:
            sns_message_body = json.loads(record.get('body', '{}'))
            event_str = sns_message_body.get('Message', '{}')
            event_obj = json.loads(event_str)
            item_to_save = {
                'PK': f"order#{event_obj.get('order_id')}",
                'order_id': event_obj.get("order_id"),
                'amount_total': event_obj.get('amount_total'),
            }
            table.put_item(Item=item_to_save)
            print(f"Successfully saved order {event_obj.get('order_id')}.")
        except Exception as e:
            print(f"ERROR: Failed to process SQS record: {record.get('messageId')}. Error: {e}")
            raise e
    return {
        'statusCode': 200,
        'body': json.dumps('DB update processing finished.')
    }
