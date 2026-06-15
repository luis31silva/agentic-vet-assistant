import os
from fastapi import FastAPI
from loguru import logger
from fastapi.middleware.cors import CORSMiddleware
from app.routers import chat, process_documents, confirm_action
from dotenv import load_dotenv, find_dotenv

app = FastAPI(title="AI Orchestrator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Forçar o Python a procurar o ficheiro .env no disco
caminho_env = find_dotenv()
load_dotenv(caminho_env)

@app.on_event("startup")
async def startup_event():
    logger.info("=== DIAGNÓSTICO DE AMBIENTE ===")
    logger.info(f"O Python está a correr a partir de: {os.getcwd()}")
    logger.info(f"Ficheiro .env encontrado em: {caminho_env}")
    logger.info(f"Valor de LLM_PROVIDER na memória: {os.getenv('LLM_PROVIDER')}")
    logger.info("=================================")

@app.get("/")
async def root():
    return {"status": "ok", "service": "ai-orchestrator"}


app.include_router(chat.router, prefix="/chat")
app.include_router(process_documents.router, prefix="/process-documents")
app.include_router(confirm_action.router, prefix="/confirm-action")
