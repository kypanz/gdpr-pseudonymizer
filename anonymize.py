import os
import json
import base64
import re
import sys
import time
import subprocess
from datetime import datetime
from pymongo import MongoClient
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
import requests

LM_STUDIO_URL = "http://192.168.1.113:1234/v1/chat/completions"
MODEL_NAME = "qwen2.5-vl-3b-instruct"
KEY_FILE = "aes_key.bin"
MONGO_URI = "mongodb://localhost:27017"
DB_ORIGIN = "proyecto_temp"
DB_DESTINO = "proyecto_anonimo"
COLECCION = "tel_interactions"
ARCHIVO_SALIDA = "proyecto_anonimo.gz"
BATCH_SIZE = 20

def log(msg):
    print(msg, flush=True)

def generar_o_cargar_key():
    if os.path.exists(KEY_FILE):
        with open(KEY_FILE, "rb") as f:
            return f.read()
    key = os.urandom(32)
    with open(KEY_FILE, "wb") as f:
        f.write(key)
    log(f"[+] Clave AES-256 generada y guardada en {KEY_FILE}")
    return key

def encrypt_aes256(plaintext: str, key: bytes) -> str:
    iv = os.urandom(16)
    padder = padding.PKCS7(128).padder()
    data = padder.update(plaintext.encode("utf-8")) + padder.finalize()
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    encryptor = cipher.encryptor()
    ct = encryptor.update(data) + encryptor.finalize()
    return base64.b64encode(iv + ct).decode("utf-8")

