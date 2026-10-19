"""Network-free regression controls for locked native source downloads."""
import contextlib
import errno
import hashlib
import http.client
import io
import json
import signal
import ssl
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "ci"))
import build_linux_probe_ipa as build


class Response:
    def __init__(self, *reads):
        self.reads = iter(reads)
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True

    def read(self, size):
        value = next(self.reads, b"")
        if isinstance(value, BaseException):
            raise value
        return value


@unittest.skipUnless(hasattr(signal, "setitimer") and hasattr(signal, "SIGALRM"),
                     "Native downloader runs on Apple CI and requires a POSIX wall-clock timer")
class DownloadSafety(unittest.TestCase):
    payload = b"verified source archive bytes\n"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.worker = build.Worker(self.root)
        self.destination = self.root / "source.tar.gz"
        self.item = dict(filename=self.destination.name, url="https://sources.example/source.tar.gz",
                         size=len(self.payload), sha256=hashlib.sha256(self.payload).hexdigest())
        self.stdout = contextlib.redirect_stdout(io.StringIO())
        self.stdout.__enter__()
        self.addCleanup(self.stdout.__exit__, None, None, None)

    def fetch(self, effects):
        with mock.patch.object(build.urllib.request, "urlopen", side_effect=effects) as opened, \
                mock.patch.object(build.time, "sleep") as slept:
            self.worker.fetch(self.item, self.destination)
        return opened, slept

    def assert_no_partial(self):
        self.assertEqual({path.name for path in self.root.iterdir()}, {"tmp", "cargo", "rustup"})

    def test_original_bytes_published_with_default_tls_verification(self):
        response = Response(self.payload, b"")
        opened, slept = self.fetch([response])
        self.assertEqual(self.destination.read_bytes(), self.payload)
        self.assertTrue(response.closed)
        slept.assert_not_called()
        args, kwargs = opened.call_args
        self.assertEqual(args, (self.item["url"],))
        self.assertGreater(kwargs["timeout"], 0)
        self.assertLessEqual(kwargs["timeout"], 60)
        self.assertNotIn("context", kwargs)
        self.assertNotIn("cafile", kwargs)
        self.assertEqual({path.name for path in self.root.iterdir()}, {"tmp", "cargo", "rustup", self.destination.name})

    def test_tls_handshake_connection_reset_then_success(self):
        reset = urllib.error.URLError(ConnectionResetError(errno.ECONNRESET, "connection reset"))
        opened, slept = self.fetch([reset, Response(self.payload)])
        self.assertEqual(opened.call_count, 2)
        self.assertEqual([call.args[0] for call in slept.call_args_list], [2])
        self.assertEqual(self.destination.read_bytes(), self.payload)
        self.assertTrue(self.worker.downloads)
        json.dumps(self.worker.downloads)
        self.assertIn(self.item["url"], json.dumps(self.worker.downloads))
        self.assertIn("ConnectionResetError", json.dumps(self.worker.downloads))

    def test_mid_read_reset_cleans_partial_before_retry(self):
        first = Response(self.payload[:7], ConnectionResetError(errno.ECONNRESET, "read reset"))
        snapshots = []

        def opening(url, **kwargs):
            snapshots.append([path for path in self.root.iterdir() if path.is_file()])
            return first if len(snapshots) == 1 else Response(self.payload)

        with mock.patch.object(build.urllib.request, "urlopen", side_effect=opening), \
                mock.patch.object(build.time, "sleep"):
            self.worker.fetch(self.item, self.destination)
        self.assertTrue(first.closed)
        self.assertFalse(self.destination in snapshots[0])
        self.assertFalse(self.destination in snapshots[1])
        # The previous attempt's bytes must not survive or prefix the next file.
        self.assertEqual(self.destination.read_bytes(), self.payload)
        self.assertEqual({p.name for p in self.root.iterdir()}, {"tmp", "cargo", "rustup", self.destination.name})

    def test_incomplete_read_exception_then_success(self):
        opened, _ = self.fetch([Response(http.client.IncompleteRead(b"partial", 100)), Response(self.payload)])
        self.assertEqual(opened.call_count, 2)
        self.assertEqual(self.destination.read_bytes(), self.payload)

    def test_attempts_exhausted_after_three_and_two_bounded_delays(self):
        reset = urllib.error.URLError(ConnectionResetError(errno.ECONNRESET, "reset"))
        with mock.patch.object(build.urllib.request, "urlopen", side_effect=reset) as opened, \
                mock.patch.object(build.time, "sleep") as slept:
            with self.assertRaises(urllib.error.URLError):
                self.worker.fetch(self.item, self.destination)
        self.assertEqual(opened.call_count, 3)
        self.assertEqual([call.args[0] for call in slept.call_args_list], [2, 4])
        self.assert_no_partial()
        json.dumps(self.worker.downloads)

    def test_certificate_and_nontransient_errors_fail_without_retry(self):
        errors = [
            ssl.SSLCertVerificationError(1, "certificate verify failed"),
            urllib.error.URLError(ssl.SSLCertVerificationError(1, "certificate verify failed")),
            ssl.SSLError(1, "TLS protocol error"),
            urllib.error.URLError("Tunnel connection failed: 403 Forbidden"),
            PermissionError(errno.EACCES, "permission denied"),
        ]
        for error in errors:
            with self.subTest(error=error), \
                    mock.patch.object(build.urllib.request, "urlopen", side_effect=error) as opened, \
                    mock.patch.object(build.time, "sleep") as slept:
                with self.assertRaises(type(error)):
                    self.worker.fetch(self.item, self.destination)
                self.assertEqual(opened.call_count, 1)
                slept.assert_not_called()
                self.assert_no_partial()

    def test_http_access_and_permanent_errors_fail_without_retry(self):
        for code in (400, 401, 403, 404, 407):
            with self.subTest(code=code), \
                    mock.patch.object(build.urllib.request, "urlopen",
                                      side_effect=urllib.error.HTTPError(self.item["url"], code, "denied", {}, None)) as opened, \
                    mock.patch.object(build.time, "sleep") as slept:
                with self.assertRaises(urllib.error.HTTPError):
                    self.worker.fetch(self.item, self.destination)
                self.assertEqual(opened.call_count, 1)
                slept.assert_not_called()
                self.assert_no_partial()

    def test_selected_transient_http_status_retries(self):
        for code in (408, 429, 500, 502, 503, 504):
            with self.subTest(code=code):
                error = urllib.error.HTTPError(self.item["url"], code, "temporary", {}, None)
                opened, _ = self.fetch([error, Response(self.payload)])
                self.assertEqual(opened.call_count, 2)
                self.assertEqual(self.destination.read_bytes(), self.payload)
                self.destination.unlink()

    def test_integrity_failures_never_retry_and_remove_owned_partial(self):
        for payload in (self.payload[:-1], self.payload + b"extra", b"X" * len(self.payload)):
            with self.subTest(payload=payload), \
                    mock.patch.object(build.urllib.request, "urlopen", return_value=Response(payload)) as opened, \
                    mock.patch.object(build.time, "sleep") as slept:
                with self.assertRaises(ValueError):
                    self.worker.fetch(self.item, self.destination)
                self.assertEqual(opened.call_count, 1)
                slept.assert_not_called()
                self.assert_no_partial()

    def test_existing_file_is_untouched_and_no_request_is_made(self):
        self.destination.write_bytes(b"unrelated existing artifact")
        with mock.patch.object(build.urllib.request, "urlopen") as opened:
            with self.assertRaises(FileExistsError):
                self.worker.fetch(self.item, self.destination)
        opened.assert_not_called()
        self.assertEqual(self.destination.read_bytes(), b"unrelated existing artifact")

    def test_existing_dangling_symlink_is_untouched_without_request(self):
        self.destination.symlink_to(self.root / "not-created")
        with mock.patch.object(build.urllib.request, "urlopen") as opened:
            with self.assertRaises(FileExistsError):
                self.worker.fetch(self.item, self.destination)
        opened.assert_not_called()
        self.assertTrue(self.destination.is_symlink())
        self.assertEqual(self.destination.readlink(), self.root / "not-created")

    def test_destination_race_never_overwrites_other_file(self):
        def opening(url, **kwargs):
            self.destination.write_bytes(b"other writer")
            return Response(self.payload)

        with mock.patch.object(build.urllib.request, "urlopen", side_effect=opening), \
                mock.patch.object(build.time, "sleep") as slept:
            with self.assertRaises(FileExistsError):
                self.worker.fetch(self.item, self.destination)
        slept.assert_not_called()
        self.assertEqual(self.destination.read_bytes(), b"other writer")
        self.assertEqual({p.name for p in self.root.iterdir()}, {"tmp", "cargo", "rustup", self.destination.name})

    def test_exhausted_aggregate_budget_prevents_network(self):
        self.worker.started -= build.NATIVE_BUILD_BUDGET_SECONDS + 1
        with mock.patch.object(build.urllib.request, "urlopen") as opened:
            with self.assertRaises(TimeoutError):
                self.worker.fetch(self.item, self.destination)
        opened.assert_not_called()
        self.assert_no_partial()

    def test_file_deadline_blocks_retry_that_cannot_fit_backoff(self):
        reset = ConnectionResetError(errno.ECONNRESET, "reset")
        with mock.patch.object(build, "DOWNLOAD_TIMEOUT_SECONDS", 0.05), \
                mock.patch.object(build.urllib.request, "urlopen", side_effect=reset) as opened, \
                mock.patch.object(build.time, "sleep") as slept:
            with self.assertRaises(build.DownloadDeadlineExceeded):
                self.worker.fetch(self.item, self.destination)
        self.assertEqual(opened.call_count, 1)
        slept.assert_not_called()
        self.assert_no_partial()

    def test_worker_budget_expiration_after_transport_error_prevents_next_attempt(self):
        def opening(url, **kwargs):
            self.worker.started = time.monotonic() - (build.NATIVE_BUILD_BUDGET_SECONDS + 1)
            raise ConnectionResetError(errno.ECONNRESET, "reset")

        with mock.patch.object(build.urllib.request, "urlopen", side_effect=opening) as opened, \
                mock.patch.object(build.time, "sleep") as slept:
            with self.assertRaisesRegex(TimeoutError, "Aggregate"):
                self.worker.fetch(self.item, self.destination)
        self.assertEqual(opened.call_count, 1)
        slept.assert_not_called()
        self.assert_no_partial()

    @unittest.skipUnless(hasattr(signal, "setitimer"), "POSIX wall-clock timer required by Apple worker")
    def test_stalled_read_is_interrupted_by_real_file_deadline(self):
        class StalledResponse(Response):
            def read(self, size):
                time.sleep(1)
                return b""

        response = StalledResponse()
        before = time.monotonic()
        previous_handler = signal.getsignal(signal.SIGALRM)
        with mock.patch.object(build, "DOWNLOAD_TIMEOUT_SECONDS", 0.03), \
                mock.patch.object(build.urllib.request, "urlopen", return_value=response) as opened:
            with self.assertRaises(build.DownloadDeadlineExceeded):
                self.worker.fetch(self.item, self.destination)
        self.assertLess(time.monotonic() - before, 0.75)
        self.assertEqual(opened.call_count, 1)
        self.assertTrue(response.closed)
        self.assertEqual(signal.getsignal(signal.SIGALRM), previous_handler)
        self.assertEqual(signal.getitimer(signal.ITIMER_REAL), (0.0, 0.0))
        self.assert_no_partial()
        self.assertEqual(self.worker.downloads[-1]["status"], "failed")
        self.assertIn("DownloadDeadlineExceeded", json.dumps(self.worker.downloads))

    @unittest.skipUnless(hasattr(signal, "setitimer"), "POSIX wall-clock timer required by Apple worker")
    def test_stalled_open_is_interrupted_by_real_remaining_worker_budget(self):
        def opening(url, **kwargs):
            time.sleep(1)
            return Response(self.payload)

        self.worker.started = time.monotonic() - (build.NATIVE_BUILD_BUDGET_SECONDS - 0.03)
        before = time.monotonic()
        with mock.patch.object(build.urllib.request, "urlopen", side_effect=opening) as opened:
            with self.assertRaises(build.DownloadDeadlineExceeded):
                self.worker.fetch(self.item, self.destination)
        self.assertLess(time.monotonic() - before, 0.75)
        self.assertEqual(opened.call_count, 1)
        self.assert_no_partial()

    @unittest.skipUnless(hasattr(signal, "setitimer"), "POSIX wall-clock timer required by Apple worker")
    def test_active_timer_is_preserved_and_download_refused(self):
        previous_handler = signal.getsignal(signal.SIGALRM)
        signal.setitimer(signal.ITIMER_REAL, 30)
        try:
            with mock.patch.object(build.urllib.request, "urlopen") as opened:
                with self.assertRaisesRegex(RuntimeError, "active wall-clock timer"):
                    self.worker.fetch(self.item, self.destination)
            opened.assert_not_called()
            self.assertGreater(signal.getitimer(signal.ITIMER_REAL)[0], 29)
            self.assertEqual(signal.getsignal(signal.SIGALRM), previous_handler)
            self.assert_no_partial()
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)

    def test_non_main_thread_refuses_unbounded_fallback(self):
        failures = []

        def download():
            try:
                self.worker.fetch(self.item, self.destination)
            except Exception as error:
                failures.append(error)

        with mock.patch.object(build.urllib.request, "urlopen") as opened:
            thread = threading.Thread(target=download)
            thread.start()
            thread.join(timeout=1)
        self.assertFalse(thread.is_alive())
        opened.assert_not_called()
        self.assertEqual(len(failures), 1)
        self.assertIsInstance(failures[0], RuntimeError)
        self.assertIn("main-thread", str(failures[0]))
        self.assert_no_partial()

    def test_per_socket_timeout_is_clipped_to_remaining_worker_budget(self):
        self.worker.started = time.monotonic() - (build.NATIVE_BUILD_BUDGET_SECONDS - 2)
        opened, _ = self.fetch([Response(self.payload)])
        self.assertLessEqual(opened.call_args.kwargs["timeout"], 2)
        self.assertEqual(self.destination.read_bytes(), self.payload)


if __name__ == "__main__":
    unittest.main()
