"""
Comprehensive unit tests for database session management.

Tests database session creation, tenant context handling, RLS integration,
and connection management functionality.
"""

from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession


class TestGetDbSession:
    """Test get_db_session dependency function."""

    @patch("src.multi_tenant_db.db.session.SessionLocal")
    @pytest.mark.asyncio
    async def test_get_db_session_success(self, mock_session_local):
        """Test successful database session creation and cleanup."""
        from src.multi_tenant_db.db.session import get_db_session
        
        # Create mock session
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session_local.return_value.__aenter__.return_value = mock_session
        mock_session_local.return_value.__aexit__.return_value = None
        
        # Use the generator
        async for session in get_db_session():
            assert session == mock_session
            break
        
        # Verify session was closed properly
        mock_session.close.assert_called_once()

    @patch("src.multi_tenant_db.db.session.SessionLocal")
    @pytest.mark.asyncio
    async def test_get_db_session_exception_handling(self, mock_session_local):
        """Test database session handles exceptions with rollback."""
        from src.multi_tenant_db.db.session import get_db_session
        
        # Create mock session
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session_local.return_value.__aenter__.return_value = mock_session
        mock_session_local.return_value.__aexit__.return_value = None
        
        # Simulate exception during session use
        with pytest.raises(RuntimeError):
            async for session in get_db_session():
                # Simulate an exception occurring during session use
                raise RuntimeError("Database operation failed")
        
        # Verify rollback and close were called
        mock_session.rollback.assert_called_once()
        mock_session.close.assert_called_once()


class TestGetTenantSession:
    """Test get_tenant_session context manager."""

    @patch("src.multi_tenant_db.db.session.SessionLocal")
    @pytest.mark.asyncio
    async def test_get_tenant_session_success(self, mock_session_local):
        """Test successful tenant session creation with context setting."""
        from src.multi_tenant_db.db.session import get_tenant_session
        
        # Create mock session
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session_local.return_value.__aenter__.return_value = mock_session
        mock_session_local.return_value.__aexit__.return_value = None
        
        tenant_id = str(uuid4())
        
        # Use the context manager
        async with get_tenant_session(tenant_id) as session:
            assert session == mock_session
        
        # Verify tenant context was set
        mock_session.execute.assert_called_once()
        call_args = mock_session.execute.call_args
        assert "set_tenant_context" in str(call_args[0][0])
        assert call_args[1]["tenant_id"] == tenant_id
        
        # Verify session was closed
        mock_session.close.assert_called_once()

    @patch("src.multi_tenant_db.db.session.SessionLocal")
    @pytest.mark.asyncio
    async def test_get_tenant_session_invalid_tenant(self, mock_session_local):
        """Test tenant session with invalid tenant ID."""
        from src.multi_tenant_db.db.session import get_tenant_session
        
        # Create mock session that raises ProgrammingError for invalid tenant
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.execute.side_effect = ProgrammingError("Invalid tenant ID", None, None)
        mock_session_local.return_value.__aenter__.return_value = mock_session
        mock_session_local.return_value.__aexit__.return_value = None
        
        invalid_tenant_id = "not-a-uuid"
        
        # Should raise ProgrammingError
        with pytest.raises(ProgrammingError):
            async with get_tenant_session(invalid_tenant_id) as session:
                pass
        
        # Verify rollback and close were called
        mock_session.rollback.assert_called_once()
        mock_session.close.assert_called_once()

    @patch("src.multi_tenant_db.db.session.SessionLocal")
    @pytest.mark.asyncio
    async def test_get_tenant_session_exception_handling(self, mock_session_local):
        """Test tenant session handles exceptions properly."""
        from src.multi_tenant_db.db.session import get_tenant_session
        
        # Create mock session
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session_local.return_value.__aenter__.return_value = mock_session
        mock_session_local.return_value.__aexit__.return_value = None
        
        tenant_id = str(uuid4())
        
        # Simulate exception during session use
        with pytest.raises(RuntimeError):
            async with get_tenant_session(tenant_id) as session:
                raise RuntimeError("Operation failed")
        
        # Verify rollback and close were called
        mock_session.rollback.assert_called_once()
        mock_session.close.assert_called_once()


