import json
import os
import boto3

ORDERS_TABLE_NAME = os.environ.get('ORDERS_TABLE_NAME')
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(ORDERS_TABLE_NAME) if ORDERS_TABLE_NAME else None


def lambda_handler(event, context):
    print(f"Received event: {json.dumps(event)}")

    for record in event.get('Records', []):
        try:
            sns_message_body = json.loads(record.get('body', '{}'))
            event_str = sns_message_body.get('Message', '{}')
            event_obj = json.loads(event_str)

            order_id = event_obj.get('order_id')
            print(f"Processing inventory update for order: {order_id}")

            response = table.get_item(Key={'PK': 'inventory'})

            if 'Item' in response:
                current_stock = response['Item'].get('stock_quantity', 100)
            else:
                current_stock = 100
                print("Inventory record not found. Creating new record with stock_quantity=100")

            new_stock = current_stock - 1
            print(f"Updating stock: {current_stock} -> {new_stock}")

            table.put_item(Item={
                'PK': 'inventory',
                'stock_quantity': new_stock
            })
            print(f"Successfully updated inventory. New stock: {new_stock}")
        except Exception as e:
            print(f"ERROR: Failed to process SQS record: {record.get('messageId')}. Error: {e}")
            raise e

    return {
        'statusCode': 200,
        'body': json.dumps('Inventory processing finished.')
    }
