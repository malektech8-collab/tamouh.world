"""
Tests for authentication endpoints and JWT functionality.
"""

import pytest
from fastapi import status
from app.auth import hash_password, verify_password, create_access_token


@pytest.mark.unit
class TestPasswordHashing:
    """Test password hashing functions."""

    def test_hash_password(self):
        """Test that password hashing works."""
        password = "securepassword123"
        hashed = hash_password(password)

        assert hashed != password
        assert len(hashed) > 20

    def test_verify_password_success(self):
        """Test that correct password verifies."""
        password = "securepassword123"
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True

    def test_verify_password_failure(self):
        """Test that incorrect password fails."""
        password = "securepassword123"
        wrong_password = "wrongpassword"
        hashed = hash_password(password)

        assert verify_password(wrong_password, hashed) is False


@pytest.mark.unit
class TestJWTToken:
    """Test JWT token generation and validation."""

    def test_create_access_token(self):
        """Test JWT token creation."""
        user_id = "test-user-123"
        token = create_access_token(data={"sub": user_id})

        assert isinstance(token, str)
        assert len(token) > 50
        assert token.count(".") == 2  # JWT has 3 parts separated by 2 dots


@pytest.mark.unit
class TestAuthenticationEndpoints:
    """Test authentication API endpoints."""

    def test_register_success(self, test_client):
        """Test successful user registration."""
        response = test_client.post(
            "/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "securepassword123"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["email"] == "newuser@example.com"
        assert data["user"]["is_active"] is True

    def test_register_duplicate_email(self, test_client, test_db):
        """Test registration with existing email fails."""
        from models.db_models import User
        from app.auth import hash_password

        # Create existing user
        existing_user = User(
            id="existing-id",
            email="existing@example.com",
            hashed_password=hash_password("password123"),
            is_active=True
        )
        test_db.add(existing_user)
        test_db.commit()

        # Try to register with same email
        response = test_client.post(
            "/auth/register",
            json={
                "email": "existing@example.com",
                "password": "newpassword123"
            }
        )

        assert response.status_code == 409
        assert "already registered" in response.json()["detail"]

    def test_register_weak_password(self, test_client):
        """Test registration with weak password fails."""
        response = test_client.post(
            "/auth/register",
            json={
                "email": "user@example.com",
                "password": "short"  # Less than 8 characters
            }
        )

        assert response.status_code == 422  # Validation error

    def test_register_invalid_email(self, test_client):
        """Test registration with invalid email fails."""
        response = test_client.post(
            "/auth/register",
            json={
                "email": "not-an-email",
                "password": "securepassword123"
            }
        )

        assert response.status_code == 422  # Validation error

    def test_login_success(self, test_client, test_db):
        """Test successful login."""
        from models.db_models import User
        from app.auth import hash_password

        # Create user
        user = User(
            id="user-123",
            email="testuser@example.com",
            hashed_password=hash_password("securepassword123"),
            is_active=True
        )
        test_db.add(user)
        test_db.commit()

        # Login
        response = test_client.post(
            "/auth/login",
            json={
                "email": "testuser@example.com",
                "password": "securepassword123"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] > 0

    def test_login_wrong_password(self, test_client, test_db):
        """Test login with wrong password fails."""
        from models.db_models import User
        from app.auth import hash_password

        # Create user
        user = User(
            id="user-123",
            email="testuser@example.com",
            hashed_password=hash_password("securepassword123"),
            is_active=True
        )
        test_db.add(user)
        test_db.commit()

        # Login with wrong password
        response = test_client.post(
            "/auth/login",
            json={
                "email": "testuser@example.com",
                "password": "wrongpassword"
            }
        )

        assert response.status_code == 401
        assert "Invalid email or password" in response.json()["detail"]

    def test_login_nonexistent_user(self, test_client):
        """Test login with nonexistent user fails."""
        response = test_client.post(
            "/auth/login",
            json={
                "email": "nonexistent@example.com",
                "password": "anypassword"
            }
        )

        assert response.status_code == 401
        assert "Invalid email or password" in response.json()["detail"]

    def test_login_inactive_user(self, test_client, test_db):
        """Test login with inactive user fails."""
        from models.db_models import User
        from app.auth import hash_password

        # Create inactive user
        user = User(
            id="user-123",
            email="inactive@example.com",
            hashed_password=hash_password("securepassword123"),
            is_active=False
        )
        test_db.add(user)
        test_db.commit()

        # Try to login
        response = test_client.post(
            "/auth/login",
            json={
                "email": "inactive@example.com",
                "password": "securepassword123"
            }
        )

        assert response.status_code == 403
        assert "inactive" in response.json()["detail"]


@pytest.mark.unit
class TestProtectedEndpoints:
    """Test protected endpoints requiring authentication."""

    def test_resume_create_without_auth(self, test_client, sample_pdf_file):
        """Test creating resume without auth fails."""
        with open(sample_pdf_file, "rb") as f:
            files = {"file": ("resume.pdf", f, "application/pdf")}
            response = test_client.post("/resume/create", files=files)

        assert response.status_code == 403  # Forbidden (no auth)

    def test_resume_create_with_valid_auth(
        self, test_client, test_db, sample_pdf_file
    ):
        """Test creating resume with valid auth succeeds."""
        from models.db_models import User
        from app.auth import hash_password, create_access_token

        # Create user
        user = User(
            id="user-123",
            email="testuser@example.com",
            hashed_password=hash_password("password123"),
            is_active=True
        )
        test_db.add(user)
        test_db.commit()

        # Generate token
        token = create_access_token(data={"sub": user.id})

        # Create resume with auth
        with open(sample_pdf_file, "rb") as f:
            files = {"file": ("resume.pdf", f, "application/pdf")}
            response = test_client.post(
                "/resume/create",
                files=files,
                headers={"Authorization": f"Bearer {token}"}
            )

        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "queued"

    def test_resume_status_without_auth(self, test_client):
        """Test getting resume status without auth fails."""
        response = test_client.get(
            "/resume/status/any-job-id"
        )

        assert response.status_code == 403  # Forbidden

    def test_resume_status_with_auth(self, test_client, test_db):
        """Test getting resume status with auth."""
        from models.db_models import User, ResumeJob
        from app.auth import hash_password, create_access_token
        import uuid

        # Create user
        user = User(
            id="user-123",
            email="testuser@example.com",
            hashed_password=hash_password("password123"),
            is_active=True
        )
        test_db.add(user)
        test_db.commit()

        # Create job for user
        job_id = str(uuid.uuid4())
        job = ResumeJob(
            id=job_id,
            user_id=user.id,
            status="processing"
        )
        test_db.add(job)
        test_db.commit()

        # Generate token
        token = create_access_token(data={"sub": user.id})

        # Get status
        response = test_client.get(
            f"/resume/status/{job_id}",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == job_id
        assert data["status"] == "processing"

    def test_resume_status_cross_user_access_denied(
        self, test_client, test_db
    ):
        """Test that users cannot access other user's jobs."""
        from models.db_models import User, ResumeJob
        from app.auth import hash_password, create_access_token
        import uuid

        # Create two users
        user1 = User(
            id="user-1",
            email="user1@example.com",
            hashed_password=hash_password("password123"),
            is_active=True
        )
        user2 = User(
            id="user-2",
            email="user2@example.com",
            hashed_password=hash_password("password123"),
            is_active=True
        )
        test_db.add_all([user1, user2])
        test_db.commit()

        # Create job for user1
        job_id = str(uuid.uuid4())
        job = ResumeJob(
            id=job_id,
            user_id=user1.id,
            status="processing"
        )
        test_db.add(job)
        test_db.commit()

        # Try to access with user2's token
        token = create_access_token(data={"sub": user2.id})
        response = test_client.get(
            f"/resume/status/{job_id}",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 404
        assert "access denied" in response.json()["detail"]

    def test_list_user_resumes(self, test_client, test_db):
        """Test listing user's resumes."""
        from models.db_models import User, ResumeJob
        from app.auth import hash_password, create_access_token
        import uuid

        # Create user
        user = User(
            id="user-123",
            email="testuser@example.com",
            hashed_password=hash_password("password123"),
            is_active=True
        )
        test_db.add(user)
        test_db.commit()

        # Create multiple jobs for user
        for i in range(3):
            job = ResumeJob(
                id=str(uuid.uuid4()),
                user_id=user.id,
                status="completed"
            )
            test_db.add(job)
        test_db.commit()

        # Generate token
        token = create_access_token(data={"sub": user.id})

        # List resumes
        response = test_client.get(
            "/my-resumes",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        jobs = response.json()
        assert len(jobs) == 3
