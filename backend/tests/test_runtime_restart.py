import threading
import unittest
from unittest import mock

from pdf2zh.offline import OfflineError
from server.services.runtime_service import LocalRuntime


class RuntimeRestartTests(unittest.TestCase):
    def test_restart_refuses_while_the_previous_preparation_is_still_running(self):
        """BUG-017: a second _prepare must not race one that ignored the stop."""
        runtime = LocalRuntime()
        stuck = mock.Mock(spec=threading.Thread)
        stuck.is_alive.return_value = True
        runtime._thread = stuck
        runtime.state = "LOCAL_PREPARING"

        with mock.patch.object(runtime, "start") as start:
            with self.assertRaises(OfflineError) as caught:
                runtime.restart("cpu", timeout=1)

        start.assert_not_called()
        self.assertIs(runtime._thread, stuck)
        self.assertEqual(caught.exception.code, "LOCAL_RUNTIME_UNAVAILABLE")

    def test_restart_waits_for_the_preparation_to_settle_not_a_fixed_poll(self):
        runtime = LocalRuntime()
        runtime.state = "LOCAL_PREPARING"

        def prepare():
            runtime.state = "LOCAL_DATA_INVALID"

        with mock.patch.object(runtime, "_prepare_worker", side_effect=prepare):
            with self.assertRaises(OfflineError) as caught:
                runtime.restart("cpu", timeout=5)

        self.assertEqual(caught.exception.code, "LOCAL_DATA_INVALID")
        self.assertTrue(runtime._settled.is_set())


if __name__ == "__main__":
    unittest.main()
