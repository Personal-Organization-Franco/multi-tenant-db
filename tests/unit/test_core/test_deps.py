"""
Unit tests for dependency injection module.

Tests dependency injection functions for database sessions,
tenant context, and FastAPI integration.
"""

from typing import Annotated
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.multi_tenant_db.core.deps import (
    get_tenant_db_session,
    get_current_tenant,
    TenantDBSession,
    CurrentTenant,
    DBSession,
)


class TestGetTenantDbSession:
    """Test cases for get_tenant_db_session dependency."""

    @pytest.mark.asyncio
    async def test_get_tenant_db_session_basic_functionality(self):
        """Test basic functionality of get_tenant_db_session."""
        # Mock objects
        mock_request = MagicMock(spec=Request)
        mock_session = AsyncMock(spec=AsyncSession)
        tenant_id = str(uuid4())
        
        # Mock the dependencies
        with patch("src.multi_tenant_db.core.deps.get_current_tenant_id") as mock_get_tenant_id, \
             patch("src.multi_tenant_db.core.deps.set_tenant_context") as mock_set_context:
            
            mock_get_tenant_id.return_value = tenant_id
            mock_set_context.return_value = None
            
            # Call the function
            result = await get_tenant_db_session(mock_request, mock_session)
            
            # Assertions
            assert result is mock_session
            mock_get_tenant_id.assert_called_once_with(mock_request)
            mock_set_context.assert_called_once_with(mock_session, tenant_id)

    @pytest.mark.asyncio
    async def test_get_tenant_db_session_with_different_tenant_ids(self):
        """Test get_tenant_db_session with different tenant IDs."""
        mock_request = MagicMock(spec=Request)
        mock_session = AsyncMock(spec=AsyncSession)
        
        test_tenant_ids = [
            str(uuid4()),
            str(uuid4()),
            "test-tenant-123",
            "another-tenant-456",
        ]
        
        for tenant_id in test_tenant_ids:
            with patch("src.multi_tenant_db.core.deps.get_current_tenant_id") as mock_get_tenant_id, \
                 patch("src.multi_tenant_db.core.deps.set_tenant_context") as mock_set_context:
                
                mock_get_tenant_id.return_value = tenant_id
                mock_set_context.return_value = None
                
                result = await get_tenant_db_session(mock_request, mock_session)
                
                assert result is mock_session
                mock_get_tenant_id.assert_called_once_with(mock_request)
                mock_set_context.assert_called_once_with(mock_session, tenant_id)

    @pytest.mark.asyncio
    async def test_get_tenant_db_session_propagates_exceptions(self):
        """Test that get_tenant_db_session propagates exceptions from dependencies."""
        mock_request = MagicMock(spec=Request)
        mock_session = AsyncMock(spec=AsyncSession)
        
        # Test exception from get_current_tenant_id
        with patch("src.multi_tenant_db.core.deps.get_current_tenant_id") as mock_get_tenant_id:
            mock_get_tenant_id.side_effect = ValueError("Tenant ID not found")
            
            with pytest.raises(ValueError, match="Tenant ID not found"):
                await get_tenant_db_session(mock_request, mock_session)

    @pytest.mark.asyncio
    async def test_get_tenant_db_session_propagates_context_exceptions(self):
        """Test that get_tenant_db_session propagates exceptions from set_tenant_context."""
        mock_request = MagicMock(spec=Request)
        mock_session = AsyncMock(spec=AsyncSession)
        tenant_id = str(uuid4())
        
        with patch("src.multi_tenant_db.core.deps.get_current_tenant_id") as mock_get_tenant_id, \
             patch("src.multi_tenant_db.core.deps.set_tenant_context") as mock_set_context:
            
            mock_get_tenant_id.return_value = tenant_id
            mock_set_context.side_effect = RuntimeError("Database context error")
            
            with pytest.raises(RuntimeError, match="Database context error"):
                await get_tenant_db_session(mock_request, mock_session)

    @pytest.mark.asyncio
    async def test_get_tenant_db_session_call_order(self):
        """Test that get_tenant_db_session calls dependencies in correct order."""
        mock_request = MagicMock(spec=Request)
        mock_session = AsyncMock(spec=AsyncSession)
        tenant_id = str(uuid4())
        
        call_order = []
        
        def mock_get_tenant_id(request):
            call_order.append("get_tenant_id")
            return tenant_id
        
        async def mock_set_context(session, tid):
            call_order.append("set_context")
            assert tid == tenant_id  # Verify correct tenant_id is passed
            assert session is mock_session  # Verify correct session is passed
        
        with patch("src.multi_tenant_db.core.deps.get_current_tenant_id", side_effect=mock_get_tenant_id), \
             patch("src.multi_tenant_db.core.deps.set_tenant_context", side_effect=mock_set_context):
            
            result = await get_tenant_db_session(mock_request, mock_session)
            
            assert result is mock_session
            assert call_order == ["get_tenant_id", "set_context"]

    def test_get_tenant_db_session_is_async_function(self):
        """Test that get_tenant_db_session is an async function."""
        import inspect
        assert inspect.iscoroutinefunction(get_tenant_db_session)

    def test_get_tenant_db_session_signature(self):
        """Test get_tenant_db_session function signature."""
        import inspect
        
        sig = inspect.signature(get_tenant_db_session)
        params = list(sig.parameters.keys())
        
        assert len(params) == 2
        assert "request" in params
        assert "session" in params
        
        # Check parameter annotations
        request_param = sig.parameters["request"]
        session_param = sig.parameters["session"]
        
        assert request_param.annotation == Request
        assert session_param.annotation.__origin__ == Annotated  # type: ignore
        
        # Check return annotation
        assert sig.return_annotation == AsyncSession


