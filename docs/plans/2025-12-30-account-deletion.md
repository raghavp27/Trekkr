# Account Deletion Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement secure account deletion endpoint with password verification and explicit confirmation, leveraging database CASCADE constraints for automatic data cleanup.

**Architecture:** RESTful DELETE endpoint at `/api/auth/account` with two-factor confirmation (password + "DELETE" text). Hard delete of User record triggers CASCADE deletion of related records (Device, UserCellVisit, IngestBatch, UserAchievement) while preserving global H3 cell registry.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic v2, pytest, PostgreSQL with existing CASCADE constraints

---

## Context

**Design Document:** `docs/plans/2025-12-30-account-deletion-design.md`

**Related Files:**
- Models: `backend/models/user.py`, `backend/models/device.py`, `backend/models/visits.py`, `backend/models/achievements.py`
- Auth Router: `backend/routers/auth.py`
- Auth Schemas: `backend/schemas/auth.py`
- Auth Service: `backend/services/auth.py`

**Database Constraints:** Existing CASCADE constraints on foreign keys handle automatic cleanup - no migration needed.

**Testing Database:** Use existing test setup from `backend/tests/conftest.py`

---

## Task 1: Add AccountDeleteRequest Schema

**Files:**
- Modify: `backend/schemas/auth.py`
- Test: `backend/tests/test_schemas_auth.py` (create if needed)

**Step 1: Write failing test for schema validation**

Create `backend/tests/test_schemas_auth.py`:

```python
import pytest
from pydantic import ValidationError
from schemas.auth import AccountDeleteRequest


def test_account_delete_request_valid():
    """Test valid account deletion request."""
    request = AccountDeleteRequest(
        password="MyPassword123",
        confirmation="DELETE"
    )
    assert request.password == "MyPassword123"
    assert request.confirmation == "DELETE"


def test_account_delete_request_wrong_confirmation():
    """Test that confirmation must be exactly 'DELETE'."""
    with pytest.raises(ValidationError) as exc_info:
        AccountDeleteRequest(
            password="MyPassword123",
            confirmation="delete"  # lowercase should fail
        )

    errors = exc_info.value.errors()
    assert any(
        "Confirmation must be exactly 'DELETE'" in str(error.get("msg", ""))
        for error in errors
    )


def test_account_delete_request_missing_confirmation():
    """Test that confirmation field is required."""
    with pytest.raises(ValidationError):
        AccountDeleteRequest(password="MyPassword123")


def test_account_delete_request_missing_password():
    """Test that password field is required."""
    with pytest.raises(ValidationError):
        AccountDeleteRequest(confirmation="DELETE")
```

**Step 2: Run tests to verify they fail**

```bash
cd backend
TEST_DATABASE_URL="postgresql+psycopg2://appuser:apppass@localhost:5434/appdb_test" python -m pytest tests/test_schemas_auth.py -v
```

Expected: FAIL with "cannot import name 'AccountDeleteRequest'"

**Step 3: Implement AccountDeleteRequest schema**

Add to `backend/schemas/auth.py`:

```python
class AccountDeleteRequest(BaseModel):
    """Request schema for account deletion.

    Requires both password verification and explicit confirmation
    to prevent accidental account deletion.
    """

    password: str
    confirmation: str

    @field_validator("confirmation")
    @classmethod
    def validate_confirmation(cls, v: str) -> str:
        """Ensure confirmation is exactly 'DELETE' (case-sensitive)."""
        if v != "DELETE":
            raise ValueError("Confirmation must be exactly 'DELETE'")
        return v
```

**Step 4: Run tests to verify they pass**

```bash
TEST_DATABASE_URL="postgresql+psycopg2://appuser:apppass@localhost:5434/appdb_test" python -m pytest tests/test_schemas_auth.py -v
```

Expected: PASS (4 tests)

**Step 5: Commit**

```bash
git add backend/schemas/auth.py backend/tests/test_schemas_auth.py
git commit -m "feat: add AccountDeleteRequest schema with validation

- Password and confirmation fields required
- Confirmation must be exactly 'DELETE' (case-sensitive)
- Pydantic validator enforces confirmation text
- 4 tests covering valid/invalid cases

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 2: Implement DELETE /api/auth/account Endpoint

**Files:**
- Modify: `backend/routers/auth.py`
- Test: `backend/tests/test_auth_delete_account.py` (create)

**Step 1: Write failing test for successful deletion**

Create `backend/tests/test_auth_delete_account.py`:

```python
import pytest
from fastapi import status
from models.user import User
from models.device import Device
from models.visits import UserCellVisit, IngestBatch
from models.achievements import UserAchievement, Achievement
from models.geo import H3Cell


