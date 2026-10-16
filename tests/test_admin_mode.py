import hashlib
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from fastapi.testclient import TestClient

from src import app as activities_app


class AdminModeTests(unittest.TestCase):
    def setUp(self):
        self.original_teachers_file = activities_app.TEACHERS_FILE
        self.original_activities = deepcopy(activities_app.activities)
        self.temp_dir = tempfile.TemporaryDirectory()
        activities_app.TEACHERS_FILE = Path(self.temp_dir.name) / "teachers.json"
        salt = bytes.fromhex("00112233445566778899aabbccddeeff")
        digest = hashlib.pbkdf2_hmac(
            "sha256", b"correct horse battery staple", salt, 600_000
        )
        activities_app.TEACHERS_FILE.write_text(
            json.dumps(
                [
                    {
                        "username": "teacher",
                        "password_hash": (
                            f"pbkdf2_sha256$600000${salt.hex()}${digest.hex()}"
                        ),
                    }
                ]
            ),
            encoding="utf-8",
        )
        activities_app.sessions.clear()
        self.client = TestClient(activities_app.app)

    def tearDown(self):
        self.client.close()
        activities_app.TEACHERS_FILE = self.original_teachers_file
        activities_app.activities.clear()
        activities_app.activities.update(self.original_activities)
        activities_app.sessions.clear()
        self.temp_dir.cleanup()

    def test_activities_and_participants_remain_public(self):
        response = self.client.get("/activities")

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "michael@mergington.edu",
            response.json()["Chess Club"]["participants"],
        )
        self.assertEqual(
            self.client.get("/auth/session").json(),
            {"authenticated": False},
        )

    def test_signup_and_unregister_require_teacher_login(self):
        signup = self.client.post(
            "/activities/Chess%20Club/signup",
            params={"email": "student@mergington.edu"},
        )
        unregister = self.client.delete(
            "/activities/Chess%20Club/unregister",
            params={"email": "michael@mergington.edu"},
        )

        self.assertEqual(signup.status_code, 401)
        self.assertEqual(unregister.status_code, 401)

    def test_teacher_login_allows_registration_and_unregistration(self):
        login = self.client.post(
            "/auth/login",
            json={
                "username": "teacher",
                "password": "correct horse battery staple",
            },
        )

        self.assertEqual(login.status_code, 200)
        self.assertTrue(login.json()["authenticated"])
        self.assertIn("httponly", login.headers["set-cookie"].lower())
        self.assertEqual(
            self.client.get("/auth/session").json(),
            {"authenticated": True, "username": "teacher"},
        )

        signup = self.client.post(
            "/activities/Chess%20Club/signup",
            params={"email": "student@mergington.edu"},
        )
        unregister = self.client.delete(
            "/activities/Chess%20Club/unregister",
            params={"email": "student@mergington.edu"},
        )

        self.assertEqual(signup.status_code, 200)
        self.assertEqual(unregister.status_code, 200)

    def test_invalid_password_is_rejected(self):
        response = self.client.post(
            "/auth/login",
            json={"username": "teacher", "password": "wrong password"},
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "Invalid username or password")

    def test_full_activity_cannot_accept_another_student(self):
        activities_app.activities["Chess Club"]["participants"] = [
            f"student{number}@mergington.edu"
            for number in range(activities_app.activities["Chess Club"]["max_participants"])
        ]
        self.client.post(
            "/auth/login",
            json={
                "username": "teacher",
                "password": "correct horse battery staple",
            },
        )

        response = self.client.post(
            "/activities/Chess%20Club/signup",
            params={"email": "additional@mergington.edu"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Activity is full")

    def test_logout_invalidates_teacher_session(self):
        self.client.post(
            "/auth/login",
            json={
                "username": "teacher",
                "password": "correct horse battery staple",
            },
        )

        logout = self.client.post("/auth/logout")
        signup = self.client.post(
            "/activities/Chess%20Club/signup",
            params={"email": "student@mergington.edu"},
        )

        self.assertEqual(logout.status_code, 200)
        self.assertEqual(self.client.get("/auth/session").json(), {"authenticated": False})
        self.assertEqual(signup.status_code, 401)


if __name__ == "__main__":
    unittest.main()