class TestGetCurrentTenant:
    """Test cases for get_current_tenant dependency."""

    @pytest.mark.asyncio
    async def test_get_current_tenant_basic_functionality(self):
        """Test basic functionality of get_current_tenant."""
        mock_request = MagicMock(spec=Request)
        tenant_id = str(uuid4())
        
        with patch("src.multi_tenant_db.core.deps.get_current_tenant_id") as mock_get_tenant_id:
            mock_get_tenant_id.return_value = tenant_id
            
            result = await get_current_tenant(mock_request)
            
            assert result == tenant_id
            mock_get_tenant_id.assert_called_once_with(mock_request)

    @pytest.mark.asyncio
    async def test_get_current_tenant_with_different_tenant_ids(self):
        """Test get_current_tenant with different tenant ID formats."""
        mock_request = MagicMock(spec=Request)
        
        test_tenant_ids = [
            str(uuid4()),
            "tenant-123",
            "hsbc-hong-kong",
            "jp-morgan-chase",
            "subsidiary-456",
        ]
        
        for tenant_id in test_tenant_ids:
            with patch("src.multi_tenant_db.core.deps.get_current_tenant_id") as mock_get_tenant_id:
                mock_get_tenant_id.return_value = tenant_id
                
                result = await get_current_tenant(mock_request)
                
                assert result == tenant_id
                mock_get_tenant_id.assert_called_once_with(mock_request)

    @pytest.mark.asyncio
    async def test_get_current_tenant_propagates_exceptions(self):
        """Test that get_current_tenant propagates exceptions."""
        mock_request = MagicMock(spec=Request)
        
        with patch("src.multi_tenant_db.core.deps.get_current_tenant_id") as mock_get_tenant_id:
            mock_get_tenant_id.side_effect = KeyError("Tenant context missing")
            
            with pytest.raises(KeyError, match="Tenant context missing"):
                await get_current_tenant(mock_request)

    def test_get_current_tenant_is_async_function(self):
        """Test that get_current_tenant is an async function."""
        import inspect
        assert inspect.iscoroutinefunction(get_current_tenant)

    def test_get_current_tenant_signature(self):
        """Test get_current_tenant function signature."""
        import inspect
        
        sig = inspect.signature(get_current_tenant)
        params = list(sig.parameters.keys())
        
        assert len(params) == 1
        assert "request" in params
        
        # Check parameter annotation
        request_param = sig.parameters["request"]
        assert request_param.annotation == Request
        
        # Check return annotation
        assert sig.return_annotation == str

    @pytest.mark.asyncio
    async def test_get_current_tenant_returns_string(self):
        """Test that get_current_tenant returns a string."""
        mock_request = MagicMock(spec=Request)
        tenant_id = str(uuid4())
        
        with patch("src.multi_tenant_db.core.deps.get_current_tenant_id") as mock_get_tenant_id:
            mock_get_tenant_id.return_value = tenant_id
            
            result = await get_current_tenant(mock_request)
            
            assert isinstance(result, str)
            assert result == tenant_id


