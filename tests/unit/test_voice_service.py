"""Unit tests for the VOXAORA Voice Service"""
import pytest
from app.services.voice_service import VoiceService


@pytest.fixture
def svc():
    return VoiceService()


def test_mock_transcription(svc):
    result = svc._mock_transcription()
    assert "text" in result
    assert result["confidence"] > 0


def test_mock_intent_restaurant(svc):
    intent = svc._mock_intent("أريد بيتزا كبيرة")
    assert intent["category"] == "restaurant"
    assert intent["confidence"] > 0


def test_mock_intent_pharmacy(svc):
    intent = svc._mock_intent("أحتاج دواء من الصيدلية")
    assert intent["category"] == "pharmacy"


def test_mock_intent_coffee(svc):
    intent = svc._mock_intent("قهوة لاتيه كبيرة")
    assert intent["category"] == "coffee"


def test_mock_intent_language_detection(svc):
    intent_ar = svc._mock_intent("أريد بيتزا")
    assert intent_ar["language"] == "ar"

    intent_en = svc._mock_intent("I want pizza")
    assert intent_en["language"] == "en"


def test_build_results_response_arabic(svc):
    results = [
        {"name": "Al-Baik", "name_ar": "البيك", "rating": 4.8, "estimated_eta_minutes": 20},
    ]
    response = svc.build_results_response(results, language="ar")
    assert "البيك" in response or "4.8" in response or "20" in response


def test_build_no_results(svc):
    response = svc.build_results_response([], language="ar")
    assert len(response) > 0


def test_build_confirmation_arabic(svc):
    response = svc.build_confirmation_response("البيك", 25, language="ar")
    assert "البيك" in response
    assert "25" in response
