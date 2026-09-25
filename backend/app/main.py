import csv
import io
import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session
from xwa_sdk import Error, Event, to_dict

from . import analyzer, database, models, schemas, security

SERVICE_VERSION = "0.3.0"
TOOL = "azuma"

ERROR_CODES = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMITED",
    500: "INTERNAL",
    502: "UPSTREAM_ERROR",
    503: "SERVICE_UNAVAILABLE",
}
RETRYABLE_STATUS = {429, 502, 503}


def _error_payload(code: str, message: str, detail=None, retryable: bool = False) -> dict:
    return {
        "error": {
            "code": code,
            "message": message,
            "detail": detail,
            "retryable": retryable,
        }
    }


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

app.add_middleware(CORSMiddleware, **security.cors_settings())
app.middleware("http")(security.auth_middleware)
app.middleware("http")(security.rate_limit_middleware)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    code = ERROR_CODES.get(exc.status_code, "HTTP_ERROR")
    message = exc.detail if isinstance(exc.detail, str) else code
    detail = exc.detail if isinstance(exc.detail, dict) else None
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_payload(code, message, detail, exc.status_code in RETRYABLE_STATUS),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content=_error_payload(
            "VALIDATION_ERROR",
            "Request validation failed.",
            {"errors": jsonable_encoder(exc.errors())},
        ),
    )


class TokenRequest(BaseModel):
    password: str


class TokenResponse(BaseModel):
    token: str
    expires_in: int


def _utcnow() -> str:
    """UTC ISO-8601 timestamp for xwa-sdk events."""
    return datetime.now(timezone.utc).isoformat()


