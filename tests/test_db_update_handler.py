import json
import unittest
from unittest.mock import MagicMock, patch

from lambda_src.db_update_handler import app


class TestDbUpdateHandler(unittest.TestCase):

    @patch('boto3.resource')
    def test_lambda_handler_success(self, mock_boto_resource):
        # Mock DynamoDB table
        mock_table = MagicMock()
        mock_boto_resource.return_value.Table.return_value = mock_table

        # Mock event
        event = {
            'Records': [
                {
                    'body': json.dumps({
                        'Message': json.dumps({
                            'order_id': '123',
                            'amount_total': 100
                        })
                    })
                }
            ]
        }

        # Set environment variable
        app.ORDERS_TABLE_NAME = 'test_table'
        app.table = mock_table

        # Call the handler
        response = app.lambda_handler(event, None)

        # Assertions
        self.assertEqual(response['statusCode'], 200)
        mock_table.put_item.assert_called_once()

    def test_lambda_handler_no_table(self):
        # Unset environment variable
        app.ORDERS_TABLE_NAME = None
        app.table = None

        # Call the handler
        response = app.lambda_handler({}, None)

        # Assertions
        self.assertEqual(response['statusCode'], 500)


if __name__ == '__main__':
    unittest.main()

