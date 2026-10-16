"""
High School Management System API

A super simple FastAPI application that allows students to view and sign up
for extracurricular activities at Mergington High School.
"""

import hashlib
import hmac
import json
import logging
import secrets
import time
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

app = FastAPI(
    title="Mergington High School API",
    description="API for viewing and signing up for extracurricular activities",
)
logger = logging.getLogger(__name__)

# Mount the static files directory
current_dir = Path(__file__).parent
app.mount("/static", StaticFiles(directory=current_dir / "static"), name="static")
TEACHERS_FILE = current_dir / "teachers.json"
SESSION_COOKIE = "teacher_session"
SESSION_TTL_SECONDS = 8 * 60 * 60
PASSWORD_HASH_ITERATIONS = 600_000
DUMMY_PASSWORD_HASH = (
    "pbkdf2_sha256$600000$"
    "00000000000000000000000000000000$"
    "0000000000000000000000000000000000000000000000000000000000000000"
)
sessions: dict[str, tuple[str, float]] = {}

# In-memory activity database
activities = {
    "Chess Club": {
        "description": "Learn strategies and compete in chess tournaments",
        "schedule": "Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 12,
        "participants": ["michael@mergington.edu", "daniel@mergington.edu"]
    },
    "Programming Class": {
        "description": "Learn programming fundamentals and build software projects",
        "schedule": "Tuesdays and Thursdays, 3:30 PM - 4:30 PM",
        "max_participants": 20,
        "participants": ["emma@mergington.edu", "sophia@mergington.edu"]
    },
    "Gym Class": {
        "description": "Physical education and sports activities",
        "schedule": "Mondays, Wednesdays, Fridays, 2:00 PM - 3:00 PM",
        "max_participants": 30,
        "participants": ["john@mergington.edu", "olivia@mergington.edu"]
    },
    "Soccer Team": {
        "description": "Join the school soccer team and compete in matches",
        "schedule": "Tuesdays and Thursdays, 4:00 PM - 5:30 PM",
        "max_participants": 22,
        "participants": ["liam@mergington.edu", "noah@mergington.edu"]
    },
    "Basketball Team": {
        "description": "Practice and play basketball with the school team",
        "schedule": "Wednesdays and Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["ava@mergington.edu", "mia@mergington.edu"]
    },
    "Art Club": {
        "description": "Explore your creativity through painting and drawing",
        "schedule": "Thursdays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["amelia@mergington.edu", "harper@mergington.edu"]
    },
    "Drama Club": {
        "description": "Act, direct, and produce plays and performances",
        "schedule": "Mondays and Wednesdays, 4:00 PM - 5:30 PM",
        "max_participants": 20,
        "participants": ["ella@mergington.edu", "scarlett@mergington.edu"]
    },
    "Math Club": {
        "description": "Solve challenging problems and participate in math competitions",
        "schedule": "Tuesdays, 3:30 PM - 4:30 PM",
        "max_participants": 10,
        "participants": ["james@mergington.edu", "benjamin@mergington.edu"]
    },
    "Debate Team": {
        "description": "Develop public speaking and argumentation skills",
        "schedule": "Fridays, 4:00 PM - 5:30 PM",
        "max_participants": 12,
        "participants": ["charlotte@mergington.edu", "henry@mergington.edu"]
    }
}

class LoginRequest(BaseModel):
    username: str
    password: str


