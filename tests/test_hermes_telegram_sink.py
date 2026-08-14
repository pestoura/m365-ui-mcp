"""Focused tests for the concrete Hermes/Telegram MFA notification sink.

Tests mock ``shutil.which`` and ``subprocess`` so no real ``hermes`` binary is
invoked and no real message is sent. They prove the payload is derived **only**
from :class:`MfaNotification` fields, the CLI is invoked without a shell, and
every failure mode returns a fixed, sanitized ``delivered=False`` result with no
exception message or subprocess output leaked into the detail.
"""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

from planner_mcp.notifications.hermes_telegram import (
    build_message,
    hermes_telegram_sink,
)
from planner_mcp.notifications.mfa import MfaNotification


def make_notification() -> MfaNotification:
    return MfaNotification(
        mfa_number="123456",
        operation_id="op-abc",
        service="Microsoft Planner",
        description="Number matching required",
        expires_at="2026-08-14T12:00:00Z",
        approve_in_authenticator_only=True,
        approval_channel="microsoft_authenticator",
    )


def test_build_message_uses_only_notification_fields() -> None:
    note = make_notification()
    msg = build_message(note)

    # Every closed MfaNotification field value appears in the message.
    assert note.mfa_number in msg
    assert note.operation_id in msg
    assert note.service in msg
    assert note.description in msg
    assert note.expires_at in msg
    assert note.approval_channel in msg

    # No approval action / link / callback / secret/credential material.
    assert "http" not in msg
    assert "token" not in msg.lower()
    assert "password" not in msg.lower()
    assert "cookie" not in msg.lower()
    assert "refresh" not in msg.lower()
    # The only "approve" mention is the static Authenticator-only statement.
    assert "APPROVE ONLY in Microsoft Authenticator" in msg


@patch("builtins.open")
@patch("planner_mcp.notifications.hermes_telegram.subprocess")
@patch("planner_mcp.notifications.hermes_telegram.shutil")
@patch("planner_mcp.notifications.hermes_telegram.os")
def test_sink_sends_without_shell_and_no_file_read(
    mock_os: MagicMock,
    mock_shutil: MagicMock,
    mock_subprocess: MagicMock,
    mock_open: MagicMock,
) -> None:
    note = make_notification()
    mock_shutil.which.return_value = "/usr/local/bin/hermes"
    mock_os.path.isabs.return_value = True
    mock_os.access.return_value = True
    proc = MagicMock()
    proc.returncode = 0
    mock_subprocess.run.return_value = proc

    result = hermes_telegram_sink(note)

    assert result.delivered is True
    assert result.channel == "hermes-telegram"
    assert result.detail == "sent"
    # No Hermes config/token file is read.
    mock_open.assert_not_called()
    # Invoked without shell, exact argv, bounded timeout, no stderr capture.
    args, kwargs = mock_subprocess.run.call_args
    argv = args[0]
    assert argv == [
        "/usr/local/bin/hermes",
        "send",
        "--to",
        "telegram",
        build_message(note),
    ]
    assert kwargs.get("shell") is False
    assert kwargs.get("timeout") == 10.0
    assert kwargs.get("stdout") is mock_subprocess.DEVNULL
    assert kwargs.get("stderr") is mock_subprocess.DEVNULL


@patch("planner_mcp.notifications.hermes_telegram.subprocess")
@patch("planner_mcp.notifications.hermes_telegram.shutil")
@patch("planner_mcp.notifications.hermes_telegram.os")
def test_sink_hermes_not_found(
    mock_os: MagicMock, mock_shutil: MagicMock, mock_subprocess: MagicMock
) -> None:
    mock_shutil.which.return_value = None
    result = hermes_telegram_sink(make_notification())
    assert result.delivered is False
    assert result.detail == "hermes-not-found"
    mock_subprocess.run.assert_not_called()


