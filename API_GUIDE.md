# 🛡️ DB-Sentinel API Developer Guide (Blueprint Edition)

## 🚀 Quick Start (Onboarding)

Si eres un desarrollador nuevo en el sistema, **debes seguir estos pasos en orden obligatorio** para evitar errores de infraestructura:

1.  **Inicializar la Infraestructura**: 
    Llama al comando `system.init_infra`. Esto crea las tablas maestras, incluyendo el almacén de Blueprints.
    - `POST /exec?cmd=system.init_infra`
2.  **Definir tu Mapa (Blueprint)**: 
    Sube el diseño de tu plataforma (rutas JSONB y operaciones).
    - `POST /exec?cmd=dev.blueprint.define` $\rightarrow$ Params: `developer_name`, `map_definition`.
3.  **Asignar el Mapa al Tenant**: 
    (Acción del Admin) El administrador debe vincular el ID de tu Blueprint al Tenant correspondiente.
4.  **Operar**: 
    Ahora puedes usar `data.upsert` para guardar datos o `data.operate` para ejecutar la lógica definida en tu mapa.

---

Bienvenido a la documentación técnica de **DB-Sentinel**. Este sistema implementa una arquitectura de **Command Dispatcher** sobre PostgreSQL (JSONB), donde la lógica de administración y almacenamiento es definida por el Desarrollador mediante **Blueprints (Mapas de Operaciones)**.

---

## 🚀 El Concepto de Blueprint (Mapa de Operaciones)

A diferencia de las bases de datos rígidas, DB-Sentinel utiliza **Blueprints**. Un Blueprint es un archivo JSONB que actúa como el "Manual de Instrucciones" para un Tenant.

**¿Qué define un Desarrollador en su Mapa?**
1.  **Entidades**: Qué "tablas virtuales" existen (ej: `wallet`, `inventory`).
2.  **Rutas de Almacenamiento (`storage_path`)**: En qué campo exacto del JSONB se guarda la información (ej: `"finances.balance"`).
3.  **Operaciones Dinámicas**: Qué acciones se pueden ejecutar sobre esos datos (ej: `add_funds` $\rightarrow$ tipo `sum`).

### 🔄 Flujo de Trabajo del Desarrollador
1.  **Definir**: El desarrollador crea un Mapa JSONB y lo sube vía `dev.blueprint.define`.
2.  **Asignar**: El Administrador vincula ese Mapa a uno o varios Tenants.
3.  **Operar**: El Tenant utiliza el sistema. Cuando se llama a una operación, el motor busca en el Mapa la ruta y la acción correspondiente para ejecutarla en la DB.

---

## 🔑 Interacción con la API

### El Endpoint Maestro: `/exec`
Toda acción se centraliza en un único punto de entrada.

- **URL:** `https://<tu-dominio>/exec`
- **Método:** `POST`
- **Parámetro de Query:** `cmd=<nombre_del_comando>`
- **Cuerpo (Body):** JSON con los parámetros requeridos.

**Ejemplo de Operación Dinámica:**
```bash
curl -X POST "https://api.sentinel.io/exec?cmd=data.operate" \
     -H "x-admin-token: TOKEN_TENANT" \
     -H "Content-Type: application/json" \
     -d '{ "entity": "wallet", "id": "user_123", "operation": "add_funds", "value": 100 }'
```

---

## 🛠️ Catálogo de Comandos

### 🛠️ `dev.*` (Gestión de Blueprints - Solo Admin/Dev)
Comandos para definir la inteligencia del sistema.
- `dev.blueprint.define`: Sube o actualiza un Mapa JSONB para un desarrollador.
- `dev.blueprint.list`: Lista todos los mapas disponibles y sus IDs.

### 📦 `data.*` (Motor de Datos y Operaciones)
Operaciones sobre el sector JSONB del Tenant.
- `data.operate`: **(Core)** Ejecuta una operación definida en el Mapa (ej: sumar saldo, restar stock).
- `data.upsert`: Crea o actualiza un registro. Valida que la entidad exista en el Mapa.
- `data.get`: Recupera un registro por su ID.
- `data.query`: Consulta registros usando filtros JSONB (`@>`).
- `data.list`: Versión paginada de `data.query`.
- `data.count`: Cuenta registros que coinciden con un filtro.
- `data.delete`: Elimina un registro.

### 💰 `plan.*` y `fin.*` (Monetización y Finanzas)
- `plan.define` / `plan.list` / `plan.set`: Gestión de niveles de suscripción y asignación a tenants.
- `fin.gateway.configure`: Configura pasarelas de pago.
- `fin.transaction.create` / `update_status`: Ciclo de vida de transacciones.
- `fin.movement.log`: Registro de flujo de caja (Ledger).
- `fin.ledger.balance`: Cálculo de saldos basado en movimientos.

### 🎨 `sdui.*` (Server-Driven UI)
Control de la interfaz desde el servidor.
- `sdui.set_theme`: Personaliza colores, logos y modo oscuro del tenant.
- `sdui.set_layout`: Define la estructura de una pantalla vía JSON.
- `sdui.get_screen`: Recupera la configuración completa (Theme + Layout) de una pantalla.
- `sdui.define_component`: Define componentes globales reutilizables.

### 🤖 `bot.*` y `chat.*` (IA y Orquestación)
- `chat.session.sync`: Sincroniza el estado de la sesión del usuario en tiempo real.
- `chat.messages.stream`: Inserción masiva de mensajes en el historial.
- `bot.graph.set_node` / `bot.graph.link`: Construye la lógica de flujo del bot (nodos y aristas).

### ⚙️ `system.*` e `infra.*` (Mantenimiento - Solo Root)
- `system.init_infra`: Inicializa tablas base y el almacén universal.
- `infra.backup.snapshot`: Crea un respaldo JSONB de una entidad.
- `infra.backup.restore`: Restaura una entidad desde un snapshot.

---

## 🔑 Autenticación

El acceso se controla mediante el header `x-admin-token`.
- **Root Admin**: Acceso total, gestión de Blueprints y Planes.
- **Tenant User**: Acceso restringido a sus propios datos y operaciones permitidas por su Mapa.

---

## ⚠️ Errores y Debugging

El sistema es auto-documentado. Si un comando falla o no existe, la API sugerirá la corrección mediante **Fuzzy Matching**.

**Códigos de Error Comunes:**
- `BLUEPRINT_ENTITY_NOT_FOUND`: La entidad solicitada no existe en el Mapa del desarrollador.
- `OPERATION_FAILED`: La operación no está definida en el Mapa o hubo un error de cálculo.
- `BLUEPRINT_NOT_FOUND`: El Tenant no tiene un Mapa asignado.
- `INSUFFICIENT_PERMISSIONS`: Intento de usar comandos de sistema con token de tenant.
- `VALIDATION_FAILED`: El dato no cumple con los requisitos básicos.

### Tip Pro:
Utiliza `GET /api/commands` para obtener la lista actualizada de todos los comandos, sus descripciones y los parámetros exactos que esperan.
