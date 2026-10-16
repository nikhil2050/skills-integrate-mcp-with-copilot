# Mergington High School Activities API

A FastAPI application for viewing extracurricular activities and managing student signups.

## Features

- View all available extracurricular activities
- View activity participants without signing in
- Teacher-only student registration and unregistration
- Teacher login with expiring, HTTP-only sessions

## Getting Started

1. Install the dependencies:

   ```
   pip install fastapi uvicorn
   ```

2. Run the application from the repository root:

   ```
   uvicorn app:app --app-dir src --reload
   ```

3. Open your browser and go to:
   - API documentation: http://localhost:8000/docs
   - Alternative documentation: http://localhost:8000/redoc

## Run tests

Install the development dependencies and run the API tests:

```sh
pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
```

## Configure teacher accounts

Teacher accounts are stored in `src/teachers.json`. The committed file starts
empty; add teacher usernames and **PBKDF2-SHA256 password hashes**, never
plaintext passwords. Generate a hash with Python:

```sh
python - <<'PY'
import getpass
import hashlib
import secrets

credential = getpass.getpass("Teacher password: ")
salt = secrets.token_bytes(16)
digest = hashlib.pbkdf2_hmac("sha256", credential.encode(), salt, 600000)
print(f"pbkdf2_sha256$600000${salt.hex()}${digest.hex()}")
PY
```

Add the generated value to the JSON file in this format:

```json
[
  {
    "username": "teacher",
    "password_hash": "pbkdf2_sha256$600000$<salt-hex>$<hash-hex>"
  }
]
```

The application reads the file when a teacher logs in. Do not commit real
teacher password hashes to a public repository. Sessions expire after eight
hours and are stored in memory, so restarting the server logs teachers out.

## API Endpoints

| Method | Endpoint | Description |
| --- | --- | --- |
| GET | `/activities` | Get activities and participant details |
| GET | `/auth/session` | Check whether the current browser has a teacher session |
| POST | `/auth/login` | Log in with a JSON `username` and `password` body |
| POST | `/auth/logout` | End the current teacher session |
| POST | `/activities/{activity_name}/signup?email=student@mergington.edu` | Teacher-only registration; rejects duplicate and full activities |
| DELETE | `/activities/{activity_name}/unregister?email=student@mergington.edu` | Teacher-only unregistration |

## Data Model

The application uses a simple data model with meaningful identifiers:

1. **Activities** - Uses activity name as identifier:
   - Description
   - Schedule
   - Maximum number of participants allowed
   - List of student emails who are signed up

2. **Students** - Uses email as identifier:
   - Name
   - Grade level

Activity and session data is stored in memory and resets when the server
restarts. Teacher credential hashes are read from `src/teachers.json`.
