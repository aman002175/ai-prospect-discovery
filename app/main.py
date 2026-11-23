"""Main FastAPI app entrypoint for the prospect discovery service."""
import logging
import os
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app import config
from app.schemas import ProspectDiscoveryRequest, ProspectDiscoveryResponse
from app.services.prospect_service import prospect_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("prospect_discovery_api")

app = FastAPI(
    title="AI-Powered Multi-Platform Prospect Discovery API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Standard CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Mask internal stack traces in production responses
@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled error at %s: %s", request.url.path, exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"}
    )

# Format validation errors into clean messages
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    msg = "Invalid request payload."
    if errors:
        first = errors[0]
        field_loc = ".".join(str(l) for l in first.get("loc", []))
        msg = f"{first.get('msg', 'Validation error')} for field '{field_loc}'"
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": msg}
    )

@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": str(exc)}
    )

@app.get("/", tags=["Info"])
async def root():
    has_tavily = bool(os.getenv("TAVILY_API_KEY", "").strip() or config.TAVILY_API_KEY)
    discovery_engine = (
        "Tavily Search API (Primary) + Multi-Tier Fallback Chain (DuckDuckGo & Bing HTML)"
        if has_tavily
        else "Multi-Tier Search Fallback (DuckDuckGo HTML, DuckDuckGo Lite, Bing HTML)"
    )
    return {
        "service": "AI-Powered Multi-Platform Prospect Discovery API",
        "version": "1.0.0",
        "status": "operational",
        "docs_url": "/docs",
        "supported_platforms": [
            "Google", "LinkedIn", "X", "YouTube",
            "Instagram", "WhatsApp", "Facebook", "Email", "Threads"
        ],
        "discovery_engine": discovery_engine,
        "ai_engine": "Google Gemini 2.0 Flash (with deterministic rule-based fallback)"
    }

@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok"}

@app.post(
    "/prospect-discovery",
    response_model=ProspectDiscoveryResponse,
    tags=["Prospect Discovery"],
    status_code=status.HTTP_200_OK
)
async def discover_prospects_endpoint(payload: ProspectDiscoveryRequest):
    return await prospect_service.discover_prospects(payload.query)

if __name__ == "__main__":
    import uvicorn
    from app.config import HOST, PORT
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=False)
