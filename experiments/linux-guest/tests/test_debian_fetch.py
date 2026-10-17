"""Offline fault injection at the real fetch/CI boundary; no network or secrets."""
import contextlib
import errno
import hashlib
import http.client
import io
import json
import os
from pathlib import Path
import runpy
import socket
import ssl
import sys
import tempfile
import time
import traceback
import unittest
from unittest.mock import Mock, patch
import urllib.error

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "experiments/linux-guest/tools"))
sys.path.insert(0, str(ROOT / "ci"))
import debian_bundle as bundle
import build_linux_probe_ipa as build
import check_build_request


class Response(io.BytesIO):
    status = 200


class InterruptedResponse(Response):
    def __init__(self, prefix, error):
        super().__init__(prefix)
        self.error = error

    def read(self, size):
        prefix = super().read(size)
        if prefix:
            return prefix
        raise self.error


class DebianFetchChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.destination = self.root / "payload.tar"
        self.data = b"offline exact payload bytes\n" * 31
        self.expected = {"size": len(self.data), "sha256": hashlib.sha256(self.data).hexdigest()}
        self.lock = {"schema": 1, "files": dict.fromkeys(bundle.NAMES, {}), "payload": self.expected}
        self.lockpath = self.root / "lock.json"
        self.lockpath.write_text(json.dumps(self.lock))
        self.token = "TOKEN_SENTINEL_NEVER_LOG"
        self.secret = "URL_HEADER_BODY_ENV_EXCEPTION_SENTINEL"
        self.url = "https://api.github.com/repos/Mi-Yomi/iDeck/releases/assets/647969136"
        self.environment = {"IDECK_DEBIAN_PAYLOAD_URL": self.url,
                            "IDECK_DEBIAN_PAYLOAD_TOKEN": self.token,
                            "UNRELATED_ENV": self.secret}
        self.factory = self.enterContext(patch.object(bundle.urllib.request, "build_opener"))
        # Any accidental live request fails the test, even outside the opener.
        self.enterContext(patch.object(socket, "create_connection", side_effect=AssertionError("offline only")))
        self.enterContext(patch.dict(os.environ, self.environment))

    def http_error(self, status):
        body = Response(self.secret.encode())
        error = urllib.error.HTTPError(self.url + "?signed=" + self.secret, status,
                                      self.secret, {"Authorization": self.token}, body)
        error.add_note(self.secret)
        error.__cause__ = RuntimeError(self.token)
        return error, body

    def assert_safe(self, text):
        for forbidden in (self.url, self.token, self.secret, "Authorization", "Bearer ",
                          "IDECK_DEBIAN_PAYLOAD_URL", "IDECK_DEBIAN_PAYLOAD_TOKEN", "UNRELATED_ENV"):
            self.assertNotIn(forbidden, text)

    def failure(self, code, received=b"", scope="partial", published=None):
        output = io.StringIO()
        diagnostic = {}
        try:
            with contextlib.redirect_stdout(output):
                bundle.fetch(self.destination, self.lockpath, diagnostic=diagnostic)
        except bundle.FetchError as error:
            rendered = "".join(traceback.format_exception(error))
            self.assertTrue(error.__suppress_context__)
            self.assertIsNone(error.__cause__)
            self.assertIsNone(error.__context__)
            self.assertEqual(str(error), code)
            self.assertEqual(error.diagnostic, diagnostic)
        else:
            self.fail("unsafe fetch was accepted")
        self.assert_safe(output.getvalue() + rendered + json.dumps(diagnostic))
        self.assertEqual(json.loads(output.getvalue().split("=", 1)[1]), diagnostic)
        self.assertEqual(set(diagnostic) - {"cleanup_failure"}, {
            "code", "exception_class", "http_status", "errno", "received_bytes",
            "expected_size", "sha256", "sha256_scope", "elapsed_seconds"})
        self.assertEqual(diagnostic["code"], code)
        self.assertEqual(diagnostic["received_bytes"], len(received))
        self.assertEqual(diagnostic["expected_size"], len(self.data))
        self.assertEqual(diagnostic["sha256"], hashlib.sha256(received).hexdigest())
        self.assertEqual(diagnostic["sha256_scope"], scope)
        self.assertGreaterEqual(diagnostic["elapsed_seconds"], 0)
        self.assertFalse(list(self.root.glob(".debian-download-*")))
        if published is None:
            self.assertFalse(self.destination.exists())
        else:
            self.assertEqual(self.destination.read_bytes(), published)
        return diagnostic

    def test_exact_success_reports_complete_digest_without_transport_details(self):
        response = Response(self.data)
        self.factory.return_value.open.return_value = response
        diagnostic, output = {}, io.StringIO()
        with contextlib.redirect_stdout(output):
            result = bundle.fetch(self.destination, self.lockpath, diagnostic=diagnostic)
        self.assertEqual(result, self.expected)
        self.assertEqual(self.destination.read_bytes(), self.data)
        self.assertEqual(diagnostic["code"], "DEBIAN_FETCH_OK")
        self.assertEqual(diagnostic["sha256_scope"], "complete")
        self.assertEqual(diagnostic["sha256"], self.expected["sha256"])
        self.assertEqual(diagnostic["received_bytes"], len(self.data))
        self.assertEqual(diagnostic["http_status"], 200)
        self.assertIsNone(diagnostic["exception_class"])
        self.assertTrue(response.closed)
        self.assertFalse(list(self.root.glob(".debian-download-*")))
        self.assert_safe(output.getvalue())

    def test_http_access_throttling_and_server_failures_never_read_error_body(self):
        for status in (401, 403, 404, 429, 500, 502, 503, 504, 599):
            with self.subTest(status=status):
                error, body = self.http_error(status)
                body.read = Mock(side_effect=AssertionError("error body must not be read"))
                self.factory.return_value.open.side_effect = error
                diagnostic = self.failure("DEBIAN_FETCH_OPEN_FAILED")
                self.assertEqual(diagnostic["http_status"], status)
                self.assertEqual(diagnostic["exception_class"], "HTTPError")
                self.assertIsNone(diagnostic["errno"])
                self.assertTrue(body.closed)
                body.read.assert_not_called()

    def test_open_timeout_tls_and_dns_direct_or_wrapped_have_numeric_details(self):
        errors = [TimeoutError(errno.ETIMEDOUT, self.secret), ssl.SSLError(1, self.secret),
                  ssl.SSLCertVerificationError(1, self.secret), socket.gaierror(-2, self.secret)]
        for error in errors:
            for wrapped in (False, True):
                with self.subTest(error=type(error).__name__, wrapped=wrapped):
                    self.factory.return_value.open.side_effect = urllib.error.URLError(error) if wrapped else error
                    diagnostic = self.failure("DEBIAN_FETCH_OPEN_FAILED")
                    self.assertEqual(diagnostic["exception_class"], type(error).__name__)
                    self.assertEqual(diagnostic["errno"], error.errno)

    def test_read_timeout_tls_and_connection_reset_keep_prefix_hash(self):
        prefix = self.data[:17]
        for error in (TimeoutError(errno.ETIMEDOUT, self.secret), ssl.SSLError(1, self.secret),
                      ConnectionResetError(errno.ECONNRESET, self.secret)):
            with self.subTest(error=type(error).__name__):
                response = InterruptedResponse(prefix, error)
                self.factory.return_value.open.return_value = response
                diagnostic = self.failure("DEBIAN_FETCH_READ_FAILED", prefix)
                self.assertEqual(diagnostic["exception_class"], type(error).__name__)
                self.assertEqual(diagnostic["errno"], error.errno)
                self.assertEqual(diagnostic["http_status"], 200)
                self.assertTrue(response.closed)

    def test_incomplete_read_accounts_for_exception_partial_without_printing_it(self):
        prefix, partial = self.data[:11], self.secret.encode()
        self.factory.return_value.open.return_value = InterruptedResponse(
            prefix, http.client.IncompleteRead(partial, len(self.data)))
        diagnostic = self.failure("DEBIAN_FETCH_READ_FAILED", prefix + partial)
        self.assertEqual(diagnostic["exception_class"], "IncompleteRead")

    def test_clean_eof_at_short_size_is_still_partial_and_rejected(self):
        self.factory.return_value.open.return_value = Response(self.data[:-1])
        self.failure("DEBIAN_FETCH_VERIFY_SIZE", self.data[:-1])

    def test_extra_bytes_are_counted_hashed_and_rejected_before_publication(self):
        extra = self.data + b"EXTRA"
        self.factory.return_value.open.return_value = Response(extra)
        self.failure("DEBIAN_FETCH_VERIFY_SIZE", extra)

    def test_complete_wrong_hash_is_distinct_from_short_or_interrupted_read(self):
        wrong = b"X" * len(self.data)
        self.factory.return_value.open.return_value = Response(wrong)
        self.failure("DEBIAN_FETCH_VERIFY_HASH", wrong, "complete")

    def test_stored_file_is_verified_independently_of_received_bytes(self):
        self.factory.return_value.open.return_value = Response(self.data)
        original_fdopen = os.fdopen
        def fdopen(fd, mode):
            target = original_fdopen(fd, mode)
            proxy = Mock(wraps=target)
            proxy.write.side_effect = lambda chunk: target.write(b"X" * len(chunk))
            return proxy
        with patch.object(bundle.os, "fdopen", side_effect=fdopen):
            self.failure("DEBIAN_FETCH_VERIFY_FILE", self.data, "complete")

    def test_deadline_failure_accounts_for_received_chunk_without_publishing(self):
        self.factory.return_value.open.return_value = Response(self.data)
        with patch.object(bundle.time, "monotonic", side_effect=[0, 0, 0, 301, 302]):
            diagnostic = self.failure("DEBIAN_FETCH_READ_FAILED", self.data)
        self.assertEqual(diagnostic["exception_class"], "TimeoutError")
        self.assertEqual(diagnostic["elapsed_seconds"], 302)

    def test_temporary_open_failure_does_not_start_download(self):
        with patch.object(bundle.tempfile, "mkstemp", side_effect=PermissionError(errno.EACCES, self.secret)):
            diagnostic = self.failure("DEBIAN_FETCH_WRITE_FAILED")
        self.assertEqual(diagnostic["errno"], errno.EACCES)
        self.factory.assert_not_called()

    def test_write_error_and_short_write_never_publish(self):
        original_fdopen = os.fdopen
        for short in (False, True):
            with self.subTest(short=short):
                self.factory.return_value.open.return_value = Response(self.data)
                def fdopen(fd, mode):
                    target = original_fdopen(fd, mode)
                    proxy = Mock(wraps=target)
                    if short: proxy.write.return_value = 1
                    else: proxy.write.side_effect = OSError(errno.ENOSPC, self.secret)
                    return proxy
                with patch.object(bundle.os, "fdopen", side_effect=fdopen):
                    diagnostic = self.failure("DEBIAN_FETCH_WRITE_FAILED", self.data)
                self.assertEqual(diagnostic["errno"], errno.EIO if short else errno.ENOSPC)

    def test_close_flush_error_after_eof_is_write_failure(self):
        self.factory.return_value.open.return_value = Response(self.data)
        original_fdopen = os.fdopen
        def fdopen(fd, mode):
            target = original_fdopen(fd, mode)
            proxy = Mock(wraps=target)
            def close():
                if target.closed: return
                target.close()
                raise OSError(errno.ENOSPC, self.secret)
            proxy.close.side_effect = close
            return proxy
        with patch.object(bundle.os, "fdopen", side_effect=fdopen):
            self.failure("DEBIAN_FETCH_WRITE_FAILED", self.data, "complete")

    def test_publish_error_is_distinct_and_cleans_partial(self):
        self.factory.return_value.open.return_value = Response(self.data)
        with patch.object(bundle.os, "link", side_effect=PermissionError(errno.EACCES, self.secret)):
            diagnostic = self.failure("DEBIAN_FETCH_PUBLISH_FAILED", self.data, "complete")
        self.assertEqual(diagnostic["errno"], errno.EACCES)

    def test_publish_race_preserves_existing_destination(self):
        self.factory.return_value.open.return_value = Response(self.data)
        def race(source, destination):
            destination.write_bytes(b"existing user bytes")
            raise FileExistsError(errno.EEXIST, self.secret)
        with patch.object(bundle.os, "link", side_effect=race):
            self.failure("DEBIAN_FETCH_PUBLISH_FAILED", self.data, "complete", published=b"existing user bytes")

    def test_existing_destination_is_never_replaced_or_downloaded_again(self):
        self.destination.write_bytes(b"existing user bytes")
        self.failure("DEBIAN_FETCH_CONFIG_DESTINATION", published=b"existing user bytes")
        self.factory.assert_not_called()

    def test_untrusted_exception_class_text_notes_and_numeric_fields_cannot_leak(self):
        class SecretError(Exception):
            def __str__(self): raise AssertionError("exception text was inspected")
        SecretError.__name__ = self.secret
        error = SecretError(self.token)
        error.errno = self.token
        error.add_note(self.secret)
        error.__cause__ = ValueError(self.secret)
        self.factory.return_value.open.side_effect = error
        diagnostic = self.failure("DEBIAN_FETCH_OPEN_FAILED")
        self.assertEqual(diagnostic["exception_class"], "Exception")
        self.assertIsNone(diagnostic["errno"])

    def test_cleanup_failure_is_safe_and_keeps_original_reason(self):
        self.factory.return_value.open.side_effect = self.http_error(403)[0]
        original_unlink = Path.unlink
        output, diagnostic = io.StringIO(), {}
        def unlink(path, *args, **kwargs):
            if path.name.startswith(".debian-download-"): raise PermissionError(errno.EACCES, self.secret)
            return original_unlink(path, *args, **kwargs)
        with patch.object(Path, "unlink", unlink), contextlib.redirect_stdout(output):
            with self.assertRaises(bundle.FetchError):
                bundle.fetch(self.destination, self.lockpath, diagnostic=diagnostic)
        self.assertEqual(diagnostic["code"], "DEBIAN_FETCH_OPEN_FAILED")
        self.assertEqual(diagnostic["http_status"], 403)
        self.assertEqual(diagnostic["cleanup_failure"]["code"], "DEBIAN_FETCH_CLEANUP_FAILED")
        self.assertEqual(diagnostic["cleanup_failure"]["errno"], errno.EACCES)
        self.assert_safe(output.getvalue())
        self.assertFalse(self.destination.exists())
        for partial in self.root.glob(".debian-download-*"): partial.unlink()

    def test_configuration_rejection_is_sanitized_before_network(self):
        cases = [("http://example.com/" + self.secret, "", "URL"),
                 ("https://example.com/" + self.secret, self.token, "TOKEN_SCOPE"),
                 (self.url + "?signed=" + self.secret, self.token, "TOKEN_SCOPE")]
        for url, token, reason in cases:
            with self.subTest(reason=reason), patch.dict(os.environ, {
                    "IDECK_DEBIAN_PAYLOAD_URL": url, "IDECK_DEBIAN_PAYLOAD_TOKEN": token}):
                self.failure("DEBIAN_FETCH_CONFIG_" + reason)
        self.factory.assert_not_called()

    def test_redirect_policy_failure_is_open_stage_and_does_not_expose_signed_url(self):
        def open_request(request, timeout):
            return bundle.HTTPSOnlyRedirect().redirect_request(
                request, None, 302, self.secret, {"Location": self.secret}, "http://example.com/" + self.secret)
        self.factory.return_value.open.side_effect = open_request
        diagnostic = self.failure("DEBIAN_FETCH_OPEN_FAILED")
        self.assertEqual(diagnostic["exception_class"], "ValueError")

    def test_fetch_cli_emits_only_safe_json_and_exits_without_exception_trace(self):
        self.factory.return_value.open.side_effect = self.http_error(404)[0]
        output, errors = io.StringIO(), io.StringIO()
        with patch.object(sys, "argv", [str(Path(bundle.__file__)), "fetch", str(self.destination), str(self.lockpath)]), \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            with self.assertRaises(SystemExit) as stopped:
                runpy.run_path(bundle.__file__, run_name="__main__")
        self.assertEqual(stopped.exception.code, 1)
        self.assertEqual(errors.getvalue(), "")
        self.assertEqual(json.loads(output.getvalue().split("=", 1)[1])["http_status"], 404)
        self.assert_safe(output.getvalue())
        self.assertNotIn("Traceback", output.getvalue())

    def test_ci_failure_persists_safe_diagnostic_and_never_reaches_native_build(self):
        self.factory.return_value.open.side_effect = self.http_error(401)[0]
        worker = Mock(started=time.monotonic(), steps=[], downloads=[])
        worker.run.side_effect = lambda name, command: "a" * 40 if name == "checkout" else "offline gate fixture"
        output = io.StringIO()
        with patch.object(build, "ROOT", self.root), patch.object(build.platform, "system", return_value="Darwin"), \
                patch.object(build, "Worker", return_value=worker), patch.object(check_build_request, "main"), \
                patch.object(bundle, "load_lock", return_value=self.lock), \
                patch("gui_bundle.load_lock", return_value={"status":"ready"}), \
                patch.dict(os.environ, {"IDECK_WORKFLOW_ID": "ideck-linux-probe-ipa", "NATIVE_BUILD_APPROVED": "true"}), \
                contextlib.redirect_stdout(output):
            try:
                build.main()
            except SystemExit as error:
                self.assertEqual(error.code, 1)
                rendered = "".join(traceback.format_exception(error))
                self.assertTrue(error.__suppress_context__)
            else:
                self.fail("CI accepted a failed payload fetch")
        result = json.loads((self.root / ".work/linux-ipa/result.json").read_text())
        self.assertEqual(result["failure"], "DEBIAN_FETCH_OPEN_FAILED")
        self.assertEqual(result["debian_payload_fetch"]["http_status"], 401)
        self.assertEqual(result["debian_payload_fetch"]["expected_size"], len(self.data))
        self.assertEqual(result["status"], "failed")
        self.assertFalse(result["ipa_created"])
        self.assertNotIn("debian_payload", result)
        self.assertEqual([call.args[0] for call in worker.run.call_args_list], ["checkout", "xcode", "swift-source-check"])
        self.assert_safe(output.getvalue() + rendered + json.dumps(result))
        self.assertNotIn("HTTPError:", rendered)
        self.assertFalse(list((self.root / ".work/linux-ipa").glob(".debian-download-*")))


if __name__ == "__main__": unittest.main()
