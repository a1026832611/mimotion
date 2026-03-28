from unittest import mock
import unittest

import requests

from util import zepp_helper


class ZeppHelperNetworkTestCase(unittest.TestCase):
    @mock.patch("util.zepp_helper.requests.post")
    def test_login_access_token_handles_request_exception(self, mocked_post: mock.Mock) -> None:
        mocked_post.side_effect = requests.exceptions.ConnectionError("boom")

        token, message = zepp_helper.login_access_token("demo@example.com", "password")

        self.assertIsNone(token)
        self.assertIn("网络异常", message)

    @mock.patch("util.zepp_helper.requests.get")
    def test_check_app_token_handles_request_exception(self, mocked_get: mock.Mock) -> None:
        mocked_get.side_effect = requests.exceptions.Timeout("timeout")

        ok, message = zepp_helper.check_app_token("token")

        self.assertFalse(ok)
        self.assertIn("网络异常", message)


if __name__ == "__main__":
    unittest.main()
