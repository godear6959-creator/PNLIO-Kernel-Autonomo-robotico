#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""COMANDANTE ADÁN 2031 v1.3.1 — Auto-despliegue total en Ubuntu (un solo archivo).
Hace TODO solo: chequeo de espacio, dependencias, Ollama, modelo phi3:mini,
entorno virtual, librerías de PDF/Word/Excel, chat y lanzador de escritorio.

USO:
    nano despliegue_adan2031.py -> pegar, Ctrl+O, Enter, Ctrl+X
    python3 despliegue_adan2031.py

Copyright 2026 Gonzalo Mauricio De la Rivera Arellano
SPDX-License-Identifier: Apache-2.0
"""
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

BANNER = """
╔══════════════════════════════════════════╗
║        COMANDANTE ADÁN 2031              ║
║   Auto-despliegue · 100% local · CPU     ║
║   Chat Local + Docs · v1.3.1             ║
╚══════════════════════════════════════════╝
"""
MODELO = "phi3:mini"
CARPETA = Path.home() / "adan2031"
ENTORNO = CARPETA / "env"
PUERTO_OLLAMA = "http://localhost:11434"
ESPACIO_MINIMO_GB = 8  # FIX: antes 6, ahora con margen real

CHAT_PY = r'''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""COMANDANTE ADÁN 2031 — Chat local con Ollama que lee tus documentos.
  /doc <ruta>  -> carga PDF, Word, Excel o txt
  /docs        -> lista documentos
  /limpiar     -> borra documentos y conversación
  /salir       -> terminar
Todo corre en localhost:11434. Nada sale de esta máquina.
"""
import json
from pathlib import Path
import requests
from pypdf import PdfReader
import docx
import pandas as pd

API = "http://localhost:11434/api/chat"
MODELO = "phi3:mini"
MAX_CARACTERES_DOC = 24_000

def extraer_texto(ruta: str) -> str:
    p = Path(ruta).expanduser()
    if not p.exists():
        raise FileNotFoundError(f"no existe: {p}")
    suf = p.suffix.lower()
    if suf == ".pdf":
        return "\n".join(pg.extract_text() or "" for pg in PdfReader(str(p)).pages)
    if suf == ".docx":
        d = docx.Document(str(p))
        return "\n".join(par.text for par in d.paragraphs if par.text)
    if suf in (".xlsx", ".xls"):
        # FIX: maneja hojas vacías
        textos = []
        for h in pd.read_excel(str(p), sheet_name=None).values():
            if h.empty:
                continue
            textos.append(h.fillna("").astype(str).to_string(index=False))
        return "\n".join(textos)
    if suf in (".txt", ".md", ".csv"):
        return p.read_text(encoding="utf-8", errors="ignore")
    raise ValueError(f"formato no soportado: {suf}")

def chat(mensajes):
    with requests.post(API, json={"model": MODELO, "messages": mensajes,
                                  "stream": True}, stream=True, timeout=600) as r:
        r.raise_for_status()
        partes = []
        for linea in r.iter_lines():
            if not linea: continue
            dato = json.loads(linea)
            trozo = dato.get("message", {}).get("content", "")
            print(trozo, end="", flush=True)
            partes.append(trozo)
            if dato.get("done"): break
        print()
        return "".join(partes)

def main():
    docs, historial = [], []
    print("═" * 60)
    print("  COMANDANTE ADÁN 2031 — Chat local (phi3:mini, offline)")
    print("  /doc <archivo>  para cargar PDF/Word/Excel/txt")
    print("═" * 60)
    while True:
        try: usuario = input("\nTú > ").strip()
        except (EOFError, KeyboardInterrupt): break
        if not usuario: continue
        if usuario == "/salir": break
        if usuario == "/limpiar":
            docs.clear(); historial.clear()
            print("(memoria limpiada)"); continue
        if usuario == "/docs":
            print("\n".join(f" - {n} ({len(t)} car.)" for n, t in docs) or "(sin documentos)")
            continue
        if usuario.startswith("/doc "):
            ruta = usuario[5:].strip().strip('"')
            try:
                texto = extraer_texto(ruta)
                if len(texto) > MAX_CARACTERES_DOC:
                    print(f"(recortado de {len(texto)} a {MAX_CARACTERES_DOC})")
                    texto = texto[:MAX_CARACTERES_DOC]
                docs.append((Path(ruta).name, texto))
                print(f"(cargado: {Path(ruta).name}, {len(texto)} caracteres)")
            except Exception as e:
                print(f"(error al cargar: {e})")
            continue
        sistema = ("Eres ADÁN 2031, asistente local en español, directo y útil. "
                   "Con documentos: responde apoyándote en ellos y cita la parte relevante.")
        if docs:
            sistema += "\n\nDocumentos:\n" + "\n\n".join(f"### {n}\n{t}" for n, t in docs)
        if not historial:
            historial.append({"role": "system", "content": sistema})
        else:
            historial[0] = {"role": "system", "content": sistema}
        historial.append({"role": "user", "content": usuario})
        try:
            print("\nADÁN 2031 >", end=" ")
            respuesta = chat([historial[0]] + historial[1:][-29:])
            historial.append({"role": "assistant", "content": respuesta})
        except requests.exceptions.ConnectionError:
            print("(sin conexión con Ollama: systemctl status ollama)")
        except Exception as e:
            print(f"(error: {e})")
    print("\nComandante fuera. Todo quedó en tu máquina.")

