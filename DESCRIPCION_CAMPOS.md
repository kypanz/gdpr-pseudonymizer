# Descripción de Campos — proyecto_anonimo

## Identificadores (cifrados con AES-256)

### `_id`
Identificador único de cada registro.  
Original: ObjectId de MongoDB.  
Anonimizado: cifrado con AES-256-CBC (IV + ciphertext en base64).  
No permite identificar al usuario.

### `device_id`
Identificador del dispositivo desde donde se realizó la interacción.  
Ejemplo original: `0b745e`, `device_pruebas`, `25c784`.  
Anonimizado: cifrado con AES-256-CBC.  
Garantiza que no se puede rastrear qué dispositivo real usó la persona.

### `avatar_id`
Nombre del avatar/persona virtual con la que interactuó el usuario.  
Ejemplo original: `Esmeralda`, `Agustina`, `Ramiro`, `wav2lip256_avatar1`.  
Anonimizado: cifrado con AES-256-CBC.

### `stream_id`
Identificador único de la sesión de conversación.  
Conecta las interacciones con su sesión correspondiente en `tel_session_starts`.  
Anonimizado: cifrado con AES-256-CBC.

## Mensajes (anonimizados con LLM)

### `user_msg`
Mensaje escrito por el usuario.  
Procesado por el modelo `qwen2.5-vl-3b-instruct` (LM Studio local) para eliminar:
- Nombres propios
- Direcciones
- Teléfonos
- Correos electrónicos
- DNI / documentos
- Cualquier otro dato personal

El sentido y tono del mensaje se conservan.  
Si el mensaje no contenía datos personales, se mantiene intacto.

### `assistant_msg`
Respuesta generada por el asistente/avatar.  
Mismo proceso de anonimización que `user_msg`.

## Emoción

### `emotion`
Emoción detectada en la interacción.  
Valores posibles: `feliz`, `triste`, `enojo`, `miedo`, `disgusto`, `neutral`, `none`.  
No se modifica (no contiene datos personales).

## Datos de Sesión

### `session_inicio`
Fecha y hora de inicio de la sesión a la que pertenece esta interacción.  
Se obtiene del registro `tel_session_starts` con el mismo `stream_id`.  
Formato: ISO 8601 (ej: `2026-04-09 18:23:10.383000`).

### `session_duracion`
Duración de la sesión en formato legible.  
Se calcula como el tiempo entre esta sesión y la siguiente sesión del mismo `device_id`.  
Ejemplos: `47m 15s`, `2h 30m`, `5s`.  
La última sesión de cada dispositivo aparece como `"activa"` porque no hay una sesión siguiente que marque su fin.

### `session_duracion_seg`
La misma duración de sesión expresada en segundos (número).  
Útil para cálculos estadísticos (promedios, histogramas, etc.).  
Valor `null` para sesiones activas.

### `session_num`
Número ordinal de esta sesión dentro del total de sesiones del dispositivo.  
Ejemplo: si un dispositivo tiene 5 sesiones, la primera sesión tiene `session_num: 1`, la segunda `2`, etc.

### `session_total`
Cantidad total de sesiones que tuvo ese dispositivo en toda la base de datos.  
Ejemplo: si un dispositivo aparece en 5 sesiones, `session_total: 5`.

## Fechas

### `createdAt`
Fecha y hora de creación del registro.  
No se modifica.

### `updatedAt`
Fecha y hora de la última actualización del registro.  
No se modifica.

---

## Ejemplo de cálculo de sesiones

Dispositivo `0b745e` tiene 3 sesiones en `tel_session_starts`:

| stream_id | session_inicio | session_duracion | session_num | session_total |
|-----------|---------------|------------------|-------------|---------------|
| 537968 | 2026-04-09 18:23:10 | 47m 15s | 1 | 3 |
| 245830 | 2026-04-09 19:10:25 | 286h 9m | 2 | 3 |
| 315718 | 2026-04-21 17:19:47 | activa | 3 | 3 |

- Sesión 1 duró 47m 15s (hasta que inició la sesión 2)
- Sesión 2 duró 286h 9m (hasta que inició la sesión 3, días después)
- Sesión 3 está activa (es la última, no hay sesión siguiente)

Cada interacción hereda los datos de sesión según su `stream_id`.
