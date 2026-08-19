"""
Unit tests for SWIFT Dedicated Safety Validator
"""
import pytest
from backend.safety.safety_validator import safety_validator


def test_valid_signal_command():
    cmd = {
        "junction_id": "J1",
        "signal_state": "GREEN_NS",
        "green_duration": 15.0,
        "priority": True
    }
    curr = {"signal_state": "GREEN_NS", "remaining_green": 10.0}
    is_valid, reasons = safety_validator.validate_signal_command(cmd, curr)
    assert is_valid is True
    assert len(reasons) == 0


def test_reject_conflicting_green():
    cmd = {
        "junction_id": "J1",
        "signal_state": "GREEN_NS",
        "green_duration": 15.0,
        "conflicting_green_override": True
    }
    curr = {"signal_state": "GREEN_NS"}
    is_valid, reasons = safety_validator.validate_signal_command(cmd, curr)
    assert is_valid is False
    assert any("Conflicting green" in r for r in reasons)


def test_reject_short_green_duration():
    cmd = {
        "junction_id": "J2",
        "signal_state": "GREEN_EW",
        "green_duration": 1.5
    }
    curr = {"signal_state": "GREEN_EW"}
    is_valid, reasons = safety_validator.validate_signal_command(cmd, curr)
    assert is_valid is False
    assert any("minimum safe duration" in r for r in reasons)
