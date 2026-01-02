# Account Deletion Feature Design

**Created:** 2025-12-30
**Feature:** Permanent account deletion with safety confirmations
**Status:** Design Complete, Ready for Implementation

---

## Overview

Enable authenticated users to permanently delete their account and all associated personal data through a secure API endpoint. The feature implements two-factor safety confirmation (password + explicit "DELETE" text) and leverages database CASCADE constraints for automatic data cleanup.

## Business Requirements

- Users can permanently delete their account at any time
- Deletion must be irreversible and complete (GDPR compliance)
- Prevent accidental deletion with dual confirmation
- All personal data must be removed
- Global shared data (H3 cells) must be preserved

## Technical Decisions

### 1. Hard Delete with CASCADE

**Decision:** Delete user record and rely on database CASCADE constraints to clean up related data.

**Rationale:**
- Cleanest approach for data privacy (true deletion)
- Existing models already have correct CASCADE constraints
- No orphaned data or partial deletions
- GDPR-compliant

**Alternative Rejected:** Soft delete (anonymization)
- Reason: Violates data minimization principle, adds complexity

### 2. Stateless Token Invalidation

**Decision:** No explicit token revocation - deletion makes tokens useless naturally.

**Rationale:**
- Deleted user means `get_current_user()` dependency fails automatically
- Keeps authentication stateless (no Redis/blacklist needed)
- Tokens expire naturally within minutes
- Simpler implementation

**Alternative Rejected:** Token blacklist or versioning
- Reason: Adds state management complexity for minimal security gain in MVP

### 3. Two-Factor Confirmation

**Decision:** Require both password verification AND typing "DELETE" exactly.

**Rationale:**
- Password proves user identity
- "DELETE" text prevents accidental clicks
- Single API call (no multi-step flow)
- Common pattern (GitHub, AWS, etc.)

**Alternative Rejected:** Password-only or soft delete with grace period
- Reason: Too risky for password-only, grace period adds complexity

---

## API Specification

### Endpoint

**Route:** `DELETE /api/auth/account`

**Authentication:** Required (Bearer token in Authorization header)

**Request Body:**
```json
{
  "password": "MyPassword123",
  "confirmation": "DELETE"
}
```

**Success Response:**
- **Status:** 204 No Content
- **Body:** Empty

**Error Responses:**

| Status | Condition | Response |
|--------|-----------|----------|
| 401 Unauthorized | Invalid/missing token | `{"detail": "Could not validate credentials"}` |
| 401 Unauthorized | Wrong password | `{"detail": "Invalid password"}` |
| 422 Validation Error | confirmation != "DELETE" | Pydantic validation error |
| 422 Validation Error | Missing required fields | Pydantic validation error |

---

## Implementation Details

### 1. Request Schema

**File:** `backend/schemas/auth.py`

```python
class AccountDeleteRequest(BaseModel):
    """Request schema for account deletion."""

    password: str
    confirmation: str

    @field_validator("confirmation")
    @classmethod
    def validate_confirmation(cls, v: str) -> str:
        if v != "DELETE":
            raise ValueError("Confirmation must be exactly 'DELETE'")
        return v
```

**Design Notes:**
- Password is plain string - verified in endpoint logic
- Pydantic validator ensures "DELETE" is exact match (case-sensitive)
- Follows existing validation pattern from `UserRegister`

### 2. Endpoint Implementation

**File:** `backend/routers/auth.py`