def _dbnow() -> datetime:
    """Naive UTC timestamp for database columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


@app.get("/")
def read_root():
    return {"status": "ok", "service": TOOL, "version": SERVICE_VERSION}


@app.get("/api/health")
def health():
    db_status = "ok" if database.ping() else "error"
    return JSONResponse(
        status_code=200 if db_status == "ok" else 503,
        content={
            "status": db_status,
            "database": db_status,
            "version": SERVICE_VERSION,
            "tool": TOOL,
        },
    )


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

    for finding in result["session_findings"]:
        db.add(
            models.SessionFinding(
                analysis_id=analysis.id,
                kind=finding.kind,
                category=finding.category,
                severity=finding.severity,
                title=finding.title,
                description=finding.description,
                target_url=finding.target_url,
                method=finding.method,
                csrf_present=(
                    int(finding.csrf_present) if finding.csrf_present is not None else None
                ),
                evidence=json.dumps(finding.evidence) if finding.evidence else None,
            )
        )


@app.post("/api/auth/token", response_model=TokenResponse)
def issue_token(request: TokenRequest):
    """Issue a signed token. Only available when AZUMA_JWT_SECRET is set."""
    if not security.AUTH_REQUIRED:
        raise HTTPException(status_code=403, detail="Auth is disabled (no AZUMA_JWT_SECRET).")
    if request.password != security.AUTH_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid password.")
    return TokenResponse(
        token=security.issue_token(),
        expires_in=security.TOKEN_TTL_HOURS * 3600,
    )


def _counts(analysis: models.FormAnalysis) -> dict:
    return {
        "form_count": len(analysis.forms),
        "oauth_flow_count": len(analysis.oauth_flows),
        "session_cookie_count": len(analysis.session_cookies),
        "session_finding_count": len(analysis.session_findings),
    }


@app.get("/api/analyses", response_model=list[schemas.AnalysisListItem])
def list_analyses(db: Session = Depends(database.get_db)):
    rows = (
        db.query(models.FormAnalysis)
        .order_by(models.FormAnalysis.id.desc())
        .limit(50)
        .all()
    )
    return [
        schemas.AnalysisListItem(
            id=row.id,
            target=row.target,
            status=row.status,
            analysis_type=row.analysis_type,
            created_at=row.created_at,
            **_counts(row),
        )
        for row in rows
    ]


@app.get("/api/analyses/{analysis_id}", response_model=schemas.FormAnalysisRead)
def get_analysis(analysis_id: int, db: Session = Depends(database.get_db)):
    analysis = db.get(models.FormAnalysis, analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    return analysis


def _analysis_export(analysis: models.FormAnalysis) -> dict:
    """Full JSON export of an analysis as a downloadable file."""
    return {
        "id": analysis.id,
        "target": analysis.target,
        "status": analysis.status,
        "analysis_type": analysis.analysis_type,
        "created_at": _iso(analysis.created_at),
        "started_at": _iso(analysis.started_at),
        "finished_at": _iso(analysis.finished_at),
        "error_message": analysis.error_message,
        "forms": [
            {
                "page_url": form.page_url,
                "action": form.action,
                "method": form.method,
                "enctype": form.enctype,
                "is_secure": bool(form.is_secure),
                "redirect_chain": json.loads(form.redirect_chain) if form.redirect_chain else [],
                "fields": [
                    {
                        "name": f.name,
                        "input_type": f.input_type,
                        "required": bool(f.required),
                        "is_csrf": bool(f.is_csrf),
                        "autocomplete": f.autocomplete,
                    }
                    for f in form.fields
                ],
            }
            for form in analysis.forms
        ],
        "oauth_flows": [
            {
                "endpoint": flow.endpoint,
                "flow_type": flow.flow_type,
                "client_id": flow.client_id,
                "redirect_uri": flow.redirect_uri,
                "scope": flow.scope,
                "uses_state": bool(flow.uses_state),
                "weakness": flow.weakness,
            }
            for flow in analysis.oauth_flows
        ],
        "session_cookies": [
            {
                "name": cookie.name,
                "domain": cookie.domain,
                "path": cookie.path,
                "http_only": bool(cookie.http_only),
                "secure": bool(cookie.secure),
                "same_site": cookie.same_site,
                "max_age": cookie.max_age,
            }
            for cookie in analysis.session_cookies
        ],
        "session_findings": [
            {
                "kind": finding.kind,
                "category": finding.category,
                "severity": finding.severity,
                "title": finding.title,
                "description": finding.description,
                "target_url": finding.target_url,
                "method": finding.method,
                "csrf_present": (
                    bool(finding.csrf_present) if finding.csrf_present is not None else None
                ),
                "evidence": json.loads(finding.evidence) if finding.evidence else None,
            }
            for finding in analysis.session_findings
        ],
    }


CSV_HEADER = [
    "kind",
    "analysis_id",
    "target",
    "page_url",
    "method",
    "action",
    "enctype",
    "is_secure",
    "field_name",
    "field_type",
    "field_required",
    "field_csrf",
    "field_autocomplete",
    "endpoint",
    "flow_type",
    "client_id",
    "redirect_uri",
    "scope",
    "uses_state",
    "weakness",
    "cookie_name",
    "cookie_domain",
    "cookie_path",
    "http_only",
    "secure",
    "same_site",
    "max_age",
    "finding_kind",
    "finding_severity",
    "finding_title",
    "finding_description",
    "finding_target_url",
    "finding_method",
    "finding_csrf",
    "finding_evidence",
]

def _export_csv(analysis: models.FormAnalysis) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_HEADER, restval="")
    writer.writeheader()

    base = {"analysis_id": analysis.id, "target": analysis.target}

    for form in analysis.forms:
        form_base = {
            **base,
            "kind": "form",
            "page_url": form.page_url or "",
            "method": form.method or "",
            "action": form.action or "",
            "enctype": form.enctype or "",
            "is_secure": int(form.is_secure or 0),
        }
        if not form.fields:
            writer.writerow(form_base)
        for field in form.fields:
            writer.writerow(
                {
                    **form_base,
                    "field_name": field.name or "",
                    "field_type": field.input_type or "",
                    "field_required": int(field.required or 0),
                    "field_csrf": int(field.is_csrf or 0),
                    "field_autocomplete": field.autocomplete or "",
                }
            )

    for flow in analysis.oauth_flows:
        writer.writerow(
            {
                **base,
                "kind": "oauth_flow",
                "endpoint": flow.endpoint or "",
                "flow_type": flow.flow_type or "",
                "client_id": flow.client_id or "",
                "redirect_uri": flow.redirect_uri or "",
                "scope": flow.scope or "",
                "uses_state": int(flow.uses_state or 0),
                "weakness": flow.weakness or "",
            }
        )

    for cookie in analysis.session_cookies:
        writer.writerow(
            {
                **base,
                "kind": "session_cookie",
                "cookie_name": cookie.name or "",
                "cookie_domain": cookie.domain or "",
                "cookie_path": cookie.path or "",
                "http_only": int(cookie.http_only or 0),
                "secure": int(cookie.secure or 0),
                "same_site": cookie.same_site or "",
                "max_age": cookie.max_age or "",
            }
        )

    for finding in analysis.session_findings:
        writer.writerow(
            {
                **base,
                "kind": "session_finding",
                "finding_kind": finding.kind or "",
                "finding_severity": finding.severity or "",
                "finding_title": finding.title or "",
                "finding_description": finding.description or "",
                "finding_target_url": finding.target_url or "",
                "finding_method": finding.method or "",
                "finding_csrf": (
                    int(finding.csrf_present) if finding.csrf_present is not None else ""
                ),
                "finding_evidence": finding.evidence or "",
            }
        )

    return buffer.getvalue()


@app.get("/api/analyses/{analysis_id}/export")
def export_analysis(
    analysis_id: int,
    fmt: Literal["json", "csv"] = Query("json", alias="format"),
    db: Session = Depends(database.get_db),
):
    """Download an analysis as JSON (default) or CSV."""
    analysis = db.get(models.FormAnalysis, analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found.")

    if fmt == "csv":
        return Response(
            content=_export_csv(analysis),
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="azuma-analysis-{analysis.id}.csv"'
            },
        )

    return JSONResponse(
        content=_analysis_export(analysis),
        headers={
            "Content-Disposition": f'attachment; filename="azuma-analysis-{analysis.id}.json"'
        },
    )


@app.delete("/api/analyses/{analysis_id}", status_code=204)
def delete_analysis(analysis_id: int, db: Session = Depends(database.get_db)):
    analysis = db.get(models.FormAnalysis, analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    db.delete(analysis)
    db.commit()
    return Response(status_code=204)


@app.delete("/api/analyses", status_code=204)
def delete_all_analyses(db: Session = Depends(database.get_db)):
    db.query(models.FormAnalysis).delete()
    db.commit()
    return Response(status_code=204)


@app.post("/api/forms/discover", response_model=schemas.DiscoverResponse)
async def discover_forms(
    request: schemas.DiscoverRequest,
    db: Session = Depends(database.get_db),
):
    analysis = models.FormAnalysis(
        target=request.target, status="RUNNING", started_at=_dbnow()
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    try:
        result = await analyzer.analyze_target(request.target)
        _persist_analysis(db, analysis, result)
        analysis.status = "COMPLETED"
        analysis.finished_at = _dbnow()
        db.commit()
    except analyzer.TargetError as exc:
        analysis.status = "ERROR"
        analysis.finished_at = _dbnow()
        analysis.error_message = str(exc)
        db.commit()
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    db.refresh(analysis)
    return schemas.DiscoverResponse(analysis=analysis, **_counts(analysis))


@app.websocket("/api/forms/live")
async def websocket_forms(websocket: WebSocket, target: str, token: str | None = None):
    """Persist the analysis and stream the full pipeline as xwa-sdk Events."""
    if security.AUTH_REQUIRED and not security.validate_ws_token(token):
        await websocket.close(code=1008, reason="Unauthorized")
        return

    await websocket.accept()

    db = database.SessionLocal()
    analysis = models.FormAnalysis(
        target=target, status="RUNNING", started_at=_dbnow()
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    analysis_id = str(analysis.id)
    seq = 0

    def event(event_type: str, payload=None) -> str:
        nonlocal seq
        seq += 1
        return json.dumps(
            to_dict(
                Event(
                    seq=seq,
                    type=event_type,
                    tool=TOOL,
                    analysis_id=analysis_id,
                    ts=_utcnow(),
                    payload=payload,
                )
            )
        )

    try:
        await websocket.send_text(event("analysis_started", {"target": target}))
        result = await analyzer.analyze_target(target)
        _persist_analysis(db, analysis, result)
        analysis.status = "COMPLETED"
        analysis.finished_at = _dbnow()
        db.commit()

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
        for finding in result["session_findings"]:
            await websocket.send_text(event("item_found", {
                "kind": "session_finding", "severity": finding.severity,
                "title": finding.title, "target_url": finding.target_url,
            }))

        await websocket.send_text(event("analysis_completed", _counts(analysis)))
    except analyzer.TargetError as exc:
        analysis.status = "ERROR"
        analysis.finished_at = _dbnow()
        analysis.error_message = str(exc)
        db.commit()
        try:
            await websocket.send_text(
                event("analysis_error", to_dict(Error(code="TARGET_ERROR", message=str(exc), retryable=True)))
            )
        except WebSocketDisconnect:
            return
    except WebSocketDisconnect:
        analysis.status = "CANCELLED"
        analysis.finished_at = _dbnow()
        db.commit()
    finally:
        db.close()