def llm_anonymize_batch(textos, tipo=""):
    if not textos:
        return []
    lines = "\n".join(f"[{i+1}] {t}" for i, t in enumerate(textos))
    prompt = (
        "Task: Anonymize each text. Replace names, phone numbers, addresses, emails, IDs with [oculto]. "
        "If no personal data, return it as-is. Keep meaning and tone. "
        "OUTPUT FORMAT: ONLY the anonymized texts, one per line with the same numbering.\n"
        "Examples:\n"
        "Input: [1] Hola, soy María García\n[2] vivo en Calle Real 10\n"
        "Output:\n[1] Hola, soy [oculto]\n[2] vivo en [oculto]\n\n"
        f"Inputs:\n{lines}\n\nOutputs:"
    )
    try:
        resp = requests.post(
            LM_STUDIO_URL,
            headers={"Content-Type": "application/json"},
            json={
                "model": MODEL_NAME,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 4096,
                "temperature": 0.1,
            },
            timeout=300,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"].strip()
        if "</think>" in content:
            content = content.split("</think>")[-1].strip()
        result = {}
        for match in re.finditer(r'\[(\d+)\]\s*(.*?)(?=\n\[\d+\]|\Z)', content, re.DOTALL):
            idx = int(match.group(1)) - 1
            text = match.group(2).strip()
            if 0 <= idx < len(textos):
                result[idx] = text
        return [result.get(i, textos[i]) for i in range(len(textos))]
    except Exception as e:
        log(f"  [!] Error en batch LLM: {e}")
        return textos

def exportar_mongodb():
    log(f"\n[+] Exportando {DB_DESTINO} a {ARCHIVO_SALIDA} ...")
    result = subprocess.run(
        ["mongodump", "--db", DB_DESTINO, "--archive=" + ARCHIVO_SALIDA, "--gzip"],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        tamano = os.path.getsize(ARCHIVO_SALIDA)
        log(f"[+] Exportado: {ARCHIVO_SALIDA} ({tamano/1024:.1f} KB)")
    else:
        log(f"[!] Error exportando: {result.stderr}")
    return result.returncode == 0

def main():
    t_inicio = time.time()
    key = generar_o_cargar_key()

    client = MongoClient(MONGO_URI)
    db_orig = client[DB_ORIGIN]
    db_dest = client[DB_DESTINO]
    coleccion_orig = db_orig[COLECCION]
    coleccion_dest = db_dest[COLECCION]

    coleccion_dest.drop()
    docs = list(coleccion_orig.find())
    total = len(docs)
    log(f"[+] {total} documentos cargados desde {DB_ORIGIN}.{COLECCION}")
    log(f"[+] Modelo LLM: {MODEL_NAME}")
    log("")

    nuevos = []
    stats_anon = {"user_ok": 0, "user_nochange": 0, "assist_ok": 0, "assist_nochange": 0}

    log("--- CIFRANDO CAMPOS (AES-256) ---")
    for i, doc in enumerate(docs, 1):
        nuevo = {"_id": encrypt_aes256(str(doc["_id"]), key)}
        for campo in ["device_id", "avatar_id", "stream_id"]:
            valor = doc.get(campo)
            nuevo[campo] = encrypt_aes256(str(valor), key) if valor is not None else valor
        nuevo["emotion"] = doc.get("emotion")
        nuevo["createdAt"] = doc.get("createdAt")
        nuevo["updatedAt"] = doc.get("updatedAt")
        nuevos.append(nuevo)
    log(f"[+] {total} IDs, device_ids, avatar_ids y stream_ids cifrados.\n")

    user_batches = []
    assistant_batches = []
    for i in range(0, total, BATCH_SIZE):
        batch_docs = docs[i:i + BATCH_SIZE]
        user_batches.append((i, [d.get("user_msg", "") for d in batch_docs]))
        assistant_batches.append((i, [d.get("assistant_msg", "") for d in batch_docs]))

    log("--- ANONIMIZANDO MENSAJES ---")

    log("[*] User messages...")
    for start_idx, batch_users in user_batches:
        indices_con_texto = [(j, t) for j, t in enumerate(batch_users) if t and t.strip()]
        if not indices_con_texto:
            continue
        textos = [t for _, t in indices_con_texto]
        result = llm_anonymize_batch(textos, "usuario")
        for (j, orig), anon in zip(indices_con_texto, result):
            nuevos[start_idx + j]["user_msg"] = anon
            if orig != anon:
                stats_anon["user_ok"] += 1
            else:
                stats_anon["user_nochange"] += 1
            log(f"  [{start_idx + j + 1}] U: {orig[:80]}")
            log(f"      → {anon[:80]}")
        log("")

    log("[*] Assistant messages...")
    for start_idx, batch_assistants in assistant_batches:
        indices_con_texto = [(j, t) for j, t in enumerate(batch_assistants) if t and t.strip()]
        if not indices_con_texto:
            continue
        textos = [t for _, t in indices_con_texto]
        result = llm_anonymize_batch(textos, "asistente")
        for (j, orig), anon in zip(indices_con_texto, result):
            nuevos[start_idx + j]["assistant_msg"] = anon
            if orig != anon:
                stats_anon["assist_ok"] += 1
            else:
                stats_anon["assist_nochange"] += 1
            log(f"  [{start_idx + j + 1}] A: {orig[:80]}")
            log(f"      → {anon[:80]}")
        log("")

    coleccion_dest.insert_many(nuevos)
    log(f"[+] {total} documentos insertados en {DB_DESTINO}.{COLECCION}")

    exportar_mongodb()

    t_total = time.time() - t_inicio
    log("")
    log("=" * 50)
    log("=== RESUMEN ===")
    log(f"Documentos procesados: {total}")
    log(f"User messages anonimizados: {stats_anon['user_ok']}")
    log(f"Assistant messages anonimizados: {stats_anon['assist_ok']}")
    log(f"Sin cambios (sin datos personales): {stats_anon['user_nochange'] + stats_anon['assist_nochange']}")
    log(f"Tiempo total: {t_total:.1f}s ({t_total/60:.1f} min)")
    log(f"Archivo exportado: {ARCHIVO_SALIDA}")
    log(f"Clave AES-256: {KEY_FILE} (GUARDAR PARA DESENCRIPTAR)")
    log("=" * 50)

    client.close()

if __name__ == "__main__":
    main()
