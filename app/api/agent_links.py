"""Agent link APIs: list blueprints and start chats from shareable links."""

from __future__ import annotations

import json
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.services import agent_links as links_service
from app.services import agent_links_runtime
from app.services.profile_helper import sessions as profile_sessions

router = APIRouter()
MAX_ZIP_SIZE_BYTES = 5 * 1024 * 1024
MAX_WORKSPACE_UPLOAD_SIZE_BYTES = 30 * 1024 * 1024


class AgentLinkInfo(BaseModel):
    slug: str
    name: str
    description: str
    module: str
    entry_skill: str = ""
    blueprint_root: str = ""
    agent_workdir: str = ""
    rule_file_path: str = ""
    skills_path: str = ""
    docs_path: str = ""
    template_path: str = ""
    welcome_message: str = ""
    default_model: str = ""


class StartLinkSessionRequest(BaseModel):
    session_id: str | None = None


class StartLinkSessionResponse(BaseModel):
    session_id: str
    agent_link: AgentLinkInfo
    welcome_message: str = ""
    agent_workdir: str = ""


class LinkChatRequest(BaseModel):
    session_id: str | None = None
    message: str
    model: str | None = None


class ImportPreviewResponse(BaseModel):
    files: list[str]
    total: int


class UploadWorkspaceFileResponse(BaseModel):
    session_id: str
    path: str
    size: int


def _resolve_link_or_404(slug: str) -> dict:
    link = links_service.get_agent_link(slug)
    if not link:
        raise HTTPException(status_code=404, detail=f"Agent link '{slug}' not found")
    if link.get("module") != "profile_helper":
        raise HTTPException(status_code=400, detail=f"Unsupported agent link module: {link.get('module')}")
    return link


def _ensure_bound_session(slug: str, req_session_id: str | None) -> tuple[str, dict]:
    existing = profile_sessions.get(req_session_id) if req_session_id else None
    if existing:
        bound_slug = existing.get("agent_link_slug")
        if bound_slug and bound_slug != slug:
            raise HTTPException(
                status_code=409,
                detail=f"Session already bound to '{bound_slug}', cannot reuse for '{slug}'",
            )
        sid, session = req_session_id, existing
    else:
        sid, session = profile_sessions.get_or_create(req_session_id)
    return sid, session


def _apply_link_context(session: dict, link: dict, *, newly_created: bool) -> None:
    session["agent_link_slug"] = link["slug"]
    session["agent_link_name"] = link["name"]
    # Keep blueprint root for observability; runtime uses per-session temp workspace.
    session["agent_workdir"] = link.get("agent_workdir") or ""
    session["agent_rule_file_path"] = link.get("rule_file_path") or ""
    session["agent_welcome_message"] = link.get("welcome_message") or ""
    if newly_created:
        template = links_service.load_template_for_link(link)
        if template:
            session["profile"] = template


def _safe_join_workdir(workdir: str, rel_path: str) -> Path:
    ws = Path(workdir).resolve()
    rel = Path(rel_path)
    if rel.is_absolute():
        raise HTTPException(status_code=400, detail="target_path must be relative")
    target = (ws / rel).resolve()
    if target != ws and ws not in target.parents:
        raise HTTPException(status_code=400, detail="target_path is outside workspace")
    return target


def _load_rule_prompt_for_session(link: dict, session_workdir: str) -> tuple[str, str | None]:
    """Load rule prompt using session workspace path when possible."""
    source_root_raw = str(link.get("agent_workdir") or link.get("blueprint_root") or "").strip()
    rule_raw = str(link.get("rule_file_path") or "").strip()
    if not source_root_raw or not rule_raw:
        return links_service.load_rule_prompt_for_link(link)
    try:
        source_root = Path(source_root_raw).resolve()
        rule_src = Path(rule_raw).resolve()
        rel = rule_src.relative_to(source_root)
        rule_in_session = (Path(session_workdir).resolve() / rel).resolve()
        ws = Path(session_workdir).resolve()
        if rule_in_session != ws and ws not in rule_in_session.parents:
            return links_service.load_rule_prompt_for_link(link)
        if not rule_in_session.exists() or not rule_in_session.is_file():
            return links_service.load_rule_prompt_for_link(link)
        return str(rule_in_session), rule_in_session.read_text(encoding="utf-8")
    except Exception:
        return links_service.load_rule_prompt_for_link(link)


