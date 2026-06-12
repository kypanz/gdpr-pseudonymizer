# Proceso de Anonimización

Script que anonimiza la base MongoDB `proyecto` usando AES-256 + LLM local (Qwen2.5-VL-3B).

## Que hace

1. Cifra con AES-256-CBC: `_id`, `device_id`, `avatar_id`, `stream_id`
2. Anonimiza con LLM local: `user_msg`, `assistant_msg` (nombres, teléfonos, direcciones, emails → `[oculto]`)
3. Deja intactos: `emotion`, `createdAt`, `updatedAt`

## Requisitos

```bash
pip install pymongo cryptography requests
```

MongoDB corriendo en localhost:27017  
LM Studio con `qwen2.5-vl-3b-instruct` en `http://192.168.1.113:1234`

## Ejecutar

```bash
python3 anonymize.py
```

## Archivos generados

| Archivo | Que es |
|---------|--------|
| `proyecto_anonimo.gz` | Base anonimizada exportable |
| `aes_key.bin` | Clave AES-256 (guardar segura) |
| `INSTRUCCIONES.md` | Instrucciones de importación + RGPD |
# gdpr-pseudonymizer
