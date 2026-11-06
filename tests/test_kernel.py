import json
import math
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from pnlio_kernel import AuditLog, ActuatorGuard, PNLIOKernel, RCRSample, SafetyState


def make_kernel(tmp_path):
    audit = AuditLog(Path(tmp_path) / "audit.jsonl", b"test-audit-key")
    return PNLIOKernel(b"test-kernel-key", audit)


def sample(value, now=None):
    x = math.sqrt(value)
    return RCRSample(x, x, 0.0, now or time.time())


class KernelTests(unittest.TestCase):
    def test_kernel_starts_safe_and_enters_normal(self):
        with TemporaryDirectory() as tmp:
            kernel = make_kernel(tmp)
            self.assertIs(kernel.state, SafetyState.SAFE)
            self.assertAlmostEqual(kernel.ingest_sample(sample(0.8)), 0.8)
            self.assertIs(kernel.state, SafetyState.NORMAL)

    def test_low_rcr_enters_safe(self):
        with TemporaryDirectory() as tmp:
            kernel = make_kernel(tmp)
            kernel.ingest_sample(sample(0.2))
            self.assertIs(kernel.state, SafetyState.SAFE)

    def test_authorization_is_single_use(self):
        with TemporaryDirectory() as tmp:
            kernel = make_kernel(tmp)
            kernel.ingest_sample(sample(0.8))
            params = {"mode": "observe", "limit": 1}
            auth = kernel.issue_authorization("a-1", "operator-1", params)
            guard = ActuatorGuard(kernel)
            self.assertEqual(guard.release(auth, params, lambda p: "ok"), "ok")
            with self.assertRaises(PermissionError):
                guard.release(auth, params, lambda _: "must-not-run")

    def test_parameters_and_signature_are_verified(self):
        with TemporaryDirectory() as tmp:
            kernel = make_kernel(tmp)
            kernel.ingest_sample(sample(0.8))
            auth = kernel.issue_authorization("a-2", "operator-1", {"limit": 1})
            self.assertFalse(kernel.verify_authorization(auth, {"limit": 2}))

    def test_invalid_sample_is_audited_and_fault_is_sticky(self):
        with TemporaryDirectory() as tmp:
            kernel = make_kernel(tmp)
            kernel.report_fault("watchdog")
            with self.assertRaises(ValueError):
                kernel.ingest_sample(RCRSample(2.0, 0.5, 0.0, time.time()))
            self.assertIs(kernel.state, SafetyState.FAULT)
            events = [json.loads(line)["event"] for line in Path(tmp, "audit.jsonl").read_text().splitlines()]
            self.assertIn("sample_denied", events)
            kernel.clear_fault("operator-1")
            self.assertIs(kernel.state, SafetyState.SAFE)

    def test_hardware_error_transitions_to_fault(self):
        with TemporaryDirectory() as tmp:
            kernel = make_kernel(tmp)
            kernel.ingest_sample(sample(0.8))
            auth = kernel.issue_authorization("a-3", "operator-1", {})
            with self.assertRaises(RuntimeError):
                ActuatorGuard(kernel).release(auth, {}, lambda _: (_ for _ in ()).throw(RuntimeError("csp")))
            self.assertIs(kernel.state, SafetyState.FAULT)

    def test_audit_hmac_chain_is_present(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.jsonl"
            log = AuditLog(path, b"audit-key")
            log.append("one", {})
            log.append("two", {"x": 1})
            rows = [json.loads(x) for x in path.read_text().splitlines()]
            self.assertEqual(rows[1]["previous_hash"], rows[0]["entry_hash"])
            self.assertEqual(rows[0]["sequence"], 1)
            self.assertEqual(rows[1]["sequence"], 2)
            self.assertEqual(len(rows[0]["entry_hash"]), 64)

    def test_non_finite_samples_are_rejected(self):
        with TemporaryDirectory() as tmp:
            kernel = make_kernel(tmp)
            for sample_value in (
                RCRSample(1.0, 1.0, float("nan"), time.time()),
                RCRSample(1.0, 1.0, 0.0, float("nan")),
                RCRSample(1.0, 1.0, 0.0, time.time(), float("nan")),
            ):
                with self.assertRaises(ValueError):
                    kernel.ingest_sample(sample_value)
            self.assertIs(kernel.state, SafetyState.SAFE)
            self.assertIsNone(kernel.rcr)

    def test_tampered_audit_is_rejected_on_recovery(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.jsonl"
            log = AuditLog(path, b"audit-key")
            log.append("one", {})
            row = json.loads(path.read_text().splitlines()[0])
            row["event"] = "tampered"
            path.write_text(json.dumps(row) + "\n")
            with self.assertRaises(RuntimeError):
                AuditLog(path, b"audit-key")

    def test_non_finite_authorization_parameters_are_rejected(self):
        with TemporaryDirectory() as tmp:
            kernel = make_kernel(tmp)
            kernel.ingest_sample(sample(0.8))
            with self.assertRaises(ValueError):
                kernel.issue_authorization("a-nan", "operator-1", {"limit": float("nan")})


if __name__ == "__main__":
    unittest.main()
