import os, hashlib
key_path = os.path.expanduser("~/.pnlio_csp_key")
os.makedirs(os.path.dirname(key_path), exist_ok=True)
if not os.path.exists(key_path):
    with open(key_path, "wb") as f:
        f.write(hashlib.sha256(b"pnlio_etapa1_secure").digest())
    print("Clave de CSP generada en:", key_path)
os.makedirs("build", exist_ok=True)
with open("build/main.py", "w") as f:
    f.write("# Stub CSP Firmware Etapa 1\nprint('CSP Active')\n")
with open("build/manifest.json", "w") as f:
    f.write('{"version": "1.0", "status": "secured"}\n')