class TestSetTenantContext:
    """Test set_tenant_context function."""

    @pytest.mark.asyncio
    async def test_set_tenant_context_success(self):
        """Test successful tenant context setting."""
        from src.multi_tenant_db.db.session import set_tenant_context
        
        # Create mock session
        mock_session = AsyncMock(spec=AsyncSession)
        tenant_id = str(uuid4())
        
        # Execute function
        await set_tenant_context(mock_session, tenant_id)
        
        # Verify correct SQL was executed
        mock_session.execute.assert_called_once()
        call_args = mock_session.execute.call_args
        assert "set_tenant_context" in str(call_args[0][0])
        assert call_args[1]["tenant_id"] == tenant_id

    @pytest.mark.asyncio
    async def test_set_tenant_context_invalid_tenant(self):
        """Test tenant context setting with invalid tenant ID."""
        from src.multi_tenant_db.db.session import set_tenant_context
        
        # Create mock session that raises error
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.execute.side_effect = ProgrammingError("Invalid tenant ID", None, None)
        
        invalid_tenant_id = "invalid-uuid"
        
        # Should raise ProgrammingError
        with pytest.raises(ProgrammingError):
            await set_tenant_context(mock_session, invalid_tenant_id)

    @pytest.mark.asyncio
    async def test_set_tenant_context_nonexistent_tenant(self):
        """Test tenant context setting with nonexistent tenant ID."""
        from src.multi_tenant_db.db.session import set_tenant_context
        
        # Create mock session that raises error for nonexistent tenant
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.execute.side_effect = ProgrammingError("Tenant not found", None, None)
        
        nonexistent_tenant_id = str(uuid4())
        
        # Should raise ProgrammingError
        with pytest.raises(ProgrammingError):
            await set_tenant_context(mock_session, nonexistent_tenant_id)


class TestClearTenantContext:
    """Test clear_tenant_context function."""

    @pytest.mark.asyncio
    async def test_clear_tenant_context_success(self):
        """Test successful tenant context clearing."""
        from src.multi_tenant_db.db.session import clear_tenant_context
        
        # Create mock session
        mock_session = AsyncMock(spec=AsyncSession)
        
        # Execute function
        await clear_tenant_context(mock_session)
        
        # Verify correct SQL was executed
        mock_session.execute.assert_called_once()
        call_args = mock_session.execute.call_args
        assert "clear_tenant_context" in str(call_args[0][0])

    @pytest.mark.asyncio
    async def test_clear_tenant_context_database_error(self):
        """Test tenant context clearing with database error."""
        from src.multi_tenant_db.db.session import clear_tenant_context
        
        # Create mock session that raises error
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.execute.side_effect = ProgrammingError("Function not found", None, None)
        
        # Should raise ProgrammingError
        with pytest.raises(ProgrammingError):
            await clear_tenant_context(mock_session)


class TestGetCurrentTenantId:
    """Test get_current_tenant_id function."""

    @pytest.mark.asyncio
    async def test_get_current_tenant_id_with_tenant_set(self):
        """Test getting current tenant ID when tenant is set."""
        from src.multi_tenant_db.db.session import get_current_tenant_id
        
        # Create mock session and result
        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = Mock()
        tenant_id = str(uuid4())
        mock_result.scalar.return_value = tenant_id
        mock_session.execute.return_value = mock_result
        
        # Execute function
        result = await get_current_tenant_id(mock_session)
        
        # Verify result
        assert result == tenant_id
        
        # Verify correct SQL was executed
        mock_session.execute.assert_called_once()
        call_args = mock_session.execute.call_args
        assert "current_setting" in str(call_args[0][0])
        assert "app.current_tenant_id" in str(call_args[0][0])

    @pytest.mark.asyncio
    async def test_get_current_tenant_id_no_tenant_set(self):
        """Test getting current tenant ID when no tenant is set."""
        from src.multi_tenant_db.db.session import get_current_tenant_id
        
        # Create mock session and result
        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = Mock()
        mock_result.scalar.return_value = ""  # Empty string when not set
        mock_session.execute.return_value = mock_result
        
        # Execute function
        result = await get_current_tenant_id(mock_session)
        
        # Verify result is None for empty string
        assert result is None

    @pytest.mark.asyncio
    async def test_get_current_tenant_id_null_result(self):
        """Test getting current tenant ID when result is null."""
        from src.multi_tenant_db.db.session import get_current_tenant_id
        
        # Create mock session and result
        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = Mock()
        mock_result.scalar.return_value = None
        mock_session.execute.return_value = mock_result
        
        # Execute function
        result = await get_current_tenant_id(mock_session)
        
        # Verify result is None
        assert result is None

    @pytest.mark.asyncio
    async def test_get_current_tenant_id_database_error(self):
        """Test getting current tenant ID with database error."""
        from src.multi_tenant_db.db.session import get_current_tenant_id
        
        # Create mock session that raises error
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.execute.side_effect = ProgrammingError("Setting not found", None, None)
        
        # Should raise ProgrammingError
        with pytest.raises(ProgrammingError):
            await get_current_tenant_id(mock_session)


