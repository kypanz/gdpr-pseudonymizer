# gdpr-pseudonymizer

GDPR-compliant pseudonymization script. Encrypts MongoDB document IDs with AES-256 and anonymizes text fields via local LLM.

Script de seudonimización conforme al RGPD. Cifra identificadores en MongoDB con AES-256 y anonimiza campos de texto mediante LLM local.

## Features / Características

1. **Pseudonymization / Seudonimización**: encrypts `_id`, `device_id`, `avatar_id`, `stream_id` with AES-256-CBC — cifra identificadores con AES-256-CBC
2. **Text anonymization / Anonimización de texto**: removes PII (names, phones, addresses, emails → `[oculto]`) via local LLM (Qwen2.5-VL-3B) — elimina datos personales de los mensajes
3. **Preserves / Conserva**: `emotion`, `createdAt`, `updatedAt` (non-identifying fields / campos no identificativos)

## Requirements / Requisitos

```bash
pip install pymongo cryptography requests
```

- MongoDB running on / corriendo en `localhost:27017`
- LM Studio with / con `qwen2.5-vl-3b-instruct` at / en `http://192.168.1.113:1234`

## Usage / Ejecutar

```bash
python3 anonymize.py
```

## Output files / Archivos generados

| File / Archivo | Description / Descripción |
|----------------|---------------------------|
| `proyecto_anonimo.gz` | Exported anonymized database / Base anonimizada exportable |
| `aes_key.bin` | AES-256 key (keep secure!) / Clave AES-256 (¡guardar segura!) |
| `INSTRUCCIONES.md` | Import instructions / Instrucciones de importación (ES) |
