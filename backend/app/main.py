import asyncio
import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from sqlalchemy.orm import Session
from xwa_sdk import Event, to_dict

from . import analyzer, database, models, schemas

SERVICE_VERSION = "0.1.0"


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
        final_url, _, forms = await analyzer.discover(request.target)
        for form_data in forms:
            form = models.Form(
                analysis_id=analysis.id,
                page_url=form_data.page_url,
                action=form_data.action,
                method=form_data.method,
                enctype=form_data.enctype,
                is_secure=int(form_data.is_secure),
            )
            db.add(form)
            db.flush()
            for field in form_data.fields:
                db.add(
                    models.FormField(
                        form_id=form.id,
                        name=field.name,
                        input_type=field.input_type,
                        required=int(field.required),
                        autocomplete=field.autocomplete,
                        placeholder=field.placeholder,
                    )
                )

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
    return schemas.DiscoverResponse(analysis=analysis, form_count=len(analysis.forms))


@app.websocket("/api/forms/live")
async def websocket_forms(websocket: WebSocket, target: str):
    """Stream form discovery progress as xwa-sdk Events."""
    await websocket.accept()
    seq = 0

    def event(event_type: str, payload=None) -> str:
        nonlocal seq
        seq += 1
        return to_dict(
            Event(
                seq=seq,
                type=event_type,
                tool="azuma",
                analysis_id=target,
                ts=_utcnow(),
                payload=payload,
            )
        )

    try:
        await websocket.send_text(json.dumps(event("analysis_started", {"target": target})))
        final_url, title, forms = await analyzer.discover(target)
        await websocket.send_text(
            json.dumps(event("analysis_progress", {"page": final_url, "title": title}))
        )
        for form in forms:
            await websocket.send_text(
                json.dumps(event("item_found", to_dict(form)))
            )
        await websocket.send_text(
            json.dumps(event("analysis_completed", {"form_count": len(forms)}))
        )
    except analyzer.TargetError as exc:
        await websocket.send_text(
            json.dumps(event("analysis_error", {"code": "TARGET_ERROR", "message": str(exc)}))
        )
    except WebSocketDisconnect:
        return
