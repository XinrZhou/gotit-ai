"""MCP connectors settings API — CRUD, JSON import, probe."""

from __future__ import annotations

from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from gotit.api.auth import require_api_key
from gotit.api.mcp_toolsets import probe_connector
from gotit.api.routes._common import _user_id
from gotit.api.settings import Settings, get_settings
from gotit.core.models import McpConnector
from gotit.db import ops as day_ops
from gotit.db import session_scope

router = APIRouter()

Transport = Literal["stdio", "http", "sse"]


class ConnectorCreateBody(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    transport: Transport
    config: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class ConnectorPatchBody(BaseModel):
    name: str | None = None
    transport: Transport | None = None
    config: dict[str, Any] | None = None
    enabled: bool | None = None


class ConnectorImportBody(BaseModel):
    """Paste Claude/Cursor-style `{mcpServers: {...}}` or a bare server map."""

    config: dict[str, Any]


@router.get(
    "/v1/connectors",
    response_model=list[McpConnector],
    dependencies=[Depends(require_api_key)],
)
async def list_connectors(
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[McpConnector]:
    async with session_scope() as session:
        return await day_ops.list_connectors(session, user_id=_user_id(settings))


@router.post(
    "/v1/connectors",
    response_model=McpConnector,
    dependencies=[Depends(require_api_key)],
)
async def create_connector(
    body: ConnectorCreateBody,
    settings: Annotated[Settings, Depends(get_settings)],
) -> McpConnector:
    try:
        async with session_scope() as session:
            return await day_ops.upsert_connector(
                session,
                user_id=_user_id(settings),
                name=body.name,
                transport=body.transport,
                config=body.config,
                enabled=body.enabled,
            )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/v1/connectors/import",
    response_model=list[McpConnector],
    dependencies=[Depends(require_api_key)],
)
async def import_connectors(
    body: ConnectorImportBody,
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[McpConnector]:
    try:
        async with session_scope() as session:
            return await day_ops.import_connectors(
                session,
                user_id=_user_id(settings),
                payload=body.config,
            )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch(
    "/v1/connectors/{connector_id}",
    response_model=McpConnector,
    dependencies=[Depends(require_api_key)],
)
async def patch_connector(
    connector_id: UUID,
    body: ConnectorPatchBody,
    settings: Annotated[Settings, Depends(get_settings)],
) -> McpConnector:
    try:
        async with session_scope() as session:
            return await day_ops.update_connector(
                session,
                user_id=_user_id(settings),
                connector_id=connector_id,
                name=body.name,
                transport=body.transport,
                config=body.config,
                enabled=body.enabled,
            )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete(
    "/v1/connectors/{connector_id}",
    status_code=204,
    dependencies=[Depends(require_api_key)],
)
async def delete_connector(
    connector_id: UUID,
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    try:
        async with session_scope() as session:
            await day_ops.delete_connector(
                session,
                user_id=_user_id(settings),
                connector_id=connector_id,
            )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/v1/connectors/{connector_id}/probe",
    response_model=McpConnector,
    dependencies=[Depends(require_api_key)],
)
async def probe_connector_route(
    connector_id: UUID,
    settings: Annotated[Settings, Depends(get_settings)],
) -> McpConnector:
    async with session_scope() as session:
        conn = await day_ops.get_connector(
            session, user_id=_user_id(settings), connector_id=connector_id
        )
        if conn is None:
            raise HTTPException(status_code=404, detail="connector not found")
        ok, err = await probe_connector(conn)
        return await day_ops.set_connector_status(
            session,
            user_id=_user_id(settings),
            connector_id=connector_id,
            status="ok" if ok else "error",
            error=None if ok else err,
        )
