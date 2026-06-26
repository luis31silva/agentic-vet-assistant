# AI Veterinary Assistant

Microserviço FastAPI que funciona como assistente de IA para uma clínica veterinária. Orquestra NLP, classificação de intents, extração de entidades, processamento de imagens, e conselhos clínicos contextuais.

## Arquitetura

```
┌─────────────────────────────────────────────────────────┐
│  Routers (endpoints)                                     │
│  ├── POST /chat           → fluxo conversacional         │
│  ├── POST /clinical-advice → conselhos clínicos          │
│  ├── POST /confirm-action  → confirmar/cancelar ações    │
│  └── POST /process-documents → OCR de imagens            │
├─────────────────────────────────────────────────────────┤
│  Middleware                                              │
│  ├── APIKeyMiddleware     → autenticação                 │
│  └── InputValidationMiddleware → limites de input        │
├─────────────────────────────────────────────────────────┤
│  Services                                                │
│  ├── IntentService        → classificação de intent      │
│  └── ClinicalAdvisor      → recomendações clínicas       │
├─────────────────────────────────────────────────────────┤
│  Agents                                                  │
│  ├── Orchestrator         → decisão de fluxo central     │
│  └── WorkflowEngine       → execução de ações confirmadas│
├─────────────────────────────────────────────────────────┤
│  Tools (9 disponíveis)                                   │
│  ├── CreateOwnerTool                                     │
│  ├── CreatePatientTool                                   │
│  ├── CreateOwnerAndPatientTool (composto)                │
│  ├── AddVaccinesTool                                     │
│  ├── SearchPatientTool                                   │
│  ├── SearchOwnerTool                                     │
│  ├── GetPatientHistoryTool                               │
│  ├── GetAppointmentsTool                                 │
│  └── GetOwnerPatientsTool                                │
├─────────────────────────────────────────────────────────┤
│  Providers (abstração de LLM)                            │
│  ├── OpenAIAdapter        → GPT-4o-mini                  │
│  └── GeminiAdapter        → Gemini 2.5 Flash             │
├─────────────────────────────────────────────────────────┤
│  Utils                                                   │
│  ├── PHPApiClient         → HTTP client para backend PHP │
│  └── ImageProcessor       → compressão de imagens        │
└─────────────────────────────────────────────────────────┘
```

## Instalação

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Editar .env com as configurações
```

## Execução

```bash
# Desenvolvimento (auto-reload)
uvicorn app.main:app --reload --host 127.0.0.1 --port 9000

# Produção
uvicorn app.main:app --host 127.0.0.1 --port 9000 --workers 2
```

## Configuração (.env)

| Variável | Descrição | Default |
|----------|-----------|---------|
| `LLM_PROVIDER` | Provider de LLM: `openai` ou `gemini` | `openai` |
| `OPENAI_API_KEY` | API key da OpenAI | — |
| `GEMINI_API_KEY` | API key do Gemini | — |
| `PHP_API_URL` | URL base da API PHP | `http://localhost:8000/api` |
| `AI_SERVICE_KEY` | Chave partilhada para autenticação | — (sem auth em dev) |
| `ALLOWED_ORIGINS` | Origens CORS (separadas por vírgula) | `*` |
| `BIND_HOST` | Host para bind do uvicorn | `127.0.0.1` |
| `BIND_PORT` | Porta | `9000` |
| `LOG_LEVEL` | Nível de logging | `INFO` |

## Endpoints

### POST /chat

Endpoint principal — fluxo conversacional completo.

```json
// Request
{
  "conversation": {
    "conversation_id": "uuid",
    "history": [],
    "pending_action": null
  },
  "message": "Bom dia",
  "images": []
}

// Response
{
  "status": "ok",
  "response": "Bom dia! Em que posso ajudar?",
  "intent": "CHAT",
  "pending_action": null,
  "data": null
}
```

### POST /clinical-advice

Conselhos clínicos contextuais (chamado por botão dedicado).

```json
// Request
{
  "patient_id": 1,
  "symptoms": "Vómitos frequentes há 3 dias, perda de apetite"
}

// Response
{
  "status": "ok",
  "advice": "Com base nos dados do paciente..."
}
```

### POST /confirm-action

Confirmar/cancelar ação pendente.

```json
// Request
{
  "conversation": {
    "conversation_id": "uuid",
    "history": [],
    "pending_action": { "tool": "CREATE_OWNER", "payload": {...}, "workflow_state": "WAITING_CONFIRMATION" }
  },
  "message": "Sim"
}
```

## Intents suportados

| Intent | Descrição |
|--------|-----------|
| `CHAT` | Conversa geral, saudações, perguntas veterinárias |
| `CREATE_OWNER_AND_PATIENT` | Criar tutor + animal (composto) |
| `CREATE_OWNER` | Criar só tutor |
| `CREATE_PATIENT` | Criar só animal |
| `ADD_VACCINES` | Registar vacinas |
| `SEARCH_PATIENT` | Pesquisar animal |
| `SEARCH_OWNER` | Pesquisar tutor |
| `GET_PATIENT_HISTORY` | Histórico clínico |
| `GET_APPOINTMENTS` | Consultas de um animal |
| `GET_OWNER_PATIENTS` | Animais de um tutor |
| `CLINICAL_ADVICE` | Conselhos clínicos |
| `CANCEL_ACTION` | Cancelar ação pendente |

## Segurança

- **API Key**: Todas as rotas (exceto `/`) requerem header `X-API-Key`
- **Network binding**: Configurar `BIND_HOST=127.0.0.1` para não expor externamente
- **CORS**: Configurar `ALLOWED_ORIGINS` com domínios específicos em produção
- **Input limits**: Mensagens limitadas a 5000 chars, máximo 5 imagens por request
- **Sem delete**: O AI service nunca executa operações de eliminação

## Contrato com o PHP Backend

- O AI service é **stateless** — todo o estado vem no campo `conversation`
- O PHP é responsável por persistir `conversation_id`, `history`, e `pending_action`
- Imagens no `history` só devem aparecer no turn em que foram enviadas
- O PHP deve passar o JWT no header `Authorization: Bearer <token>` para que o AI service autentique chamadas à PHP API
- O AI service nunca acede à base de dados diretamente

## Extensibilidade

- **Novo provider**: Implementar `app/providers/base.ModelProvider` e registar em `factory.py`
- **Novo tool**: Criar classe em `app/tools/` implementando `BaseTool` e registar em `registry.py`
- **Novo intent**: Adicionar a `VALID_INTENTS` em `intent_service.py` e tratar no `Orchestrator`