@patch("planner_mcp.notifications.hermes_telegram.subprocess")
@patch("planner_mcp.notifications.hermes_telegram.shutil")
@patch("planner_mcp.notifications.hermes_telegram.os")
def test_sink_hermes_not_executable(
    mock_os: MagicMock, mock_shutil: MagicMock, mock_subprocess: MagicMock
) -> None:
    mock_shutil.which.return_value = "/usr/local/bin/hermes"
    mock_os.path.isabs.return_value = True
    mock_os.access.return_value = False
    result = hermes_telegram_sink(make_notification())
    assert result.delivered is False
    assert result.detail == "hermes-not-executable"
    mock_subprocess.run.assert_not_called()


@patch("planner_mcp.notifications.hermes_telegram.subprocess")
@patch("planner_mcp.notifications.hermes_telegram.shutil")
@patch("planner_mcp.notifications.hermes_telegram.os")
def test_sink_relative_path_rejected(
    mock_os: MagicMock, mock_shutil: MagicMock, mock_subprocess: MagicMock
) -> None:
    # shutil.which should return an absolute path; a relative match is invalid.
    mock_shutil.which.return_value = "hermes"
    mock_os.path.isabs.return_value = False
    result = hermes_telegram_sink(make_notification())
    assert result.delivered is False
    assert result.detail == "hermes-not-executable"
    mock_subprocess.run.assert_not_called()


@patch("planner_mcp.notifications.hermes_telegram.subprocess")
@patch("planner_mcp.notifications.hermes_telegram.shutil")
@patch("planner_mcp.notifications.hermes_telegram.os")
def test_sink_nonzero_exit(
    mock_os: MagicMock, mock_shutil: MagicMock, mock_subprocess: MagicMock
) -> None:
    mock_shutil.which.return_value = "/usr/local/bin/hermes"
    mock_os.path.isabs.return_value = True
    mock_os.access.return_value = True
    proc = MagicMock()
    proc.returncode = 1
    mock_subprocess.run.return_value = proc
    result = hermes_telegram_sink(make_notification())
    assert result.delivered is False
    assert result.detail == "hermes-nonzero-exit"
    # Fixed detail only; no subprocess output leaked.
    assert "1" not in result.detail


@patch("planner_mcp.notifications.hermes_telegram.subprocess")
@patch("planner_mcp.notifications.hermes_telegram.shutil")
@patch("planner_mcp.notifications.hermes_telegram.os")
def test_sink_timeout_yields_sanitized_failure(
    mock_os: MagicMock, mock_shutil: MagicMock, mock_subprocess: MagicMock
) -> None:
    mock_shutil.which.return_value = "/usr/local/bin/hermes"
    mock_os.path.isabs.return_value = True
    mock_os.access.return_value = True
    mock_subprocess.run.side_effect = subprocess.TimeoutExpired(
        cmd=["hermes", "send"], timeout=10
    )
    result = hermes_telegram_sink(make_notification())
    assert result.delivered is False
    assert result.detail == "hermes-invoke-failed"
    # No exception class name / cmd leaked into the result.
    assert "TimeoutExpired" not in result.detail
    assert "hermes', 'send" not in result.detail


@patch("planner_mcp.notifications.hermes_telegram.subprocess")
@patch("planner_mcp.notifications.hermes_telegram.shutil")
@patch("planner_mcp.notifications.hermes_telegram.os")
def test_sink_generic_exception_yields_sanitized_failure(
    mock_os: MagicMock, mock_shutil: MagicMock, mock_subprocess: MagicMock
) -> None:
    mock_shutil.which.return_value = "/usr/local/bin/hermes"
    mock_os.path.isabs.return_value = True
    mock_os.access.return_value = True
    mock_subprocess.run.side_effect = OSError("permission denied: /etc/hermes")
    result = hermes_telegram_sink(make_notification())
    assert result.delivered is False
    assert result.detail == "hermes-invoke-failed"
    assert "permission" not in result.detail
    assert "/etc/hermes" not in result.detail
