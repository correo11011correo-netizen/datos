# 🛡️ DB-Sentinel API Guide

Bienvenido a la guía de integración de **DB-Sentinel**. Este sistema proporciona una capa de abstracción sobre PostgreSQL (JSONB) que permite gestionar datos de forma dinámica sin necesidad de migraciones constantes de esquema.

## 🚀 Conceptos Fundamentales

La API no utiliza rutas tradicionales para cada operación. En su lugar, implementa un **Command Dispatcher**. Todos los cambios y consultas pasan por un único punto de entrada: `/exec`.

---

## 🔑 Autenticación

Todas las peticiones deben incluir un token de administración en las cabeceras HTTP.

- **Header:** `x-admin-token`
- **Valor:** `<TU_TOKEN_SECRETO>`

Si utilizas el token raíz (root), tendrás permisos de nivel `SYSTEM` (infraestructura). Si utilizas un token de Tenant, estarás restringido a los datos de tu organización.

---

## 🛠️ El Endpoint Maestro: `/exec`

Este es el núcleo del sistema. Para ejecutar cualquier función, debes enviar una petición `POST`.

**URL:** `https://<tu-dominio>/exec`
**Método:** `POST`
**Parámetros de URL:** `cmd=<nombre_del_comando>`

### Formato de Petición
El cuerpo de la petición debe ser un JSON con los parámetros que el comando específico requiera.

**Ejemplo General:**
```bash
curl -X POST "https://datos-production.up.railway.app/exec?cmd=data.query" 
     -H "x-admin-token: tu_token_aqui" 
     -H "Content-Type: application/json" 
     -d '{
       "entity": "usuarios",
       "filters": { "status": "activo" },
       "limit": 5
     }'
```

---

## 📚 Catálogo de Comandos (Auto-Descubrimiento)

No necesitas memorizar todos los comandos. El sistema es **auto-didacta**.

**Endpoint:** `GET /api/commands`
**Función:** Devuelve la lista de todos los comandos disponibles, sus descripciones y los parámetros exactos que esperan.

---

## ⚡ Comandos de Datos más Comunes

### 1. `data.query` (Consulta Dinámica)
Recupera registros filtrando por cualquier campo del JSONB.
- **Parámetros principales:** `entity`, `filters` (dict), `limit`, `offset`, `sort_by`.
- **Uso:** Ideal para crear tablas, listas y buscadores.

### 2. `data.patch` (Actualización Parcial)
Actualiza solo los campos enviados, manteniendo el resto del objeto intacto.
- **Parámetros principales:** `entity`, `record_id`, `updates` (dict).
- **Uso:** Actualizar un perfil, cambiar un estado, añadir una etiqueta.

### 3. `data.increment` (Operación Atómica)
Suma o resta un valor a un campo numérico sin riesgo de colisiones.
- **Parámetros principales:** `entity`, `record_id`, `field`, `value`.
- **Uso:** Gestión de stock, contadores de vistas, saldos.

### 4. `data.upsert` (Insertar o Actualizar)
Crea un registro nuevo o actualiza uno existente basado en una llave única.
- **Parámetros principales:** `entity`, `unique_key`, `unique_value`, `data`.

---

## ⚠️ Manejo de Errores

La API devuelve errores estructurados para facilitar el debug:

- **`COMMAND_NOT_FOUND`**: El comando no existe. La API te sugerirá el comando más parecido (Fuzzy Match).
- **`INSUFFICIENT_PERMISSIONS`**: Intentaste ejecutar un comando de sistema (como formateo) con un token de usuario.
- **`QUERY_ERROR`**: Error en la construcción de la consulta o datos inválidos.

**Ejemplo de respuesta de error:**
```json
{
  "status": "error",
  "error": "COMMAND_NOT_FOUND",
  "message": "Command 'data.quary' not found. Did you mean 'data.query'?",
  "hint": "The command 'data.query' does the following: Retrieves records...",
  "example": { "cmd": "data.query", "params": { ... } }
}
```