def load_teachers() -> list[dict[str, str]]:
    try:
        teacher_records = json.loads(TEACHERS_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        logger.exception("Teacher credentials file is missing")
        raise HTTPException(
            status_code=503, detail="Teacher login is not configured"
        ) from error
    except OSError as error:
        logger.exception("Teacher credentials file could not be read")
        raise HTTPException(
            status_code=500, detail="Teacher login is misconfigured"
        ) from error
    except json.JSONDecodeError as error:
        logger.exception("Teacher credentials file contains invalid JSON")
        raise HTTPException(
            status_code=500, detail="Teacher login is misconfigured"
        ) from error

    if not isinstance(teacher_records, list):
        logger.error("Teacher credentials file must contain a JSON array")
        raise HTTPException(status_code=500, detail="Teacher login is misconfigured")

    for teacher in teacher_records:
        if (
            not isinstance(teacher, dict)
            or not isinstance(teacher.get("username"), str)
            or not isinstance(teacher.get("password_hash"), str)
        ):
            logger.error("Teacher credentials file contains an invalid record")
            raise HTTPException(
                status_code=500, detail="Teacher login is misconfigured"
            )

    return teacher_records


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations_text, salt_text, expected_hash = password_hash.split("$")
        iterations = int(iterations_text)
        salt = bytes.fromhex(salt_text)
        expected = bytes.fromhex(expected_hash)
    except (ValueError, TypeError):
        logger.error("Teacher password hash has an invalid format")
        raise HTTPException(status_code=500, detail="Teacher login is misconfigured")

    if (
        algorithm != "pbkdf2_sha256"
        or not PASSWORD_HASH_ITERATIONS <= iterations <= 2_000_000
        or len(salt) < 16
        or len(expected) != hashlib.sha256().digest_size
    ):
        logger.error("Teacher password hash uses invalid parameters")
        raise HTTPException(status_code=500, detail="Teacher login is misconfigured")

    candidate = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, iterations
    )
    return hmac.compare_digest(candidate, expected)


def require_teacher(request: Request) -> str:
    token = request.cookies.get(SESSION_COOKIE)
    session = sessions.get(token) if token else None
    if session is None or session[1] <= time.time():
        if token:
            sessions.pop(token, None)
        raise HTTPException(status_code=401, detail="Teacher login required")
    return session[0]


@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")


@app.get("/activities")
def get_activities():
    return activities


@app.get("/auth/session")
def get_session(request: Request):
    token = request.cookies.get(SESSION_COOKIE)
    session = sessions.get(token) if token else None
    if session is None or session[1] <= time.time():
        if token:
            sessions.pop(token, None)
        return {"authenticated": False}
    return {"authenticated": True, "username": session[0]}


@app.post("/auth/login")
def login(credentials: LoginRequest, request: Request, response: Response):
    teachers = load_teachers()
    now = time.time()
    for expired_token in [
        token for token, (_, expires_at) in sessions.items() if expires_at <= now
    ]:
        sessions.pop(expired_token, None)
    teacher = next(
        (record for record in teachers if record["username"] == credentials.username),
        None,
    )
    password_is_valid = verify_password(
        credentials.password,
        teacher["password_hash"] if teacher else DUMMY_PASSWORD_HASH,
    )
    if teacher is None or not password_is_valid:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = secrets.token_urlsafe(32)
    sessions[token] = (
        credentials.username,
        time.time() + SESSION_TTL_SECONDS,
    )
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="strict",
        path="/",
    )
    return {"authenticated": True, "username": credentials.username}


@app.post("/auth/logout")
def logout(request: Request, response: Response):
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        sessions.pop(token, None)
    response.delete_cookie(SESSION_COOKIE, path="/", httponly=True, samesite="strict")
    return {"authenticated": False}


@app.post("/activities/{activity_name}/signup")
def signup_for_activity(
    activity_name: str, email: str, teacher: str = Depends(require_teacher)
):
    """Sign up a student for an activity"""
    # Validate activity exists
    if activity_name not in activities:
        raise HTTPException(status_code=404, detail="Activity not found")

    # Get the specific activity
    activity = activities[activity_name]

    # Validate student is not already signed up
    if email in activity["participants"]:
        raise HTTPException(
            status_code=400,
            detail="Student is already signed up"
        )

    if len(activity["participants"]) >= activity["max_participants"]:
        raise HTTPException(status_code=400, detail="Activity is full")

    # Add student
    activity["participants"].append(email)
    return {"message": f"Signed up {email} for {activity_name}"}


@app.delete("/activities/{activity_name}/unregister")
def unregister_from_activity(
    activity_name: str, email: str, teacher: str = Depends(require_teacher)
):
    """Unregister a student from an activity"""
    # Validate activity exists
    if activity_name not in activities:
        raise HTTPException(status_code=404, detail="Activity not found")

    # Get the specific activity
    activity = activities[activity_name]

    # Validate student is signed up
    if email not in activity["participants"]:
        raise HTTPException(
            status_code=400,
            detail="Student is not signed up for this activity"
        )

    # Remove student
    activity["participants"].remove(email)
    return {"message": f"Unregistered {email} from {activity_name}"}
