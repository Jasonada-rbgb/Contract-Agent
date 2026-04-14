import base64
import json
import os
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import HTTPException, Request
from pydantic import BaseModel

from mlflow.genai.agent_server import AgentServer, setup_mlflow_git_based_version_tracking

# Load env vars from .env before importing the agent for proper auth
load_dotenv(dotenv_path=".env", override=True)

# Need to import the agent to register the functions with the server
import agent_server.agent  # noqa: E402

# Evaluator (requires pandas/openpyxl/python-dateutil in pyproject.toml)
from agent_server.claims_batch import evaluate_claims_file  # noqa: E402

agent_server = AgentServer("ResponsesAgent", enable_chat_proxy=True)

# Define the app as a module level variable to enable multiple workers
app = agent_server.app  # noqa: F841

setup_mlflow_git_based_version_tracking()


# ---------------------------------------------------------------------------
# GET /api/contracts — list available (oem, kb_id) from the KB manifest
# ---------------------------------------------------------------------------
@app.get("/api/contracts")
def get_contracts(request: Request, oem: Optional[str] = None) -> List[Dict[str, Any]]:
    from databricks.sdk import WorkspaceClient

    # Use OBO token if present, else fall back to app service principal
    token = request.headers.get("x-forwarded-access-token")
    wc = WorkspaceClient(token=token) if token else WorkspaceClient()

    kb_base = os.environ.get("KB_BUNDLE_BASE", "").strip().rstrip("/")
    if not kb_base:
        raise HTTPException(status_code=500, detail="KB_BUNDLE_BASE not configured")

    try:
        resp = wc.files.download(f"{kb_base}/manifest.json")
        data = json.loads(resp.contents.read().decode("utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not read manifest: {exc}")

    if oem:
        data = [x for x in data if str(x.get("oem")) == oem]
    return data


# ---------------------------------------------------------------------------
# POST /api/evaluate-claims — batch warranty evaluation
# ---------------------------------------------------------------------------
class EvaluateClaimsRequest(BaseModel):
    oem: str
    contract_id: str
    filename: str
    file_base64: str  # base64-encoded bytes of CSV/XLSX


def _serialize_claims_response(
    oem: str,
    contract_id: str,
    rows: list[dict[str, Any]],
    mapping_warnings: list[str],
) -> Dict[str, Any]:
    return {
        "oem": oem,
        "contract_id": contract_id,
        "rows": rows,
        "mapping_warnings": mapping_warnings,
    }


@app.post("/api/evaluate-claims")
def api_evaluate_claims(req: EvaluateClaimsRequest) -> Dict[str, Any]:
    if not req.oem or not req.contract_id:
        raise HTTPException(status_code=400, detail="oem and contract_id are required")
    if not req.filename or not req.file_base64:
        raise HTTPException(status_code=400, detail="filename and file_base64 are required")

    try:
        raw = base64.b64decode(req.file_base64)
    except Exception:
        raise HTTPException(status_code=400, detail="file_base64 is not valid base64")

    try:
        rows, mapping_warnings = evaluate_claims_file(
            file_bytes=raw,
            filename=req.filename,
            oem=req.oem,
            contract_id=req.contract_id,
        )
        return _serialize_claims_response(
            req.oem,
            req.contract_id,
            rows,
            mapping_warnings,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to evaluate claims: {e}")


@app.get("/health")
def health():
    return {"status": "ok", "app": "agent-contract-api"}


def main():
    agent_server.run(app_import_string="agent_server.start_server:app")
