"""PNLIO CSP v0.2 for RP2040/MicroPython.

Capa de seguridad física: watchdog, E-STOP, heartbeat, límites duros y
veto local. El E-STOP debe cortar la habilitación por cable, independiente
del firmware; este módulo solo supervisa y registra ese circuito.

Protocolo autenticado (CRC detecta errores; HMAC autentica origen):
  K->CSP: HELLO|kernel_ver|fw_hash|nonce|mac
          HB|estado|rcr|nonce|mac
          ARM|nonce|mac / DISARM|nonce|mac
          INTENT|action_id|vel|par|auth_hash|nonce|mac
  CSP->K: READY|fw_ver|fw_hash, ACK|nonce, NACK|motivo, CUT|motivo

Provisionar AUTH_KEY durante el build. Nunca usar la clave de ejemplo.
SPDX-License-Identifier: Apache-2.0
"""
from machine import ADC, PWM, Pin, UART, WDT
import time
import uhashlib

try:
    import hmac
except ImportError:
    hmac = None

FW_VERSION = "csp-0.2"
FW_HASH = "REPLACE_WITH_BUILD_HASH"
AUTH_KEY = b"REPLACE_IN_SECURE_PROVISIONING"

PIN_TX, PIN_RX = 0, 1
PIN_ESTOP, PIN_CLEAR, PIN_ENABLE, PIN_BUMPER = 2, 3, 4, 7
PIN_PWM_BASE, PIN_PWM_BRAZO = 5, 6
PIN_ADC_CORRIENTE, PIN_ADC_TEMPERATURA = 26, 27
UART_BAUD = 115200
CICLO_MS = 10
HB_TIMEOUT_MS = 300
VEL_MAX_MPS = 0.8
PAR_MAX = 0.6
CORRIENTE_MAX_ADC = 65000
TEMP_MAX_ADC = 58000
KERNEL_STATES_OK = ("NORMAL", "RESTRICTED")


def crc16(text):
    crc = 0xFFFF
    for byte in text.encode("utf-8"):
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def frame(message):
    return ("$%s*%04X\n" % (message, crc16(message))).encode()


def mac_hex(message):
    if hmac is None or AUTH_KEY.startswith(b"REPLACE_"):
        return ""
    return hmac.new(AUTH_KEY, message.encode("utf-8"), uhashlib.sha256).hexdigest()


