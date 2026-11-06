#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PNLIO CSP - PRUEBA 2
Simulador de protocolo con transporte serial loopback.
SIN MOTORES - SIN ACTUADORES FISICOS.

Verifica:
A. MAC incorrecto
B. ARM sin heartbeat y ARM autorizado
C. INTENT de velocidad y par
D. Limites y NaN
E. Perdida de heartbeat
F. DISARM
G. Bumper
H. E-STOP simulado
"""

import json
import time
import hmac
import hashlib
import math
import os
import sys
from datetime import datetime, timezone

import serial


KEY = b"PNLIO_CSP_TEST_KEY_ONLY_NOT_FOR_HARDWARE"
HEARTBEAT_TIMEOUT = 0.25
MAX_SPEED = 100.0
MAX_TORQUE = 50.0


def canonical(data):
    clean = {k: v for k, v in data.items() if k != "mac"}
    return json.dumps(
        clean, sort_keys=True, separators=(",", ":"), allow_nan=True
    ).encode()


def sign(data, key=KEY):
    return hmac.new(key, canonical(data), hashlib.sha256).hexdigest()


class CSPSimulator:

    def __init__(self):
        self.armed = False
        self.last_heartbeat = None
        self.bumper = False
        self.estop = False
        self.speed = 0.0
        self.torque = 0.0

    def safe(self):
        self.armed = False
        self.speed = 0.0
        self.torque = 0.0

    def handle(self, message):

        received_mac = message.get("mac", "")
        expected_mac = sign(message)

        if not hmac.compare_digest(str(received_mac), expected_mac):
            self.safe()
            return {"ok": False, "reason": "INVALID_MAC"}

        command = message.get("cmd")

        if command == "HELLO":
            return {"ok": True, "reason": "HELLO_ACK"}

        if command == "HB":
            self.last_heartbeat = time.monotonic()
            return {"ok": True, "reason": "HEARTBEAT_OK"}

        if command == "ARM":
            if self.last_heartbeat is None:
                return {"ok": False, "reason": "HEARTBEAT_REQUIRED"}

            if time.monotonic() - self.last_heartbeat > HEARTBEAT_TIMEOUT:
                return {"ok": False, "reason": "HEARTBEAT_EXPIRED"}

            if self.estop or self.bumper:
                return {"ok": False, "reason": "SAFETY_INPUT_ACTIVE"}

            self.armed = True
            return {"ok": True, "reason": "ARMED"}

        if command == "INTENT":

            if not self.armed:
                return {"ok": False, "reason": "NOT_ARMED"}

            if self.last_heartbeat is None:
                self.safe()
                return {"ok": False, "reason": "NO_HEARTBEAT"}

            if time.monotonic() - self.last_heartbeat > HEARTBEAT_TIMEOUT:
                self.safe()
                return {"ok": False, "reason": "HEARTBEAT_LOST"}

            if self.estop or self.bumper:
                self.safe()
                return {"ok": False, "reason": "SAFETY_INPUT_ACTIVE"}

            speed = message.get("speed")
            torque = message.get("torque")

            if not isinstance(speed, (int, float)):
                return {"ok": False, "reason": "INVALID_SPEED"}

            if not isinstance(torque, (int, float)):
                return {"ok": False, "reason": "INVALID_TORQUE"}

            if not math.isfinite(speed) or not math.isfinite(torque):
                self.safe()
                return {"ok": False, "reason": "NON_FINITE_VALUE"}

            if abs(speed) > MAX_SPEED or abs(torque) > MAX_TORQUE:
                return {"ok": False, "reason": "LIMIT_EXCEEDED"}

            # Solo registra valores en memoria.
            # NO controla PWM ni hardware.
            self.speed = float(speed)
            self.torque = float(torque)

            return {"ok": True, "reason": "INTENT_ACCEPTED"}

        if command == "DISARM":
            self.safe()
            return {"ok": True, "reason": "DISARMED"}

        return {"ok": False, "reason": "UNKNOWN_COMMAND"}


class SerialLoopback:

    def __init__(self):
        self.port = serial.serial_for_url(
            "loop://", baudrate=115200, timeout=1
        )
        self.device = CSPSimulator()

    def send(self, message, key=KEY):

        message["mac"] = sign(message, key)

        frame = (
            json.dumps(message, allow_nan=True) + "\n"
        ).encode()

        self.port.write(frame)
        received = self.port.readline()

        if not received:
            raise RuntimeError("Timeout en transporte serial loopback")

        decoded = json.loads(received.decode().strip())
        return self.device.handle(decoded)

    def close(self):
        self.port.close()


def run_test(name, description, function):
    try:
        function()
        print(f"[OK] {name}: {description}")
        return {
            "descripcion": description,
            "resultado": "OK"
        }
    except Exception as error:
        print(f"[FAIL] {name}: {description} -> {error}")
        return {
            "descripcion": description,
            "resultado": "FAIL",
            "error": str(error)
        }


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def main():

    print("\n========================================")
    print(" PNLIO CSP - PRUEBA 2")
    print(" SIMULACION SERIAL / SIN MOTORES")
    print("========================================\n")

    results = {}

    def test_a():
        link = SerialLoopback()
        try:
            response = link.send(
                {"cmd": "HELLO"},
                key=b"WRONG_TEST_KEY"
            )
            require(not response["ok"], "Acepto MAC incorrecto")
            require(
                response["reason"] == "INVALID_MAC",
                "Respuesta MAC inesperada"
            )
        finally:
            link.close()

    results["A"] = run_test(
        "A", "Rechazo de MAC incorrecto", test_a
    )

    def test_b():
        link = SerialLoopback()
        try:
            response = link.send({"cmd": "ARM"})
            require(not response["ok"], "ARM sin heartbeat fue aceptado")

            link.send({"cmd": "HB"})
            response = link.send({"cmd": "ARM"})
            require(response["ok"], "ARM correcto fue rechazado")
        finally:
            link.close()

    results["B"] = run_test(
        "B", "ARM sin heartbeat / ARM con heartbeat", test_b
    )

    def test_c():
        link = SerialLoopback()
        try:
            link.send({"cmd": "HB"})
            link.send({"cmd": "ARM"})

            response = link.send({
                "cmd": "INTENT",
                "speed": 40.0,
                "torque": 20.0
            })

            require(response["ok"], "INTENT valido rechazado")
            require(link.device.speed == 40.0, "Velocidad incorrecta")
            require(link.device.torque == 20.0, "Par incorrecto")
        finally:
            link.close()

    results["C"] = run_test(
        "C", "INTENT valido de velocidad y par", test_c
    )

    def test_d():
        link = SerialLoopback()
        try:
            link.send({"cmd": "HB"})
            link.send({"cmd": "ARM"})

            excessive = link.send({
                "cmd": "INTENT",
                "speed": 150.0,
                "torque": 10.0
            })

            require(not excessive["ok"], "Acepto velocidad excesiva")
            require(
                excessive["reason"] == "LIMIT_EXCEEDED",
                "No detecto limite"
            )

            nan_response = link.send({
                "cmd": "INTENT",
                "speed": float("nan"),
                "torque": 10.0
            })

            require(not nan_response["ok"], "Acepto NaN")
            require(
                nan_response["reason"] == "NON_FINITE_VALUE",
                "No detecto NaN"
            )
            require(not link.device.armed, "No desarmo ante NaN")
        finally:
            link.close()

    results["D"] = run_test(
        "D", "Limite excedido y rechazo de NaN", test_d
    )

    def test_e():
        link = SerialLoopback()
        try:
            link.send({"cmd": "HB"})
            link.send({"cmd": "ARM"})

            link.device.last_heartbeat = (
                time.monotonic() - HEARTBEAT_TIMEOUT - 0.1
            )

            response = link.send({
                "cmd": "INTENT",
                "speed": 10.0,
                "torque": 5.0
            })

            require(not response["ok"], "Acepto heartbeat vencido")
            require(not link.device.armed, "No desarmo al perder heartbeat")
        finally:
            link.close()

    results["E"] = run_test(
        "E", "Corte por perdida de heartbeat", test_e
    )

    def test_f():
        link = SerialLoopback()
        try:
            link.send({"cmd": "HB"})
            link.send({"cmd": "ARM"})

            response = link.send({"cmd": "DISARM"})

            require(response["ok"], "DISARM rechazado")
            require(not link.device.armed, "Sigue armado")
            require(link.device.speed == 0.0, "Velocidad no fue a cero")
        finally:
            link.close()

    results["F"] = run_test(
        "F", "DISARM y puesta a cero", test_f
    )

    def test_g():
        link = SerialLoopback()
        try:
            link.device.bumper = True
            link.send({"cmd": "HB"})

            response = link.send({"cmd": "ARM"})

            require(not response["ok"], "ARM aceptado con bumper activo")
            require(
                response["reason"] == "SAFETY_INPUT_ACTIVE",
                "No detecto bumper"
            )
        finally:
            link.close()

    results["G"] = run_test(
        "G", "Bloqueo por bumper simulado", test_g
    )

    def test_h():
        link = SerialLoopback()
        try:
            link.device.estop = True
            link.send({"cmd": "HB"})

            response = link.send({"cmd": "ARM"})

            require(not response["ok"], "ARM aceptado con E-STOP activo")
            require(
                response["reason"] == "SAFETY_INPUT_ACTIVE",
                "No detecto E-STOP simulado"
            )
        finally:
            link.close()

    results["H"] = run_test(
        "H", "Bloqueo por E-STOP simulado", test_h
    )

    passed = sum(
        1 for result in results.values()
        if result["resultado"] == "OK"
    )

    total = len(results)

    report = {
        "fecha_utc": datetime.now(timezone.utc).isoformat(),
        "prueba": "PNLIO CSP - Etapa 2",
        "transporte": "pyserial loop://",
        "motores": False,
        "hardware_fisico": False,
        "pruebas": results,
        "resumen": {
            "aprobadas": passed,
            "total": total
        },
        "estado": "PASSED" if passed == total else "FAILED"
    }

    os.makedirs("resultados", exist_ok=True)

    output = "resultados/prueba2_csp_resultados.json"

    with open(output, "w", encoding="utf-8") as file:
        json.dump(report, file, indent=4, ensure_ascii=False)

    print("\n========================================")
    print(f" RESULTADO: {passed}/{total}")
    print(f" ESTADO: {report['estado']}")
    print(f" INFORME: {output}")
    print("========================================\n")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
