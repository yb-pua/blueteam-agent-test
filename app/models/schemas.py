from __future__ import annotations

from pydantic import BaseModel

class IoCSourceResult(BaseModel):
    source: str
    data: dict
    error: str | None = None

class IoCQueryResponse(BaseModel):
    ioc_type: str
    ioc_value: str
    score: int
    risk_level: str
    summary: str
    sources: list[IoCSourceResult]
    recommendation: str

class AlertParseRequest(BaseModel):
    raw_text: str
    source: str | None = None

class AlertMatchItem(BaseModel):
    attack_type: str
    risk_level: str
    confidence: int
    mitre_id: str | None = None
    mitre_name: str | None = None

class AlertParseResponse(BaseModel):
    attack_type: str
    mitre_id: str | None
    mitre_name: str | None
    risk_level: str
    confidence: int
    description: str
    recommendation: str
    related_techniques: list[dict]
    detected_format: str | None = None
    all_matches: list[AlertMatchItem] = []
    line_count: int | None = None
    match_count: int | None = None
    file_info: dict | None = None
