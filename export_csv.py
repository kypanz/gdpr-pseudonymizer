import os
import csv
import json
import base64
import re
import sys
import time
import subprocess
from datetime import datetime, timezone
from collections import defaultdict
from pymongo import MongoClient
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives import hashes, hmac
import requests

LM_STUDIO_URL = "http://192.168.1.113:1234/v1/chat/completions"
MODEL_NAME = "qwen2.5-vl-3b-instruct"
KEY_FILE = "aes_key.bin"
MONGO_URI = "mongodb://localhost:27017"
DB_ORIGIN = "proyecto_temp"
DB_DESTINO = "proyecto_anonimo"
ARCHIVO_CSV = "proyecto_anonimo.csv"
ARCHIVO_GZ = "proyecto_anonimo.gz"
BATCH_SIZE = 8

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

def encrypt_aes256_deterministic(plaintext: str, key: bytes) -> str:
    h = hmac.HMAC(key, hashes.SHA256())
    h.update(plaintext.encode("utf-8"))
    iv = h.finalize()[:16]
    padder = padding.PKCS7(128).padder()
    data = padder.update(plaintext.encode("utf-8")) + padder.finalize()
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    encryptor = cipher.encryptor()
    ct = encryptor.update(data) + encryptor.finalize()
    return base64.b64encode(iv + ct).decode("utf-8")

def calcular_duracion_sesiones(session_starts):
    sesiones_por_device = defaultdict(list)
    for s in session_starts:
        sesiones_por_device[s["device_id"]].append(s)

    duraciones = {}
    for device_id, sesiones in sesiones_por_device.items():
        sesiones.sort(key=lambda x: x["createdAt"])
        total = len(sesiones)
        for i in range(len(sesiones)):
            stream_id = sesiones[i]["stream_id"]
            inicio = sesiones[i]["createdAt"]
            if i + 1 < len(sesiones):
                fin = sesiones[i + 1]["createdAt"]
                duracion_seg = (fin - inicio).total_seconds()
            else:
                duracion_seg = None
            duraciones[stream_id] = {
                "inicio": inicio,
                "duracion_seg": duracion_seg,
                "device_id": device_id,
                "session_num": i + 1,
                "total_sessions": total,
            }
    return duraciones