class TestTypeAliases:
    """Test cases for type aliases."""

    def test_tenant_db_session_alias_definition(self):
        """Test TenantDBSession type alias definition."""
        import inspect
        
        # Check that it's an Annotated type
        assert hasattr(TenantDBSession, '__origin__')
        assert TenantDBSession.__origin__ == Annotated
        
        # Check the annotation components
        args = TenantDBSession.__args__
        assert len(args) == 2
        assert args[0] == AsyncSession
        
        # The second argument should be a Depends object
        depends_obj = args[1]
        assert isinstance(depends_obj, Depends)
        assert depends_obj.dependency == get_tenant_db_session

    def test_current_tenant_alias_definition(self):
        """Test CurrentTenant type alias definition."""
        import inspect
        
        # Check that it's an Annotated type
        assert hasattr(CurrentTenant, '__origin__')
        assert CurrentTenant.__origin__ == Annotated
        
        # Check the annotation components
        args = CurrentTenant.__args__
        assert len(args) == 2
        assert args[0] == str
        
        # The second argument should be a Depends object
        depends_obj = args[1]
        assert isinstance(depends_obj, Depends)
        assert depends_obj.dependency == get_current_tenant

    def test_db_session_alias_definition(self):
        """Test DBSession type alias definition."""
        # Check that it's an Annotated type
        assert hasattr(DBSession, '__origin__')
        assert DBSession.__origin__ == Annotated
        
        # Check the annotation components
        args = DBSession.__args__
        assert len(args) == 2
        assert args[0] == AsyncSession
        
        # The second argument should be a Depends object
        depends_obj = args[1]
        assert isinstance(depends_obj, Depends)
        # Check that it depends on get_db_session (imported from session module)

    def test_type_aliases_are_properly_typed(self):
        """Test that type aliases have proper typing."""
        from typing import get_args, get_origin
        
        # TenantDBSession
        assert get_origin(TenantDBSession) == Annotated
        args = get_args(TenantDBSession)
        assert args[0] == AsyncSession
        
        # CurrentTenant
        assert get_origin(CurrentTenant) == Annotated
        args = get_args(CurrentTenant)
        assert args[0] == str
        
        # DBSession
        assert get_origin(DBSession) == Annotated
        args = get_args(DBSession)
        assert args[0] == AsyncSession

    def test_type_aliases_usage_in_function_signatures(self):
        """Test that type aliases can be used in function signatures."""
        # This tests that the type aliases are properly constructed
        def example_route_handler(
            db: TenantDBSession,
            tenant_id: CurrentTenant,
            plain_db: DBSession,
        ) -> dict:
            return {"db": db, "tenant_id": tenant_id, "plain_db": plain_db}
        
        import inspect
        sig = inspect.signature(example_route_handler)
        
        # Check parameter annotations
        db_param = sig.parameters["db"]
        tenant_param = sig.parameters["tenant_id"]
        plain_db_param = sig.parameters["plain_db"]
        
        assert db_param.annotation == TenantDBSession
        assert tenant_param.annotation == CurrentTenant
        assert plain_db_param.annotation == DBSession