class TestTestDatabaseConnection:
    """Test test_database_connection function."""

    @patch("src.multi_tenant_db.db.session.SessionLocal")
    @pytest.mark.asyncio
    async def test_database_connection_success(self, mock_session_local):
        """Test successful database connection test."""
        from src.multi_tenant_db.db.session import test_database_connection
        
        # Create mock session
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session_local.return_value.__aenter__.return_value = mock_session
        mock_session_local.return_value.__aexit__.return_value = None
        
        # Execute function
        result = await test_database_connection()
        
        # Verify result
        assert result is True
        
        # Verify simple query was executed
        mock_session.execute.assert_called_once()
        call_args = mock_session.execute.call_args
        assert "SELECT 1" in str(call_args[0][0])

    @patch("src.multi_tenant_db.db.session.SessionLocal")
    @pytest.mark.asyncio
    async def test_database_connection_failure(self, mock_session_local):
        """Test database connection test failure."""
        from src.multi_tenant_db.db.session import test_database_connection
        
        # Create mock session that raises exception
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.execute.side_effect = Exception("Connection failed")
        mock_session_local.return_value.__aenter__.return_value = mock_session
        mock_session_local.return_value.__aexit__.return_value = None
        
        # Execute function
        result = await test_database_connection()
        
        # Verify result
        assert result is False

    @patch("src.multi_tenant_db.db.session.SessionLocal")
    @pytest.mark.asyncio
    async def test_database_connection_session_creation_failure(self, mock_session_local):
        """Test database connection test when session creation fails."""
        from src.multi_tenant_db.db.session import test_database_connection
        
        # Mock session creation failure
        mock_session_local.side_effect = Exception("Cannot create session")
        
        # Execute function
        result = await test_database_connection()
        
        # Verify result
        assert result is False


class TestCloseDatabaseConnections:
    """Test close_db_connections function."""

    @patch("src.multi_tenant_db.db.session.engine")
    @pytest.mark.asyncio
    async def test_close_database_connections_success(self, mock_engine):
        """Test successful database connections closure."""
        from src.multi_tenant_db.db.session import close_db_connections
        
        # Mock engine dispose
        mock_engine.dispose = AsyncMock()
        
        # Execute function
        await close_db_connections()
        
        # Verify engine dispose was called
        mock_engine.dispose.assert_called_once()

    @patch("src.multi_tenant_db.db.session.engine")
    @pytest.mark.asyncio
    async def test_close_database_connections_error(self, mock_engine):
        """Test database connections closure with error."""
        from src.multi_tenant_db.db.session import close_db_connections
        
        # Mock engine dispose that raises error
        mock_engine.dispose = AsyncMock(side_effect=Exception("Dispose failed"))
        
        # Should raise the exception
        with pytest.raises(Exception, match="Dispose failed"):
            await close_db_connections()


class TestSessionLocalConfiguration:
    """Test SessionLocal configuration and engine setup."""

    @patch("src.multi_tenant_db.db.session.get_settings")
    @patch("src.multi_tenant_db.db.session.create_async_engine")
    @patch("src.multi_tenant_db.db.session.async_sessionmaker")
    def test_engine_configuration(self, mock_sessionmaker, mock_create_engine, mock_get_settings):
        """Test database engine is configured correctly."""
        # Mock settings
        mock_settings = Mock()
        mock_settings.database_url = "postgresql+asyncpg://test:test@localhost/test"
        mock_settings.db_pool_size = 10
        mock_settings.db_max_overflow = 20
        mock_settings.db_pool_timeout = 60
        mock_settings.debug = True
        mock_get_settings.return_value = mock_settings
        
        # Mock engine
        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine
        
        # Import module to trigger configuration
        import importlib
        import src.multi_tenant_db.db.session
        importlib.reload(src.multi_tenant_db.db.session)
        
        # Verify engine was created with correct parameters
        mock_create_engine.assert_called()
        call_args = mock_create_engine.call_args
        assert "pool_size" in call_args[1]
        assert "max_overflow" in call_args[1]
        assert "pool_timeout" in call_args[1]
        assert "pool_pre_ping" in call_args[1]
        assert "echo" in call_args[1]
        
        # Verify sessionmaker was configured
        mock_sessionmaker.assert_called_once()
        sessionmaker_call = mock_sessionmaker.call_args[1]
        assert sessionmaker_call["bind"] == mock_engine
        assert sessionmaker_call["expire_on_commit"] is False
        assert sessionmaker_call["autoflush"] is False
        assert sessionmaker_call["autocommit"] is False


