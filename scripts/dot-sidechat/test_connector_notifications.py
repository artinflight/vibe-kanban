import json
import unittest
import connector
from verify_attention_connector import verify


class ConnectorFacade:
    """CI exercises exported connector contracts without a host installation."""
    def handle(self, message):
        if message["method"] == "tools/list":
            return {"result": {"tools": connector.TOOLS}}
        params = message["params"]
        value = connector.call(params["name"], params["arguments"])
        return {"result": {"content": [{"type": "text", "text": json.dumps(value)}]}}


class ConnectorNotificationContracts(unittest.TestCase):
    def test_advertised_attention_lifecycle_and_legacy_dispatch(self):
        result = verify(ConnectorFacade(), connector)
        self.assertEqual("passed", result["attention_lifecycle_and_retry"])
        self.assertFalse(result["live_store_opened"])


if __name__ == "__main__":
    unittest.main()
