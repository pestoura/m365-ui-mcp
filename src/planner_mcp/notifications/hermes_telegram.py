"""Concrete Hermes/Telegram sink for the sanitized MFA notification contract.

This is the external Hermes adapter transport for :mod:`planner_mcp.notifications.mfa`.
It is deliberately narrow and fail-closed:

* It resolves the ``hermes`` CLI on ``PATH`` with :func:`shutil.which` and refuses to
  run unless the resolved path is **absolute** and **executable**.
* It invokes ``hermes send --to telegram <message>`` **without a shell**, passing the
  message as a positional argument (the validated host CLI contract:
  ``hermes send --to telegram "deploy finished"``).
* The message is built **only** from :class:`MfaNotification` fields. No approval
  action, callback, link, token, cookie or credential material is ever added.
* Delivery failures (lookup miss, non-absolute/non-executable path, timeout,
  nonzero exit, any exception) return ``delivered=False`` with a fixed, sanitized
  ``detail``. The exception message and subprocess stderr are **never** placed in
  the result.
* It never reads Hermes config/token files.

Requirement IDs: AUTH-099 (notification contract), AUTH-100 (fail-closed MFA
detection), AUTH-101 (encrypted-store operator sign-in automation).
"""

from __future__ import annotations

import os
import shutil
import subprocess

from planner_mcp.notifications.mfa import MfaNotification, MfaNotificationResult

_CHANNEL = "hermes-telegram"

# Bounded upper bound on a single notification send. A hang here is a delivery
# degradation, never an MFA approval.
_INVOKE_TIMEOUT_SECONDS = 10.0

# Fixed, sanitized failure details. None of these ever embed an exception
# message, argv, or subprocess stderr.
_DETAIL_NOT_FOUND = "hermes-not-found"
_DETAIL_NOT_EXECUTABLE = "hermes-not-executable"
_DETAIL_INVOKE_FAILED = "hermes-invoke-failed"
_DETAIL_NONZERO_EXIT = "hermes-nonzero-exit"
_DETAIL_SENT = "sent"


def build_message(notification: MfaNotification) -> str:
    """Build the sanitized Telegram message from notification fields only.

    The message states that approval occurs **only** in Microsoft Authenticator
    and carries no reply/action path. Every interpolated value comes from the
    closed :class:`MfaNotification` field set; no other source is consulted.
    """
    return (
        "Planner MCP MFA challenge — APPROVE ONLY in Microsoft Authenticator.\n"
        f"MFA number: {notification.mfa_number}\n"
        f"Operation: {notification.operation_id}\n"
        f"Service: {notification.service}\n"
        f"Description: {notification.description}\n"
        f"Expires at: {notification.expires_at}\n"
        f"Approval channel: {notification.approval_channel}"
    )


def hermes_telegram_sink(notification: MfaNotification) -> MfaNotificationResult:
    """Deliver a sanitized MFA notification via the Hermes ``send`` CLI.

    Fail-closed: any lookup/validation/timeout/nonzero/exception condition yields
    ``delivered=False`` with a fixed detail. No credential, token, approval action
    or subprocess output is ever returned.
    """
    hermes_path = shutil.which("hermes")
    if hermes_path is None:
        return MfaNotificationResult(
            delivered=False, channel=_CHANNEL, detail=_DETAIL_NOT_FOUND
        )

    # Require an absolute, executable binary. A relative or non-executable
    # resolution is treated as a missing/invalid transport.
    if not os.path.isabs(hermes_path) or not os.access(hermes_path, os.X_OK):
        return MfaNotificationResult(
            delivered=False, channel=_CHANNEL, detail=_DETAIL_NOT_EXECUTABLE
        )

    message = build_message(notification)
    try:
        proc = subprocess.run(  # noqa: S603, S607 - path validated absolute+executable; no shell
            [hermes_path, "send", "--to", "telegram", message],
            shell=False,
            check=False,
            timeout=_INVOKE_TIMEOUT_SECONDS,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        # Never surface the exception message or any subprocess output.
        return MfaNotificationResult(
            delivered=False, channel=_CHANNEL, detail=_DETAIL_INVOKE_FAILED
        )

    if proc.returncode != 0:
        return MfaNotificationResult(
            delivered=False, channel=_CHANNEL, detail=_DETAIL_NONZERO_EXIT
        )

    return MfaNotificationResult(delivered=True, channel=_CHANNEL, detail=_DETAIL_SENT)