Add new endpoint:

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
    - User account
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
    Raises: 401 if password incorrect, 422 if confirmation invalid
    """
    # Verify current password
    if not verify_password(request.password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid password",
        )

    # Delete user (CASCADE constraints handle related data)
    db.delete(current_user)
    db.commit()

    # Return 204 No Content (no response body)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

**Required Imports:**
```python
from fastapi.responses import Response
from schemas.auth import AccountDeleteRequest
```

### 3. Database CASCADE Behavior

**Existing Constraints (No Changes Needed):**

When `User` is deleted, these tables CASCADE automatically:

```python
# devices table
user_id -> ForeignKey("users.id", ondelete="CASCADE")

# user_cell_visits table
user_id -> ForeignKey("users.id", ondelete="CASCADE")

# ingest_batches table
user_id -> ForeignKey("users.id", ondelete="CASCADE")

# user_achievements table
user_id -> ForeignKey("users.id", ondelete="CASCADE")
```

**Preserved Data:**

- `h3_cells` table - Global registry, no foreign key to users
- `achievements` table - Achievement definitions (catalog)

---

## Security Considerations

### 1. Password Brute-Force Protection

**Current State:** No specific rate limiting on this endpoint

**Recommendation for MVP:** Rely on global API rate limiting (if exists)

**Future Enhancement:** Add endpoint-specific rate limit:
```python
@limiter.limit("5/minute")
@router.delete("/account", ...)
```

### 2. Token Behavior Post-Deletion

**Scenario:** User deletes account, then tries to use existing JWT token

**Behavior:**
1. Token remains syntactically valid until expiry (typically 15-60 minutes)
2. Any API call with that token fails at `get_current_user()` dependency
3. Database query `User.id == token_user_id` returns None
4. Raises 401 Unauthorized

**Implication:** No special token revocation needed - stateless design handles it

### 3. Concurrent Deletion Attempts

**Scenario:** Two requests try to delete same account simultaneously

**Behavior:**
1. First request: Loads user, verifies password, deletes user, returns 204
2. Second request: Attempts to load user via `get_current_user()`, fails (user already deleted), returns 401

**Implication:** Database transaction isolation prevents race conditions

### 4. Email/Username Reuse

**Scenario:** User deletes account, then tries to register with same email/username

**Behavior:**
- Email and username become available immediately after deletion
- New registration succeeds - creates fresh account
- No connection to previous account

**Implication:** This is expected behavior (clean slate)

---

## Testing Strategy

### Test File

**File:** `backend/tests/test_auth_delete_account.py` (new)

### Test Cases

#### 1. Happy Path
```python
def test_delete_account_success(client, test_user, auth_headers):
    """Test successful account deletion with valid password and confirmation."""
    # Test deletion succeeds
    # Verify subsequent API calls with token fail (401)
```

#### 2. Authentication Errors
```python
def test_delete_account_wrong_password(client, test_user, auth_headers):
    """Test deletion fails with incorrect password."""

def test_delete_account_unauthenticated(client):
    """Test deletion requires authentication."""
```

#### 3. Validation Errors
```python
def test_delete_account_wrong_confirmation(client, test_user, auth_headers):
    """Test deletion fails with incorrect confirmation text (e.g., 'delete' lowercase)."""

def test_delete_account_missing_confirmation(client, test_user, auth_headers):
    """Test deletion fails with missing confirmation field."""
```

#### 4. Data Integrity
```python
def test_delete_account_cascades_data(client, test_user, auth_headers, db_session):
    """Test that deleting user cascades to Device, UserCellVisit, IngestBatch, UserAchievement."""

def test_delete_account_preserves_h3_cells(client, test_user, auth_headers, db_session):
    """Test that deleting user does NOT delete global H3 cells."""
```

### Coverage Target

- 100% line coverage for new endpoint
- All error paths tested (401, 422)
- CASCADE behavior verified (critical safety check)

---

## Edge Cases

### 1. Concurrent Deletions
- **Scenario:** Two simultaneous deletion requests
- **Handling:** Database transaction isolation - one succeeds (204), other gets 401
- **Action Required:** None (handled automatically)

### 2. Token Validity After Deletion
- **Scenario:** User deletes account, JWT still valid for 15+ minutes
- **Handling:** Token becomes useless - all endpoints fail at `get_current_user()`
- **Action Required:** None (stateless design handles it)

### 3. Email/Username Reuse
- **Scenario:** Delete account, re-register with same email
- **Handling:** Allowed - creates fresh account with no historical data
- **Action Required:** None (expected behavior)

### 4. Deletion During Active Session
- **Scenario:** User has multiple devices/tabs, deletes from one
- **Handling:** All other sessions immediately fail at next API call
- **Action Required:** Frontend should handle 401 gracefully (redirect to login)

---

## Documentation Requirements

### API Documentation (Swagger)

- Detailed docstring with example request/response
- Error codes and meanings documented
- Security requirements clearly stated

### User-Facing Documentation

**Not in scope for backend MVP** - Frontend should provide:
- Warning dialog explaining irreversibility
- List of data being deleted
- Clear instructions for confirmation

---

## Implementation Checklist

- [ ] Add `AccountDeleteRequest` schema to `backend/schemas/auth.py`
- [ ] Add `delete_account` endpoint to `backend/routers/auth.py`
- [ ] Add `Response` import to auth router
- [ ] Create `backend/tests/test_auth_delete_account.py` with 7 test cases
- [ ] Verify CASCADE constraints work as expected (test)
- [ ] Verify H3 cells are preserved (test)
- [ ] Update API documentation (Swagger docstring)
- [ ] Manual testing: Delete account, verify token fails, re-register succeeds

---

## Out of Scope (Future Enhancements)

### Phase 2 Features

1. **Email Notification**
   - Send confirmation email after deletion
   - Requires email infrastructure (SMTP setup)

2. **Audit Logging**
   - Log deletions to separate audit table
   - Include: user_id, email, timestamp, IP address
   - Retention: 90 days for security investigations

3. **Data Export Before Deletion**
   - Offer JSON export of user data
   - Include: stats, visit history, achievements
   - GDPR Article 20 (data portability)

4. **Rate Limiting**
   - Endpoint-specific rate limit (5 attempts/minute)
   - Prevent password brute-forcing

5. **Soft Delete Option**
   - Mark deleted, hide data, keep in DB for 30 days
   - Allow account recovery within grace period
   - Permanent deletion after grace period

---

## Success Criteria

**Implementation is complete when:**

- ✅ All 7 test cases pass
- ✅ Endpoint documented with examples
- ✅ CASCADE behavior verified in tests
- ✅ Manual end-to-end test successful
- ✅ Code review approved

**Performance Target:**

- Response time < 100ms (simple DELETE operation)

---

## Open Questions

**Q: Should we add rate limiting to this endpoint?**
**A:** Not for MVP. Rely on global rate limiting. Add in Phase 2 if abuse detected.

**Q: Should we send confirmation email after deletion?**
**A:** Not for MVP (no email infrastructure). Add in Phase 2 with password reset.

**Q: Should we log deletions for audit purposes?**
**A:** Not for MVP. Add separate audit table in Phase 2 for compliance.

**Q: Should we allow account recovery after deletion?**
**A:** No. Deletion is permanent. User can re-register with same email if needed.

---

## References

- Feature specification: `docs/plans/backend_mvp_features.md` - Feature 5
- Existing models: `backend/models/user.py`, `backend/models/device.py`, `backend/models/visits.py`, `backend/models/achievements.py`
- Auth patterns: `backend/routers/auth.py` (password verification)
- Schema patterns: `backend/schemas/auth.py` (Pydantic validators)