class TestDependencyIntegration:
    """Test cases for dependency integration scenarios."""

    @pytest.mark.asyncio
    async def test_dependencies_work_together(self):
        """Test that dependencies work together in realistic scenarios."""
        mock_request = MagicMock(spec=Request)
        mock_session = AsyncMock(spec=AsyncSession)
        tenant_id = str(uuid4())
        
        # Test both dependencies with same request
        with patch("src.multi_tenant_db.core.deps.get_current_tenant_id") as mock_get_tenant_id, \
             patch("src.multi_tenant_db.core.deps.set_tenant_context") as mock_set_context:
            
            mock_get_tenant_id.return_value = tenant_id
            mock_set_context.return_value = None
            
            # Get current tenant
            current_tenant = await get_current_tenant(mock_request)
            
            # Get tenant DB session
            db_session = await get_tenant_db_session(mock_request, mock_session)
            
            assert current_tenant == tenant_id
            assert db_session is mock_session
            
            # Verify both called get_current_tenant_id (should be called twice)
            assert mock_get_tenant_id.call_count == 2
            mock_set_context.assert_called_once_with(mock_session, tenant_id)

    def test_dependency_import_structure(self):
        """Test that dependencies import correctly from their modules."""
        # Test that the functions are imported from the right modules
        from src.multi_tenant_db.core.deps import get_tenant_db_session, get_current_tenant
        from src.multi_tenant_db.api.middleware.tenant import get_current_tenant_id
        from src.multi_tenant_db.db.session import get_db_session, set_tenant_context
        
        # These should be callable
        assert callable(get_tenant_db_session)
        assert callable(get_current_tenant)
        assert callable(get_current_tenant_id)
        assert callable(get_db_session)
        assert callable(set_tenant_context)

    @pytest.mark.asyncio
    async def test_realistic_fintech_tenant_scenarios(self):
        """Test dependencies with realistic fintech tenant scenarios."""
        mock_request = MagicMock(spec=Request)
        mock_session = AsyncMock(spec=AsyncSession)
        
        fintech_tenant_scenarios = [
            {"tenant_id": "hsbc-holdings", "description": "Parent bank"},
            {"tenant_id": "hsbc-hong-kong", "description": "Regional subsidiary"},
            {"tenant_id": "jpmorgan-chase", "description": "Investment bank parent"},
            {"tenant_id": "jpmorgan-london", "description": "European subsidiary"},
            {"tenant_id": str(uuid4()), "description": "UUID-based tenant"},
        ]
        
        for scenario in fintech_tenant_scenarios:
            tenant_id = scenario["tenant_id"]
            
            with patch("src.multi_tenant_db.core.deps.get_current_tenant_id") as mock_get_tenant_id, \
                 patch("src.multi_tenant_db.core.deps.set_tenant_context") as mock_set_context:
                
                mock_get_tenant_id.return_value = tenant_id
                mock_set_context.return_value = None
                
                # Test get_current_tenant
                current_tenant = await get_current_tenant(mock_request)
                assert current_tenant == tenant_id
                
                # Test get_tenant_db_session
                db_session = await get_tenant_db_session(mock_request, mock_session)
                assert db_session is mock_session
                
                mock_set_context.assert_called_once_with(mock_session, tenant_id)

    def test_function_docstrings_and_examples(self):
        """Test that functions have proper docstrings and examples."""
        # Check get_tenant_db_session docstring
        docstring = get_tenant_db_session.__doc__
        assert docstring is not None
        assert "tenant context" in docstring.lower()
        assert "example:" in docstring.lower()
        assert "@router.get" in docstring or "async def" in docstring
        
        # Check get_current_tenant docstring
        docstring = get_current_tenant.__doc__
        assert docstring is not None
        assert "tenant id" in docstring.lower()
        assert "example:" in docstring.lower()

    @pytest.mark.asyncio
    async def test_error_handling_scenarios(self):
        """Test error handling in various scenarios."""
        mock_request = MagicMock(spec=Request)
        mock_session = AsyncMock(spec=AsyncSession)
        
        error_scenarios = [
            {
                "error": ValueError("Invalid tenant ID format"),
                "description": "Invalid tenant ID",
            },
            {
                "error": KeyError("Tenant context not found"),
                "description": "Missing tenant context",
            },
            {
                "error": RuntimeError("Database connection failed"),
                "description": "Database error",
            },
        ]
        
        for scenario in error_scenarios:
            error = scenario["error"]
            
            # Test get_current_tenant error handling
            with patch("src.multi_tenant_db.core.deps.get_current_tenant_id") as mock_get_tenant_id:
                mock_get_tenant_id.side_effect = error
                
                with pytest.raises(type(error)):
                    await get_current_tenant(mock_request)
            
            # Test get_tenant_db_session error handling from get_current_tenant_id
            with patch("src.multi_tenant_db.core.deps.get_current_tenant_id") as mock_get_tenant_id:
                mock_get_tenant_id.side_effect = error
                
                with pytest.raises(type(error)):
                    await get_tenant_db_session(mock_request, mock_session)

    def test_module_level_imports(self):
        """Test that all necessary imports are available at module level."""
        from src.multi_tenant_db.core import deps
        
        # Check that main functions are available
        assert hasattr(deps, 'get_tenant_db_session')
        assert hasattr(deps, 'get_current_tenant')
        
        # Check that type aliases are available
        assert hasattr(deps, 'TenantDBSession')
        assert hasattr(deps, 'CurrentTenant')
        assert hasattr(deps, 'DBSession')
        
        # Check that they are the same objects
        assert deps.get_tenant_db_session is get_tenant_db_session
        assert deps.get_current_tenant is get_current_tenant
        assert deps.TenantDBSession is TenantDBSession
        assert deps.CurrentTenant is CurrentTenant
        assert deps.DBSession is DBSession