def formatear_duracion(seg):
    if seg is None:
        return "activa"
    if seg < 60:
        return f"{int(seg)}s"
    elif seg < 3600:
        return f"{int(seg // 60)}m {int(seg % 60)}s"
    else:
        h = int(seg // 3600)
        m = int((seg % 3600) // 60)
        return f"{h}h {m}m"

def llm_anonymize_batch(textos, profundidad=0):
    if not textos or all(not t or not t.strip() for t in textos):
        return textos
    indices_reales = [(i, t) for i, t in enumerate(textos) if t and t.strip()]
    if not indices_reales:
        return textos
    solo_textos = [t for _, t in indices_reales]
    lines = "\n".join(f"[{i+1}] {t}" for i, t in enumerate(solo_textos))
    prompt = (
        "Task: Anonymize each text. Replace names, phone numbers, addresses, emails, IDs with [oculto]. "
        "If no personal data, return it as-is. Keep meaning and tone. "
        "OUTPUT FORMAT: ONLY the anonymized texts, one per line with the same numbering.\n"
        "Examples:\n"
        "Input: [1] Hola, soy María García\n[2] vivo en Calle Real 10\n"
        "Output:\n[1] Hola, soy [oculto]\n[2] vivo en [oculto]\n\n"
        f"Inputs:\n{lines}\n\nOutputs:"
    )
    if profundidad > 3:
        return textos
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
        if resp.status_code == 400 and len(solo_textos) > 1:
            mid = len(solo_textos) // 2
            izq = llm_anonymize_batch(solo_textos[:mid], profundidad + 1)
            der = llm_anonymize_batch(solo_textos[mid:], profundidad + 1)
            solo_textos = izq + der
        else:
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"].strip()
            if "</think>" in content:
                content = content.split("</think>")[-1].strip()
            result = {}
            for match in re.finditer(r'\[(\d+)\]\s*(.*?)(?=\n\[\d+\]|\Z)', content, re.DOTALL):
                idx = int(match.group(1)) - 1
                text = match.group(2).strip()
                if 0 <= idx < len(solo_textos):
                    result[idx] = text
            for i in range(len(solo_textos)):
                solo_textos[i] = result.get(i, solo_textos[i])
    except Exception as e:
        log(f"  [!] Error en batch LLM: {e}")

    resultado = list(textos)
    for (ori_idx, _), anon in zip(indices_reales, solo_textos):
        resultado[ori_idx] = anon
    return resultado

def main():
    t_inicio = time.time()
    key = generar_o_cargar_key()

    client = MongoClient(MONGO_URI)
    db_orig = client[DB_ORIGIN]
    db_dest = client[DB_DESTINO]

    coleccion_interactions = db_orig["tel_interactions"]
    coleccion_session_starts = db_orig["tel_session_starts"]

    interactions = list(coleccion_interactions.find())
    session_starts = list(coleccion_session_starts.find())
    log(f"[+] Interactions: {len(interactions)}")
    log(f"[+] Session starts: {len(session_starts)}")

    log("[*] Calculando duración de sesiones...")
    duraciones = calcular_duracion_sesiones(session_starts)
    stats = {"con_duracion": 0, "sin_duracion": 0}
    for sid, info in duraciones.items():
        if info["duracion_seg"] is not None:
            stats["con_duracion"] += 1
        else:
            stats["sin_duracion"] += 1
    log(f"  Sesiones con duración calculada: {stats['con_duracion']}")
    log(f"  Sesiones activas (última): {stats['sin_duracion']}")

    log("[*] Cifrando campos y anonimizando mensajes...")
    user_texts = [d.get("user_msg", "") for d in interactions]
    user_anons = llm_anonymize_batch(user_texts)
    assist_texts = [d.get("assistant_msg", "") for d in interactions]
    assist_anons = llm_anonymize_batch(assist_texts)

    db_dest["tel_interactions"].drop()
    nuevos_mongo = []

    for i, doc in enumerate(interactions):
        encrypted_id = encrypt_aes256_deterministic(str(doc["_id"]), key)
        encrypted_device = encrypt_aes256_deterministic(str(doc["device_id"]), key) if doc.get("device_id") else ""
        encrypted_avatar = encrypt_aes256_deterministic(str(doc["avatar_id"]), key) if doc.get("avatar_id") else ""
        encrypted_stream = encrypt_aes256_deterministic(str(doc["stream_id"]), key) if doc.get("stream_id") else ""

        stream_id = doc.get("stream_id", "")
        info_sesion = duraciones.get(stream_id, {})
        duracion = formatear_duracion(info_sesion.get("duracion_seg"))
        duracion_seg = info_sesion.get("duracion_seg")
        inicio_sesion = info_sesion.get("inicio", doc.get("createdAt"))

        session_num = info_sesion.get("session_num")
        total_sessions = info_sesion.get("total_sessions")

        nuevos_mongo.append({
            "_id": encrypted_id,
            "device_id": encrypted_device,
            "avatar_id": encrypted_avatar,
            "stream_id": encrypted_stream,
            "user_msg": user_anons[i],
            "assistant_msg": assist_anons[i],
            "emotion": doc.get("emotion"),
            "createdAt": doc.get("createdAt"),
            "updatedAt": doc.get("updatedAt"),
            "session_inicio": inicio_sesion,
            "session_duracion": duracion,
            "session_duracion_seg": duracion_seg,
            "session_num": session_num,
            "session_total": total_sessions,
        })

    db_dest["tel_interactions"].insert_many(nuevos_mongo)
    log(f"[+] {len(nuevos_mongo)} documentos insertados en {DB_DESTINO}.tel_interactions")

    log("[*] Exportando CSV...")
    campos_csv = [
        "_id", "device_id", "avatar_id", "stream_id",
        "user_msg", "assistant_msg", "emotion",
        "session_inicio", "session_duracion", "session_duracion_seg",
        "session_num", "session_total",
        "createdAt", "updatedAt"
    ]
    with open(ARCHIVO_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=campos_csv)
        writer.writeheader()
        for doc in nuevos_mongo:
            row = {c: doc.get(c, "") for c in campos_csv}
            row["session_inicio"] = str(row["session_inicio"]) if row["session_inicio"] else ""
            row["createdAt"] = str(row["createdAt"]) if row["createdAt"] else ""
            row["updatedAt"] = str(row["updatedAt"]) if row["updatedAt"] else ""
            writer.writerow(row)
    tamano_csv = os.path.getsize(ARCHIVO_CSV)
    log(f"[+] CSV exportado: {ARCHIVO_CSV} ({tamano_csv/1024:.1f} KB)")

    log("[*] Exportando MongoDB...")
    result = subprocess.run(
        ["mongodump", "--db", DB_DESTINO, "--archive=" + ARCHIVO_GZ, "--gzip"],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        tamano_gz = os.path.getsize(ARCHIVO_GZ)
        log(f"[+] MongoDB exportado: {ARCHIVO_GZ} ({tamano_gz/1024:.1f} KB)")
    else:
        log(f"[!] Error exportando MongoDB: {result.stderr}")

    t_total = time.time() - t_inicio
    log("")
    log("=" * 50)
    log("=== RESUMEN ===")
    log(f"Interacciones: {len(interactions)}")
    log(f"Sesiones: {len(session_starts)}")
    log(f"CSV: {ARCHIVO_CSV}")
    log(f"MongoDB: {ARCHIVO_GZ}")
    log(f"Tiempo total: {t_total:.1f}s ({t_total/60:.1f} min)")
    log("=" * 50)

    client.close()

if __name__ == "__main__":
    main()
