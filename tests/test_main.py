import os
import tempfile
import unittest

from main import ConfigError, TokenStore, normalize_user_name, parse_app_config


class ParseAppConfigTestCase(unittest.TestCase):
    def test_parse_app_config_uses_defaults_and_normalizes_users(self) -> None:
        config = parse_app_config(
            {
                "USER": "13800138000#demo@example.com",
                "PWD": "pwd1#pwd2",
            }
        )

        self.assertEqual(config.min_step, 18000)
        self.assertEqual(config.max_step, 20000)
        self.assertEqual(config.sleep_gap, 5.0)
        self.assertFalse(config.use_concurrent)
        self.assertEqual(config.accounts[0].user, "+8613800138000")
        self.assertEqual(config.accounts[1].user, "demo@example.com")

    def test_parse_app_config_rejects_mismatched_accounts(self) -> None:
        with self.assertRaises(ConfigError):
            parse_app_config(
                {
                    "USER": "13800138000#13800138001",
                    "PWD": "only-one",
                }
            )

    def test_parse_app_config_rejects_invalid_step_range(self) -> None:
        with self.assertRaises(ConfigError):
            parse_app_config(
                {
                    "USER": "13800138000",
                    "PWD": "password",
                    "MIN_STEP": "20000",
                    "MAX_STEP": "10000",
                }
            )

    def test_parse_app_config_rejects_negative_sleep_gap(self) -> None:
        with self.assertRaises(ConfigError):
            parse_app_config(
                {
                    "USER": "13800138000",
                    "PWD": "password",
                    "SLEEP_GAP": "-1",
                }
            )


class NormalizeUserNameTestCase(unittest.TestCase):
    def test_phone_user_will_add_cn_prefix(self) -> None:
        self.assertEqual(normalize_user_name("13800138000"), "+8613800138000")

    def test_email_user_keeps_original_value(self) -> None:
        self.assertEqual(normalize_user_name("demo@example.com"), "demo@example.com")


class TokenStoreTestCase(unittest.TestCase):
    def test_token_store_can_persist_and_reload(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_path = os.path.join(temp_dir, "tokens.data")
            store = TokenStore(aes_key=b"1234567890abcdef", data_path=data_path)
            store.set("demo", {"app_token": "abc", "login_token": "def"})
            store.persist()

            reloaded_store = TokenStore(aes_key=b"1234567890abcdef", data_path=data_path)
            reloaded_store.load()

            self.assertEqual(reloaded_store.get("demo"), {"app_token": "abc", "login_token": "def"})
            self.assertIsNone(reloaded_store.load_error)

    def test_token_store_reports_invalid_key(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_path = os.path.join(temp_dir, "tokens.data")
            store = TokenStore(aes_key=b"1234567890abcdef", data_path=data_path)
            store.set("demo", {"app_token": "abc"})
            store.persist()

            reloaded_store = TokenStore(aes_key=b"fedcba0987654321", data_path=data_path)
            reloaded_store.load()

            self.assertEqual(reloaded_store.tokens, {})
            self.assertIsNotNone(reloaded_store.load_error)


if __name__ == "__main__":
    unittest.main()
