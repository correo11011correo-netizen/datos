# 🛡️ DB-Sentinel API Guide

Bienvenido a la guía de integración de **DB-Sentinel**. Este sistema proporciona una capa de abstracción sobre PostgreSQL (JSONB) que permite gestionar datos de forma dinámica sin necesidad de migraciones constantes de esquema.

## 🚀 Conceptos Fundamentales

La API no utiliza rutas tradicionales para cada operación. En su lugar, implementa un **Command Dispatcher**. Todos los cambios y consultas pasan por un único punto de entrada: `/exec`.

---

## 🔑 Autenticación

Todas las peticiones deben incluir un token en las cabeceras HTTP.

- **Header:** `x-admin-token`
- **Valor:** `<TU_TOKEN_SECRETO>`

### Niveles de Acceso
1. **Root Admin (System)**: Posee el token maestro. Puede gestionar la infraestructura, crear nuevos tenants y generar tokens.
2. **Tenant User**: Posee un token vinculado a un `tenant_id`. Está restringido a los datos de su propia organización y no puede ejecutar comandos de sistema.

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

## 📚 Catálogo de Comandos y Auto-Descubrimiento

El sistema es **auto-didacta**. Si no conoces un comando o quieres ver los parámetros exactos, utiliza el endpoint de descubrimiento:

**Endpoint:** `GET /api/commands`
**Función:** Devuelve la lista de todos los comandos disponibles, sus descripciones y los esquemas de parámetros que esperan.

---

## 👑 Administración de Cuentas (Solo Root Admin)

Para evitar el uso compartido del token maestro, el administrador puede crear entornos aislados para otros desarrolladores o clientes.

### 1. Crear un Tenant (Cuenta)
`cmd=create_tenant`
- **Parámetros:** `{"name": "NombreCuenta", "plan": "free|pro|enterprise"}`
- **Resultado:** Devuelve un `tenant_id` único.

### 2. Generar Token de Acceso
`cmd=create_api_key`
- **Parámetros:** `{"tenant_id": "ID_DEL_TENANT", "label": "EtiquetaToken"}`
- **Resultado:** Devuelve el `token` que el usuario deberá usar en `x-admin-token`.

---

## ⚡ Comandos de Datos más Comunes

### 1. `data.query` (Consulta Dinámica)
Recupera registros filtrando por cualquier campo del JSONB.
- **Parámetros:** `entity`, `filters` (dict), `limit`, `offset`, `sort_by`, `impersonate_tid`.

### 2. `data.patch` (Actualización Parcial)
Actualiza solo los campos enviados, manteniendo el resto del objeto intacto.
- **Parámetros:** `entity`, `record_id`, `updates` (dict).

### 3. `data.increment` (Operación Atómica)
Suma o resta un valor a un campo numérico sin riesgo de colisiones.
- **Parámetros:** `entity`, `record_id`, `field`, `value`.

### 4. `data.upsert` (Insertar o Actualizar)
Crea un registro nuevo o actualiza uno existente basado en una llave única.
- **Parámetros:** `entity`, `unique_key`, `unique_value`, `data`.

---

## ⚠️ Manejo de Errores

La API devuelve errores estructurados para facilitar el debug:

- **`COMMAND_NOT_FOUND`**: El comando no existe. La API sugerirá el más parecido (Fuzzy Match).
- **`INSUFFICIENT_PERMISSIONS`**: Intento de ejecutar comando de sistema con token de usuario.
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