class TestTenantContextScenarios:
    """Test complex tenant context scenarios."""

    @patch("src.multi_tenant_db.db.session.SessionLocal")
    @pytest.mark.asyncio
    async def test_nested_tenant_context_changes(self, mock_session_local):
        """Test changing tenant context within a session."""
        from src.multi_tenant_db.db.session import (
            get_tenant_session,
            set_tenant_context,
            clear_tenant_context
        )
        
        # Create mock session
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session_local.return_value.__aenter__.return_value = mock_session
        mock_session_local.return_value.__aexit__.return_value = None
        
        tenant_id1 = str(uuid4())
        tenant_id2 = str(uuid4())
        
        # Use tenant session with context changes
        async with get_tenant_session(tenant_id1) as session:
            # Change to different tenant
            await set_tenant_context(session, tenant_id2)
            
            # Clear context
            await clear_tenant_context(session)
            
            # Set context again
            await set_tenant_context(session, tenant_id1)
        
        # Verify all context operations were called
        assert mock_session.execute.call_count == 4  # Initial + 3 operations

    @pytest.mark.asyncio
    async def test_concurrent_tenant_contexts(self):
        """Test that different sessions can have different tenant contexts."""
        from src.multi_tenant_db.db.session import set_tenant_context
        
        # Create two mock sessions
        session1 = AsyncMock(spec=AsyncSession)
        session2 = AsyncMock(spec=AsyncSession)
        
        tenant_id1 = str(uuid4())
        tenant_id2 = str(uuid4())
        
        # Set different contexts in each session
        await set_tenant_context(session1, tenant_id1)
        await set_tenant_context(session2, tenant_id2)
        
        # Verify each session got its own context
        session1.execute.assert_called_once()
        session2.execute.assert_called_once()
        
        # Verify different tenant IDs were used
        call1_args = session1.execute.call_args[1]
        call2_args = session2.execute.call_args[1]
        assert call1_args["tenant_id"] == tenant_id1
        assert call2_args["tenant_id"] == tenant_id2


class TestSessionErrorRecovery:
    """Test session error recovery scenarios."""

    @patch("src.multi_tenant_db.db.session.SessionLocal")
    @pytest.mark.asyncio
    async def test_session_recovery_after_error(self, mock_session_local):
        """Test that sessions can be used again after errors."""
        from src.multi_tenant_db.db.session import get_db_session
        
        # First session fails
        mock_session1 = AsyncMock(spec=AsyncSession)
        
        # Second session succeeds
        mock_session2 = AsyncMock(spec=AsyncSession)
        
        # Configure session local to return different sessions
        mock_session_local.return_value.__aenter__.side_effect = [mock_session1, mock_session2]
        mock_session_local.return_value.__aexit__.return_value = None
        
        # First session use fails
        with pytest.raises(RuntimeError):
            async for session in get_db_session():
                raise RuntimeError("First session failed")
        
        # Second session use succeeds
        async for session in get_db_session():
            assert session == mock_session2
            break
        
        # Verify both sessions were properly closed
        mock_session1.close.assert_called_once()
        mock_session2.close.assert_called_once()

    @patch("src.multi_tenant_db.db.session.SessionLocal")
    @pytest.mark.asyncio
    async def test_tenant_session_recovery_after_invalid_context(self, mock_session_local):
        """Test tenant session recovery after invalid context."""
        from src.multi_tenant_db.db.session import get_tenant_session
        
        # Create mock sessions
        mock_session1 = AsyncMock(spec=AsyncSession)
        mock_session1.execute.side_effect = ProgrammingError("Invalid tenant", None, None)
        
        mock_session2 = AsyncMock(spec=AsyncSession)
        
        # Configure session local
        mock_session_local.return_value.__aenter__.side_effect = [mock_session1, mock_session2]
        mock_session_local.return_value.__aexit__.return_value = None
        
        invalid_tenant_id = "invalid"
        valid_tenant_id = str(uuid4())
        
        # First attempt with invalid tenant fails
        with pytest.raises(ProgrammingError):
            async with get_tenant_session(invalid_tenant_id):
                pass
        
        # Second attempt with valid tenant succeeds
        async with get_tenant_session(valid_tenant_id) as session:
            assert session == mock_session2
        
        # Verify both sessions were handled properly
        mock_session1.rollback.assert_called_once()
        mock_session1.close.assert_called_once()
        mock_session2.close.assert_called_once()