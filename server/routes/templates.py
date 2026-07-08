"""Legal document template endpoint. Hand-coded templates; no LLM in the
loop so users get reliable boilerplate that doesn't drift between calls."""
from fastapi import APIRouter, Depends, HTTPException, Request

from schemas import TemplateRequest, TemplateResponse
from auth import current_user
from rate_limit import burst_limit
import templates as templates_lib

router = APIRouter(prefix="/api/templates", tags=["templates"])


@router.post("/render", response_model=TemplateResponse)
@burst_limit("30/minute")
async def render_endpoint(
    request: Request, req: TemplateRequest, _user: dict = Depends(current_user)
) -> TemplateResponse:
    try:
        rendered = templates_lib.build(req.kind, req.fields)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))
    return TemplateResponse(
        kind=req.kind,
        title=rendered["title"],
        body=rendered["body"],
        notes=rendered.get("notes", []),
    )
