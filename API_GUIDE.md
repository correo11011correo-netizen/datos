# 🛡️ DB-Sentinel API Developer Guide

Bienvenido a la documentación técnica de **DB-Sentinel**. Este sistema implementa una arquitectura de **Command Dispatcher** sobre PostgreSQL (JSONB), permitiendo una gestión de datos dinámica, multi-tenant y extremadamente flexible.

---

## 🚀 Arquitectura de Interacción

A diferencia de las APIs REST tradicionales con múltiples endpoints, DB-Sentinel centraliza todas las operaciones en un único punto de entrada.

### El Endpoint Maestro: `/exec`
Toda acción (lectura, escritura, configuración) se ejecuta enviando un comando específico a través de este endpoint.

- **URL:** `https://<tu-dominio>/exec`
- **Método:** `POST`
- **Parámetro de Query:** `cmd=<nombre_del_comando>`
- **Cuerpo (Body):** JSON con los parámetros requeridos por el comando.

**Ejemplo de flujo:**
```bash
curl -X POST "https://api.sentinel.io/exec?cmd=data.query" 
     -H "x-admin-token: TU_TOKEN" 
     -H "Content-Type: application/json" 
     -d '{ "entity": "products", "filters": { "category": "electronics" } }'
```

---

## 🔑 Autenticación y Seguridad

El acceso está controlado mediante el header `x-admin-token`.

| Rol | Alcance | Capacidades |
| :--- | :--- | :--- |
| **Root Admin** | Global | Gestión de infraestructura, creación de Tenants, configuración de Planes. |
| **Tenant User** | Aislado | Solo puede acceder a los datos vinculados a su `tenant_id`. |

---

## 🔍 Auto-Descubrimiento (La llave para el desarrollador)

El sistema es **auto-documentado**. No necesitas buscar una lista estática de comandos; puedes consultarlos en tiempo real.

### Endpoint de Introspección
`GET /api/commands`

Este endpoint devuelve un array de todos los comandos disponibles en la versión actual, incluyendo:
- `command`: El nombre exacto para usar en `/exec?cmd=...`.
- `description`: Qué hace el comando.
- `params`: El esquema de parámetros esperado (tipos de datos y nombres).

**Tip para desarrolladores:** Siempre comienza una nueva integración llamando a `/api/commands` para verificar si hay nuevas funcionalidades o cambios en los parámetros.

---

## 🛠️ Mapa de Comandos (Namespaces)

Los comandos están organizados por namespaces para facilitar su ubicación:

### 📦 `data.*` (Gestión de Datos Genéricos)
Operaciones CRUD sobre cualquier entidad definida en el esquema virtual. Todos los comandos de escritura validan los datos contra el esquema del tenant.
- `data.upsert`: Crea un registro o actualiza uno existente (si se proporciona el ID). Valida tipos de datos.
- `data.get`: Recupera un único registro por su ID.
- `data.delete`: Elimina un registro específico.
- `data.query`: Consultas rápidas con filtros JSONB (ej: `{"category": "books"}`).
- `data.list`: Versión paginada de `data.query` para manejo de grandes volúmenes de datos.
- `data.count`: Cuenta cuántos registros coinciden con un filtro.

### 💰 `plan.*` y `fin.*` (Monetización y Finanzas)
Gestión de planes de suscripción y flujos monetarios.
- `plan.define` / `plan.set`: Configuración y asignación de planes.
- `fin.gateway.configure`: Configuración de pasarelas de pago.
- `fin.movement.log`: Registro de entradas/salidas de dinero.
- `fin.ledger.balance`: Consulta de saldos.

### 🎨 `sdui.*` (Server-Driven UI)
Control dinámico de la interfaz de usuario.
- `sdui.set_theme`: Define colores, logos y modo oscuro.
- `sdui.set_layout`: Estructura de pantallas vía JSON.
- `sdui.get_screen`: Recupera la config completa de una pantalla.

### 🤖 `bot.*` y `chat.*` (Orquestación de IA/Chat)
Gestión de grafos de conversación y sesiones.
- `bot.graph.set_node` / `bot.graph.link`: Construcción del flujo del bot.
- `chat.session.sync`: Sincronización de estado de usuario.
- `chat.messages.stream`: Inserción masiva de mensajes.

### ⚙️ `system.*` e `infra.*` (Mantenimiento)
Operaciones de bajo nivel (Solo Root Admin).
- `system.init_infra`: Inicializa tablas base del sistema.
- `infra.backup.snapshot`: Crea respaldo de una entidad.
- `infra.backup.restore`: Restaura datos desde un snapshot.

---

## ⚠️ Manejo de Errores y Debugging

El sistema implementa **Fuzzy Matching**. Si escribes mal un comando, la API no solo dará error, sino que te sugerirá la corrección.

**Ejemplo de respuesta de error:**
```json
{
  "status": "error",
  "error": "COMMAND_NOT_FOUND",
  "message": "Command 'data.quary' not found. Did you mean 'data.query'?",
  "hint": "The command 'data.query' retrieves records based on dynamic filters.",
  "example": { 
    "cmd": "data.query", 
    "params": { "entity": "string", "filters": "dict" } 
  }
}
```

### Códigos Comunes:
- `VALIDATION_ERROR`: El dato enviado no coincide con el esquema definido en `schema.define`.
- `INSUFFICIENT_PERMISSIONS`: Estás intentando usar un comando de Root Admin con un token de Tenant.
- `SCHEMA_NOT_FOUND`: Debes definir el esquema virtual del Tenant antes de insertar datos.
