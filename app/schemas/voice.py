from pydantic import BaseModel
from typing import Optional, List, Dict, Any


class PreviousResult(BaseModel):
    name: str
    name_ar: Optional[str] = None
    estimated_eta_minutes: int = 0
    delivery_fee: float = 0
    distance_km: float = 0
    rating: float = 0


class VoiceContext(BaseModel):
    previous_transcript: str = ""
    previous_results: List[PreviousResult] = []
    previous_session_id: str = ""


class VoiceIntentRequest(BaseModel):
    transcript: str
    latitude: float
    longitude: float
    language: str = "ar"
    session_id: Optional[str] = None
    context: Optional[VoiceContext] = None   # multi-turn context


class VoiceIntentResponse(BaseModel):
    session_id: str
    transcript: str
    intent: Dict[str, Any]
    recommendations: List[Dict[str, Any]]
    tts_response: str
    tts_audio_url: Optional[str]
    processing_ms: int


class VoiceProcessRequest(BaseModel):
    latitude: float
    longitude: float


class VoiceConfirmRequest(BaseModel):
    session_id: str
    selected_index: int = 0
    payment_method: str = "mock"
    address_id: Optional[str] = None


class VoiceConfirmResponse(BaseModel):
    order_id: str
    order_number: str
    merchant_name: str
    estimated_eta: int
    total_amount: float
    tts_response: str
    status: str
