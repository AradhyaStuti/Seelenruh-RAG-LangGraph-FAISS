"""Scheme eligibility checker — rule-based, no LLM involved."""
from fastapi import APIRouter, Depends, Request

from schemas import EligibilityRequest, EligibilityResponse, SchemeMatch
from auth import current_user
from rate_limit import burst_limit
import db
import eligibility

router = APIRouter(prefix="/api/schemes", tags=["schemes"])


@router.post("/match", response_model=EligibilityResponse)
@burst_limit("60/minute")
async def match_endpoint(
    request: Request, req: EligibilityRequest, _user: dict = Depends(current_user)
) -> EligibilityResponse:
    overrides = await db.load_scheme_overrides()
    hits = eligibility.match(req.model_dump(exclude_none=True), overrides=overrides)
    return EligibilityResponse(matches=[SchemeMatch(**h) for h in hits])
