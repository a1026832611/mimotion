from datetime import datetime
import unittest

from util.push_util import PushConfig, not_in_push_time_range


class PushTimeRangeTestCase(unittest.TestCase):
    def test_without_push_hour_always_push(self) -> None:
        config = PushConfig(push_plus_hour=None)
        self.assertFalse(not_in_push_time_range(config))

    def test_matching_hour_will_push(self) -> None:
        config = PushConfig(push_plus_hour=21)
        current_time = datetime(2026, 3, 29, 21, 5, 0)
        self.assertFalse(not_in_push_time_range(config, current_time))

    def test_non_matching_hour_will_skip(self) -> None:
        config = PushConfig(push_plus_hour=21)
        current_time = datetime(2026, 3, 29, 20, 5, 0)
        self.assertTrue(not_in_push_time_range(config, current_time))


if __name__ == "__main__":
    unittest.main()
