import logging
from typing import AsyncGenerator, AsyncIterator, Optional
from uuid import uuid4

from agents.result import StreamEvent
from databricks.sdk import WorkspaceClient
from mlflow.types.responses import ResponsesAgentRequest, ResponsesAgentStreamEvent


def get_session_id(request: ResponsesAgentRequest) -> str | None:
    if request.context and request.context.conversation_id:
        return request.context.conversation_id
    if request.custom_inputs and isinstance(request.custom_inputs, dict):
        return request.custom_inputs.get("session_id")
    return None


def get_databricks_host(workspace_client: WorkspaceClient | None = None) -> Optional[str]:
    workspace_client = workspace_client or WorkspaceClient()
    try:
        return workspace_client.config.host
    except Exception as e:
        logging.exception(f"Error getting databricks host from env: {e}")
        return None


def build_mcp_url(path: str, workspace_client: WorkspaceClient | None = None) -> str:
    if not path.startswith("/"):
        return path
    hostname = get_databricks_host(workspace_client)
    return f"{hostname}{path}"


def get_user_workspace_client() -> WorkspaceClient:
    """Return a WorkspaceClient.

    Prefers the OBO token from the MLflow AgentServer request headers
    (available when running behind the FastAPI backend).  Falls back to
    default auth (service-principal in Databricks Apps) when the OBO
    token is unavailable.

    NOTE: x-forwarded-access-token is OAuth, not a PAT.  Do NOT pass
    auth_type='pat' -- let the SDK auto-detect so scopes work correctly.
    """
    try:
        from mlflow.genai.agent_server import get_request_headers

        token = get_request_headers().get("x-forwarded-access-token")
        if token:
            return WorkspaceClient(token=token)
    except Exception:
        pass
    # Fall back to default auth (service principal in Databricks Apps)
    return WorkspaceClient()


async def process_agent_stream_events(
    async_stream: AsyncIterator[StreamEvent],
) -> AsyncGenerator[ResponsesAgentStreamEvent, None]:
    curr_item_id = str(uuid4())
    async for event in async_stream:
        if event.type == "raw_response_event":
            event_data = event.data.model_dump()
            if event_data["type"] == "response.output_item.added":
                curr_item_id = str(uuid4())
                event_data["item"]["id"] = curr_item_id
            elif event_data.get("item") is not None and event_data["item"].get("id") is not None:
                event_data["item"]["id"] = curr_item_id
            elif event_data.get("item_id") is not None:
                event_data["item_id"] = curr_item_id
            yield event_data
        elif event.type == "run_item_stream_event" and event.item.type == "tool_call_output_item":
            yield ResponsesAgentStreamEvent(
                type="response.output_item.done",
                item=event.item.to_input_item(),
            )