@router.get("", response_model=list[AgentLinkInfo])
def list_agent_links():
    return [AgentLinkInfo(**x) for x in links_service.list_agent_links()]


@router.get("/{slug}", response_model=AgentLinkInfo)
def get_agent_link(slug: str):
    return AgentLinkInfo(**_resolve_link_or_404(slug))


@router.post("/import/preview", response_model=ImportPreviewResponse)
async def preview_agent_link_zip(file: UploadFile = File(...)):
    filename = (file.filename or "").lower()
    if not filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only .zip is supported")

    try:
        content = await file.read()
    finally:
        await file.close()
    if len(content) > MAX_ZIP_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="Zip file is too large. Max size is 5MB.")

    try:
        with tempfile.TemporaryDirectory(prefix="agent-link-preview-") as tmp:
            tmp_dir = Path(tmp)
            zip_path = tmp_dir / "preview.zip"
            zip_path.write_bytes(content)
            with zipfile.ZipFile(zip_path) as zf:
                files: list[str] = []
                for member in zf.infolist():
                    resolved = (tmp_dir / member.filename).resolve()
                    if tmp_dir.resolve() not in resolved.parents and resolved != tmp_dir.resolve():
                        raise HTTPException(status_code=400, detail="Invalid zip structure")
                    if member.is_dir():
                        continue
                    files.append(member.filename)
                files.sort()
                return ImportPreviewResponse(files=files[:300], total=len(files))
    except zipfile.BadZipFile as e:
        raise HTTPException(status_code=400, detail=f"Invalid zip: {e}") from e


@router.post("/import", response_model=AgentLinkInfo)
async def import_agent_link(
    file: UploadFile = File(...),
    slug: str | None = Form(None),
    name: str = Form(...),
    description: str | None = Form(None),
    rule_file_path: str = Form(...),
    welcome_message: str = Form(...),
    default_model: str | None = Form(None),
    overwrite: bool = Form(False),
):
    filename = (file.filename or "").lower()
    if not filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only .zip is supported")

    if not rule_file_path.strip():
        raise HTTPException(status_code=400, detail="rule_file_path is required")
    if not name.strip():
        raise HTTPException(status_code=400, detail="name is required")
    if not welcome_message.strip():
        raise HTTPException(status_code=400, detail="welcome_message is required")

    try:
        content = await file.read()
    finally:
        await file.close()
    if len(content) > MAX_ZIP_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="Zip file is too large. Max size is 5MB.")

    try:
        with tempfile.TemporaryDirectory(prefix="agent-link-import-") as tmp:
            tmp_dir = Path(tmp)
            zip_path = tmp_dir / "upload.zip"
            zip_path.write_bytes(content)

            extract_dir = tmp_dir / "extracted"
            extract_dir.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(zip_path) as zf:
                for member in zf.infolist():
                    member_path = extract_dir / member.filename
                    resolved = member_path.resolve()
                    if extract_dir.resolve() not in resolved.parents and resolved != extract_dir.resolve():
                        raise HTTPException(status_code=400, detail="Invalid zip structure")
                zf.extractall(extract_dir)

            children = [p for p in extract_dir.iterdir() if p.name != "__MACOSX"]
            source_dir = extract_dir
            if len(children) == 1 and children[0].is_dir():
                source_dir = children[0]

            link = links_service.import_blueprint(
                str(source_dir),
                overwrite=overwrite,
                slug_override=slug,
                name_override=name,
                description_override=description,
                rule_file_path_override=rule_file_path,
                welcome_message_override=welcome_message,
                default_model_override=default_model,
            )
            return AgentLinkInfo(**link)
    except FileExistsError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except (ValueError, FileNotFoundError, zipfile.BadZipFile) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{slug}/session", response_model=StartLinkSessionResponse)
