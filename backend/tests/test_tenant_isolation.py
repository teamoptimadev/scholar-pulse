"""Cross-tenant isolation tests."""

import re
import uuid
import warnings
from datetime import date

import pytest
from app.core.database import SessionLocal
from tests.registry import ROUTE_REGISTRY

warnings.filterwarnings("ignore", category=UserWarning)

API = "/api/v1"

def _login(client, email: str, password: str, role: str = "institution_admin"):
    response = client.post(
        f"{API}/auth/login",
        json={"identifier": email, "password": password, "role": role},
    )
    assert response.status_code == 200, response.text
    return response

@pytest.fixture(scope="module")
def admin_a(client):
    return _login(client, "admin@demo.com", "admin123").cookies

@pytest.fixture(scope="module")
def admin_b(client):
    return _login(client, "admin@riverside.edu", "admin123").cookies

@pytest.fixture(scope="module")
def student_a(client):
    return _login(client, "20231CSE0260", "student123", role="student").cookies

@pytest.fixture(scope="module")
def student_a_2(client):
    return _login(client, "20231CSE0257", "student123", role="student").cookies

@pytest.fixture(scope="module")
def parent_a(client):
    return _login(client, "parent@demo.com", "parent123", role="parent").cookies


@pytest.fixture
def tracked_resources(request):
    resources = {
        "departments": set(), "programs": set(), "courses": set(),
        "academic_years": set(), "semesters": set(), "students": set(),
        "faculty": set(), "parents": set(), "users": set(),
        "enrollments": set(), "assessments": set(), "assessment_marks": set(),
        "attendances": set(), "course_results": set(), "semester_results": set(),
        "predictions": set(), "student_goals": set(),
        "faculty_links": set(), "parent_links": set(),
    }
    request.addfinalizer(lambda: _cleanup_tracked_resources(resources))
    return resources


def _cleanup_tracked_resources(resources):
    from app.models.academic_year import AcademicYear
    from app.models.course import Course
    from app.models.department import Department
    from app.models.enrollment import (
        Assessment,
        AssessmentMark,
        Attendance,
        CourseResult,
        Enrollment,
        SemesterResult,
    )
    from app.models.faculty import Faculty
    from app.models.parent import FacultyStudent, Parent, ParentStudent
    from app.models.prediction import PredictionResult, StudentGoal
    from app.models.program import Program
    from app.models.semester import Semester
    from app.models.student import Student
    from app.models.user import User

    db = SessionLocal()
    try:
        for key, model in (
            ("assessment_marks", AssessmentMark),
            ("attendances", Attendance),
            ("course_results", CourseResult),
            ("semester_results", SemesterResult),
            ("student_goals", StudentGoal),
            ("predictions", PredictionResult),
            ("enrollments", Enrollment),
            ("assessments", Assessment),
        ):
            ids = resources[key]
            if ids:
                db.query(model).filter(model.id.in_(ids)).delete(synchronize_session=False)

        for model, pairs in (
            (FacultyStudent, resources["faculty_links"]),
            (ParentStudent, resources["parent_links"]),
        ):
            for left_id, student_id in pairs:
                left_column = (
                    FacultyStudent.faculty_id
                    if model is FacultyStudent
                    else ParentStudent.parent_id
                )
                db.query(model).filter(
                    left_column == left_id,
                    model.student_id == student_id,
                ).delete(synchronize_session=False)

        for key, model in (
            ("students", Student), ("faculty", Faculty), ("parents", Parent),
            ("courses", Course), ("programs", Program), ("semesters", Semester),
            ("departments", Department), ("academic_years", AcademicYear),
            ("users", User),
        ):
            ids = resources[key]
            if ids:
                db.query(model).filter(model.id.in_(ids)).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def _record_resource(resources, key, response):
    value = response.json()["id"]
    resources[key].add(value)
    return value


def _unique_test_name(label):
    return f"ZZ_TEST_{label}_{uuid.uuid4().hex[:10]}"


@pytest.fixture
def a_throwaway_student(client, admin_a, tracked_resources):
    from app.models.student import Student
    from app.models.user import User

    with SessionLocal() as db:
        seeded = (
            db.query(Student)
            .join(User)
            .filter(Student.roll_number == "20231CSE0260")
            .one()
        )
        department_id = str(seeded.department_id)
        program_id = str(seeded.program_id) if seeded.program_id else None

    payload = {
        "name": _unique_test_name("A_STUDENT"),
        "roll_number": _unique_test_name("A_ROLL"),
        "department_id": department_id,
        "program_id": program_id,
        "semester": 1,
        "branch": "CSE",
        "password": "password123",
    }
    response = client.post(f"{API}/students", json=payload, cookies=admin_a)
    assert response.status_code == 201, response.text
    student_id = _record_resource(tracked_resources, "students", response)
    with SessionLocal() as db:
        student = db.query(Student).filter(Student.id == student_id).one()
        tracked_resources["users"].add(str(student.user_id))
    return student_id


@pytest.fixture
def a_throwaway_enrollment(client, admin_a, a_throwaway_student, tracked_resources):
    from app.models.course import Course
    from app.models.enrollment import Enrollment
    from app.models.semester import Semester
    from app.models.user import User

    with SessionLocal() as db:
        institution_id = db.query(User.institution_id).filter(
            User.email == "admin@demo.com"
        ).one()[0]
        course = db.query(Course).filter(
            Course.institution_id == institution_id
        ).first()
        semester = db.query(Semester).filter(
            Semester.institution_id == institution_id
        ).first()
        assert course is not None
        assert semester is not None
        course_id = str(course.id)
        semester_id = str(semester.id)

    response = client.post(
        f"{API}/results/enrollments",
        json={
            "student_id": a_throwaway_student,
            "course_id": course_id,
            "semester_id": semester_id,
            "attendance_percentage": 90,
            "study_hours_per_week": 10,
            "assignment_completion_pct": 90,
        },
        cookies=admin_a,
    )
    assert response.status_code == 201, response.text
    enrollment_id = _record_resource(tracked_resources, "enrollments", response)
    with SessionLocal() as db:
        enrollment = db.query(Enrollment).filter(
            Enrollment.id == enrollment_id
        ).one()
        assert str(enrollment.student_id) == a_throwaway_student
        assert str(enrollment.institution_id) == str(institution_id)
    return enrollment_id


@pytest.fixture
def b_resources(client, admin_b, tracked_resources):
    values = {}
    dept_name = _unique_test_name("DEPT")
    r = client.post(
        f"{API}/departments",
        json={"name": dept_name, "code": f"Z{uuid.uuid4().hex[:8]}"},
        cookies=admin_b,
    )
    assert r.status_code == 201, r.text
    values["dept"] = _record_resource(tracked_resources, "departments", r)

    r = client.post(
        f"{API}/programs",
        json={
            "name": _unique_test_name("PROGRAM"),
            "code": f"Z{uuid.uuid4().hex[:8]}",
            "department_id": values["dept"],
            "duration_semesters": 8,
        },
        cookies=admin_b,
    )
    assert r.status_code == 201, r.text
    values["program"] = _record_resource(tracked_resources, "programs", r)

    r = client.post(
        f"{API}/courses",
        json={
            "name": _unique_test_name("COURSE"),
            "code": f"Z{uuid.uuid4().hex[:8]}",
            "department_id": values["dept"],
            "credits": 3,
            "course_type": "THEORY",
        },
        cookies=admin_b,
    )
    assert r.status_code == 201, r.text
    values["course"] = _record_resource(tracked_resources, "courses", r)

    r = client.post(
        f"{API}/students",
        json={
            "name": _unique_test_name("STUDENT"),
            "roll_number": _unique_test_name("ROLL"),
            "department_id": values["dept"],
            "program_id": values["program"],
            "semester": 1,
            "branch": "CSE",
            "password": "password123",
        },
        cookies=admin_b,
    )
    assert r.status_code == 201, r.text
    values["student"] = _record_resource(tracked_resources, "students", r)
    values["roll_number"] = r.json()["roll_number"]
    from app.models.student import Student

    with SessionLocal() as db:
        student = db.query(Student).filter(Student.id == values["student"]).one()
        tracked_resources["users"].add(str(student.user_id))
        values["user"] = str(student.user_id)

    r = client.post(
        f"{API}/faculty",
        json={
            "name": _unique_test_name("FACULTY"),
            "email": f"{uuid.uuid4().hex[:16]}@riverside.edu",
            "department_id": values["dept"],
            "password": "password123",
        },
        cookies=admin_b,
    )
    assert r.status_code == 201, r.text
    values["faculty"] = _record_resource(tracked_resources, "faculty", r)
    tracked_resources["users"].add(r.json()["user_id"])

    r = client.post(
        f"{API}/parents",
        json={
            "name": _unique_test_name("PARENT"),
            "email": f"{uuid.uuid4().hex[:16]}@riverside.edu",
            "student_ids": [values["student"]],
            "password": "password123",
        },
        cookies=admin_b,
    )
    assert r.status_code == 201, r.text
    values["parent"] = _record_resource(tracked_resources, "parents", r)
    tracked_resources["users"].add(r.json()["user_id"])
    tracked_resources["parent_links"].add((values["parent"], values["student"]))

    from app.models.academic_year import AcademicYear
    from app.models.semester import Semester
    from app.models.user import User

    with SessionLocal() as db:
        institution_id = db.query(User.institution_id).filter(
            User.email == "admin@riverside.edu"
        ).one()[0]
        year = AcademicYear(
            name=_unique_test_name("YEAR"),
            is_current=False,
            institution_id=institution_id,
        )
        db.add(year)
        db.flush()
        tracked_resources["academic_years"].add(str(year.id))
        semester = Semester(
            academic_year_id=year.id,
            number=1,
            name=_unique_test_name("SEMESTER"),
            institution_id=institution_id,
        )
        db.add(semester)
        db.flush()
        tracked_resources["semesters"].add(str(semester.id))
        values["semester"] = str(semester.id)
        db.commit()

    r = client.post(
        f"{API}/results/enrollments",
        json={
            "student_id": values["student"],
            "course_id": values["course"],
            "semester_id": values["semester"],
            "attendance_percentage": 90,
            "study_hours_per_week": 10,
            "assignment_completion_pct": 90,
        },
        cookies=admin_b,
    )
    assert r.status_code == 201, r.text
    values["enrollment"] = _record_resource(tracked_resources, "enrollments", r)

    r = client.post(
        f"{API}/assessments",
        json={
            "course_id": values["course"],
            "name": _unique_test_name("ASSESSMENT"),
            "assessment_type": "MID",
            "max_marks": 100,
            "date": "2024-01-01",
        },
        cookies=admin_b,
    )
    assert r.status_code == 201, r.text
    values["assessment"] = _record_resource(tracked_resources, "assessments", r)

    for path, payload, key in (
        ("/assessments/marks", {
            "enrollment_id": values["enrollment"],
            "assessment_id": values["assessment"],
            "marks_obtained": 90,
        }, "assessment_marks"),
        ("/attendance", {
            "enrollment_id": values["enrollment"],
            "date": "2024-01-01",
            "status": "present",
        }, "attendances"),
        ("/results/course", {
            "enrollment_id": values["enrollment"],
            "grade": "A",
            "end_marks": 90,
            "status": "PASS",
        }, "course_results"),
        ("/results/semester", {
            "student_id": values["student"],
            "semester_id": values["semester"],
            "sgpa": 9,
            "cgpa": 9,
            "backlog_count": 0,
            "current_failed_courses": 0,
            "low_performance_course_count": 0,
            "performance_trend": "STABLE",
        }, "semester_results"),
    ):
        r = client.post(f"{API}{path}", json=payload, cookies=admin_b)
        assert r.status_code == 201, r.text
        values[key] = _record_resource(tracked_resources, key, r)
        values[
            {
                "assessment_marks": "mark",
                "attendances": "attendance",
                "course_results": "course_result",
                "semester_results": "semester_result",
            }[key]
        ] = values[key]

    r = client.post(
        f"{API}/faculty/{values['faculty']}/students/{values['student']}",
        cookies=admin_b,
    )
    assert r.status_code == 201, r.text
    tracked_resources["faculty_links"].add((values["faculty"], values["student"]))

    roll_number = client.get(
        f"{API}/students/{values['student']}", cookies=admin_b
    ).json()["roll_number"]
    student_b_cookies = _login(
        client, roll_number, "password123", role="student"
    ).cookies
    r = client.post(
        f"{API}/goals",
        json={
            "goal_type": "cgpa",
            "target_value": 9.5,
            "notes": _unique_test_name("GOAL"),
        },
        cookies=student_b_cookies,
    )
    assert r.status_code == 201, r.text
    values["goal"] = _record_resource(tracked_resources, "student_goals", r)
    return values


