"""
Entry point for the Multi-Tenant Database API.

This module imports the FastAPI application from the main package
and provides the entry point for running the application.
"""

from src.multi_tenant_db.main import app

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
