# gdpr-pseudonymizer

Script de seudonimización conforme al RGPD. Cifra identificadores en MongoDB con AES-256 y anonimiza campos de texto mediante LLM local.

## Características

1. **Seudonimización**: cifra `_id`, `device_id`, `avatar_id`, `stream_id` con AES-256-CBC
2. **Anonimización de texto**: elimina datos personales (nombres, teléfonos, direcciones, emails → `[oculto]`) vía LLM local (Qwen2.5-VL-3B)
3. **Conserva**: `emotion`, `createdAt`, `updatedAt` (campos no identificativos)

## Requisitos

```bash
pip install pymongo cryptography requests
```

- MongoDB corriendo en `localhost:27017`
- LM Studio con `qwen2.5-vl-3b-instruct` en `http://192.168.1.113:1234`

## Ejecutar

```bash
python3 anonymize.py
```

## Archivos generados

| Archivo | Descripción |
|---------|-------------|
| `proyecto_anonimo.gz` | Base anonimizada exportable |
| `aes_key.bin` | Clave AES-256 (¡guardar segura!) |
| `INSTRUCCIONES.md` | Instrucciones de importación |
