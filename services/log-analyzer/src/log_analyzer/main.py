"""FastAPI application for log analysis and extraction."""

from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(
    title="Log Analyzer Service",
    description="LLM-powered log analysis and structured extraction",
    version="0.1.0",
)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "healthy", "service": "log-analyzer"}


@app.get("/health")
async def health():
    """Detailed health check."""
    return {
        "status": "healthy",
        "service": "log-analyzer",
        "version": "0.1.0",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
