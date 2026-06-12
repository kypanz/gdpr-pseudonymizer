# Instrucciones de Importación — proyecto_anonimo

Base de datos anonimizada lista para importar.  
Cumple con **RGPD (GDPR)**: datos personales cifrados y mensajes anonimizados.

## Requisitos

- MongoDB 4.4+ con `mongorestore`

## Importar

```bash
mongorestore --gzip --archive=proyecto_anonimo.gz
```

Se importa en la base `proyecto_anonimo`, colección `tel_interactions`.

### Importar con otro nombre

```bash
mongorestore --gzip --archive=proyecto_anonimo.gz \
  --nsFrom="proyecto_anonimo.*" --nsTo="mi_base.*"
```

## Verificar

```bash
mongosh proyecto_anonimo --eval "db.tel_interactions.countDocuments()"
# → 366 documentos
```

## Archivos

| Archivo | Descripción |
|---------|-------------|
| `proyecto_anonimo.gz` | Base MongoDB lista para `mongorestore` |
| `proyecto_anonimo.csv` | CSV plano con todos los datos |

## Estructura (MongoDB y CSV)

| Columna | Tipo | Tratamiento |
|---------|------|-------------|
| `_id` | String | Cifrado AES-256 |
| `device_id` | String | Cifrado AES-256 |
| `avatar_id` | String | Cifrado AES-256 |
| `stream_id` | String | Cifrado AES-256 |
| `user_msg` | String | Texto anonimizado |
| `assistant_msg` | String | Texto anonimizado |
| `emotion` | String | Original sin cambios |
| `session_inicio` | Date | Inicio de sesión |
| `session_duracion` | String | Duración legible (ej: `5m 30s`) |
| `session_duracion_seg` | Number | Duración en segundos |
| `session_num` | Number | N° de sesión del dispositivo (ej: 2 = 2da sesión) |
| `session_total` | Number | Total de sesiones del dispositivo (ej: 3 = tiene 3 sesiones) |
| `createdAt` | Date | Original sin cambios |
| `updatedAt` | Date | Original sin cambios |

> **session_duracion**: se calcula como el tiempo entre una sesión y la siguiente del mismo `device_id`. La última sesión de cada dispositivo aparece como `"activa"`.

## Cumplimiento RGPD

- **Minimización**: solo campos necesarios para análisis
- **Seudonimización**: identificadores cifrados con AES-256-CBC
- **Anonimización**: mensajes procesados por LLM local (Qwen2.5-VL-3B) — sin conexión externa
- **No reidentificable**: sin la clave `aes_key.bin` no se pueden recuperar los valores originales
- **Procesamiento local**: nunca salió de la máquina local

## Desencriptar (solo con la clave)

```python
import base64
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding

key = open("aes_key.bin", "rb").read()

def decrypt(val):
    raw = base64.b64decode(val)
    iv, ct = raw[:16], raw[16:]
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    dec = cipher.decryptor()
    pad = padding.PKCS7(128).unpadder()
    return (pad.update(dec.update(ct) + dec.finalize()) + pad.finalize()).decode()

# Ejemplo: decrypt(documento["_id"])
```
