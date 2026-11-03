"""Serial adapter for the PNLIO RP2040 CSP.

This adapter sends authenticated INTENT frames. It never accesses GPIO or
actuators directly; the RP2040 CSP remains the final veto and limiter.
"""
from __future__ import annotations

import hashlib
import hmac
import time
from pathlib import Path
from typing import Any


class CSPSerialAdapter:
    def __init__(self, port: str, key: bytes, baudrate: int = 115200, serial_factory=None):
        if not key:
            raise ValueError("key es obligatoria")
        if serial_factory is None:
            import serial
            serial_factory = serial.Serial
        self.key = key
        self.serial = serial_factory(port, baudrate=baudrate, timeout=0.05)
        self.partial = b""

    @staticmethod
    def crc16(message: str) -> int:
        crc = 0xFFFF
        for byte in message.encode("utf-8"):
            crc ^= byte << 8
            for _ in range(8):
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
        return crc

    def _mac(self, message: str) -> str:
        return hmac.new(self.key, message.encode("utf-8"), hashlib.sha256).hexdigest()

    def _send(self, message: str) -> None:
        self.serial.write(f"${message}*{self.crc16(message):04X}\n".encode())

    def _read(self) -> list[list[str]]:
        self.partial += self.serial.read(512)
        frames = []
        while b"\n" in self.partial:
            raw, self.partial = self.partial.split(b"\n", 1)
            line = raw.decode("utf-8", "ignore").strip()
            if not line.startswith("$") or "*" not in line:
                continue
            body, crc_text = line[1:].rsplit("*", 1)
            try:
                if self.crc16(body) == int(crc_text, 16):
                    frames.append(body.split("|"))
            except ValueError:
                continue
        return frames

    def intent(self, auth, parameters: dict[str, Any], timeout_s: float = 0.5) -> dict[str, Any]:
        action_id = str(auth.action_id)
        velocity = float(parameters["velocity_mps"])
        torque = float(parameters["torque"])
        nonce = auth.nonce
        auth_hash = auth.signature
        canonical = f"INTENT|{action_id}|{velocity:.2f}|{torque:.2f}|{auth_hash}|{nonce}"
        self._send(canonical + "|" + self._mac(canonical))
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            for frame in self._read():
                if frame and frame[0] == "ACK" and len(frame) > 1 and frame[1] == nonce:
                    return {"status": "accepted", "frame": frame}
                if frame and frame[0] in {"NACK", "CUT"}:
                    return {"status": frame[0].lower(), "reason": "|".join(frame[1:])}
            time.sleep(0.01)
        return {"status": "timeout"}

    def close(self) -> None:
        self.serial.close()