def test_delete_account_success(client, test_user, auth_headers):
    """Test successful account deletion with valid password and confirmation."""
    response = client.delete(
        "/api/auth/account",
        json={"password": "TestPass123", "confirmation": "DELETE"},
        headers=auth_headers,
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert response.content == b""  # No response body for 204

    # Verify token is now invalid (user deleted)
    response = client.get("/api/auth/me", headers=auth_headers)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_delete_account_wrong_password(client, test_user, auth_headers):
    """Test deletion fails with incorrect password."""
    response = client.delete(
        "/api/auth/account",
        json={"password": "WrongPassword123", "confirmation": "DELETE"},
        headers=auth_headers,
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Invalid password" in response.json()["detail"]

    # Verify user still exists
    response = client.get("/api/auth/me", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK


def test_delete_account_unauthenticated(client):
    """Test deletion requires authentication."""
    response = client.delete(
        "/api/auth/account",
        json={"password": "TestPass123", "confirmation": "DELETE"},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
```

**Step 2: Run tests to verify they fail**

```bash
TEST_DATABASE_URL="postgresql+psycopg2://appuser:apppass@localhost:5434/appdb_test" python -m pytest tests/test_auth_delete_account.py::test_delete_account_success -v
```

Expected: FAIL with "404 Not Found" (endpoint doesn't exist)

**Step 3: Implement delete_account endpoint**

Add to `backend/routers/auth.py`:

First, add import at the top:
```python
from fastapi.responses import Response
from schemas.auth import AccountDeleteRequest  # Add to existing imports
```

Then add endpoint:
```python
@router.delete("/account", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    request: AccountDeleteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Permanently delete the authenticated user's account and all associated data.

    This action is irreversible. Deletes:
    - User account and credentials
    - Device record
    - All location visit history
    - All achievement unlocks
    - All ingestion batch records

    Global H3 cell registry is preserved (shared across users).

    Example request:
    ```json
    {
      "password": "MySecurePass123",
      "confirmation": "DELETE"
    }
    ```

    The confirmation field must contain exactly "DELETE" (case-sensitive).

    Requires: Authorization header with Bearer token
    Body: password (current password), confirmation (must be "DELETE")
    Returns: 204 No Content on success
    Raises:
      - 401 Unauthorized if password is incorrect
      - 422 Validation Error if confirmation is invalid
    """
    # Verify current password
    if not verify_password(request.password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid password",
        )

    # Delete user (CASCADE constraints handle related data automatically)
    db.delete(current_user)
    db.commit()

    # Return 204 No Content (no response body)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

**Step 4: Run tests to verify they pass**

```bash
TEST_DATABASE_URL="postgresql+psycopg2://appuser:apppass@localhost:5434/appdb_test" python -m pytest tests/test_auth_delete_account.py::test_delete_account_success -v
TEST_DATABASE_URL="postgresql+psycopg2://appuser:apppass@localhost:5434/appdb_test" python -m pytest tests/test_auth_delete_account.py::test_delete_account_wrong_password -v
TEST_DATABASE_URL="postgresql+psycopg2://appuser:apppass@localhost:5434/appdb_test" python -m pytest tests/test_auth_delete_account.py::test_delete_account_unauthenticated -v
```

Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add backend/routers/auth.py backend/tests/test_auth_delete_account.py
git commit -m "feat: implement DELETE /api/auth/account endpoint

- Password verification before deletion
- Returns 204 No Content on success
- Leverages database CASCADE for data cleanup
- 3 tests: success, wrong password, unauthenticated

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 3: Add Validation Error Tests

**Files:**
- Modify: `backend/tests/test_auth_delete_account.py`

**Step 1: Write tests for Pydantic validation errors**

Add to `backend/tests/test_auth_delete_account.py`:

```python
def test_delete_account_wrong_confirmation(client, test_user, auth_headers):
    """Test deletion fails with incorrect confirmation text."""
    response = client.delete(
        "/api/auth/account",
        json={"password": "TestPass123", "confirmation": "delete"},  # lowercase
        headers=auth_headers,
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # Verify error message mentions confirmation validation
    errors = response.json()["detail"]
    assert any(
        "Confirmation must be exactly 'DELETE'" in str(error)
        for error in errors
    )

    # Verify user still exists
    response = client.get("/api/auth/me", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK


def test_delete_account_missing_confirmation(client, test_user, auth_headers):
    """Test deletion fails with missing confirmation field."""
    response = client.delete(
        "/api/auth/account",
        json={"password": "TestPass123"},
        headers=auth_headers,
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # Verify user still exists
    response = client.get("/api/auth/me", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK


def test_delete_account_missing_password(client, test_user, auth_headers):
    """Test deletion fails with missing password field."""
    response = client.delete(
        "/api/auth/account",
        json={"confirmation": "DELETE"},
        headers=auth_headers,
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # Verify user still exists
    response = client.get("/api/auth/me", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK
```

**Step 2: Run tests to verify they pass**

```bash
TEST_DATABASE_URL="postgresql+psycopg2://appuser:apppass@localhost:5434/appdb_test" python -m pytest tests/test_auth_delete_account.py::test_delete_account_wrong_confirmation -v
TEST_DATABASE_URL="postgresql+psycopg2://appuser:apppass@localhost:5434/appdb_test" python -m pytest tests/test_auth_delete_account.py::test_delete_account_missing_confirmation -v
TEST_DATABASE_URL="postgresql+psycopg2://appuser:apppass@localhost:5434/appdb_test" python -m pytest tests/test_auth_delete_account.py::test_delete_account_missing_password -v
```

Expected: PASS (3 tests)

**Step 3: Commit**

```bash
git add backend/tests/test_auth_delete_account.py
git commit -m "test: add validation error tests for account deletion

- Wrong confirmation text (case-sensitive check)
- Missing confirmation field
- Missing password field
- All return 422 validation errors

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 4: Test CASCADE Deletion Behavior

**Files:**
- Modify: `backend/tests/test_auth_delete_account.py`

**Step 1: Write test for CASCADE deletion of related data**

Add to `backend/tests/test_auth_delete_account.py`:

```python
def test_delete_account_cascades_to_device(client, test_user, auth_headers, db_session):
    """Test that deleting user cascades to Device table."""
    # Create device for user
    device = Device(
        user_id=test_user.id,
        device_name="Test Device",
        platform="ios"
    )
    db_session.add(device)
    db_session.commit()
    device_id = device.id

    # Verify device exists
    assert db_session.query(Device).filter(Device.id == device_id).count() == 1

    # Delete account
    response = client.delete(
        "/api/auth/account",
        json={"password": "TestPass123", "confirmation": "DELETE"},
        headers=auth_headers,
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT

    # Verify device was CASCADE deleted
    assert db_session.query(Device).filter(Device.id == device_id).count() == 0
    assert db_session.query(Device).filter(Device.user_id == test_user.id).count() == 0


def test_delete_account_cascades_to_user_cell_visits(client, test_user, auth_headers, db_session):
    """Test that deleting user cascades to UserCellVisit table."""
    # Create H3 cell and user visit
    h3_cell = H3Cell(
        h3_index="882830810ffffff",
        res=8,
        centroid="POINT(-122.4194 37.7749)"
    )
    db_session.add(h3_cell)
    db_session.flush()

    visit = UserCellVisit(
        user_id=test_user.id,
        h3_index="882830810ffffff",
        res=8
    )
    db_session.add(visit)
    db_session.commit()
    visit_id = visit.id

    # Verify visit exists
    assert db_session.query(UserCellVisit).filter(UserCellVisit.id == visit_id).count() == 1

    # Delete account
    response = client.delete(
        "/api/auth/account",
        json={"password": "TestPass123", "confirmation": "DELETE"},
        headers=auth_headers,
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT

    # Verify visit was CASCADE deleted
    assert db_session.query(UserCellVisit).filter(UserCellVisit.id == visit_id).count() == 0
    assert db_session.query(UserCellVisit).filter(UserCellVisit.user_id == test_user.id).count() == 0


def test_delete_account_cascades_to_ingest_batches(client, test_user, auth_headers, db_session):
    """Test that deleting user cascades to IngestBatch table."""
    # Create ingest batch
    batch = IngestBatch(
        user_id=test_user.id,
        cells_count=50,
        res_min=6,
        res_max=8
    )
    db_session.add(batch)
    db_session.commit()
    batch_id = batch.id

    # Verify batch exists
    assert db_session.query(IngestBatch).filter(IngestBatch.id == batch_id).count() == 1

    # Delete account
    response = client.delete(
        "/api/auth/account",
        json={"password": "TestPass123", "confirmation": "DELETE"},
        headers=auth_headers,
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT

    # Verify batch was CASCADE deleted
    assert db_session.query(IngestBatch).filter(IngestBatch.id == batch_id).count() == 0
    assert db_session.query(IngestBatch).filter(IngestBatch.user_id == test_user.id).count() == 0


def test_delete_account_cascades_to_user_achievements(client, test_user, auth_headers, db_session):
    """Test that deleting user cascades to UserAchievement table."""
    # Create achievement and user unlock
    achievement = Achievement(
        code="first_steps",
        name="First Steps",
        description="Visit your first location"
    )
    db_session.add(achievement)
    db_session.flush()

    user_achievement = UserAchievement(
        user_id=test_user.id,
        achievement_id=achievement.id
    )
    db_session.add(user_achievement)
    db_session.commit()
    user_achievement_id = user_achievement.id

    # Verify user achievement exists
    assert db_session.query(UserAchievement).filter(UserAchievement.id == user_achievement_id).count() == 1

    # Delete account
    response = client.delete(
        "/api/auth/account",
        json={"password": "TestPass123", "confirmation": "DELETE"},
        headers=auth_headers,
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT

    # Verify user achievement was CASCADE deleted
    assert db_session.query(UserAchievement).filter(UserAchievement.id == user_achievement_id).count() == 0
    assert db_session.query(UserAchievement).filter(UserAchievement.user_id == test_user.id).count() == 0

    # Verify achievement definition still exists (global catalog)
    assert db_session.query(Achievement).filter(Achievement.id == achievement.id).count() == 1
```

**Step 2: Run tests to verify they pass**

```bash
TEST_DATABASE_URL="postgresql+psycopg2://appuser:apppass@localhost:5434/appdb_test" python -m pytest tests/test_auth_delete_account.py::test_delete_account_cascades_to_device -v
TEST_DATABASE_URL="postgresql+psycopg2://appuser:apppass@localhost:5434/appdb_test" python -m pytest tests/test_auth_delete_account.py::test_delete_account_cascades_to_user_cell_visits -v
TEST_DATABASE_URL="postgresql+psycopg2://appuser:apppass@localhost:5434/appdb_test" python -m pytest tests/test_auth_delete_account.py::test_delete_account_cascades_to_ingest_batches -v
TEST_DATABASE_URL="postgresql+psycopg2://appuser:apppass@localhost:5434/appdb_test" python -m pytest tests/test_auth_delete_account.py::test_delete_account_cascades_to_user_achievements -v
```

Expected: PASS (4 tests)

**Step 3: Commit**

```bash
git add backend/tests/test_auth_delete_account.py
git commit -m "test: verify CASCADE deletion for all related tables

- Device records deleted when user deleted
- UserCellVisit records deleted
- IngestBatch records deleted
- UserAchievement records deleted
- Achievement definitions preserved (global)

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 5: Test H3 Cell Preservation

**Files:**
- Modify: `backend/tests/test_auth_delete_account.py`

**Step 1: Write test to verify H3 cells are NOT deleted**

Add to `backend/tests/test_auth_delete_account.py`:

```python
def test_delete_account_preserves_h3_cells(client, test_user, auth_headers, db_session):
    """Test that deleting user does NOT delete global H3 cells."""
    # Create H3 cell
    h3_cell = H3Cell(
        h3_index="882830810ffffff",
        res=8,
        centroid="POINT(-122.4194 37.7749)"
    )
    db_session.add(h3_cell)
    db_session.flush()

    # Create user visit to that cell
    visit = UserCellVisit(
        user_id=test_user.id,
        h3_index="882830810ffffff",
        res=8
    )
    db_session.add(visit)
    db_session.commit()

    # Verify both cell and visit exist
    assert db_session.query(H3Cell).filter(H3Cell.h3_index == "882830810ffffff").count() == 1
    assert db_session.query(UserCellVisit).filter(UserCellVisit.user_id == test_user.id).count() == 1

    # Delete account
    response = client.delete(
        "/api/auth/account",
        json={"password": "TestPass123", "confirmation": "DELETE"},
        headers=auth_headers,
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT

    # Verify H3 cell still exists (global registry)
    assert db_session.query(H3Cell).filter(H3Cell.h3_index == "882830810ffffff").count() == 1

    # But user visit is gone
    assert db_session.query(UserCellVisit).filter(UserCellVisit.user_id == test_user.id).count() == 0
```

**Step 2: Run test to verify it passes**

```bash
TEST_DATABASE_URL="postgresql+psycopg2://appuser:apppass@localhost:5434/appdb_test" python -m pytest tests/test_auth_delete_account.py::test_delete_account_preserves_h3_cells -v
```

Expected: PASS

**Step 3: Commit**

```bash
git add backend/tests/test_auth_delete_account.py
git commit -m "test: verify H3 cells preserved after user deletion

- H3 cells are global registry, shared across users
- UserCellVisit deleted (personal data)
- H3Cell preserved (global geographic data)

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 6: Run Full Test Suite

**Step 1: Run all account deletion tests**

```bash
TEST_DATABASE_URL="postgresql+psycopg2://appuser:apppass@localhost:5434/appdb_test" python -m pytest tests/test_auth_delete_account.py -v
```

Expected: PASS (11 tests total)
- 1 success test
- 1 wrong password test
- 1 unauthenticated test
- 3 validation error tests
- 4 CASCADE deletion tests
- 1 H3 cell preservation test

**Step 2: Run schema validation tests**

```bash
TEST_DATABASE_URL="postgresql+psycopg2://appuser:apppass@localhost:5434/appdb_test" python -m pytest tests/test_schemas_auth.py -v
```

Expected: PASS (4 tests)

**Step 3: Run all auth tests to ensure no regressions**

```bash
TEST_DATABASE_URL="postgresql+psycopg2://appuser:apppass@localhost:5434/appdb_test" python -m pytest tests/test_auth*.py -v
```

Expected: PASS (all existing auth tests still passing)

**Step 4: Check test coverage**

```bash
TEST_DATABASE_URL="postgresql+psycopg2://appuser:apppass@localhost:5434/appdb_test" python -m pytest tests/test_auth_delete_account.py --cov=routers.auth --cov=schemas.auth --cov-report=term-missing
```

Expected: 100% coverage for delete_account endpoint and AccountDeleteRequest schema

---

## Task 7: Manual End-to-End Testing

**Step 1: Start test database**

```bash
cd backend
docker compose up -d db_test
```

**Step 2: Run migrations on test database**

```bash
export TEST_DATABASE_URL="postgresql+psycopg2://appuser:apppass@localhost:5434/appdb_test"
alembic upgrade head
```

**Step 3: Start development server**

```bash
export DATABASE_URL="postgresql+psycopg2://appuser:apppass@localhost:5433/appdb"
uvicorn main:app --reload
```

**Step 4: Test via Swagger UI**

1. Open browser to `http://localhost:8000/docs`
2. Register new user via `/api/auth/register`
3. Copy access_token
4. Authorize in Swagger (click "Authorize" button, paste token)
5. Try DELETE `/api/auth/account` with wrong password → expect 401
6. Try DELETE `/api/auth/account` with wrong confirmation → expect 422
7. Try DELETE `/api/auth/account` with correct password + "DELETE" → expect 204
8. Try GET `/api/auth/me` with same token → expect 401 (user deleted)
9. Register new user with same email → expect success (email available)

**Step 5: Test via curl (alternative)**

```bash
# Register user
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","username":"testuser","password":"TestPass123"}'

# Save token
TOKEN="<access_token_from_response>"

# Try wrong password
curl -X DELETE http://localhost:8000/api/auth/account \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"password":"WrongPass123","confirmation":"DELETE"}' \
  -v

# Expected: 401 Unauthorized

# Try wrong confirmation
curl -X DELETE http://localhost:8000/api/auth/account \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"password":"TestPass123","confirmation":"delete"}' \
  -v

# Expected: 422 Validation Error

# Delete account successfully
curl -X DELETE http://localhost:8000/api/auth/account \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"password":"TestPass123","confirmation":"DELETE"}' \
  -v

# Expected: 204 No Content

# Verify token invalid
curl -X GET http://localhost:8000/api/auth/me \
  -H "Authorization: Bearer $TOKEN" \
  -v

# Expected: 401 Unauthorized
```

**Step 6: Verify database cleanup**

Connect to test database:
```bash
psql postgresql://appuser:apppass@localhost:5433/appdb
```

Run queries:
```sql
-- Should return 0 (user deleted)
SELECT COUNT(*) FROM users WHERE email = 'test@example.com';

-- Should return 0 (device deleted via CASCADE)
SELECT COUNT(*) FROM devices WHERE user_id = <test_user_id>;

-- Should return 0 (visits deleted via CASCADE)
SELECT COUNT(*) FROM user_cell_visits WHERE user_id = <test_user_id>;

-- Should return 0 (achievements deleted via CASCADE)
SELECT COUNT(*) FROM user_achievements WHERE user_id = <test_user_id>;

-- H3 cells should still exist
SELECT COUNT(*) FROM h3_cells;
```

---

## Task 8: Final Review and Commit

**Step 1: Review all changes**

```bash
git status
git diff main --stat
```

Expected files changed:
- `backend/schemas/auth.py` (added AccountDeleteRequest)
- `backend/routers/auth.py` (added delete_account endpoint)
- `backend/tests/test_schemas_auth.py` (4 schema tests)
- `backend/tests/test_auth_delete_account.py` (11 endpoint tests)

**Step 2: Run full test suite one more time**

```bash
TEST_DATABASE_URL="postgresql+psycopg2://appuser:apppass@localhost:5434/appdb_test" python -m pytest tests/ -v
```

Expected: All tests passing

**Step 3: Review commit history**

```bash
git log --oneline -10
```

Expected: 5 commits (schema, endpoint, validation tests, CASCADE tests, H3 preservation test)

**Step 4: Update feature checklist in backend_mvp_features.md**

Edit `docs/plans/backend_mvp_features.md`:

Change:
```yaml
  - id: account-deletion
    content: Implement DELETE /auth/account with cascade validation
    status: pending
```

To:
```yaml
  - id: account-deletion
    content: Implement DELETE /auth/account with cascade validation
    status: completed
```

**Step 5: Final commit**

```bash
git add docs/plans/backend_mvp_features.md
git commit -m "docs: mark account deletion feature as completed

Feature 5 complete:
- DELETE /api/auth/account endpoint
- Password + 'DELETE' confirmation required
- CASCADE deletion of all user data
- H3 cells preserved (global registry)
- 15 tests with 100% coverage

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Verification Checklist

Before marking complete, verify:

- [ ] All 15 tests pass (4 schema + 11 endpoint tests)
- [ ] Manual end-to-end test successful via Swagger or curl
- [ ] Database CASCADE verified (Device, UserCellVisit, IngestBatch, UserAchievement deleted)
- [ ] H3 cells preserved after user deletion
- [ ] Token becomes invalid after deletion (401 on subsequent requests)
- [ ] Email/username available for re-registration after deletion
- [ ] Swagger docs accurate (docstring shows examples)
- [ ] No regressions in existing auth tests
- [ ] All commits follow conventional commit format
- [ ] Feature marked complete in backend_mvp_features.md

---

## Success Criteria

**Feature is complete when:**

✅ All 15 tests passing
✅ 100% code coverage for new code
✅ Manual E2E test successful
✅ Database CASCADE behavior verified
✅ Documentation complete (Swagger docstring)
✅ No regressions in existing tests

---

## Troubleshooting

**Test fails: "IntegrityError: null value in column violates not-null constraint"**

Issue: Missing required fields in model creation
Fix: Check model definitions, ensure all non-nullable fields provided

**Test fails: "H3Cell was deleted when it shouldn't be"**

Issue: Incorrect CASCADE configuration or test setup
Fix: Verify UserCellVisit has `ondelete="CASCADE"` on h3_index foreign key, but H3Cell has no foreign key to User

**Manual test: Token still works after deletion**

Issue: User might not be actually deleted, or test using wrong token
Fix: Check database - verify user record gone. Check token decoding - ensure user_id matches deleted user

**Test fails: "Password verification failed"**

Issue: Test user password doesn't match "TestPass123"
Fix: Check `conftest.py` fixture - ensure test_user created with password "TestPass123"

---

## Notes for Implementation

**Test Fixtures Needed:**

Check `backend/tests/conftest.py` has:
- `test_user` - User with password "TestPass123"
- `auth_headers` - Authorization headers with valid token
- `db_session` - SQLAlchemy session for database access
- `client` - TestClient for API requests

**Database Setup:**

Tests require:
- Test database running at `localhost:5434`
- Migrations applied (`alembic upgrade head`)
- CASCADE constraints present (should exist from earlier migrations)

**Import Statements:**

Ensure tests import:
```python
from models.user import User
from models.device import Device
from models.visits import UserCellVisit, IngestBatch
from models.achievements import UserAchievement, Achievement
from models.geo import H3Cell
from fastapi import status
```

**Reference Implementation:**

Similar patterns exist in:
- Password verification: `backend/routers/auth.py::login()`
- Pydantic validators: `backend/schemas/auth.py::UserRegister`
- CASCADE behavior: `backend/models/device.py`, `backend/models/visits.py`