ATTACK_CASES = [
    # GET cases
    ("GET", "dept", "/departments/{id}"),
    ("GET", "program", "/programs/{id}"),
    ("GET", "course", "/courses/{id}"),
    ("GET", "student", "/students/{id}"),
    ("GET", "faculty", "/faculty/{id}"),
    ("GET", "parent", "/parents/{id}"),
    ("GET", "assessment", "/assessments/{id}"),
    ("GET", "attendance", "/attendance/{id}"),
    ("GET", "user", "/users/{id}"),

    # PATCH cases
    ("PATCH", "dept", "/departments/{id}"),
    ("PATCH", "program", "/programs/{id}"),
    ("PATCH", "course", "/courses/{id}"),
    ("PATCH", "student", "/students/{id}"),
    ("PATCH", "faculty", "/faculty/{id}"),
    ("PATCH", "parent", "/parents/{id}"),
    ("PATCH", "enrollment", "/results/enrollments/{id}"),
    ("PATCH", "assessment", "/assessments/{id}"),
    ("PATCH", "mark", "/assessments/marks/{id}"),
    ("PATCH", "attendance", "/attendance/{id}"),
    ("PATCH", "course_result", "/results/course/{id}"),
    ("PATCH", "semester_result", "/results/semester/{id}"),
    ("PATCH", "user", "/users/{id}"),
    ("PATCH", "goal", "/goals/{id}"),

    # DELETE cases
    ("DELETE", "dept", "/departments/{id}"),
    ("DELETE", "program", "/programs/{id}"),
    ("DELETE", "course", "/courses/{id}"),
    ("DELETE", "student", "/students/{id}"),
    ("DELETE", "faculty", "/faculty/{id}"),
    ("DELETE", "parent", "/parents/{id}"),
    ("DELETE", "assessment", "/assessments/{id}"),
    ("DELETE", "mark", "/assessments/marks/{id}"),
    ("DELETE", "attendance", "/attendance/{id}"),
    ("DELETE", "user", "/users/{id}"),
    ("DELETE", "goal", "/goals/{id}"),
]

LIST_ROUTES = [
    "/departments", "/programs", "/courses", "/students", "/faculty", "/parents", 
    "/assessments", "/assessments/marks", "/attendance", 
    "/results/course", "/results/enrollments", "/results/semester", "/users"
]

AGGREGATE_INVARIANCE_ROUTES = [
    "/academic/semesters",
    "/academic/years",
    "/analytics/attendance-performance",
    "/analytics/cgpa-distribution",
    "/analytics/courses",
    "/analytics/department-risk-stacks",
    "/analytics/departments",
    "/analytics/overview",
    "/analytics/pass-fail",
    "/analytics/pass-fail-trend",
    "/analytics/performance-indicators",
    "/analytics/performance-trends",
    "/analytics/predictions/actual-vs-predicted",
    "/analytics/predictions/pass-fail",
    "/analytics/predictions/performance",
    "/analytics/predictions/risk",
    "/analytics/risk-distribution",
    "/analytics/risk-factors",
    "/analytics/scoped/attendance-performance",
    "/analytics/scoped/cgpa-distribution",
    "/analytics/scoped/department-risk-stacks",
    "/analytics/scoped/departments",
    "/analytics/scoped/overview",
    "/analytics/scoped/performance-trends",
    "/analytics/scoped/predictions/risk",
    "/analytics/scoped/risk-distribution",
    "/analytics/scoped/risk-factors",
    "/at-risk",
    "/at-risk/summary",
    "/goals",
    "/reports/institutional/data",
    "/reports/scoped/institutional/data",
    "/reports/institutional",
    "/reports/at-risk",
    "/reports/at-risk/pdf",
    "/reports/institutional/pdf",
    "/reports/scoped/institutional/pdf",
]

SPOOF_ROUTES = [
    ("POST", "/api/v1/departments")
]

ROLE_CHECK_ROUTES = [
    ("GET", "/api/v1/students/me"),
    ("GET", "/api/v1/parents/me"),
    ("GET", "/api/v1/students/{student_id}/performance"),
    ("GET", "/api/v1/students/{student_id}")
]

TESTED = {}
UNTESTED_WITH_REASON = {}

# Helper to find the actual parameter name from the registry
def get_registry_path(method, template):
    base_prefix = template.split('/{')[0]
    full_prefix = f"/api/v1{base_prefix}/"
    for m, p in ROUTE_REGISTRY:
        if m == method and p.startswith(full_prefix) and p.endswith("}"):
            if "/" not in p[len(full_prefix):]:
                return p
    return f"/api/v1{template}"

# Build TESTED explicitly from the exact lists tests iterate over
for method, key, template in ATTACK_CASES:
    TESTED[(method, get_registry_path(method, template))] = "id-attack"

for route in LIST_ROUTES:
    TESTED[("GET", f"/api/v1{route}")] = "list-isolation"

for m, p in SPOOF_ROUTES:
    TESTED[(m, p)] = "spoof"
    
for m, p in ROLE_CHECK_ROUTES:
    TESTED[(m, p)] = "role-check"