if __name__ == "__main__":
    main()
'''

def paso(msg: str) -> None: print(f"\n[ADÁN 2031] {msg}")
def ok(msg: str) -> None: print(f"[OK] {msg}")
def fallar(msg: str) -> None:
    print(f"[ERROR] {msg}"); sys.exit(1)

def correr(cmd, shell: bool = False, sudo: bool = False) -> bool:
    if sudo:
        cmd = f"sudo {cmd}" if isinstance(cmd, str) else ["sudo"] + cmd
    r = subprocess.run(cmd, shell=shell or isinstance(cmd, str))
    return r.returncode == 0

def ollama_vivo() -> bool:
    # FIX v1.3.1: Ollama nuevo ya no responde "Ollama is running"
    try:
        with urllib.request.urlopen(f"{PUERTO_OLLAMA}/api/tags", timeout=2) as r:
            return r.status == 200
    except Exception:
        return False

def main() -> None:
    print(BANNER)
    if not Path("/etc/debian_version").exists():
        fallar("este despliegue es para Ubuntu/Debian")
    if shutil.which("sudo") is None:
        fallar("falta sudo; ejecuta desde una cuenta con permisos")
    libre_gb = shutil.disk_usage(Path.home()).free / (1024 ** 3)
    if libre_gb < ESPACIO_MINIMO_GB:
        fallar(f"espacio insuficiente: {libre_gb:.1f} GB libres, se necesitan {ESPACIO_MINIMO_GB} GB")
    ok(f"Espacio en disco suficiente: {libre_gb:.1f} GB libres")
    paso("Actualizando sistema e instalando dependencias base...")
    if not correr("apt-get update -y", sudo=True):
        fallar("fallo apt-get update")
    if not correr("apt-get install -y curl zstd python3 python3-venv python3-pip", sudo=True):
        fallar("fallo instalando paquetes base")
    CARPETA.mkdir(parents=True, exist_ok=True)
    if shutil.which("ollama") is None:
        paso("Instalando Ollama (servicio local puerto 11434)...")
        if not correr("curl -fsSL https://ollama.com/install.sh | sh", shell=True):
            fallar("fallo instalando Ollama")
    else:
        ok("Ollama ya estaba instalado")
    correr("systemctl enable --now ollama", sudo=True)
    paso("Esperando el servicio Ollama (máx 60 s)...")
    for _ in range(30):
        if ollama_vivo(): break
        time.sleep(2)
    if not ollama_vivo():
        paso("systemd no levantó Ollama; arrancándolo en segundo plano...")
        subprocess.Popen(["ollama", "serve"],
                         stdout=open(CARPETA / "ollama.log", "w"),
                         stderr=subprocess.STDOUT, start_new_session=True)
        time.sleep(5)
        if not ollama_vivo():
            fallar(f"Ollama no responde (revisa {CARPETA}/ollama.log)")
    ok("Servicio Ollama activo (100% local)")
    paso(f"Descargando modelo {MODELO} (~2.3 GB)...")
    if not correr(["ollama", "pull", MODELO]):
        fallar(f"fallo descargando {MODELO}")
    ok(f"Modelo {MODELO} listo")
    paso(f"Creando entorno virtual en {ENTORNO} ...")
    if not ENTORNO.exists():
        if not correr(["python3", "-m", "venv", str(ENTORNO)]):
            fallar("fallo creando el venv")
    pip = str(ENTORNO / "bin" / "pip")
    if not correr([pip, "install", "--quiet", "--upgrade", "pip"]):
        fallar("fallo actualizando pip")
    if not correr([pip, "install", "--quiet", "requests", "pypdf", "python-docx", "openpyxl", "xlrd", "pandas"]):
        fallar("fallo instalando librerías de documentos")
    ok("PDF, Word, Excel instalados")
    paso("Escribiendo el chat ADÁN 2031...")
    (CARPETA / "chat_adan.py").write_text(CHAT_PY, encoding="utf-8")
    ok(f"Chat en {CARPETA / 'chat_adan.py'}")
    apps = Path.home() / ".local" / "share" / "applications"
    apps.mkdir(parents=True, exist_ok=True)
    (apps / "adan2031-chat.desktop").write_text(
        "[Desktop Entry]\nName=ADÁN 2031 Chat\nComment=Chat local con Ollama\n"
        f"Exec={ENTORNO}/bin/python {CARPETA}/chat_adan.py\n"
        "Icon=utilities-terminal\nTerminal=true\nType=Application\nCategories=Utility;\n",
        encoding="utf-8")
    ok("Lanzador creado: 'ADÁN 2031 Chat'")
    print("\n" + "═" * 60)
    print("  DESPLIEGUE COMPLETO — COMANDANTE ADÁN 2031 OPERATIVO")
    print(f"     {ENTORNO}/bin/python {CARPETA}/chat_adan.py")
    print("═" * 60)
    try:
        resp = input("\n¿Abrir el chat ahora? (s/N): ").strip().lower()
    except EOFError:
        resp = "n"
    if resp == "s":
        os.execv(str(ENTORNO / "bin" / "python"),
                 [str(ENTORNO / "bin" / "python"), str(CARPETA / "chat_adan.py")])

if __name__ == "__main__":
    try: main()
    except KeyboardInterrupt:
        print("\n[ADÁN 2031] despliegue interrumpido."); sys.exit(130)
