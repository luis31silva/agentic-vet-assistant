import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from loguru import logger
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv, find_dotenv

from app.middleware.auth import APIKeyMiddleware
from app.middleware.input_validation import InputValidationMiddleware
from app.routers import chat, confirm_action, clinical_advice

# Load .env before anything else
caminho_env = find_dotenv()
load_dotenv(caminho_env)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown events."""
    logger.info("=== AI Veterinary Assistant - Starting ===")
    logger.info(f"Working directory: {os.getcwd()}")
    logger.info(f".env loaded from: {caminho_env}")
    logger.info(f"LLM_PROVIDER: {os.getenv('LLM_PROVIDER', 'openai')}")
    logger.info(f"PHP_API_URL: {os.getenv('PHP_API_URL', 'http://localhost:8000/api')}")
    logger.info(f"AI_SERVICE_KEY configured: {'Yes' if os.getenv('AI_SERVICE_KEY') else 'No (dev mode)'}")
    logger.info(f"ALLOWED_ORIGINS: {os.getenv('ALLOWED_ORIGINS', '*')}")
    logger.info("============================================")
    yield
    logger.info("=== AI Veterinary Assistant - Shutting Down ===")


app = FastAPI(
    title="AI Veterinary Assistant",
    description="AI orchestrator for veterinary clinic management",
    version="2.0.0",
    lifespan=lifespan,
)

# --- Middleware (order matters: first added = outermost) ---

# CORS - configurable origins
allowed_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Input validation (body size limits)
app.add_middleware(InputValidationMiddleware)

# API Key authentication
app.add_middleware(APIKeyMiddleware)


# --- Routes ---


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "ai-veterinary-assistant", "version": "2.0.0"}


# Main chat endpoint (handles full conversational flow)
app.include_router(chat.router, prefix="/chat", tags=["Chat"])

# Dedicated clinical advice endpoint (called from appointment button)
app.include_router(clinical_advice.router, prefix="/clinical-advice", tags=["Clinical"])

# Confirm/cancel pending actions
app.include_router(confirm_action.router, prefix="/confirm-action", tags=["Actions"])