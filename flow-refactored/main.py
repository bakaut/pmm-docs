"""Entry point demonstrating class imports and handler usage.

This script shows how all the components come together via explicit
imports. It constructs a Config, instantiates the Handler and calls
its `handle` method with a mock event. In a real deployment, the
`handle` function would be connected to your cloud provider’s
function handler.
"""

from .config import Config
from .handler import Handler


def lambda_handler(event, context):
    config = Config()
    handler = Handler(config)
    return handler.handle(event, context)


if __name__ == '__main__':
    # Example usage: pass a dummy event to test the handler
    dummy_event = {'body': '{}'}
    response = lambda_handler(dummy_event, None)
    print(response)