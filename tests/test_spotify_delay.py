import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from ym2sp.models import Cancelled, YandexTrack
from ym2sp.settings import Credentials, load_credentials, save_credentials, validate_spotify_delay
from ym2sp.spotify import SpotifyService
from ym2sp.sync import _resolve


class SpotifyDelayTests(unittest.TestCase):
    def service(self, delay=1):
        service = SpotifyService.__new__(SpotifyService)
        service.request_delay = delay
        service._last_request_finished = None
        service._should_cancel = lambda: False
        return service

    def test_pause_after_success_and_error(self):
        service = self.service()
        now = [0.0]
        calls = []
        def sleep(seconds):
            now[0] += seconds
        def request():
            calls.append(now[0])
        with patch('ym2sp.spotify.time.monotonic', side_effect=lambda: now[0]), \
             patch('ym2sp.spotify.time.sleep', side_effect=sleep):
            service._call(request)
            service._call(request)
            with self.assertRaises(RuntimeError):
                service._call(Mock(side_effect=RuntimeError('network')))
            service._call(request)
        self.assertEqual(calls, [0, 1, 3])

    def test_cancel_interrupts_pause_without_request(self):
        service = self.service(60)
        cancelled = [False]
        service._should_cancel = lambda: cancelled[0]
        request = Mock()
        with patch('ym2sp.spotify.time.monotonic', return_value=0), \
             patch('ym2sp.spotify.time.sleep', side_effect=lambda _: cancelled.__setitem__(0, True)):
            service._call(request)
            with self.assertRaises(Cancelled):
                service._call(request)
        request.assert_called_once()

    def test_zero_delay_and_runtime_change(self):
        service = self.service(60)
        with patch('ym2sp.spotify.time.sleep') as sleep:
            service._call(Mock())
            service.request_delay = 0
            service._call(Mock())
        sleep.assert_not_called()

    def test_sync_does_not_swallow_cancellation(self):
        spotify = Mock()
        spotify.search.side_effect = Cancelled
        with self.assertRaises(Cancelled):
            _resolve(YandexTrack('1', 'Song'), spotify, Mock(), [], set(), [], False)

    def test_settings_round_trip_and_legacy_default(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch('ym2sp.settings.SETTINGS_FILE', Path(directory) / 'settings.json'), \
             patch('ym2sp.settings._load_legacy_config', return_value={}), \
             patch.dict('os.environ', {}, clear=True):
            self.assertEqual(load_credentials().spotify_request_delay, 1)
            for delay in (0, 0.5, 60):
                save_credentials(Credentials(spotify_request_delay=delay))
                self.assertEqual(load_credentials().spotify_request_delay, delay)

    def test_invalid_delay(self):
        for value in (-1, 61, 'nan', 'inf', '', None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_spotify_delay(value)


if __name__ == '__main__':
    unittest.main()