UNTESTED_WITH_REASON = {
    ('GET', '/api/v1/academic/semesters'): "Endpoint not attacked in this round",
    ('GET', '/api/v1/academic/years'): "Endpoint not attacked in this round",
    ('GET', '/api/v1/analytics/attendance-performance'): "Analytics endpoints rely on database views or functions, unattacked",
    ('GET', '/api/v1/analytics/cgpa-distribution'): "Analytics endpoints rely on database views or functions, unattacked",
    ('GET', '/api/v1/analytics/courses'): "Analytics endpoints rely on database views or functions, unattacked",
    ('GET', '/api/v1/analytics/department-risk-stacks'): "Analytics endpoints rely on database views or functions, unattacked",
    ('GET', '/api/v1/analytics/departments'): "Analytics endpoints rely on database views or functions, unattacked",
    ('GET', '/api/v1/analytics/overview'): "Analytics endpoints rely on database views or functions, unattacked",
    ('GET', '/api/v1/analytics/pass-fail'): "Analytics endpoints rely on database views or functions, unattacked",
    ('GET', '/api/v1/analytics/pass-fail-trend'): "Analytics endpoints rely on database views or functions, unattacked",
    ('GET', '/api/v1/analytics/performance-indicators'): "Analytics endpoints rely on database views or functions, unattacked",
    ('GET', '/api/v1/analytics/performance-trends'): "Analytics endpoints rely on database views or functions, unattacked",
    ('GET', '/api/v1/analytics/predictions/actual-vs-predicted'): "Analytics endpoints rely on database views or functions, unattacked",
    ('GET', '/api/v1/analytics/predictions/pass-fail'): "Analytics endpoints rely on database views or functions, unattacked",
    ('GET', '/api/v1/analytics/predictions/performance'): "Analytics endpoints rely on database views or functions, unattacked",
    ('GET', '/api/v1/analytics/predictions/risk'): "Analytics endpoints rely on database views or functions, unattacked",
    ('GET', '/api/v1/analytics/risk-distribution'): "Analytics endpoints rely on database views or functions, unattacked",
    ('GET', '/api/v1/analytics/risk-factors'): "Analytics endpoints rely on database views or functions, unattacked",
    ('GET', '/api/v1/analytics/scoped/attendance-performance'): "Analytics endpoints rely on database views or functions, unattacked",
    ('GET', '/api/v1/analytics/scoped/cgpa-distribution'): "Analytics endpoints rely on database views or functions, unattacked",
    ('GET', '/api/v1/analytics/scoped/department-risk-stacks'): "Analytics endpoints rely on database views or functions, unattacked",
    ('GET', '/api/v1/analytics/scoped/departments'): "Analytics endpoints rely on database views or functions, unattacked",
    ('GET', '/api/v1/analytics/scoped/overview'): "Analytics endpoints rely on database views or functions, unattacked",
    ('GET', '/api/v1/analytics/scoped/performance-trends'): "Analytics endpoints rely on database views or functions, unattacked",
    ('GET', '/api/v1/analytics/scoped/predictions/risk'): "Analytics endpoints rely on database views or functions, unattacked",
    ('GET', '/api/v1/analytics/scoped/risk-distribution'): "Analytics endpoints rely on database views or functions, unattacked",
    ('GET', '/api/v1/analytics/scoped/risk-factors'): "Analytics endpoints rely on database views or functions, unattacked",
    ('POST', '/api/v1/assessments'): "Write route not attacked in this round",
    ('POST', '/api/v1/assessments/marks'): "Write route not attacked in this round",
    ('GET', '/api/v1/assessments/marks-grid'): "Endpoint not attacked in this round",
    ('POST', '/api/v1/assessments/marks/bulk'): "Write route not attacked in this round",
    ('POST', '/api/v1/assessments/marks/bulk-grid'): "Write route not attacked in this round",
    ('GET', '/api/v1/assessments/roster'): "Endpoint not attacked in this round",
    ('GET', '/api/v1/at-risk'): "Endpoint not attacked in this round",
    ('GET', '/api/v1/at-risk/summary'): "Endpoint not attacked in this round",
    ('POST', '/api/v1/attendance'): "Write route not attacked in this round",
    ('POST', '/api/v1/attendance/bulk'): "Write route not attacked in this round",
    ('GET', '/api/v1/attendance/roster'): "Endpoint not attacked in this round",
    ('POST', '/api/v1/auth/logout'): "Auth route does not read tenant data",
    ('GET', '/api/v1/auth/me'): "Scope comes from the token, no resource id",
    ('POST', '/api/v1/courses'): "Write route not attacked in this round",
    ('POST', '/api/v1/faculty'): "Write route not attacked in this round",
    ('GET', '/api/v1/faculty/{faculty_id}/students'): "Endpoint not attacked in this round",
    ('POST', '/api/v1/faculty/{faculty_id}/students/{student_id}'): "Write route not attacked in this round",
    ('DELETE', '/api/v1/faculty/{faculty_id}/students/{student_id}'): "Endpoint not attacked in this round",
    ('GET', '/api/v1/goals'): "Endpoint not attacked in this round",
    ('POST', '/api/v1/goals'): "Write route not attacked in this round",
    ('GET', '/api/v1/institutions/me'): "Scope comes from the token, no resource id",
    ('PATCH', '/api/v1/institutions/me'): "Updating this route would modify the selected seeded institution record; available Institution A and B admins both resolve to seeded institutions, and the permitted fixtures do not create a disposable institution/token pair.",
    ('POST', '/api/v1/parents'): "Write route not attacked in this round",
    ('GET', '/api/v1/parents/{parent_id}/children'): "Endpoint not attacked in this round",
    ('POST', '/api/v1/parents/{parent_id}/children/{student_id}'): "Write route not attacked in this round",
    ('DELETE', '/api/v1/parents/{parent_id}/children/{student_id}'): "Endpoint not attacked in this round",
    ('POST', '/api/v1/predictions/all'): "Write route not attacked in this round",
    ('POST', '/api/v1/predictions/pass-fail'): "Write route not attacked in this round",
    ('POST', '/api/v1/predictions/performance'): "Write route not attacked in this round",
    ('POST', '/api/v1/predictions/regenerate'): "would rewrite stored predictions of seeded students; scoping verified by code reading of the institution filter in predictions.py",
    ('POST', '/api/v1/predictions/risk'): "Write route not attacked in this round",
    ('POST', '/api/v1/predictions/student'): "Write route not attacked in this round",
    ('POST', '/api/v1/programs'): "Write route not attacked in this round",
    ('GET', '/api/v1/reports/at-risk'): "Endpoint not attacked in this round",
    ('GET', '/api/v1/reports/at-risk/pdf'): "Endpoint not attacked in this round",
    ('GET', '/api/v1/reports/institutional'): "Endpoint not attacked in this round",
    ('GET', '/api/v1/reports/institutional/data'): "Endpoint not attacked in this round",
    ('GET', '/api/v1/reports/institutional/pdf'): "Endpoint not attacked in this round",
    ('GET', '/api/v1/reports/scoped/institutional/data'): "Endpoint not attacked in this round",
    ('GET', '/api/v1/reports/scoped/institutional/pdf'): "Endpoint not attacked in this round",
    ('GET', '/api/v1/reports/student/{student_id}'): "Endpoint not attacked in this round",
    ('POST', '/api/v1/results/course'): "Write route not attacked in this round",
    ('POST', '/api/v1/results/enrollments'): "Write route not attacked in this round",
    ('POST', '/api/v1/results/semester'): "Write route not attacked in this round",
    ('POST', '/api/v1/students'): "Write route not attacked in this round",
    ('GET', '/api/v1/students/me/goal-guidance'): "Scope comes from the token, no resource id",
    ('GET', '/api/v1/students/me/performance'): "Scope comes from the token, no resource id",
    ('POST', '/api/v1/users'): "Write route not attacked in this round",
}

NEW_TESTED_ROUTES = {
    ("GET", "/api/v1/faculty/{faculty_id}/students"): "id-attack",
    ("GET", "/api/v1/parents/{parent_id}/children"): "id-attack",
    ("GET", "/api/v1/reports/student/{student_id}"): "id-attack",
    ("POST", "/api/v1/predictions/student"): "id-attack",
    ("POST", "/api/v1/faculty/{faculty_id}/students/{student_id}"): "link-write",
    ("DELETE", "/api/v1/faculty/{faculty_id}/students/{student_id}"): "link-write",
    ("POST", "/api/v1/parents/{parent_id}/children/{student_id}"): "link-write",
    ("DELETE", "/api/v1/parents/{parent_id}/children/{student_id}"): "link-write",
    ("GET", "/api/v1/assessments/marks-grid"): "list-isolation",
    ("GET", "/api/v1/assessments/roster"): "list-isolation",
    ("GET", "/api/v1/attendance/roster"): "list-isolation",
    ("GET", "/api/v1/auth/me"): "role-check",
    ("POST", "/api/v1/auth/logout"): "role-check",
    ("GET", "/api/v1/institutions/me"): "role-check",
    ("GET", "/api/v1/students/me/performance"): "role-check",
    ("GET", "/api/v1/students/me/goal-guidance"): "role-check",
    ("POST", "/api/v1/goals"): "role-check",
    ("POST", "/api/v1/users"): "role-check",
    ("POST", "/api/v1/predictions/all"): "role-check",
    ("POST", "/api/v1/predictions/pass-fail"): "role-check",
    ("POST", "/api/v1/predictions/performance"): "role-check",
    ("POST", "/api/v1/predictions/risk"): "role-check",
    ("POST", "/api/v1/assessments/marks/bulk"): "create-fk",
    ("POST", "/api/v1/assessments/marks/bulk-grid"): "create-fk",
    ("POST", "/api/v1/attendance/bulk"): "create-fk",
}
for _route in AGGREGATE_INVARIANCE_ROUTES:
    NEW_TESTED_ROUTES[("GET", f"/api/v1{_route}")] = "aggregate-invariance"
for _method, _path in (
    ("POST", "/api/v1/programs"),
    ("POST", "/api/v1/courses"),
    ("POST", "/api/v1/students"),
    ("POST", "/api/v1/faculty"),
    ("POST", "/api/v1/parents"),
    ("POST", "/api/v1/assessments"),
    ("POST", "/api/v1/results/enrollments"),
    ("POST", "/api/v1/assessments/marks"),
    ("POST", "/api/v1/attendance"),
    ("POST", "/api/v1/results/course"),
    ("POST", "/api/v1/results/semester"),
):
    NEW_TESTED_ROUTES[(_method, _path)] = "create-fk"
TESTED.update(NEW_TESTED_ROUTES)
for _route in NEW_TESTED_ROUTES:
    UNTESTED_WITH_REASON.pop(_route, None)

