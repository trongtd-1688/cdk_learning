import json
import os
import unittest
from unittest.mock import MagicMock, patch

from lambda_src.email_handler import app


class TestEmailHandler(unittest.TestCase):

    @patch('lambda_src.email_handler.app.ses_client')
    @patch.dict(os.environ, {
        "SENDER_EMAIL": "sender@example.com",
        "RECIPIENT_EMAIL": "recipient@example.com"
    })
    def test_lambda_handler_success(self, mock_ses_client):
        # Mock SES client behavior
        mock_ses_client.send_email.return_value = {
            'MessageId': 'test-message-id'
        }

        # Mock event
        event = {
            'Records': [
                {
                    'body': json.dumps({
                        'Message': json.dumps({
                            'order_id': '123'
                        })
                    })
                }
            ]
        }

        # Call the handler
        response = app.lambda_handler(event, None)

        # Assertions
        self.assertEqual(response['statusCode'], 200)
        mock_ses_client.send_email.assert_called_once()


if __name__ == '__main__':
    unittest.main()
