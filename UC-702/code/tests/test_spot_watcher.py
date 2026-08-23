"""Pruebas unitarias del detector de interrupción de instancias spot UC-702."""

import os
import sys
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from checkpoint_manager import CheckpointManager
from config import SpotWatcherConfig
from models import ProviderKind
from notifications import NotificationDispatcher
from spot_watcher import AWSSpotWatcher, build_watcher


def _make_response(status_code=200, text=""):
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    return resp


class TestAWSSpotWatcher(unittest.TestCase):
    def setUp(self):
        self.config = SpotWatcherConfig(use_imdsv2=False, poll_interval_seconds=0)
        self.dispatcher = MagicMock(spec=NotificationDispatcher)
        self.dispatcher.notify.return_value = ["slack"]
        self.checkpoints = MagicMock(spec=CheckpointManager)
        self.checkpoints.create_checkpoint.return_value = {"id": "cp-1"}
        self.checkpoints.run_script.return_value = None
        self.session = MagicMock()
        self.watcher = AWSSpotWatcher(
            "node-1", config=self.config, dispatcher=self.dispatcher,
            checkpoint_manager=self.checkpoints, session=self.session,
        )

    def test_check_once_returns_none_when_no_warning(self):
        self.session.get.return_value = _make_response(404, "")
        self.assertIsNone(self.watcher.check_once())

    def test_check_once_returns_none_when_empty_body(self):
        self.session.get.return_value = _make_response(200, "   ")
        self.assertIsNone(self.watcher.check_once())

    def test_check_once_parses_json_warning(self):
        self.session.get.return_value = _make_response(
            200, '{"action": "terminate", "time": "2026-08-21T12:00:00Z"}'
        )
        event = self.watcher.check_once()
        self.assertIsNotNone(event)
        self.assertEqual(event.action, "terminate")
        self.assertEqual(event.termination_time, "2026-08-21T12:00:00Z")
        self.assertEqual(event.provider, ProviderKind.AWS)
        self.assertEqual(event.node_id, "node-1")

    def test_check_once_handles_plain_text(self):
        self.session.get.return_value = _make_response(200, "terminate-warning")
        event = self.watcher.check_once()
        self.assertIsNotNone(event)
        self.assertEqual(event.raw, {"raw": "terminate-warning"})

    def test_handle_event_notifies_and_checkpoints(self):
        self.session.get.return_value = _make_response(200, '{"action": "terminate"}')
        event = self.watcher.check_once()
        result = self.watcher.handle_event(event)
        self.dispatcher.notify.assert_called_once_with(event)
        self.checkpoints.create_checkpoint.assert_called_once()
        self.assertEqual(result["notifications_delivered"], ["slack"])

    def test_run_stops_after_detecting_event(self):
        self.session.get.return_value = _make_response(200, '{"action": "terminate"}')
        sleep_calls = []
        event = self.watcher.run(sleep_fn=lambda s: sleep_calls.append(s))
        self.assertIsNotNone(event)
        self.assertEqual(sleep_calls, [])  # se detiene antes de dormir tras detectar

    def test_run_respects_max_iterations_without_event(self):
        self.session.get.return_value = _make_response(200, "")
        sleep_calls = []
        event = self.watcher.run(max_iterations=3, sleep_fn=lambda s: sleep_calls.append(s))
        self.assertIsNone(event)
        self.assertEqual(len(sleep_calls), 3)

    def test_build_watcher_aws(self):
        watcher = build_watcher("node-2", provider=ProviderKind.AWS)
        self.assertIsInstance(watcher, AWSSpotWatcher)

    def test_build_watcher_unsupported_provider_raises(self):
        with self.assertRaises(ValueError):
            build_watcher("node-2", provider=ProviderKind.GCP)


if __name__ == "__main__":
    unittest.main()