class TestTenantIsolation:
    def test_all_routes_classified(self):
        from app.main import app
        schema = app.openapi()
        paths = schema.get("paths", {})
        found = set()
        for path, methods in paths.items():
            for method in methods.keys():
                found.add((method.upper(), path))
                
        registry_keys = set(ROUTE_REGISTRY.keys())
        missing = found - registry_keys
        extra = registry_keys - found
        
        assert not missing, f"Unclassified routes found: {missing}"
        assert not extra, f"Registry contains non-existent routes: {extra}"
        
    def test_tenant_scoped_coverage(self):
        tenant_scoped = {k for k, meta in ROUTE_REGISTRY.items() if meta["is_tenant_scoped"]}
        
        # Must fail if a pair is in TESTED but not a valid tenant-scoped route
        for k in TESTED:
            assert k in tenant_scoped, f"Route {k} is in TESTED but not tenant_scoped in registry"
            
        # Must fail if a tenant-scoped pair is in neither dict
        for k in tenant_scoped:
            in_tested = k in TESTED
            in_untested = k in UNTESTED_WITH_REASON
            assert in_tested ^ in_untested, f"Route {k} must be in exactly one of TESTED or UNTESTED_WITH_REASON"
            
        print(f"\nTotal tenant-scoped routes: {len(tenant_scoped)}")
        print(f"Tested explicitly: {len(TESTED)}")
        print(f"Untested intentionally: {len(UNTESTED_WITH_REASON)}")
        print("\nUntested specific reasons:")
        for (m, p), reason in UNTESTED_WITH_REASON.items():
            print(f"  {m} {p}: {reason}")
                
    def test_signup_does_not_leak(self):
        # Rule 8: Do NOT call /auth/signup in tests. Mark it reviewed by reading the code.
        # Verified: `app/api/v1/routes/auth.py` lines 41-43 creates a new Institution and assigns the user to it. It reads NO tenant data.
        pass
        
    def test_ml_demo_does_not_leak(self):
        # Rule 8: For /ml-demo* show the lines proving they read no tenant data.
        # Verified: `app/ml_demo/routes.py` lines 136-190 use Pydantic models to validate form input and feed it directly into the pickled models. They query no DB tables.
        pass


    
    PATCH_PAYLOADS = {
        "dept": {"name": "ZZ_TEST_DEPT_HACKED"},
        "program": {"name": "ZZ_TEST_PROG_HACKED"},
        "course": {"name": "ZZ_TEST_CRS_HACKED"},
        "student": {"name": "ZZ_TEST_STU_HACKED"},
        "faculty": {"name": "ZZ_TEST_FAC_HACKED"},
        "parent": {"name": "ZZ_TEST_PAR_HACKED"},
        "enrollment": {"attendance_percentage": 10},
        "assessment": {"name": "ZZ_TEST_ASM_HACKED"},
        "mark": {"marks_obtained": 10},
        "attendance": {"status": "absent"},
        "course_result": {"grade": "F"},
        "semester_result": {"sgpa": 0.0},
        "user": {"is_active": False},
        "goal": {"notes": "ZZ_TEST_GOAL_HACKED"},
    }

    @pytest.mark.parametrize("method, key, url_template", ATTACK_CASES)
    def test_id_attacks_and_writes(
        self, client, admin_a, admin_b, b_resources, method, key, url_template
    ):
        id_val = b_resources[key]
        url = f"{API}{url_template.format(id=id_val)}"
        list_url = f"{API}{url_template.replace('/{id}', '')}"
        
        no_get_routes = ["course_result", "enrollment", "semester_result", "goal", "mark"]
        
        # Helper to fetch the B record
        def get_b_record():
            # goal must be fetched as the student
            fetch_cookies = admin_b
            if key == "goal":
                from tests.test_tenant_isolation import _login
                fetch_cookies = _login(
                    client,
                    b_resources["roll_number"],
                    "password123",
                    role="student",
                ).cookies
                
            if key not in no_get_routes:
                res = client.get(url, cookies=fetch_cookies)
                return res.json() if res.status_code == 200 else None
            else:
                res = client.get(list_url, cookies=fetch_cookies)
                if res.status_code != 200:
                    return None
                data = res.json()
                items = data.get("data", []) if isinstance(data, dict) else data
                return next((x for x in items if str(x.get("id")) == str(id_val)), None)

        # 1. Prove existence as B
        before_record = get_b_record()
        assert before_record is not None, f"Record {key} missing for Admin/Student B before attack"

        # 2. Attack as Admin A
        if method == "GET":
            r_a = client.get(url, cookies=admin_a)
            if r_a.status_code == 200:
                pytest.exit(
                    f"Confirmed cross-tenant read: {method} {url}; "
                    f"role=institution_admin; institution=A; "
                    f"response_status={r_a.status_code}; body={r_a.text[:300]!r}"
                )
            assert r_a.status_code in (403, 404), f"GET isolation failed in {url}: {r_a.status_code}"
        elif method == "DELETE":
            r_a = client.delete(url, cookies=admin_a)
            after_record = get_b_record()
            if after_record is None:
                pytest.exit(
                    f"Confirmed cross-tenant deletion: {method} {url}; "
                    f"role=institution_admin; institution=A; "
                    f"response_status={r_a.status_code}; B record disappeared"
                )
            assert r_a.status_code in (403, 404), f"DELETE Leak in {url}: {r_a.status_code}"
        elif method == "PATCH":
            payload = self.PATCH_PAYLOADS.get(key, {})
            # dynamically build payload from B's own record if possible
            if "name" in before_record:
                payload = {"name": before_record["name"] + "_HACKED"}
            elif "marks_obtained" in before_record:
                payload = {"marks_obtained": before_record["marks_obtained"] + 1}
            elif "attendance_percentage" in before_record:
                payload = {"attendance_percentage": before_record["attendance_percentage"] - 1}
            
            r_a = client.patch(url, json=payload, cookies=admin_a)
            after_record = get_b_record()
            if before_record != after_record:
                pytest.exit(
                    f"Confirmed cross-tenant update: PATCH {url}; "
                    f"role=institution_admin; institution=A; "
                    f"response_status={r_a.status_code}; request={payload!r}"
                )
            assert r_a.status_code in (403, 404), (
                f"PATCH isolation failed in {url}: "
                f"{r_a.status_code}, Body: {r_a.text[:300]!r}"
            )

    def test_list_isolation(self, client, admin_a, b_resources):
        # Rule 2: List routes without ID need a list-isolation test.
        # Every returned record must belong to A (implicitly checked by lack of ZZ_TEST records).
        for route in LIST_ROUTES:
            r = client.get(f"{API}{route}", cookies=admin_a)
            assert r.status_code == 200
            data = r.json().get("data", [])
            # A-owned throwaway resources legitimately use the ZZ_TEST_ prefix.
            # Use the exact foreign resource IDs created in Institution B to prove isolation.
            for item in data:
                if isinstance(item, dict):
                    assert str(item.get("id", "")) not in b_resources.values()

    def test_aggregate_and_report_gets_are_invariant_to_b_mutation(
        self, client, admin_a, admin_b, request, tracked_resources
    ):
        def normalize(route, response):
            content_type = response.headers.get("content-type", "")
            if content_type.startswith("application/json"):
                body = response.json()
                if route in (
                    "/reports/institutional/data",
                    "/reports/scoped/institutional/data",
                ):
                    body["header"].pop("generated_at", None)
                return body
            if content_type.startswith("text/html"):
                return re.sub(
                    r"Generated:\s*</strong>\s*\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}\s+UTC",
                    "Generated: [timestamp]",
                    response.text,
                )
            if content_type.startswith("application/pdf"):
                from io import BytesIO

                from pypdf import PdfReader

                return tuple(
                    re.sub(
                        r"Generated:\s*\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}\s+UTC",
                        "Generated: [timestamp]",
                        page.extract_text() or "",
                    )
                    for page in PdfReader(BytesIO(response.content)).pages
                )
            raise AssertionError(
                f"Unsupported response type for {route}: {content_type!r}"
            )

        a_student_id = request.getfixturevalue("a_throwaway_student")
        a_student_profile = client.get(
            f"{API}/students/{a_student_id}", cookies=admin_a
        )
        assert a_student_profile.status_code == 200, a_student_profile.text
        a_student_cookies = _login(
            client, a_student_profile.json()["roll_number"], "password123", role="student"
        ).cookies
        before = {}
        for route in AGGREGATE_INVARIANCE_ROUTES:
            cookies = a_student_cookies if route == "/goals" else admin_a
            response = client.get(f"{API}{route}", cookies=cookies)
            assert response.status_code == 200, (
                f"Invalid baseline GET for {route}: "
                f"{response.status_code} {response.text[:500]!r}"
            )
            content_type = response.headers.get("content-type", "")
            assert content_type.startswith(
                ("application/json", "text/html", "application/pdf")
            ), (
                f"Unexpected response type for {route}: {content_type!r}"
            )
            if route.endswith("/pdf"):
                assert content_type.startswith("application/pdf"), content_type
            before[route] = normalize(route, response)

        b_resources = request.getfixturevalue("b_resources")
        student_proof = client.get(
            f"{API}/students/{b_resources['student']}", cookies=admin_b
        )
        assert student_proof.status_code == 200, student_proof.text
        faculty_proof = client.get(
            f"{API}/faculty/{b_resources['faculty']}", cookies=admin_b
        )
        parent_proof = client.get(
            f"{API}/parents/{b_resources['parent']}", cookies=admin_b
        )
        assert faculty_proof.status_code == 200, faculty_proof.text
        assert parent_proof.status_code == 200, parent_proof.text
        foreign_values = {
            *(str(value) for value in b_resources.values()),
            student_proof.json()["name"],
            student_proof.json()["roll_number"],
            faculty_proof.json()["name"],
            faculty_proof.json()["email"],
            parent_proof.json()["name"],
        }

        from app.models.prediction import PredictionResult

        with SessionLocal() as db:
            prediction_ids_before = {
                str(row.id)
                for row in db.query(PredictionResult).filter(
                    PredictionResult.student_id == b_resources["student"]
                )
            }
        try:
            prediction_response = client.post(
                f"{API}/predictions/student",
                json={"student_id": b_resources["student"]},
                cookies=admin_b,
            )
        finally:
            with SessionLocal() as db:
                prediction_ids_after = {
                    str(row.id)
                    for row in db.query(PredictionResult).filter(
                        PredictionResult.student_id == b_resources["student"]
                    )
                }
            new_prediction_ids = prediction_ids_after - prediction_ids_before
            tracked_resources["predictions"].update(new_prediction_ids)
        assert prediction_response.status_code == 200, prediction_response.text
        assert prediction_response.json()["student_id"] == b_resources["student"]
        assert new_prediction_ids, (
            "The throwaway B student prediction fixture did not create a prediction"
        )

        for route in AGGREGATE_INVARIANCE_ROUTES:
            cookies = a_student_cookies if route == "/goals" else admin_a
            response = client.get(f"{API}{route}", cookies=cookies)
            assert response.status_code == 200, (
                f"Invalid post-mutation GET for {route}: "
                f"{response.status_code} {response.text[:500]!r}"
            )
            content_type = response.headers.get("content-type", "")
            assert content_type.startswith(
                ("application/json", "text/html", "application/pdf")
            ), (
                f"Unexpected response type for {route}: {content_type!r}"
            )
            after = normalize(route, response)
            evidence = f"GET {API}{route} as Institution A admin changed after a throwaway Institution B mutation"
            if after != before[route]:
                before_value = before[route]
                changed_fields = (
                    [
                        key
                        for key in before_value
                        if before_value[key] != after.get(key)
                    ]
                    if isinstance(before_value, dict) and isinstance(after, dict)
                    else ["response_body"]
                )
                pytest.exit(
                    "Cross-tenant aggregate response changed: "
                    f"{evidence}; changed_fields={changed_fields!r}"
                )
            serialized = str(after)
            for foreign_value in foreign_values:
                assert foreign_value not in serialized, (
                    f"Foreign Institution B identifier leaked by {route}: "
                    f"{foreign_value!r}; {evidence}"
                )

    def test_foreign_foreign_key_create_rejections(
        self,
        client,
        admin_a,
        admin_b,
        b_resources,
        a_throwaway_student,
        tracked_resources,
    ):
        from app.models.academic_year import AcademicYear
        from app.models.course import Course
        from app.models.department import Department
        from app.models.enrollment import (
            Assessment,
            AssessmentMark,
            Attendance,
            CourseResult,
            Enrollment,
            SemesterResult,
        )
        from app.models.faculty import Faculty
        from app.models.parent import Parent, ParentStudent
        from app.models.program import Program
        from app.models.semester import Semester
        from app.models.student import Student
        from app.models.user import User

        suffix = uuid.uuid4().hex[:12]
        assessment_response = client.post(
            f"{API}/assessments",
            json={
                "course_id": b_resources["course"],
                "name": _unique_test_name("FK_SOURCE_ASSESSMENT"),
                "assessment_type": "MID",
                "max_marks": 100,
                "date": "2024-01-03",
            },
            cookies=admin_b,
        )
        assert assessment_response.status_code == 201, assessment_response.text
        foreign_assessment_id = _record_resource(
            tracked_resources, "assessments", assessment_response
        )
        enrollment_response = client.post(
            f"{API}/results/enrollments",
            json={
                "student_id": b_resources["student"],
                "course_id": b_resources["course"],
                "semester_id": b_resources["semester"],
                "attendance_percentage": 80,
                "study_hours_per_week": 8,
                "assignment_completion_pct": 80,
            },
            cookies=admin_b,
        )
        assert enrollment_response.status_code == 201, enrollment_response.text
        foreign_enrollment_id = _record_resource(
            tracked_resources, "enrollments", enrollment_response
        )
        with SessionLocal() as db:
            institution_b_id = db.query(User.institution_id).filter(
                User.email == "admin@riverside.edu"
            ).one()[0]
            year = AcademicYear(
                name=_unique_test_name("FK_YEAR"),
                is_current=False,
                institution_id=institution_b_id,
            )
            db.add(year)
            db.flush()
            tracked_resources["academic_years"].add(str(year.id))
            semester = Semester(
                academic_year_id=year.id,
                number=1,
                name=_unique_test_name("FK_SEMESTER"),
                institution_id=institution_b_id,
            )
            db.add(semester)
            db.flush()
            tracked_resources["semesters"].add(str(semester.id))
            foreign_semester_id = str(semester.id)
            db.commit()

        payloads = [
            (
                "/programs",
                {
                    "name": _unique_test_name("FK_PROGRAM"),
                    "code": f"Z{suffix}P",
                    "department_id": b_resources["dept"],
                    "duration_semesters": 8,
                },
                "programs",
            ),
            (
                "/courses",
                {
                    "name": _unique_test_name("FK_COURSE"),
                    "code": f"Z{suffix}C",
                    "department_id": b_resources["dept"],
                    "credits": 3,
                    "course_type": "THEORY",
                },
                "courses",
            ),
            (
                "/students",
                {
                    "name": _unique_test_name("FK_STUDENT"),
                    "roll_number": _unique_test_name("FK_ROLL"),
                    "department_id": b_resources["dept"],
                    "program_id": b_resources["program"],
                    "semester": 1,
                    "branch": "CSE",
                    "password": "password123",
                },
                "students",
            ),
            (
                "/faculty",
                {
                    "name": _unique_test_name("FK_FACULTY"),
                    "email": f"fk_{suffix}@riverside.edu",
                    "department_id": b_resources["dept"],
                    "password": "password123",
                },
                "faculty",
            ),
            (
                "/parents",
                {
                    "name": _unique_test_name("FK_PARENT"),
                    "email": f"parent_fk_{suffix}@riverside.edu",
                    "student_ids": [b_resources["student"]],
                    "password": "password123",
                },
                "parents",
            ),
            (
                "/assessments",
                {
                    "course_id": b_resources["course"],
                    "name": _unique_test_name("FK_ASSESSMENT"),
                    "assessment_type": "MID",
                    "max_marks": 100,
                    "date": "2024-01-02",
                },
                "assessments",
            ),
            (
                "/results/enrollments",
                {
                    "student_id": a_throwaway_student,
                    "course_id": b_resources["course"],
                    "semester_id": foreign_semester_id,
                    "attendance_percentage": 90,
                    "study_hours_per_week": 10,
                    "assignment_completion_pct": 90,
                },
                "enrollments",
            ),
            (
                "/assessments/marks",
                {
                    "enrollment_id": foreign_enrollment_id,
                    "assessment_id": foreign_assessment_id,
                    "marks_obtained": 75,
                },
                "assessment_marks",
            ),
            (
                "/attendance",
                {
                    "enrollment_id": foreign_enrollment_id,
                    "date": "2024-01-02",
                    "status": "present",
                },
                "attendances",
            ),
            (
                "/results/course",
                {
                    "enrollment_id": foreign_enrollment_id,
                    "grade": "B",
                    "end_marks": 75,
                    "status": "PASS",
                },
                "course_results",
            ),
            (
                "/results/semester",
                {
                    "student_id": b_resources["student"],
                    "semester_id": foreign_semester_id,
                    "sgpa": 8,
                    "cgpa": 8,
                    "backlog_count": 0,
                    "current_failed_courses": 0,
                    "low_performance_course_count": 0,
                    "performance_trend": "STABLE",
                },
                "semester_results",
            ),
        ]

        with SessionLocal() as db:
            for key, model in (
                ("dept", Department),
                ("program", Program),
                ("course", Course),
                ("student", Student),
                ("faculty", Faculty),
                ("parent", Parent),
                ("semester", Semester),
                ("enrollment", Enrollment),
                ("assessment", Assessment),
            ):
                target = db.query(model).filter(
                    model.id == b_resources[key]
                ).one()
                assert str(target.institution_id) == str(
                    db.query(User.institution_id)
                    .filter(User.email == "admin@riverside.edu")
                    .one()[0]
                )
            assert str(
                db.query(Enrollment.student_id)
                .filter(Enrollment.id == b_resources["enrollment"])
                .one()[0]
            ) == b_resources["student"]
            assert str(
                db.query(Assessment.course_id)
                .filter(Assessment.id == b_resources["assessment"])
                .one()[0]
            ) == b_resources["course"]

        def matching_ids(db, key, payload):
            if key == "programs":
                query = db.query(Program.id).filter(Program.name == payload["name"])
                return {str(row[0]) for row in query}
            if key == "courses":
                query = db.query(Course.id).filter(Course.name == payload["name"])
                return {str(row[0]) for row in query}
            if key == "students":
                query = db.query(Student.id).filter(
                    Student.roll_number == payload["roll_number"]
                )
                return {str(row[0]) for row in query}
            if key == "faculty":
                query = db.query(Faculty.id).filter(Faculty.name == payload["name"])
                return {str(row[0]) for row in query}
            if key == "parents":
                query = db.query(Parent.id).filter(Parent.name == payload["name"])
                return {str(row[0]) for row in query}
            if key == "assessments":
                query = db.query(Assessment.id).filter(
                    Assessment.name == payload["name"]
                )
                return {str(row[0]) for row in query}
            if key == "enrollments":
                query = db.query(Enrollment.id).filter(
                    Enrollment.student_id == payload["student_id"],
                    Enrollment.course_id == payload["course_id"],
                    Enrollment.semester_id == payload["semester_id"],
                )
                return {str(row[0]) for row in query}
            if key == "assessment_marks":
                query = db.query(AssessmentMark.id).filter(
                    AssessmentMark.enrollment_id == payload["enrollment_id"],
                    AssessmentMark.assessment_id == payload["assessment_id"],
                )
                return {str(row[0]) for row in query}
            if key == "attendances":
                query = db.query(Attendance.id).filter(
                    Attendance.enrollment_id == payload["enrollment_id"],
                    Attendance.date == date.fromisoformat(payload["date"]),
                )
                return {str(row[0]) for row in query}
            if key == "course_results":
                query = db.query(CourseResult.id).filter(
                    CourseResult.enrollment_id == payload["enrollment_id"]
                )
                return {str(row[0]) for row in query}
            if key == "semester_results":
                query = db.query(SemesterResult.id).filter(
                    SemesterResult.student_id == payload["student_id"],
                    SemesterResult.semester_id == payload["semester_id"],
                )
                return {str(row[0]) for row in query}
            raise AssertionError(f"No before/after probe for {key}")

        for path, payload, key in payloads:
            with SessionLocal() as db:
                before_ids = matching_ids(db, key, payload)
            assert not before_ids, (
                f"Throwaway {key} probe already exists before request"
            )
            response = client.post(
                f"{API}{path}", json=payload, cookies=admin_a
            )
            if response.status_code == 201:
                created_id = _record_resource(tracked_resources, key, response)
                if key in ("faculty", "parents"):
                    tracked_resources["users"].add(response.json()["user_id"])
                elif key == "students":
                    with SessionLocal() as db:
                        created = db.query(Student).filter(
                            Student.id == created_id
                        ).one()
                        tracked_resources["users"].add(str(created.user_id))
                if key == "parents":
                    tracked_resources["parent_links"].add(
                        (created_id, b_resources["student"])
                    )
            with SessionLocal() as db:
                after_ids = matching_ids(db, key, payload)
                new_ids = after_ids - before_ids
                tracked_resources[key].update(new_ids)
                if key == "students":
                    tracked_resources["users"].update(
                        str(row[0])
                        for row in db.query(Student.user_id).filter(
                            Student.id.in_(new_ids)
                        )
                    )
                elif key == "faculty":
                    tracked_resources["users"].update(
                        str(row[0])
                        for row in db.query(Faculty.user_id).filter(
                            Faculty.id.in_(new_ids)
                        )
                    )
                elif key == "parents":
                    tracked_resources["users"].update(
                        str(row[0])
                        for row in db.query(Parent.user_id).filter(
                            Parent.id.in_(new_ids)
                        )
                    )
                    tracked_resources["parent_links"].update(
                        (parent_id, b_resources["student"])
                        for parent_id in new_ids
                        if db.query(ParentStudent).filter(
                            ParentStudent.parent_id == parent_id,
                            ParentStudent.student_id == b_resources["student"],
                        ).first()
                    )
            if after_ids != before_ids:
                pytest.exit(
                    "Confirmed forbidden foreign-key write: "
                    f"POST {API}{path} as Institution A admin; "
                    f"request={payload!r}; status={response.status_code}; "
                    f"exact new resource IDs={sorted(after_ids - before_ids)!r}"
                )
            assert response.status_code in (403, 404), (
                f"Foreign-key attack was not rejected for {path}: "
                f"status={response.status_code}, response={response.text[:300]!r}"
            )

    def test_spoofing(self, client, admin_a, admin_b, tracked_resources):
        # Rule 6: Spoofing body institution_id
        res_b = client.get(f"{API}/institutions/me", cookies=admin_b)
        b_inst_id = res_b.json()["id"]
        
        # Attack A's department creation by injecting B's institution_id
        payload = {
            "name": _unique_test_name("SPOOF"),
            "code": f"Z{uuid.uuid4().hex[:8]}",
            "institution_id": b_inst_id,
        }
        r = client.post(
            f"{API}/departments", json=payload, cookies=admin_a
        )
        assert r.status_code == 201
        new_id = _record_resource(tracked_resources, "departments", r)
        
        # Verify it did NOT land in B
        r_check = client.get(f"{API}/departments/{new_id}", cookies=admin_b)
        assert r_check.status_code in (403, 404), "LEAK: Spoofed record landed in B"
        

    def test_role_checks_inside_a(self, client, admin_a, student_a, student_a_2, parent_a):
        # Rule 7: Role checks inside A.
        # Student A cannot read Student A2's data.
        
        r = client.get(f"{API}/students/me", cookies=student_a)
        student_a_id = r.json()["id"]
        
        r2 = client.get(f"{API}/students/me", cookies=student_a_2)
        student_a2_id = r2.json()["id"]
        
        # Attack A2 as A1
        r_attack = client.get(f"{API}/students/{student_a2_id}/performance", cookies=student_a)
        assert r_attack.status_code in (403, 404)
        
        # Parent cannot read a student who is not their linked child
        # Get parent's children
        r_parent = client.get(f"{API}/parents/me", cookies=parent_a)
        linked_children = r_parent.json()["linked_student_ids"]
        
        assert student_a_id in linked_children, "Fixture needs student_a linked to parent_a"
        # Find an unlinked student (student_a_2)
        assert student_a2_id not in linked_children
        
        r_attack2 = client.get(f"{API}/students/{student_a2_id}", cookies=parent_a)
        assert r_attack2.status_code in (403, 404)

    def test_student_prediction_foreign_student_id(
        self, client, admin_a, admin_b, b_resources
    ):
        from app.models.student import Student
        from app.models.user import User

        with SessionLocal() as db:
            target = (
                db.query(Student)
                .join(User, Student.user_id == User.id)
                .filter(Student.id == b_resources["student"])
                .one()
            )
            assert str(target.institution_id) == str(
                db.query(User.institution_id)
                .filter(User.email == "admin@riverside.edu")
                .one()[0]
            )
        request_body = {
            "student_id": b_resources["student"],
            "enrollment_id": b_resources["enrollment"],
        }
        response = client.post(
            f"{API}/predictions/student", json=request_body, cookies=admin_a
        )
        assert response.status_code == 404, (
            "Expected foreign student to be rejected; "
            f"body={request_body!r}, status={response.status_code}, "
            f"response={response.text!r}"
        )

    def test_student_prediction_foreign_enrollment_id(
        self,
        client,
        admin_a,
        admin_b,
        b_resources,
        a_throwaway_student,
        tracked_resources,
    ):
        from app.models.enrollment import Enrollment
        from app.models.prediction import PredictionResult
        from app.models.user import User

        with SessionLocal() as db:
            enrollment = (
                db.query(Enrollment)
                .filter(Enrollment.id == b_resources["enrollment"])
                .one()
            )
            institution_b_id = db.query(User.institution_id).filter(
                User.email == "admin@riverside.edu"
            ).one()[0]
            assert enrollment.institution_id == institution_b_id
            assert str(enrollment.student_id) == b_resources["student"]
            b_prediction_before = db.query(PredictionResult).filter(
                PredictionResult.student_id == enrollment.student_id
            ).all()
            a_prediction_before = {
                str(prediction.id)
                for prediction in db.query(PredictionResult)
                .filter(PredictionResult.student_id == a_throwaway_student)
                .all()
            }

        request_body = {
            "student_id": a_throwaway_student,
            "enrollment_id": b_resources["enrollment"],
        }
        try:
            response = client.post(
                f"{API}/predictions/student", json=request_body, cookies=admin_a
            )
        finally:
            with SessionLocal() as db:
                b_predictions_after = db.query(PredictionResult).filter(
                    PredictionResult.student_id == b_resources["student"]
                ).all()
                a_predictions = db.query(PredictionResult).filter(
                    PredictionResult.student_id == a_throwaway_student
                ).all()
                new_a_predictions = {
                    str(prediction.id) for prediction in a_predictions
                } - a_prediction_before
                new_b_predictions = {
                    str(prediction.id) for prediction in b_predictions_after
                } - {str(prediction.id) for prediction in b_prediction_before}
                tracked_resources["predictions"].update(new_a_predictions)
                tracked_resources["predictions"].update(new_b_predictions)

        evidence = (
            f"request={request_body!r}; status={response.status_code}; "
            f"response={response.text!r}; "
            f"B prediction IDs before={[str(p.id) for p in b_prediction_before]}, "
            f"after={[str(p.id) for p in b_predictions_after]}; "
            f"A throwaway prediction IDs before={sorted(a_prediction_before)}, "
            f"after={[str(p.id) for p in a_predictions]}"
        )
        if new_b_predictions:
            pytest.exit(f"Confirmed cross-tenant prediction mutation: {evidence}")
        assert response.status_code == 404, (
            "Foreign enrollment_id must be rejected; a 200 is never an isolation "
            f"pass. {evidence}"
        )
        assert b_resources["student"] not in response.text, evidence
        assert b_resources["enrollment"] not in response.text, evidence
        assert {str(prediction.id) for prediction in a_predictions} == a_prediction_before, evidence
        assert {
            str(prediction.id) for prediction in b_predictions_after
        } == {str(prediction.id) for prediction in b_prediction_before}, evidence

    def test_student_prediction_rejects_mismatched_same_tenant_enrollment(
        self,
        client,
        admin_a,
        a_throwaway_student,
        a_throwaway_enrollment,
        tracked_resources,
    ):
        from app.models.prediction import PredictionResult
        from app.models.student import Student

        with SessionLocal() as db:
            seeded = (
                db.query(Student)
                .filter(Student.roll_number == "20231CSE0260")
                .one()
            )
            department_id = str(seeded.department_id)
            program_id = str(seeded.program_id) if seeded.program_id else None
        second_payload = {
            "name": _unique_test_name("A_SECOND_STUDENT"),
            "roll_number": _unique_test_name("A_SECOND_ROLL"),
            "department_id": department_id,
            "program_id": program_id,
            "semester": 1,
            "branch": "CSE",
            "password": "password123",
        }
        second_response = client.post(
            f"{API}/students", json=second_payload, cookies=admin_a
        )
        assert second_response.status_code == 201, second_response.text
        second_student_id = _record_resource(
            tracked_resources, "students", second_response
        )
        with SessionLocal() as db:
            second_student = db.query(Student).filter(
                Student.id == second_student_id
            ).one()
            tracked_resources["users"].add(str(second_student.user_id))
            first_predictions_before = {
                str(row.id)
                for row in db.query(PredictionResult).filter(
                    PredictionResult.student_id == a_throwaway_student
                )
            }
            second_predictions_before = {
                str(row.id)
                for row in db.query(PredictionResult).filter(
                    PredictionResult.student_id == second_student_id
                )
            }

        enrollment_proof = client.get(
            f"{API}/results/enrollments?student_id={a_throwaway_student}",
            cookies=admin_a,
        )
        assert enrollment_proof.status_code == 200, enrollment_proof.text
        assert any(
            row["id"] == a_throwaway_enrollment
            for row in enrollment_proof.json()["data"]
        )
        body = {
            "student_id": second_student_id,
            "enrollment_id": a_throwaway_enrollment,
        }
        response = client.post(
            f"{API}/predictions/student", json=body, cookies=admin_a
        )
        assert response.status_code == 404, (
            f"Same-tenant mismatched enrollment must be rejected: "
            f"body={body!r}, response={response.status_code} {response.text!r}"
        )
        with SessionLocal() as db:
            first_after = {
                str(row.id)
                for row in db.query(PredictionResult).filter(
                    PredictionResult.student_id == a_throwaway_student
                )
            }
            second_after = {
                str(row.id)
                for row in db.query(PredictionResult).filter(
                    PredictionResult.student_id == second_student_id
                )
            }
        assert first_after == first_predictions_before
        assert second_after == second_predictions_before
        assert a_throwaway_student not in response.text
        assert a_throwaway_enrollment not in response.text

    def test_student_prediction_accepts_same_tenant_enrollment(
        self,
        client,
        admin_a,
        a_throwaway_student,
        a_throwaway_enrollment,
        tracked_resources,
    ):
        from app.models.enrollment import Enrollment
        from app.models.prediction import PredictionResult

        with SessionLocal() as db:
            enrollment = db.query(Enrollment).filter(
                Enrollment.id == a_throwaway_enrollment
            ).one()
            before_ids = {
                str(row.id)
                for row in db.query(PredictionResult).filter(
                    PredictionResult.student_id == a_throwaway_student
                )
            }
            semester_id = str(enrollment.semester_id)
            course_id = str(enrollment.course_id)
            institution_id = str(enrollment.institution_id)
            assert str(enrollment.student_id) == a_throwaway_student

        newer_enrollment = client.post(
            f"{API}/results/enrollments",
            json={
                "student_id": a_throwaway_student,
                "course_id": course_id,
                "semester_id": semester_id,
                "attendance_percentage": 5,
                "study_hours_per_week": 59,
                "assignment_completion_pct": 10,
            },
            cookies=admin_a,
        )
        assert newer_enrollment.status_code == 201, newer_enrollment.text
        newer_enrollment_id = _record_resource(
            tracked_resources, "enrollments", newer_enrollment
        )
        assert newer_enrollment_id != a_throwaway_enrollment

        try:
            response = client.post(
                f"{API}/predictions/student",
                json={
                    "student_id": a_throwaway_student,
                    "enrollment_id": a_throwaway_enrollment,
                },
                cookies=admin_a,
            )
        finally:
            with SessionLocal() as db:
                after = db.query(PredictionResult).filter(
                    PredictionResult.student_id == a_throwaway_student
                ).all()
            new_ids = {str(row.id) for row in after} - before_ids
            tracked_resources["predictions"].update(new_ids)
        assert response.status_code == 200, response.text
        assert response.json()["student_id"] == a_throwaway_student
        assert len(new_ids) == 1
        prediction = next(row for row in after if str(row.id) in new_ids)
        assert str(prediction.semester_id) == semester_id
        assert str(prediction.institution_id) == institution_id
        assert prediction.input_features["attendance_percentage_raw"] == 90
        assert prediction.input_features["study_hours_per_week_raw"] == 10
        assert (
            prediction.input_features["assignment_completion_percentage_raw"]
            == 90
        )

    def test_student_report_cross_tenant_and_role_access(
        self, client, admin_a, admin_b, student_a, student_a_2, parent_a, b_resources
    ):
        b_student = client.get(
            f"{API}/students/{b_resources['student']}", cookies=admin_b
        )
        assert b_student.status_code == 200, b_student.text
        foreign_identity = (
            b_student.json()["name"],
            b_student.json()["roll_number"],
            b_resources["student"],
        )

        for cookies in (admin_a, parent_a):
            response = client.get(
                f"{API}/reports/student/{b_resources['student']}", cookies=cookies
            )
            assert response.status_code == 404, (
                f"Foreign student HTML report returned {response.status_code}: "
                f"{response.text[:500]!r}"
            )
            assert all(identity not in response.text for identity in foreign_identity)

        a2 = client.get(f"{API}/students/me", cookies=student_a_2)
        assert a2.status_code == 200, a2.text
        response = client.get(
            f"{API}/reports/student/{a2.json()['id']}", cookies=student_a
        )
        assert response.status_code in (403, 404), response.text[:500]

        parent_profile = client.get(f"{API}/parents/me", cookies=parent_a)
        assert parent_profile.status_code == 200, parent_profile.text
        response = client.get(
            f"{API}/reports/student/{b_resources['student']}", cookies=parent_a
        )
        assert response.status_code == 404, response.text[:500]

    def test_foreign_faculty_and_parent_lists(
        self, client, admin_a, admin_b, b_resources
    ):
        for route, target_id in (
            (f"/faculty/{b_resources['faculty']}/students", b_resources["faculty"]),
            (f"/parents/{b_resources['parent']}/children", b_resources["parent"]),
        ):
            response_b = client.get(f"{API}{route}", cookies=admin_b)
            assert response_b.status_code == 200, response_b.text
            response_a = client.get(f"{API}{route}", cookies=admin_a)
            assert response_a.status_code == 404, response_a.text
            assert target_id not in response_a.text
            assert b_resources["student"] not in response_a.text

    def test_foreign_course_rosters_are_rejected(
        self, client, admin_a, admin_b, b_resources, tracked_resources
    ):
        from app.models.enrollment import Assessment
        from app.models.user import User

        query_routes = (
            (
                "/assessments/marks-grid",
                {
                    "course_id": b_resources["course"],
                    "semester_id": b_resources["semester"],
                },
            ),
            (
                "/assessments/roster",
                {
                    "course_id": b_resources["course"],
                    "assessment_id": b_resources["assessment"],
                    "semester_id": b_resources["semester"],
                },
            ),
            (
                "/attendance/roster",
                {
                    "course_id": b_resources["course"],
                    "semester_id": b_resources["semester"],
                },
            ),
        )
        for path, params in query_routes:
            if path == "/assessments/marks-grid":
                with SessionLocal() as db:
                    before_assessment_ids = {
                        str(row[0])
                        for row in db.query(Assessment.id).filter(
                            Assessment.course_id == b_resources["course"],
                            Assessment.institution_id
                            == db.query(User.institution_id)
                            .filter(User.email == "admin@riverside.edu")
                            .scalar_subquery(),
                        )
                    }
                try:
                    as_b = client.get(
                        f"{API}{path}", params=params, cookies=admin_b
                    )
                finally:
                    with SessionLocal() as db:
                        after_assessment_ids = {
                            str(row[0])
                            for row in db.query(Assessment.id).filter(
                                Assessment.course_id == b_resources["course"]
                            )
                        }
                    tracked_resources["assessments"].update(
                        after_assessment_ids - before_assessment_ids
                    )
            else:
                as_b = client.get(
                    f"{API}{path}", params=params, cookies=admin_b
                )
            assert as_b.status_code == 200, as_b.text
            assert b_resources["student"] in as_b.text
            response = client.get(
                f"{API}{path}", params=params, cookies=admin_a
            )
            assert response.status_code == 404, (
                f"Foreign roster query {path} was not rejected: "
                f"{response.status_code} {response.text[:300]!r}"
            )
            assert b_resources["student"] not in response.text
            assert b_resources["course"] not in response.text

    def test_identity_and_student_self_service_routes_are_scoped(
        self,
        client,
        admin_a,
        admin_b,
        a_throwaway_student,
        a_throwaway_enrollment,
        tracked_resources,
    ):
        from app.models.enrollment import Enrollment
        from app.models.prediction import StudentGoal
        from app.models.user import User

        institution_a = client.get(f"{API}/institutions/me", cookies=admin_a)
        assert institution_a.status_code == 200, institution_a.text
        identity = client.get(f"{API}/auth/me", cookies=admin_a)
        assert identity.status_code == 200, identity.text
        with SessionLocal() as db:
            institution_a_id = str(
                db.query(User.institution_id)
                .filter(User.email == "admin@demo.com")
                .one()[0]
            )
            institution_b_id = str(
                db.query(User.institution_id)
                .filter(User.email == "admin@riverside.edu")
                .one()[0]
            )
        assert institution_a.json()["id"] == institution_a_id
        assert identity.json()["institution_id"] == institution_a_id
        institution_b = client.get(f"{API}/institutions/me", cookies=admin_b)
        assert institution_b.status_code == 200, institution_b.text
        assert institution_b.json()["id"] == institution_b_id
        assert institution_a_id != institution_b_id
        with SessionLocal() as db:
            assert db.query(Enrollment).filter(
                Enrollment.id == a_throwaway_enrollment,
                Enrollment.student_id == a_throwaway_student,
                Enrollment.institution_id == institution_a_id,
            ).one()

        profile = client.get(
            f"{API}/students/{a_throwaway_student}", cookies=admin_a
        )
        assert profile.status_code == 200, profile.text
        student_cookies = _login(
            client, profile.json()["roll_number"], "password123", role="student"
        ).cookies
        for path in ("/students/me/performance", "/students/me/goal-guidance"):
            response = client.get(f"{API}{path}", cookies=student_cookies)
            assert response.status_code == 200, response.text
            if path.endswith("/performance"):
                assert response.json()["student_id"] == a_throwaway_student
            assert institution_b_id not in response.text

        goal_payload = {
            "goal_type": "cgpa",
            "target_value": 8.5,
            "notes": _unique_test_name("A_GOAL"),
        }
        goal_response = client.post(
            f"{API}/goals", json=goal_payload, cookies=student_cookies
        )
        assert goal_response.status_code == 201, goal_response.text
        goal_id = _record_resource(
            tracked_resources, "student_goals", goal_response
        )
        with SessionLocal() as db:
            goal = db.query(StudentGoal).filter(StudentGoal.id == goal_id).one()
            assert str(goal.student_id) == a_throwaway_student
            assert str(goal.institution_id) == institution_a_id

        for path in (
            "/predictions/performance",
            "/predictions/pass-fail",
            "/predictions/risk",
            "/predictions/all",
        ):
            payload = {
                "CA_mark": 80,
                "MID_mark": 75,
                "attendance_percentage": 90,
                "study_hours_per_week": 10,
                "assignment_completion_pct": 90,
                "previous_sgpa": 8,
                "previous_cgpa": 8,
                "backlog_count": 0,
                "course_credits": 3,
                "course_type": "THEORY",
                "branch": "CSE",
                "semester": 1,
            }
            if path.endswith("/risk"):
                payload = {
                    "attendance_percentage": 90,
                    "previous_cgpa": 8,
                    "backlog_count": 0,
                    "current_failed_courses": 0,
                    "low_performance_course_count": 0,
                    "study_hours_per_week": 10,
                    "assignment_completion_percentage": 90,
                    "performance_trend": "STABLE",
                }
            for cookies in (student_cookies, _login(
                client, "parent@demo.com", "parent123", role="parent"
            ).cookies):
                response = client.post(
                    f"{API}{path}", json=payload, cookies=cookies
                )
                assert response.status_code == 403, (
                    f"{path} should reject student/parent role: "
                    f"{response.status_code} {response.text[:300]!r}"
                )

    def test_user_creation_is_limited_to_admin_tenant(
        self,
        client,
        admin_a,
        admin_b,
        student_a,
        parent_a,
        tracked_resources,
    ):
        from app.models.user import User

        email = f"ZZ_TEST_USER_{uuid.uuid4().hex[:12]}@gmail.com"
        password = uuid.uuid4().hex
        with SessionLocal() as db:
            assert db.query(User).filter(User.email == email).count() == 0
            institution_a_id = db.query(User.institution_id).filter(
                User.email == "admin@demo.com"
            ).one()[0]
        payload = {
            "email": email,
            "password": password,
            "role": "institution_admin",
        }
        for cookies in (student_a, parent_a):
            response = client.post(
                f"{API}/users", json=payload, cookies=cookies
            )
            assert response.status_code == 403, (
                f"Non-admin POST /users was not rejected: "
                f"{response.status_code} {response.text[:300]!r}"
            )
        response = client.post(
            f"{API}/users",
            json={**payload, "institution_id": str(uuid.uuid4())},
            cookies=admin_a,
        )
        assert response.status_code == 201, response.text
        user_id = _record_resource(tracked_resources, "users", response)
        with SessionLocal() as db:
            user = db.query(User).filter(User.id == user_id).one()
            assert user.email == email
            assert str(user.institution_id) == str(institution_a_id)
        own_read = client.get(f"{API}/users/{user_id}", cookies=admin_a)
        assert own_read.status_code == 200, own_read.text
        foreign_read = client.get(f"{API}/users/{user_id}", cookies=admin_b)
        assert foreign_read.status_code == 404, foreign_read.text
        assert email not in foreign_read.text

    def test_logout_clears_both_authentication_cookies(
        self, client, student_a
    ):
        response = client.post(f"{API}/auth/logout", cookies=student_a)
        assert response.status_code == 200, response.text
        set_cookies = response.headers.get_list("set-cookie")
        assert len(set_cookies) == 2, set_cookies
        assert any(
            cookie.startswith("access_token=") and "max-age=0" in cookie.lower()
            for cookie in set_cookies
        ), set_cookies
        assert any(
            cookie.startswith("refresh_token=") and "max-age=0" in cookie.lower()
            for cookie in set_cookies
        ), set_cookies

    def test_bulk_write_routes_reject_foreign_enrollments(
        self, client, admin_a, admin_b, b_resources
    ):
        from app.models.enrollment import AssessmentMark, Attendance, Enrollment

        mark_proof = client.get(
            f"{API}/assessments/marks?enrollment_id={b_resources['enrollment']}",
            cookies=admin_b,
        )
        assert mark_proof.status_code == 200, mark_proof.text
        mark = next(
            (
                row
                for row in mark_proof.json()["data"]
                if row["assessment_id"] == b_resources["assessment"]
            ),
            None,
        )
        assert mark is not None
        with SessionLocal() as db:
            before_mark = db.query(AssessmentMark).filter(
                AssessmentMark.id == mark["id"]
            ).one().marks_obtained
            before_attendance = db.query(Enrollment).filter(
                Enrollment.id == b_resources["enrollment"]
            ).one().attendance_percentage
            before_attendance_rows = {
                str(row.id): row.status
                for row in db.query(Attendance).filter(
                    Attendance.enrollment_id == b_resources["enrollment"]
                )
            }
        body = {
            "entries": [
                {
                    "enrollment_id": b_resources["enrollment"],
                    "assessment_id": b_resources["assessment"],
                    "marks_obtained": before_mark - 1,
                }
            ]
        }
        for path, payload in (
            ("/assessments/marks/bulk", body),
            (
                "/assessments/marks/bulk-grid",
                {
                    **body,
                    "recalculate_results": False,
                    "trigger_predictions": False,
                },
            ),
        ):
            response = client.post(
                f"{API}{path}", json=payload, cookies=admin_a
            )
            with SessionLocal() as db:
                after_mark = db.query(AssessmentMark).filter(
                    AssessmentMark.id == mark["id"]
                ).one().marks_obtained
            if after_mark != before_mark:
                pytest.exit(
                    f"Confirmed foreign bulk mark mutation: POST {API}{path}; "
                    "Institution A admin modified a throwaway Institution B mark"
                )
            assert response.status_code == 404, (
                f"Expected foreign enrollment rejection at {path}: "
                f"{response.status_code} {response.text[:300]!r}"
            )

        attendance_payload = {
            "entries": [
                {
                    "enrollment_id": b_resources["enrollment"],
                    "attendance_percentage": 1,
                }
            ]
        }
        response = client.post(
            f"{API}/attendance/bulk",
            json=attendance_payload,
            cookies=admin_a,
        )
        with SessionLocal() as db:
            after_attendance = db.query(Enrollment).filter(
                Enrollment.id == b_resources["enrollment"]
            ).one().attendance_percentage
            after_attendance_rows = {
                str(row.id): row.status
                for row in db.query(Attendance).filter(
                    Attendance.enrollment_id == b_resources["enrollment"]
                )
            }
        if (
            after_attendance != before_attendance
            or after_attendance_rows != before_attendance_rows
        ):
            pytest.exit(
                "Confirmed foreign bulk attendance mutation: "
                f"POST {API}/attendance/bulk; Institution A admin modified "
                "throwaway Institution B academic data"
            )
        assert response.status_code == 404, (
            f"Expected foreign enrollment rejection at /attendance/bulk: "
            f"{response.status_code} {response.text[:300]!r}"
        )

    @pytest.mark.parametrize(
        "kind,faculty_side,student_side",
        [
            ("faculty", "a", "b"),
            ("faculty", "b", "a"),
            ("faculty", "b", "b"),
            ("parent", "a", "b"),
            ("parent", "b", "a"),
            ("parent", "b", "b"),
        ],
    )
    def test_cross_tenant_link_creation_rejections(
        self,
        client,
        admin_a,
        admin_b,
        b_resources,
        kind,
        faculty_side,
        student_side,
        student_a,
        tracked_resources,
    ):
        if faculty_side == "b":
            related_id = b_resources["faculty" if kind == "faculty" else "parent"]
            proof = client.get(
                f"{API}/faculty/{related_id}" if kind == "faculty"
                else f"{API}/parents/{related_id}",
                cookies=admin_b,
            )
            assert proof.status_code == 200, proof.text
        else:
            profile_path = f"{API}/faculty"
            proof = client.get(profile_path, cookies=admin_a)
            assert proof.status_code == 200, proof.text
            if kind == "faculty":
                related_id = proof.json()["data"][0]["id"]
            else:
                proof = client.get(f"{API}/parents", cookies=admin_a)
                assert proof.status_code == 200, proof.text
                related_id = proof.json()["data"][0]["id"]

        if student_side == "b":
            student_id = b_resources["student"]
            proof = client.get(f"{API}/students/{student_id}", cookies=admin_b)
        else:
            profile = client.get(f"{API}/students/me", cookies=student_a)
            assert profile.status_code == 200, profile.text
            student_id = profile.json()["id"]
            proof = client.get(f"{API}/students/{student_id}", cookies=admin_a)
        assert proof.status_code == 200, proof.text

        path = (
            f"/faculty/{related_id}/students/{student_id}"
            if kind == "faculty"
            else f"/parents/{related_id}/children/{student_id}"
        )
        response = client.post(f"{API}{path}", cookies=admin_a)
        if response.status_code == 201:
            from app.models.parent import FacultyStudent, ParentStudent

            link_model = FacultyStudent if kind == "faculty" else ParentStudent
            left_column = link_model.faculty_id if kind == "faculty" else link_model.parent_id
            link_pairs = (
                tracked_resources["faculty_links"]
                if kind == "faculty"
                else tracked_resources["parent_links"]
            )
            link_pairs.add((related_id, student_id))
            with SessionLocal() as db:
                created_link = (
                    db.query(link_model)
                    .filter(left_column == related_id, link_model.student_id == student_id)
                    .first()
                )
            if created_link:
                pytest.exit(
                    "Confirmed forbidden cross-tenant link creation: "
                    f"POST {path}, role=institution_admin, institution=A, "
                    f"status={response.status_code}, response={response.text!r}"
                )
        assert response.status_code == 404, (
            f"Cross-tenant {kind} link was not rejected: POST {path}; "
            f"status={response.status_code}, response={response.text!r}"
        )

    def test_cross_tenant_link_deletes_preserve_b_links(
        self, client, admin_a, admin_b, b_resources
    ):
        for path, route in (
            (
                f"/faculty/{b_resources['faculty']}/students/{b_resources['student']}",
                f"/faculty/{b_resources['faculty']}/students",
            ),
            (
                f"/parents/{b_resources['parent']}/children/{b_resources['student']}",
                f"/parents/{b_resources['parent']}/children",
            ),
        ):
            before = client.get(f"{API}{route}", cookies=admin_b)
            assert before.status_code == 200, before.text
            assert b_resources["student"] in before.json()
            response = client.delete(f"{API}{path}", cookies=admin_a)
            after = client.get(f"{API}{route}", cookies=admin_b)
            assert after.status_code == 200, after.text
            if b_resources["student"] not in after.json():
                pytest.exit(
                    "Confirmed forbidden cross-tenant link deletion: "
                    f"DELETE {path}, role=institution_admin, institution=A, "
                    f"status={response.status_code}, B relationship response={after.text!r}"
                )
            assert response.status_code == 404, (
                f"Expected cross-tenant DELETE rejection: {path}; "
                f"status={response.status_code}, response={response.text!r}"
            )
            assert b_resources["student"] in after.json()

    def test_prediction_regeneration_safe_roles(
        self,
        client,
        admin_b,
        student_a,
        parent_a,
        b_resources,
        tracked_resources,
    ):
        from app.models.prediction import PredictionResult
        from app.models.user import User

        email = f"{uuid.uuid4().hex[:16]}@riverside.edu"
        response = client.post(
            f"{API}/faculty",
            json={
            "name": _unique_test_name("UNASSIGNED_FACULTY"),
            "email": email,
            "department_id": b_resources["dept"],
            "password": "password123",
            },
            cookies=admin_b,
        )
        assert response.status_code == 201, response.text
        faculty_id = _record_resource(tracked_resources, "faculty", response)
        tracked_resources["users"].add(response.json()["user_id"])

        faculty_profile = client.get(
            f"{API}/faculty/{faculty_id}", cookies=admin_b
        )
        assert faculty_profile.status_code == 200, faculty_profile.text
        assigned = client.get(
            f"{API}/faculty/{faculty_id}/students", cookies=admin_b
        )
        assert assigned.status_code == 200, assigned.text
        assert assigned.json() == []
        with SessionLocal() as db:
            institution_b_id = db.query(User.institution_id).filter(
            User.email == "admin@riverside.edu"
            ).one()[0]
            assert str(db.query(User.institution_id).filter(
            User.id == faculty_profile.json()["user_id"]
            ).one()[0]) == str(institution_b_id)
            prediction_count_before = db.query(PredictionResult).filter(
            PredictionResult.institution_id == institution_b_id
            ).count()

        faculty_cookies = _login(
            client, email, "password123", role="faculty"
        ).cookies
        response = client.post(
            f"{API}/predictions/regenerate", cookies=faculty_cookies
        )
        assert response.status_code == 200, response.text
        assert response.json()["regenerated_count"] == 0
        with SessionLocal() as db:
            prediction_count_after_faculty = db.query(PredictionResult).filter(
            PredictionResult.institution_id == institution_b_id
            ).count()
        assert prediction_count_after_faculty == prediction_count_before

        with SessionLocal() as db:
            a_predictions_before = db.query(PredictionResult).filter(
            PredictionResult.institution_id
            == db.query(User.institution_id)
            .filter(User.email == "admin@demo.com")
            .one()[0]
            ).count()
        for cookies in (student_a, parent_a):
            response = client.post(
            f"{API}/predictions/regenerate", cookies=cookies
            )
            assert response.status_code == 403, response.text
        with SessionLocal() as db:
            a_predictions_after = db.query(PredictionResult).filter(
            PredictionResult.institution_id
            == db.query(User.institution_id)
            .filter(User.email == "admin@demo.com")
            .one()[0]
            ).count()
        assert a_predictions_after == a_predictions_before
