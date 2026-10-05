"""FileBrowser sessions must require a login. Runs the bundled filebrowser.exe on 127.0.0.1 only."""
import os
import socket
import subprocess
import tempfile
import time
import unittest

import requests

from services import filebrowser_session as fs
from utils.paths import FILEBROWSER_EXE


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class SessionValuesTests(unittest.TestCase):
    def test_sessions_are_unique_and_strong(self):
        first, second = fs.new_session(), fs.new_session()
        self.assertNotEqual(first["fb_password"], second["fb_password"])
        self.assertNotEqual(first["fb_db"], second["fb_db"])
        self.assertGreaterEqual(len(first["fb_password"]), 24)
        self.assertNotEqual(first["fb_user"], "admin")

    def test_server_arguments_never_disable_authentication(self):
        args = fs.server_arguments(fs.new_session(), "$2a$10$hash")
        self.assertNotIn("--noauth", args)
        self.assertIn("--password", args)
        self.assertEqual(args[args.index("--password") + 1], "$2a$10$hash")

    def test_cleanup_removes_session_database(self):
        session = fs.new_session()
        self.assertIn(session["fb_db"], fs.cleanup_command(session))
        self.assertIn("taskkill /F /IM filebrowser.exe", fs.cleanup_command(session))


@unittest.skipUnless(os.name == "nt" and os.path.isfile(FILEBROWSER_EXE), "needs the bundled Windows filebrowser.exe")
class LiveFileBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        with open(os.path.join(cls.tmp.name, "evidence.txt"), "w", encoding="utf-8") as handle:
            handle.write("test")
        cls.session = fs.new_session()
        cls.session["fb_db"] = os.path.join(cls.tmp.name, "fb.db")
        cls.port = free_port()
        cls.base = f"http://127.0.0.1:{cls.port}"
        args = fs.server_arguments(cls.session, fs.hash_password(cls.session["fb_password"]),
                                   address="127.0.0.1", port=cls.port, root=cls.tmp.name)
        cls.server = subprocess.Popen([FILEBROWSER_EXE, *args], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(80):
            try:
                requests.get(cls.base, timeout=1)
                break
            except requests.RequestException:
                time.sleep(0.25)

    @classmethod
    def tearDownClass(cls):
        cls.server.kill()
        cls.server.wait(timeout=10)
        cls.tmp.cleanup()

    def test_files_are_hidden_without_login(self):
        self.assertEqual(requests.get(f"{self.base}/api/resources/", timeout=5).status_code, 401)

    def test_wrong_and_default_passwords_are_rejected(self):
        with self.assertRaises(RuntimeError):
            fs.login(self.base, self.session["fb_user"], "wrong-password")
        with self.assertRaises(RuntimeError):
            fs.login(self.base, "admin", "admin")

    def test_session_credentials_give_access(self):
        token = fs.login(self.base, self.session["fb_user"], self.session["fb_password"])
        response = requests.get(f"{self.base}/api/resources/", headers={"X-Auth": token}, timeout=5)
        self.assertEqual(response.status_code, 200)
        self.assertIn("evidence.txt", [item["name"] for item in response.json()["items"]])


if __name__ == "__main__":
    unittest.main()
