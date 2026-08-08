import asyncio
import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from xwa_sdk import Event, to_dict

from . import analyzer, database, models, schemas

SERVICE_VERSION = "0.2.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.wait_for_db()
    models.Base.metadata.create_all(bind=database.engine)
    yield


app = FastAPI(
    title="Azuma API",
    description="Web form and authentication flow analyzer",
    version=SERVICE_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@app.get("/")
def read_root():
    return {"status": "ok", "service": "azuma", "version": SERVICE_VERSION}


@app.get("/api/health")
def health(db: Session = Depends(database.get_db)):
    try:
        db.execute(database.text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "error"
    return {"status": "ok", "database": db_status, "version": SERVICE_VERSION}


def _persist_analysis(db: Session, analysis: models.FormAnalysis, result: dict) -> None:
    for form_data in result["forms"]:
        form = models.Form(
            analysis_id=analysis.id,
            page_url=form_data.page_url,
            action=form_data.action,
            method=form_data.method,
            enctype=form_data.enctype,
            is_secure=int(form_data.is_secure),
            redirect_chain=analyzer.serialize_redirect_chain(form_data.redirect_chain),
        )
        db.add(form)
        db.flush()
        for field in form_data.fields:
            db.add(
                models.FormField(
                    form_id=form.id,
                    name=field.name,
                    input_type=field.input_type,
                    value=field.value,
                    required=int(field.required),
                    autocomplete=field.autocomplete,
                    placeholder=field.placeholder,
                    is_csrf=int(field.is_csrf),
                )
            )

    for flow in result["oauth_flows"]:
        db.add(
            models.OAuthFlow(
                analysis_id=analysis.id,
                endpoint=flow.endpoint,
                flow_type=flow.flow_type,
                client_id=flow.client_id,
                redirect_uri=flow.redirect_uri,
                scope=flow.scope,
                uses_state=int(flow.uses_state),
                weakness=", ".join(flow.weakness) if flow.weakness else None,
            )
        )

    for cookie in result["session_cookies"]:
        db.add(
            models.SessionCookie(
                analysis_id=analysis.id,
                name=cookie.name,
                value_preview=cookie.value_preview,
                domain=cookie.domain,
                path=cookie.path,
                http_only=int(cookie.http_only),
                secure=int(cookie.secure),
                same_site=cookie.same_site,
                max_age=cookie.max_age,
            )
        )


@app.post("/api/forms/discover", response_model=schemas.DiscoverResponse)
async def discover_forms(
    request: schemas.DiscoverRequest,
    db: Session = Depends(database.get_db),
):
    analysis = models.FormAnalysis(
        target=request.target, status="RUNNING", started_at=datetime.utcnow()
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    try:
        result = await analyzer.analyze_target(request.target)
        _persist_analysis(db, analysis, result)
        analysis.status = "COMPLETED"
        analysis.finished_at = datetime.utcnow()
        db.commit()
    except analyzer.TargetError as exc:
        analysis.status = "ERROR"
        analysis.finished_at = datetime.utcnow()
        analysis.error_message = str(exc)
        db.commit()
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    db.refresh(analysis)
    return schemas.DiscoverResponse(
        analysis=analysis,
        form_count=len(analysis.forms),
        oauth_flow_count=len(analysis.oauth_flows),
        session_cookie_count=len(analysis.session_cookies),
    )


@app.websocket("/api/forms/live")
async def websocket_forms(websocket: WebSocket, target: str):
    """Stream the full analysis pipeline as xwa-sdk Events."""
    await websocket.accept()
    seq = 0

    def event(event_type: str, payload=None) -> str:
        nonlocal seq
        seq += 1
        return json.dumps(
            to_dict(
                Event(
                    seq=seq,
                    type=event_type,
                    tool="azuma",
                    analysis_id=target,
                    ts=_utcnow(),
                    payload=payload,
                )
            )
        )

    try:
        await websocket.send_text(event("analysis_started", {"target": target}))
        result = await analyzer.analyze_target(target)

        await websocket.send_text(
            event("analysis_progress", {"page": result["final_url"], "title": result["title"]})
        )

        for form in result["forms"]:
            await websocket.send_text(event("item_found", {
                "kind": "form", "method": form.method, "action": form.action,
                "fields": len(form.fields), "csrf": sum(1 for f in form.fields if f.is_csrf),
            }))
        for flow in result["oauth_flows"]:
            await websocket.send_text(event("item_found", {
                "kind": "oauth_flow", "endpoint": flow.endpoint, "flow_type": flow.flow_type,
            }))
        for cookie in result["session_cookies"]:
            await websocket.send_text(event("item_found", {
                "kind": "session_cookie", "name": cookie.name, "secure": cookie.secure,
            }))

        await websocket.send_text(
            event("analysis_completed", {
                "form_count": len(result["forms"]),
                "oauth_flow_count": len(result["oauth_flows"]),
                "session_cookie_count": len(result["session_cookies"]),
            })
        )
    except analyzer.TargetError as exc:
        await websocket.send_text(
            event("analysis_error", {"code": "TARGET_ERROR", "message": str(exc)})
        )
    except WebSocketDisconnect:
        return