class CSP:
    def __init__(self):
        self.uart = UART(0, baudrate=UART_BAUD, tx=Pin(PIN_TX), rx=Pin(PIN_RX))
        self.wdt = WDT(timeout=200)
        self.estop = Pin(PIN_ESTOP, Pin.IN, Pin.PULL_DOWN)
        self.clear = Pin(PIN_CLEAR, Pin.IN, Pin.PULL_DOWN)
        self.bumper = Pin(PIN_BUMPER, Pin.IN, Pin.PULL_DOWN)
        self.enable = Pin(PIN_ENABLE, Pin.OUT, value=0)
        self.pwm_base = PWM(Pin(PIN_PWM_BASE), freq=20000, duty_u16=0)
        self.pwm_brazo = PWM(Pin(PIN_PWM_BRAZO), freq=20000, duty_u16=0)
        self.current = ADC(Pin(PIN_ADC_CORRIENTE))
        self.temperature = ADC(Pin(PIN_ADC_TEMPERATURA))
        self.state = "INIT"
        self.kernel_state = "SAFE"
        self.last_hb = None
        self.latched = False
        self.seen_nonces = set()
        self.partial = b""
        self.last_cycle = time.ticks_ms()
        self.cut("boot")
        self.send("READY|%s|%s" % (FW_VERSION, FW_HASH))

    def send(self, message):
        try:
            self.uart.write(frame(message))
        except OSError:
            self.cut("uart_error")

    def cut(self, reason, latch=False):
        # Physical E-STOP must also open the enable circuit without firmware.
        self.enable.value(0)
        self.pwm_base.duty_u16(0)
        self.pwm_brazo.duty_u16(0)
        if latch:
            self.latched = True
        self.state = "LATCHED" if self.latched else "CUT"
        self.send("CUT|%s" % reason)

    def valid_mac(self, canonical, supplied):
        expected = mac_hex(canonical)
        return bool(expected) and supplied and supplied == expected

    def nonce_ok(self, nonce):
        if not nonce or nonce in self.seen_nonces:
            return False
        self.seen_nonces.add(nonce)
        if len(self.seen_nonces) > 512:
            self.seen_nonces.pop()
        return True

    def read_frames(self):
        if not self.uart.any():
            return []
        try:
            self.partial += self.uart.read()
        except OSError:
            return []
        output = []
        while b"\n" in self.partial:
            raw, self.partial = self.partial.split(b"\n", 1)
            line = raw.decode("utf-8", "ignore").strip()
            if not line.startswith("$") or "*" not in line:
                continue
            body, crc = line[1:].rsplit("*", 1)
            try:
                if crc16(body) == int(crc, 16):
                    output.append(body.split("|"))
            except ValueError:
                continue
        return output

    def process(self, fields):
        if not fields:
            return
        cmd = fields[0]
        if cmd == "HELLO" and len(fields) == 5:
            ver, expected_fw, nonce, mac = fields[1:]
            canonical = "HELLO|%s|%s|%s" % (ver, expected_fw, nonce)
            if expected_fw != FW_HASH or not self.valid_mac(canonical, mac) or not self.nonce_ok(nonce):
                self.send("NACK|hello_auth")
                return
            self.send("READY|%s|%s" % (FW_VERSION, FW_HASH))
        elif cmd == "HB" and len(fields) == 5:
            state, rcr, nonce, mac = fields[1:]
            canonical = "HB|%s|%s|%s" % (state, rcr, nonce)
            if state not in ("SAFE", "RESTRICTED", "NORMAL", "FAULT") or not self.valid_mac(canonical, mac) or not self.nonce_ok(nonce):
                self.send("NACK|heartbeat_auth")
                return
            self.kernel_state = state
            self.last_hb = time.ticks_ms()
            if state == "FAULT":
                self.cut("kernel_fault", True)
        elif cmd in ("ARM", "DISARM") and len(fields) == 3:
            nonce, mac = fields[1:]
            canonical = "%s|%s" % (cmd, nonce)
            if not self.valid_mac(canonical, mac) or not self.nonce_ok(nonce):
                self.send("NACK|command_auth")
                return
            if cmd == "DISARM":
                self.cut("disarm")
            elif not self.latched and self.kernel_state in KERNEL_STATES_OK and self.fresh_hb():
                self.state = "ARMED"
                self.enable.value(1)
                self.send("ACK|%s" % nonce)
            else:
                self.send("NACK|not_armable")
        elif cmd == "INTENT" and len(fields) == 7:
            self.intent(fields[1:])
        else:
            self.send("NACK|bad_frame")

    def fresh_hb(self):
        return self.last_hb is not None and time.ticks_diff(time.ticks_ms(), self.last_hb) <= HB_TIMEOUT_MS

    def intent(self, fields):
        action_id, vel_text, par_text, auth_hash, nonce, mac = fields
        canonical = "INTENT|%s|%s|%s|%s|%s" % (action_id, vel_text, par_text, auth_hash, nonce)
        if not self.valid_mac(canonical, mac) or not self.nonce_ok(nonce):
            self.send("NACK|intent_auth")
            return
        try:
            vel, par = float(vel_text), float(par_text)
        except ValueError:
            self.send("NACK|bad_numbers")
            return
        if self.latched or self.state != "ARMED":
            self.send("NACK|not_armed")
            return
        if self.kernel_state not in KERNEL_STATES_OK or not self.fresh_hb():
            self.cut("kernel_or_heartbeat")
            return
        if vel < 0 or vel > VEL_MAX_MPS or par < 0 or par > PAR_MAX:
            self.cut("hard_limit")
            return
        if self.bumper.value() != 1:
            self.cut("bumper")
            return
        if self.current.read_u16() > CORRIENTE_MAX_ADC:
            self.cut("overcurrent")
            return
        if self.temperature.read_u16() > TEMP_MAX_ADC:
            self.cut("overtemperature")
            return
        self.pwm_base.duty_u16(int((vel / VEL_MAX_MPS) * 65535))
        self.pwm_brazo.duty_u16(int((par / PAR_MAX) * 65535))
        self.send("ACK|%s" % nonce)

    def tick(self):
        self.wdt.feed()
        if self.estop.value() != 1:
            self.cut("physical_estop", True)
        if self.latched:
            self.enable.value(0)
            self.pwm_base.duty_u16(0)
            self.pwm_brazo.duty_u16(0)
            if self.clear.value() == 1 and self.estop.value() == 1 and self.kernel_state != "FAULT":
                self.latched = False
                self.state = "CUT"
            time.sleep_ms(1)
            return
        if not self.fresh_hb():
            self.cut("heartbeat_timeout")
        if self.kernel_state not in KERNEL_STATES_OK and self.state == "ARMED":
            self.cut("kernel_state")
        if self.bumper.value() != 1 and self.state == "ARMED":
            self.cut("bumper")
        if self.current.read_u16() > CORRIENTE_MAX_ADC and self.state == "ARMED":
            self.cut("overcurrent")
        if self.temperature.read_u16() > TEMP_MAX_ADC and self.state == "ARMED":
            self.cut("overtemperature")
        for fields in self.read_frames():
            self.process(fields)
        elapsed = time.ticks_diff(time.ticks_ms(), self.last_cycle)
        if elapsed < CICLO_MS:
            time.sleep_ms(CICLO_MS - elapsed)
        self.last_cycle = time.ticks_ms()


def main():
    csp = CSP()
    while True:
        csp.tick()


if __name__ == "__main__":
    main()
