"""PNLIO Robot Kernel v1.1: policy core with human authorization.

The module does not drive hardware directly. A reviewed physical CSP must
accept the authenticated action and enforce independent limits.

Copyright 2026 Gonzalo Mauricio De la Rivera Arellano
SPDX-License-Identifier: Apache-2.0
"""
from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import secrets
import time
from collections import deque
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from threading import RLock
from typing import Any, Callable, Deque, Optional


class SafetyState(str, Enum):
    SAFE = "SAFE"
    RESTRICTED = "RESTRICTED"
    NORMAL = "NORMAL"
    FAULT = "FAULT"


@dataclass(frozen=True)
class RCRSample:
    intensity: float
    coherence: float
    entropy: float
    timestamp: float
    quality: float = 1.0

    def validate(self) -> None:
        if not all(math.isfinite(value) for value in (
            self.intensity, self.coherence, self.entropy,
            self.timestamp, self.quality,
        )):
            raise ValueError("todos los campos de la muestra deben ser finitos")
        if not 0.0 <= self.intensity <= 1.0:
            raise ValueError("intensity debe estar entre 0 y 1")
        if not 0.0 <= self.coherence <= 1.0:
            raise ValueError("coherence debe estar entre 0 y 1")
        if self.entropy < 0.0:
            raise ValueError("entropy no puede ser negativa")
        if not 0.0 <= self.quality <= 1.0:
            raise ValueError("quality debe estar entre 0 y 1")
        if self.timestamp <= 0:
            raise ValueError("timestamp debe ser positivo")

    def value(self) -> float:
        self.validate()
        return (self.intensity * self.coherence) / (1.0 + self.entropy)


@dataclass(frozen=True)
class Authorization:
    action_id: str
    operator_id: str
    parameters_hash: str
    issued_at: float
    expires_at: float
    nonce: str
    signature: str


