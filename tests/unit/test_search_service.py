"""Unit tests for the VOXAORA Search & Ranking Engine"""
import pytest
from app.services.search_service import _normalize, _estimate_eta, _score_merchant


def test_normalize_invert():
    assert _normalize(0, 0, 10, invert=True) == 1.0
    assert _normalize(10, 0, 10, invert=True) == 0.0
    assert _normalize(5, 0, 10, invert=True) == 0.5


def test_normalize_equal_min_max():
    assert _normalize(5, 5, 5) == 1.0


def test_estimate_eta():
    eta = _estimate_eta(2.0, 15)
    assert eta == 15 + int((2.0 / 25) * 60) + 3


def test_score_merchant_ordering():
    merchants = [
        {
            "id": "1",
            "distance_km": 1.0,
            "estimated_eta_minutes": 20,
            "rating": 4.8,
            "min_order_amount": 20.0,
            "total_orders": 5000,
            "is_open_now": True,
        },
        {
            "id": "2",
            "distance_km": 5.0,
            "estimated_eta_minutes": 40,
            "rating": 3.5,
            "min_order_amount": 50.0,
            "total_orders": 100,
            "is_open_now": True,
        },
    ]
    score1 = _score_merchant(merchants[0], merchants)
    score2 = _score_merchant(merchants[1], merchants)
    assert score1 > score2, "Closer, faster, higher-rated merchant should score higher"


def test_score_closed_merchant_penalized():
    merchants = [
        {
            "id": "1",
            "distance_km": 2.0,
            "estimated_eta_minutes": 30,
            "rating": 4.0,
            "min_order_amount": 30.0,
            "total_orders": 2000,
            "is_open_now": False,
        },
        {
            "id": "2",
            "distance_km": 2.0,
            "estimated_eta_minutes": 30,
            "rating": 4.0,
            "min_order_amount": 30.0,
            "total_orders": 2000,
            "is_open_now": True,
        },
    ]
    score_closed = _score_merchant(merchants[0], merchants)
    score_open = _score_merchant(merchants[1], merchants)
    # When all else is equal, open merchant should score higher due to availability weight
    assert score_open > score_closed
