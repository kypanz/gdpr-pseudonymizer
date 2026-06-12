# gdpr-pseudonymizer

GDPR-compliant pseudonymization script. Encrypts MongoDB document IDs with AES-256 and anonymizes text fields via local LLM.

## Features

1. **Pseudonymization**: encrypts `_id`, `device_id`, `avatar_id`, `stream_id` with AES-256-CBC
2. **Text anonymization**: removes PII (names, phones, addresses, emails → `[oculto]`) via local LLM (Qwen2.5-VL-3B)
3. **Preserves**: `emotion`, `createdAt`, `updatedAt` (non-identifying fields)

## Requirements

```bash
pip install pymongo cryptography requests
```

- MongoDB running on `localhost:27017`
- LM Studio with `qwen2.5-vl-3b-instruct` at `http://192.168.1.113:1234`

## Usage

```bash
python3 anonymize.py
```

## Output files

| File | Description |
|------|-------------|
| `proyecto_anonimo.gz` | Exported anonymized database |
| `aes_key.bin` | AES-256 key (keep secure!) |
| `INSTRUCCIONES.md` | Import instructions (Spanish) |
