import json
import unittest
from unittest.mock import MagicMock, patch

from lambda_src.webhook_handler import app


class TestWebhookHandler(unittest.TestCase):

    @patch('lambda_src.webhook_handler.app.sns_client')
    @patch('lambda_src.webhook_handler.app.secrets_client')
    def test_lambda_handler_success(self, mock_secrets_client, mock_sns_client):
        # Mock Secrets Manager client
        mock_secrets_client.get_secret_value.return_value = {
            'SecretString': 'test-api-key'
        }

        # Mock event
        event = {
            'body': json.dumps({
                'order_id': '123',
                'amount_total': 100,
                'api_key': 'test-api-key'
            })
        }

        # Call the handler
        response = app.lambda_handler(event, None)

        # Assertions
        self.assertEqual(response['statusCode'], 200)
        self.assertEqual(json.loads(response['body']), {'message': 'Webhook received and published successfully.'})
        mock_sns_client.publish.assert_called_once()

    @patch('lambda_src.webhook_handler.app.secrets_client')
    def test_lambda_handler_missing_fields(self, mock_secrets_client):
        # Mock Secrets Manager client
        mock_secrets_client.get_secret_value.return_value = {
            'SecretString': 'test-api-key'
        }

        # Mock event with missing fields
        event = {
            'body': json.dumps({
                'order_id': '123',
                'api_key': 'test-api-key'
            })
        }

        # Call the handler
        response = app.lambda_handler(event, None)

        # Assertions
        self.assertEqual(response['statusCode'], 400)
        self.assertEqual(json.loads(response['body']), {'message': 'Missing required fields.'})

    def test_lambda_handler_invalid_json(self):
        # Mock event with invalid JSON
        event = {
            'body': 'invalid json'
        }

        # Call the handler
        response = app.lambda_handler(event, None)

        # Assertions
        self.assertEqual(response['statusCode'], 500)
        self.assertIn('Internal server error', json.loads(response['body'])['message'])

    @patch('lambda_src.webhook_handler.app.secrets_client')
    def test_lambda_handler_invalid_api_key(self, mock_secrets_client):
        # Mock Secrets Manager client
        mock_secrets_client.get_secret_value.return_value = {
            'SecretString': 'test-api-key'
        }

        # Mock event with invalid API key
        event = {
            'body': json.dumps({
                'order_id': '123',
                'amount_total': 100,
                'api_key': 'invalid-api-key'
            })
        }

        # Call the handler
        response = app.lambda_handler(event, None)

        # Assertions


if __name__ == '__main__':
    unittest.main()

