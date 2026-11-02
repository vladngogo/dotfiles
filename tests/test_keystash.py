"""Exercise keystash in an isolated HOME: modes, exact contents, no leaks."""
import os
import pty
import select
import shutil
import subprocess
import tempfile
import termios
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KEYSTASH = ROOT / "bin/keystash"
PEM = (b"-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASC\n"
       b"line two with spaces  \n-----END PRIVATE KEY-----\n")


class KeystashTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name) / "home with spaces"
        self.home.mkdir()
        self.store = self.home / ".secrets"
        self.env = {**os.environ, "HOME": str(self.home)}
        self.env.pop("KEYSTASH_DIR", None)

    def run_ks(self, *args, stdin=b"", check=True):
        result = subprocess.run([str(KEYSTASH), *args], input=stdin, env=self.env,
                                capture_output=True, timeout=120)
        if check:
            self.assertEqual(result.returncode, 0, result.stderr.decode())
        return result

    def mode(self, path):
        return path.stat().st_mode & 0o777

    def test_save_is_private_byte_exact_and_never_echoed(self):
        result = self.run_ks("save", "api-key", stdin=PEM)
        dest = self.store / "api-key"
        self.assertEqual(dest.read_bytes(), PEM)
        self.assertEqual(self.mode(dest), 0o600)
        self.assertEqual(self.mode(self.store), 0o700)
        for stream in (result.stdout, result.stderr):
            self.assertNotIn(b"MIIEvQ", stream)
        self.assertEqual(sorted(p.name for p in self.store.iterdir()), ["api-key"])

    def test_terminal_paste_is_hidden_and_echo_restored(self):
        seen, lflag = self.paste("tty-key", PEM)
        self.assertNotIn(b"MIIEvQ", seen)
        self.assertEqual((self.store / "tty-key").read_bytes(), PEM)
        self.assertTrue(lflag & termios.ECHO)
        self.assertTrue(lflag & termios.ICANON)

    def test_terminal_paste_longer_than_line_buffer_is_kept_whole(self):
        token = b"x" * 5000 + b"\n"
        self.paste("long", token)
        self.assertEqual((self.store / "long").read_bytes(), token)

    def test_empty_terminal_input_has_no_confirmation_and_saves_nothing(self):
        seen, lflag = self.paste("empty", b"", expected_status=1)
        self.assertNotIn(b"Input received", seen)
        self.assertIn(b"no input received; nothing saved", seen)
        self.assertEqual(list(self.store.iterdir()), [])
        self.assertTrue(lflag & termios.ECHO)
        self.assertTrue(lflag & termios.ICANON)

    def paste(self, name, data, expected_status=0):
        """Type data then Ctrl-D into keystash on a pty; return output and final lflag."""
        master, slave = pty.openpty()
        self.addCleanup(os.close, master)
        proc = subprocess.Popen([str(KEYSTASH), "save", name], stdin=slave,
                                stdout=slave, stderr=slave, env=self.env)
        def cleanup_proc():
            if proc.poll() is None:
                proc.kill()
            proc.wait()
        self.addCleanup(cleanup_proc)
        self.addCleanup(os.close, slave)
        os.set_blocking(master, False)
        deadline = time.monotonic() + 15
        seen = b""
        def read_output():
            remaining = deadline - time.monotonic()
            self.assertGreater(remaining, 0, "Timed out waiting for terminal output")
            self.assertTrue(select.select([master], [], [], remaining)[0], "No terminal output")
            chunk = os.read(master, 65536)
            self.assertTrue(chunk, "Terminal closed unexpectedly")
            return chunk

        def write_input(data):
            while data:
                remaining = deadline - time.monotonic()
                self.assertGreater(remaining, 0, "Timed out writing terminal input")
                self.assertTrue(select.select([], [master], [], remaining)[1], "Terminal input stalled")
                try:
                    data = data[os.write(master, data):]
                except BlockingIOError:
                    pass

        while b"hidden" not in seen:
            seen += read_output()
        # The prompt is printed after echo is off, so it is a safe point to type.
        if data:
            write_input(data)
            while b"****** Input received; press Ctrl-D to save." not in seen:
                seen += read_output()
            self.assertFalse((self.store / name).exists())
        write_input(b"\x04")
        self.assertEqual(proc.wait(timeout=10), expected_status)
        while select.select([master], [], [], 0)[0]:
            try:
                chunk = os.read(master, 1024)
            except OSError:
                break
            if not chunk:
                break
            seen += chunk
        return seen, termios.tcgetattr(slave)[3]

    def test_save_refuses_overwrite_unless_forced(self):
        self.run_ks("save", "k", stdin=b"one")
        result = self.run_ks("save", "k", stdin=b"two", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.store / "k").read_bytes(), b"one")
        self.run_ks("save", "k", "--force", stdin=b"two")
        self.assertEqual((self.store / "k").read_bytes(), b"two")

    def test_empty_input_saves_nothing_and_leaves_no_temp_file(self):
        result = self.run_ks("save", "k", stdin=b"", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(list(self.store.iterdir()), [])

    def test_bad_names_are_rejected(self):
        for name in ("../x", "a/b", ".hidden", "-f", "a..b", ""):
            with self.subTest(name=name):
                result = self.run_ks("save", name, stdin=b"s", check=False)
                self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.home / "x").exists())

    def test_loose_store_permissions_are_tightened(self):
        self.store.mkdir(mode=0o755)
        os.chmod(self.store, 0o755)
        self.run_ks("save", "k", stdin=b"s")
        self.assertEqual(self.mode(self.store), 0o700)

    def test_symlinked_store_is_refused(self):
        real = self.home / "elsewhere"
        real.mkdir()
        self.store.symlink_to(real)
        result = self.run_ks("save", "k", stdin=b"s", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(list(real.iterdir()), [])

    def test_keystash_dir_override(self):
        custom = self.home / "custom"
        self.env["KEYSTASH_DIR"] = str(custom)
        self.run_ks("save", "k", stdin=b"s")
        self.assertEqual((custom / "k").read_bytes(), b"s")

    def test_list_and_path_never_print_contents(self):
        self.run_ks("save", "b", stdin=b"secret-b")
        self.run_ks("save", "a", stdin=b"secret-a")
        listing = self.run_ks("list").stdout
        self.assertEqual(listing, b"a\nb\n")
        self.assertEqual(self.run_ks("path", "a").stdout.decode().strip(),
                         str(self.store / "a"))
        self.assertNotEqual(self.run_ks("path", "missing", check=False).returncode, 0)

    def test_list_without_store_is_empty(self):
        self.assertEqual(self.run_ks("list").stdout, b"")

    @unittest.skipUnless(shutil.which("ssh-keygen"), "ssh-keygen not installed")
    def test_rsa_generates_private_key_pair(self):
        self.run_ks("rsa", "deploy", "--bits", "3072", "--no-passphrase")
        key, pub = self.store / "deploy", self.store / "deploy.pub"
        self.assertEqual(self.mode(key), 0o600)
        self.assertEqual(self.mode(pub), 0o644)
        self.assertTrue(pub.read_text().startswith("ssh-rsa "))
        fingerprint = subprocess.run(["ssh-keygen", "-l", "-f", str(pub)],
                                     capture_output=True, text=True, check=True).stdout
        self.assertIn("3072", fingerprint)
        self.assertIn("(RSA)", fingerprint)
        again = self.run_ks("rsa", "deploy", "--no-passphrase", check=False)
        self.assertNotEqual(again.returncode, 0)

    def test_rsa_rejects_weak_key_sizes(self):
        for bits in ("2048", "abc"):
            with self.subTest(bits=bits):
                result = self.run_ks("rsa", "k", "--bits", bits, "--no-passphrase", check=False)
                self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.store / "k").exists())


if __name__ == "__main__":
    unittest.main()
