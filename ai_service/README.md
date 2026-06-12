AI Orchestrator microservice (FastAPI)

Description
 - Lightweight stateless microservice that performs NLP, intent detection, entity extraction,
	 OCR orchestration and workflow orchestration for the clinicavet system.

Run (development)

1. create a virtualenv and install deps:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. run locally:

```bash
uvicorn app.main:app --reload --port 9000
```

Configuration (env vars)

- `PHP_API_URL` — base URL for the PHP backend (default: `http://localhost:8000/api`)
- `OPENAI_API_KEY` — OpenAI API key (if using OpenAI)
- `OCR_API_URL` — optional OCR provider endpoint that accepts `{image_url}` and returns `{text}`
- `LLM_PROVIDER` — choose model provider: `openai` (default) or `gemini`
- `GEMINI_API_URL` — (optional) HTTP endpoint for Gemini adapter
- `GEMINI_API_KEY` — (optional) API key for Gemini adapter
- `LOG_LEVEL` — logging level (INFO by default)

Provider selection

The service uses a provider factory (`app/providers/factory.py`) that returns a `ModelProvider`.
Set `LLM_PROVIDER=openai` or `LLM_PROVIDER=gemini` to select the adapter.

 - `openai` uses the built-in `OpenAIProvider` (HTTP call to OpenAI API).
 - `gemini` uses `GeminiAdapter`, which expects a configured `GEMINI_API_URL` that accepts
	 `{model,messages}` and returns a JSON response compatible with the rest of the code.

Do not let the service call the database directly — it calls the PHP backend via `PHPApiClient`.

API Endpoints (examples)

1) Classify intent and extract entities — `POST /chat`

```bash
curl -X POST http://localhost:9000/chat/ \
	-H 'Content-Type: application/json' \
	-d '{
		"conversation": { "conversation_id": "conv1", "history": [], "pending_action": null },
		"message": "Adiciona um novo paciente chamado Rex, cão da raça Labrador",
		"images": []
	}'
```

Successful JSON contains `intent` and `entities`.

2) Process documents/images via OCR — `POST /process-documents`

```bash
curl -X POST http://localhost:9000/process-documents/ \
	-H 'Content-Type: application/json' \
	-d '{ "images": ["https://example.com/photo1.jpg"] }'
```

3) Confirm or continue a pending action — `POST /confirm-action`

```bash
curl -X POST http://localhost:9000/confirm-action/ \
	-H 'Content-Type: application/json' \
	-d '{
		"conversation": { "conversation_id": "conv1", "history": [], "pending_action": {"action_id":"a1","tool":"CREATE_PATIENT","payload":{"name":"Rex"},"workflow_state":"WAITING_CONFIRMATION"}},
		"message": "Sim, confirma"
	}'
```

How to switch to Gemini

1. Provide a Gemini endpoint and key in env:

```bash
export LLM_PROVIDER=gemini
export GEMINI_API_URL=https://your-gemini-proxy.local/endpoint
export GEMINI_API_KEY=your_key_here
```

2. Restart the service. The factory will return `GeminiAdapter` and the rest of the code
	 will continue to call `ModelProvider.chat(...)` without knowing the provider details.

Notes and best practices

- The microservice is stateless: all state must be provided by the PHP backend in the `conversation` payload.
- The microservice never writes to the DB — it only orchestrates and returns structured payloads.
- The model prompts are controlled and limited to the allowed intent set; tools are whitelisted.
- Avoid exposing arbitrary provider endpoints — the Gemini adapter expects a safe proxy that
	exposes a constrained HTTP contract.

Development tips

- Use `LOG_LEVEL=DEBUG` locally for more verbose logs.
- Provide a mock `GEMINI_API_URL` during development that returns a simple OpenAI-like JSON to test the adapter.

Support/Extensibility

- To add a new model provider: implement `app/providers/base.ModelProvider` and register it in
	`app/providers/factory.py`.
- To add new tools, create classes under `app/tools/` implementing the `BaseTool` interface.
