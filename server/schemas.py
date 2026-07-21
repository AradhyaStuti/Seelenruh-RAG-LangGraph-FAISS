"""Pydantic models for request / response payloads."""
from typing import Literal, Optional
from pydantic import BaseModel, EmailStr, Field

Domain = Literal["Mental Health", "Legal", "Government Schemes", "Safety"]
Role = Literal["user", "assistant"]
Lang = Literal["auto", "en", "hi", "hi-roman", "de"]


class HistoryMessage(BaseModel):
    role: Role
    content: str = Field(min_length=1, max_length=5000)


class ChatRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    domain: Domain
    history: list[HistoryMessage] = Field(default_factory=list, max_length=20)
    sessionId: Optional[str] = None
    lang: Lang = "auto"


class SourceChunk(BaseModel):
    id: str
    topic: str
    domain: str
    score: float
    rerankScore: Optional[float] = None
    source: Optional[str] = None          # citation string (e.g. "PWDVA · NALSA")
    sourceUrl: Optional[str] = None       # resolved official URL
    lastVerifiedOn: Optional[str] = None
    verifiedBy: Optional[str] = "human"
    # Enriched fields from knowledge_meta
    documentType: Optional[str] = None
    sourceAuthority: Optional[str] = None
    reviewStatus: Optional[str] = None
    reviewNote: Optional[str] = None
    reviewFrequency: Optional[str] = None
    weightedScore: Optional[float] = None


class RoutingTrace(BaseModel):
    intent: Optional[str] = None
    reasoning: Optional[str] = None
    emotion: Optional[str] = None
    routedDomain: Optional[str] = None
    requestedDomain: Optional[str] = None
    lang: Optional[str] = None
    isEmergency: bool = False


class ChatResponse(BaseModel):
    response: str
    isEmergency: bool
    via: Optional[str] = None
    retrievedIds: list[str] = Field(default_factory=list)
    sources: list[SourceChunk] = Field(default_factory=list)
    citedIndices: list[int] = Field(default_factory=list)
    confidence: Literal["High", "Medium", "Low", "None"] = "None"
    routing: Optional[RoutingTrace] = None
    goal: Optional[str] = None          # active multi-turn goal the agent detected
    webSearched: bool = False           # true when agent autonomously ran a web search




class HealthResponse(BaseModel):
    ok: bool
    ts: int
    ragReady: bool
    dbConnected: bool = True
    providers: Optional[dict] = None


class SignupRequest(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=6, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    token: str           # short-lived access token (15 min)
    refreshToken: str    # long-lived refresh token (30 days), rotate on use
    user: dict


class EligibilityRequest(BaseModel):
    state: Optional[str] = Field(default=None, max_length=60)
    age: Optional[int] = Field(default=None, ge=0, le=120)
    incomeAnnual: Optional[float] = Field(default=None, ge=0)
    gender: Optional[str] = Field(default=None, max_length=20)
    isStudent: Optional[bool] = None
    isFarmer: Optional[bool] = None
    isDisabled: Optional[bool] = None
    isWidow: Optional[bool] = None
    casteCategory: Optional[str] = Field(default=None, max_length=20)  # sc | st | obc | general
    residenceType: Optional[str] = Field(default=None, max_length=10)  # urban | rural
    landholding: Optional[float] = Field(default=None, ge=0)           # acres owned


class SchemeMatch(BaseModel):
    id: str
    name: str
    summary: str
    link: str
    level: Literal["central", "state"]
    reason: str


class EligibilityResponse(BaseModel):
    matches: list[SchemeMatch]


TemplateKind = Literal["rti", "consumer_complaint", "rent_notice"]


class TemplateRequest(BaseModel):
    kind: TemplateKind
    fields: dict


class TemplateResponse(BaseModel):
    kind: TemplateKind
    title: str
    body: str
    notes: list[str] = Field(default_factory=list)


class SummaryRequest(BaseModel):
    messages: list[HistoryMessage] = Field(min_length=1, max_length=200)
    persona: Optional[str] = None
    sessionId: Optional[str] = None


class SummaryResponse(BaseModel):
    summary: str


class PinnedSummary(BaseModel):
    persona: str
    sessionId: str
    summary: str
    updatedAt: Optional[str] = None


class AllSummariesResponse(BaseModel):
    summaries: list[PinnedSummary] = Field(default_factory=list)


class ChangePasswordRequest(BaseModel):
    currentPassword: str = Field(min_length=1, max_length=128)
    newPassword: str = Field(min_length=6, max_length=128)