def start_link_session(slug: str, req: StartLinkSessionRequest):
    link = _resolve_link_or_404(slug)
    existing = profile_sessions.get(req.session_id) if req.session_id else None
    sid, session = _ensure_bound_session(slug, req.session_id)
    _apply_link_context(session, link, newly_created=existing is None)
    session_workdir = agent_links_runtime.ensure_session_workspace(
        sid,
        session,
        link,
        active_session_ids=agent_links_runtime.get_active_ids(),
    )
    welcome = link.get("welcome_message") or ""
    return StartLinkSessionResponse(
        session_id=sid,
        agent_link=AgentLinkInfo(**link),
        welcome_message=welcome,
        agent_workdir=session_workdir,
    )


@router.post("/{slug}/chat", response_class=StreamingResponse)
async def chat_via_agent_link(slug: str, req: LinkChatRequest):
    link = _resolve_link_or_404(slug)
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="消息不能为空")

    existing = profile_sessions.get(req.session_id) if req.session_id else None
    session_id, session = _ensure_bound_session(slug, req.session_id)
    _apply_link_context(session, link, newly_created=existing is None)
    session_workdir = agent_links_runtime.ensure_session_workspace(
        session_id,
        session,
        link,
        active_session_ids=agent_links_runtime.get_active_ids(),
    )

    model = req.model or link.get("default_model") or None
    rule_path, rule_content = _load_rule_prompt_for_session(link, session_workdir)
    system_prompt = agent_links_runtime.build_system_prompt(
        rule_path,
        rule_content,
        workspace_dir=session_workdir,
    )

    async def generate():
        try:
            async for chunk in agent_links_runtime.stream_chat(
                session_id=session_id,
                user_message=req.message,
                workdir=session_workdir,
                system_prompt=system_prompt,
                model=model,
            ):
                payload: dict[str, Any] = dict(chunk)
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Session-Id": session_id,
            "X-Agent-Link": slug,
            "X-Agent-Workdir": session_workdir,
        },
    )


@router.post("/{slug}/files/upload", response_model=UploadWorkspaceFileResponse)
async def upload_workspace_file(
    slug: str,
    file: UploadFile = File(...),
    session_id: str | None = Form(None),
    target_path: str = Form("uploads"),
):
    link = _resolve_link_or_404(slug)
    existing = profile_sessions.get(session_id) if session_id else None
    sid, session = _ensure_bound_session(slug, session_id)
    _apply_link_context(session, link, newly_created=existing is None)
    session_workdir = agent_links_runtime.ensure_session_workspace(
        sid,
        session,
        link,
        active_session_ids=agent_links_runtime.get_active_ids(),
    )
    filename = (file.filename or "").strip()
    if not filename:
        raise HTTPException(status_code=400, detail="File name is required")
    if "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="File name cannot contain path separators")

    try:
        content = await file.read()
    finally:
        await file.close()

    size = len(content)
    if size <= 0:
        raise HTTPException(status_code=400, detail="File is empty")
    if size > MAX_WORKSPACE_UPLOAD_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="File is too large. Max size is 30MB.")

    target_dir = _safe_join_workdir(session_workdir, target_path.strip() or "uploads")
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = (target_dir / filename).resolve()
    ws = Path(session_workdir).resolve()
    if target_file != ws and ws not in target_file.parents:
        raise HTTPException(status_code=400, detail="Resolved file path is outside workspace")
    target_file.write_bytes(content)

    return UploadWorkspaceFileResponse(
        session_id=sid,
        path=str(target_file.relative_to(ws)),
        size=size,
    )
