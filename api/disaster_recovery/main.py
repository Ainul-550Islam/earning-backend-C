"""
Disaster Recovery System — Main FastAPI Application
"""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from disaster_recovery.routes import router
from disaster_recovery.middleware import RequestLoggingMiddleware, AuditMiddleware
from disaster_recovery.exceptions import DRBaseException, EXCEPTION_STATUS_MAP
from disaster_recovery.config import settings

app = FastAPI(
    title="Disaster Recovery System",
    description="Comprehensive DR system with backup, restore, failover, and HA management.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Middleware
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(AuditMiddleware)

# Exception handlers
@app.exception_handler(DRBaseException)
async def dr_exception_handler(request: Request, exc: DRBaseException):
    status_code = EXCEPTION_STATUS_MAP.get(type(exc), 500)
    return JSONResponse(status_code=status_code, content=exc.to_dict())

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"error": "INTERNAL_ERROR", "message": str(exc)})

# Routes
app.include_router(router)


@app.get("/health")
def health():
    return {"status": "healthy", "service": "disaster-recovery-system", "version": "1.0.0"}


@app.get("/")
def root():
    return {"message": "Disaster Recovery System API", "docs": "/docs"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.host, port=settings.port,
                workers=settings.workers, reload=settings.debug)