class AuditLog:
    """Append-only JSONL audit with an HMAC-authenticated hash chain."""

    def __init__(self, path: str | Path, secret_key: bytes):
        if not secret_key:
            raise ValueError("secret_key es obligatorio para la auditoría")
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._key = secret_key
        self._lock = RLock()
        self._sequence, self._previous_hash = self._recover_tail()

    def _recover_tail(self) -> tuple[int, str]:
        if not self.path.exists():
            return 0, "0" * 64
        expected_sequence = 1
        previous_hash = "0" * 64
        last_sequence = 0
        with self.path.open("r", encoding="utf-8") as stream:
            for line in stream:
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                    sequence = int(entry["sequence"])
                    entry_hash = str(entry["entry_hash"])
                    if sequence != expected_sequence:
                        raise ValueError("secuencia no monotónica")
                    if entry["previous_hash"] != previous_hash:
                        raise ValueError("cadena anterior no coincide")
                    unsigned = dict(entry)
                    unsigned.pop("entry_hash")
                    expected_hash = self._entry_hmac(unsigned)
                    if not hmac.compare_digest(expected_hash, entry_hash):
                        raise ValueError("HMAC de entrada inválido")
                except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                    raise RuntimeError("el log de auditoría está corrupto") from exc
                previous_hash = entry_hash
                last_sequence = sequence
                expected_sequence += 1
        return last_sequence, previous_hash

    def _entry_hmac(self, entry: dict[str, Any]) -> str:
        canonical = json.dumps(entry, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
        return hmac.new(self._key, canonical.encode("utf-8"), hashlib.sha256).hexdigest()

    def append(self, event: str, data: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            entry = {
                "sequence": self._sequence + 1,
                "timestamp": time.time(),
                "event": event,
                "data": data,
                "previous_hash": self._previous_hash,
            }
            entry["entry_hash"] = self._entry_hmac(entry)
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(entry, sort_keys=True, ensure_ascii=False) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            self._sequence = entry["sequence"]
            self._previous_hash = entry["entry_hash"]
            return entry


class PNLIOKernel:
    """Executable PNLIO policy core; hardware access stays in the CSP."""

    def __init__(
        self,
        secret_key: bytes,
        audit: AuditLog,
        window_size: int = 8,
        restricted_threshold: float = 0.50,
        safe_threshold: float = 0.35,
        sample_max_age_s: float = 2.0,
        clock: Callable[[], float] = time.time,
    ):
        if not secret_key:
            raise ValueError("secret_key es obligatorio")
        if window_size < 1:
            raise ValueError("window_size debe ser positivo")
        if not 0.0 <= safe_threshold < restricted_threshold <= 1.0:
            raise ValueError("umbrales inválidos")
        self._key = secret_key
        self.audit = audit
        self.window_size = window_size
        self.restricted_threshold = restricted_threshold
        self.safe_threshold = safe_threshold
        self.sample_max_age_s = sample_max_age_s
        if not math.isfinite(sample_max_age_s) or sample_max_age_s <= 0:
            raise ValueError("sample_max_age_s debe ser finito y positivo")
        self.clock = clock
        self._boot_time = clock()
        self._samples: Deque[float] = deque(maxlen=window_size)
        self._used_nonces: set[str] = set()
        self._lock = RLock()
        self.state = SafetyState.SAFE
        self.rcr: Optional[float] = None
        self.audit.append("kernel_started", {"state": self.state.value, "version": "1.1"})

    @staticmethod
    def parameters_hash(parameters: dict[str, Any]) -> str:
        raw = json.dumps(parameters, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def ingest_sample(self, sample: RCRSample) -> float:
        with self._lock:
            try:
                sample.validate()
                if not all(math.isfinite(value) for value in (
                    sample.intensity, sample.coherence, sample.entropy,
                    sample.timestamp, sample.quality,
                )):
                    raise ValueError("todos los campos de la muestra deben ser finitos")
                age = self.clock() - sample.timestamp
                if age < -0.5 or age > self.sample_max_age_s or sample.quality <= 0.0:
                    raise ValueError("muestra ausente, futura o demasiado antigua")
                value = sample.value()
                if not math.isfinite(value):
                    raise ValueError("valor RCR no finito")
            except ValueError as exc:
                self._transition(SafetyState.SAFE, "sample_denied", {"reason": str(exc)})
                self.audit.append("sample_denied", {"reason": str(exc)})
                raise
            self._samples.append(value)
            self.rcr = sum(self._samples) / len(self._samples)
            target = (SafetyState.SAFE if self.rcr < self.safe_threshold else
                      SafetyState.RESTRICTED if self.rcr < self.restricted_threshold else
                      SafetyState.NORMAL)
            self._transition(target, "rcr_update")
            return self.rcr

    def report_fault(self, reason: str) -> None:
        with self._lock:
            self._transition(SafetyState.FAULT, reason)

    def clear_fault(self, operator_id: str) -> None:
        with self._lock:
            if not operator_id:
                raise ValueError("operator_id es obligatorio")
            self._transition(SafetyState.SAFE, "fault_cleared_by_operator", {"operator_id": operator_id})

    def _transition(self, target: SafetyState, reason: str, extra: Optional[dict[str, Any]] = None) -> None:
        previous = self.state
        if previous == SafetyState.FAULT and reason != "fault_cleared_by_operator":
            target = SafetyState.FAULT
        self.state = target
        if previous != target or reason != "rcr_update":
            data = {"from": previous.value, "to": target.value, "reason": reason, "rcr": self.rcr}
            if extra:
                data.update(extra)
            self.audit.append("state_transition", data)

    def issue_authorization(self, action_id: str, operator_id: str, parameters: dict[str, Any], ttl_s: float = 5.0) -> Authorization:
        with self._lock:
            if self.state not in {SafetyState.NORMAL, SafetyState.RESTRICTED}:
                raise PermissionError("el estado actual no permite autorizar acciones")
            if not action_id or not operator_id or ttl_s <= 0 or ttl_s > 60:
                raise ValueError("acción, operador o TTL inválido")
            issued = self.clock()
            nonce = secrets.token_urlsafe(24)
            p_hash = self.parameters_hash(parameters)
            payload = self._auth_payload(action_id, operator_id, p_hash, issued, issued + ttl_s, nonce)
            signature = hmac.new(self._key, payload, hashlib.sha256).hexdigest()
            auth = Authorization(action_id, operator_id, p_hash, issued, issued + ttl_s, nonce, signature)
            self.audit.append("authorization_issued", {"action_id": action_id, "operator_id": operator_id, "parameters_hash": p_hash})
            return auth

    def _verify_locked(self, auth: Authorization, parameters: dict[str, Any]) -> tuple[bool, str]:
        now = self.clock()
        if self.state not in {SafetyState.NORMAL, SafetyState.RESTRICTED}:
            return False, "unsafe_state"
        if auth.issued_at < self._boot_time:
            return False, "issued_before_boot"
        if auth.nonce in self._used_nonces:
            return False, "nonce_reuse"
        if now > auth.expires_at or auth.expires_at <= auth.issued_at:
            return False, "expired"
        if self.parameters_hash(parameters) != auth.parameters_hash:
            return False, "parameters_mismatch"
        expected = hmac.new(self._key, self._auth_payload(auth.action_id, auth.operator_id, auth.parameters_hash, auth.issued_at, auth.expires_at, auth.nonce), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, auth.signature):
            return False, "bad_signature"
        return True, "ok"

    def verify_authorization(self, auth: Authorization, parameters: dict[str, Any]) -> bool:
        with self._lock:
            ok, reason = self._verify_locked(auth, parameters)
            if not ok:
                self.audit.append("authorization_denied", {"action_id": auth.action_id, "operator_id": auth.operator_id, "reason": reason})
                return False
            self._used_nonces.add(auth.nonce)
            self.audit.append("authorization_verified", {"action_id": auth.action_id, "operator_id": auth.operator_id})
            return True

    def _auth_payload(self, action_id: str, operator_id: str, p_hash: str, issued: float, expires: float, nonce: str) -> bytes:
        return "|".join((action_id, operator_id, p_hash, f"{issued:.6f}", f"{expires:.6f}", nonce)).encode()


class ActuatorGuard:
    """Deny-by-default software boundary before a physical CSP.

    `hardware_action` must hand off to a CSP that verifies the same action,
    nonce and authentication independently. Python cannot make GPIO/power
    release atomic with this lock, so this class is not a safety certificate.
    """

    def __init__(self, kernel: PNLIOKernel):
        self.kernel = kernel

    def release(self, auth: Authorization, parameters: dict[str, Any], hardware_action: Callable[[dict[str, Any]], Any]) -> Any:
        with self.kernel._lock:
            ok, reason = self.kernel._verify_locked(auth, parameters)
            if not ok:
                self.kernel.audit.append("actuator_denied", {"action_id": auth.action_id, "reason": reason})
                raise PermissionError("actuador bloqueado: autorización inválida o estado inseguro")
            self.kernel._used_nonces.add(auth.nonce)
            self.kernel.audit.append("authorization_verified", {"action_id": auth.action_id, "operator_id": auth.operator_id})
        # Do not hold the kernel lock across external I/O. The physical CSP
        # must revalidate state, nonce and limits at the handoff boundary.
        try:
            result = hardware_action(parameters)
        except Exception as exc:
            with self.kernel._lock:
                self.kernel.audit.append("actuator_error", {"action_id": auth.action_id, "error": type(exc).__name__})
                self.kernel._transition(SafetyState.FAULT, "actuator_error")
            raise
        with self.kernel._lock:
            self.kernel.audit.append("actuator_released", {"action_id": auth.action_id})
        return result
