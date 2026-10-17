"""Run the actual POSIX launcher against command fixtures, never Valve's client.

Only the two fixed guest path assignments are relocated into the temporary test
directory. Identity/process/D-Bus commands simulate a UID1000 desktop; flock is
real. These are launcher regressions, not a GUI, Steam or iPhone acceptance gate.
"""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "guest/steam/ideck-steam"


@unittest.skipUnless(os.name == "posix" and shutil.which("flock"), "POSIX shell/flock required")
class SteamLaunchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="steam launch ")
        self.root = Path(self.tmp.name)
        self.home = self.root / "home"
        self.runtime = self.root / "runtime"
        self.bin = self.root / "bin"
        for directory in (self.home, self.runtime, self.bin):
            directory.mkdir(mode=0o700)
        self.client = self.home / ".local/share/Steam/steamrtarm64/steam"
        self.client.parent.mkdir(parents=True)
        (self.runtime / "Xauthority").write_text("fixture cookie, never an actual cookie")
        self.calls = self.root / "calls"
        self.ready = self.root / "ready"
        self.release = self.root / "release"
        self.script = self.root / "ideck-steam"
        source = SOURCE.read_text()
        self.assertEqual(source.count("steam_home=/home/ideck\n"), 1)
        self.assertEqual(source.count("runtime_dir=/run/user/1000\n"), 1)
        # No test-only configuration or environment bypass exists in production.
        import shlex
        self.script.write_text(source.replace("steam_home=/home/ideck\n", "steam_home=" + shlex.quote(str(self.home)) + "\n")
                               .replace("runtime_dir=/run/user/1000\n", "runtime_dir=" + shlex.quote(str(self.runtime)) + "\n"))
        self.executable(self.bin / "id", "case \"$1\" in -u) echo \"${FAKE_UID:-1000}\";; -un) echo ideck;; esac\n")
        self.executable(self.bin / "stat", "case \"$2\" in '%u:%a') echo \"${FAKE_RUNTIME_MODE:-1000:700}\";; '%u') echo \"${FAKE_OWNER:-1000}\";; *) exit 99;; esac\n")
        self.executable(self.bin / "pgrep", "if [ -n \"${FAKE_PGREP_STATUS:-}\" ]; then exit \"$FAKE_PGREP_STATUS\"; fi\n[ \"${FAKE_RUNNING:-0}\" = 1 ]\n")
        self.executable(self.bin / "dbus-send", "printf 'bus-probe\\n' >> \"$CALLS\"\nexit \"${FAKE_DBUS_STATUS:-0}\"\n")
        self.executable(self.bin / "dbus-run-session", "printf 'new-bus\\n' >> \"$CALLS\"\n[ \"$1\" = -- ] || exit 99\nshift\nexec \"$@\"\n")
        self.executable(self.client, """printf 'client' >> "$CALLS"
for arg do printf ' <%s>' "$arg" >> "$CALLS"; done
printf '\\n' >> "$CALLS"
printf '%s\\n' "$HOME" "$DISPLAY" "$XDG_RUNTIME_DIR" "$XAUTHORITY" "$STEAM_RUNTIME" "$LD_LIBRARY_PATH" > "$CLIENT_ENV"
printf '%s\\n' "$GDK_BACKEND" "$QT_QPA_PLATFORM" "$SDL_VIDEODRIVER" "$SDL_VIDEO_X11_DGAMOUSE" >> "$CLIENT_ENV"
if [ "$1" = -shutdown ]; then : > "$RELEASE"; exit "${FAKE_CLIENT_STATUS:-0}"; fi
: > "$READY"
if [ "${FAKE_BLOCK:-0}" = 1 ]; then
    while [ ! -f "$RELEASE" ]; do sleep 0.05; done
fi
exit "${FAKE_CLIENT_STATUS:-0}"
""")
        self.env = dict(os.environ, PATH=str(self.bin) + os.pathsep + os.defpath,
                        HOME=str(self.home), DISPLAY=":0", XDG_RUNTIME_DIR=str(self.runtime),
                        XAUTHORITY=str(self.runtime / "Xauthority"), CALLS=str(self.calls),
                        READY=str(self.ready), RELEASE=str(self.release), CLIENT_ENV=str(self.root / "client-env"))
        self.env.pop("DBUS_SESSION_BUS_ADDRESS", None)
        self.env.pop("DBUS_SESSION_BUS_PID", None)

    def tearDown(self):
        self.tmp.cleanup()

    @staticmethod
    def executable(path, text):
        path.write_text("#!/bin/sh\nset -eu\n" + text)
        path.chmod(0o755)

    def run_launcher(self, *args, **extra):
        return subprocess.run(["/bin/sh", str(self.script), *args], env=dict(self.env, **extra),
                              capture_output=True, text=True, timeout=5)

    def call_text(self):
        return self.calls.read_text() if self.calls.exists() else ""

    def test_desktop_fixed_arguments_runtime_and_new_dbus(self):
        result = self.run_launcher("desktop")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("new-bus\nclient <-clientbeta> <steamdeck_publicbeta> <-cef-ozone-platform=x11> <-cef-disable-gpu> <-nobigpicture>\n", self.call_text())
        self.assertNotIn("-no-cef-sandbox", self.call_text())
        actual = (self.root / "client-env").read_text().splitlines()
        self.assertEqual(actual[:5], [str(self.home), ":0", str(self.runtime), str(self.runtime / "Xauthority"), "1"])
        self.assertEqual(actual[5], str(self.client.parent) + ":" + str(self.client.parent / "panorama"))
        self.assertEqual(actual[6:], ["x11", "xcb", "x11", "0"])
        self.assertIn("client_returned_window_not_asserted", result.stdout)

    def test_big_picture_current_upstream_flags_and_live_dbus(self):
        result = self.run_launcher("big-picture", DBUS_SESSION_BUS_ADDRESS="unix:path=/fixture")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("bus-probe\nclient ", self.call_text())
        self.assertNotIn("new-bus", self.call_text())
        self.assertIn("<-gamepadui> <-steamdeck> <-steamos3>", self.call_text())
        self.assertNotIn("nobigpicture", self.call_text())

    def test_broken_existing_dbus_gets_new_session(self):
        result = self.run_launcher("desktop", DBUS_SESSION_BUS_ADDRESS="unix:path=/gone", FAKE_DBUS_STATUS="1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("bus-probe\nnew-bus\nclient", self.call_text())

    def test_wrong_identity_environment_or_permissions_never_launch(self):
        for changes, reason in (({"FAKE_UID": "0"}, "requires_ideck_uid1000"),
                                ({"HOME": "/root"}, "wrong_home"),
                                ({"DISPLAY": ":1"}, "existing_desktop_required"),
                                ({"XDG_RUNTIME_DIR": "/tmp"}, "wrong_runtime_dir"),
                                ({"XAUTHORITY": "/tmp/cookie"}, "wrong_xauthority"),
                                ({"FAKE_RUNTIME_MODE": "1000:777"}, "unsafe_runtime_dir"),
                                ({"FAKE_OWNER": "0"}, "wrong_xauthority_owner")):
            with self.subTest(changes=changes):
                result = self.run_launcher("desktop", **changes)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(reason, result.stderr)
                self.assertEqual(self.call_text(), "")

    def test_missing_client_and_symlink_lock_reject(self):
        self.client.unlink()
        result = self.run_launcher("desktop")
        self.assertIn("client_not_executable", result.stderr)
        self.assertNotEqual(result.returncode, 0)
        self.executable(self.client, "exit 0\n")
        (self.runtime / "ideck-steam.lock").symlink_to(self.root / "unrelated")
        result = self.run_launcher("desktop")
        self.assertIn("unsafe_lock_file", result.stderr)
        self.assertFalse((self.root / "unrelated").exists())

    def test_arbitrary_arguments_rejected(self):
        for args in ((), ("desktop", "-no-cef-sandbox"), ("login",), ("; touch pwned",)):
            with self.subTest(args=args):
                self.assertEqual(self.run_launcher(*args).returncode, 64)
                self.assertEqual(self.call_text(), "")

    def test_native_client_process_blocks_relaunch_after_wrapper_exit(self):
        result = self.run_launcher("desktop", FAKE_RUNNING="1")
        self.assertIn("client_already_running", result.stderr)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.call_text(), "")

    def test_process_probe_error_is_not_treated_as_absent_client(self):
        for mode in ("desktop", "stop"):
            with self.subTest(mode=mode):
                result = self.run_launcher(mode, FAKE_PGREP_STATUS="3")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("process_probe_failed", result.stderr)
                self.assertEqual(self.call_text(), "")

    def test_real_flock_serializes_launch_but_stop_bypasses_lock(self):
        process = subprocess.Popen(["/bin/sh", str(self.script), "desktop"], env=dict(self.env, FAKE_BLOCK="1"),
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            deadline = time.monotonic() + 3
            while not self.ready.exists() and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue(self.ready.exists(), "first fixture client did not start")
            second = self.run_launcher("big-picture")
            self.assertIn("launcher_already_running", second.stderr)
            self.assertNotEqual(second.returncode, 0)
            stop = self.run_launcher("stop", FAKE_RUNNING="1")
            self.assertEqual(stop.returncode, 0, stop.stderr)
            self.assertIn("shutdown_requested_desktop_retained", stop.stdout)
            self.assertIn("client <-shutdown>", self.call_text())
            stdout, stderr = process.communicate(timeout=3)
            self.assertEqual(process.returncode, 0, stderr)
        finally:
            self.release.touch()
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=3)

    def test_idle_stop_does_not_start_client_or_claim_clean_vm_shutdown(self):
        result = self.run_launcher("stop")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "IDECK_STEAM_STATUS=not_running\n")
        self.assertEqual(self.call_text(), "")

    def test_client_and_shutdown_failure_statuses_propagate(self):
        for mode in ("desktop", "stop"):
            with self.subTest(mode=mode):
                result = self.run_launcher(mode, FAKE_RUNNING="1" if mode == "stop" else "0", FAKE_CLIENT_STATUS="17")
                self.assertEqual(result.returncode, 17)
                self.assertIn("shutdown_request_failed" if mode == "stop" else "client_exit_nonzero", result.stderr)
                self.assertNotIn("client_returned", result.stdout)
                self.assertNotIn("shutdown_requested", result.stdout)


if __name__ == "__main__":
    unittest.main()
