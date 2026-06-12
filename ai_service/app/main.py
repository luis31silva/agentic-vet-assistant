from fastapi import FastAPI
from loguru import logger
from fastapi.middleware.cors import CORSMiddleware
from app.routers import chat, process_documents, confirm_action

app = FastAPI(title="AI Orchestrator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    logger.info("AI Orchestrator starting up")


@app.get("/")
async def root():
    return {"status": "ok", "service": "ai-orchestrator"}


app.include_router(chat.router, prefix="/chat")
app.include_router(process_documents.router, prefix="/process-documents")
app.include_router(confirm_action.router, prefix="/confirm-action")
