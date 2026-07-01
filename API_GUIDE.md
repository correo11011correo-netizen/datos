# 🛡️ DB-Sentinel API Developer Guide (Blueprint Edition)

## 🚀 Tutorial Paso a Paso: Desde Cero hasta la Primera Operación

Para que un desarrollador pueda poner en marcha su plataforma, debe seguir esta secuencia exacta. **No saltar ningún paso**, ya que cada uno construye la base del siguiente.

### 🛠️ Fase A: Preparación de Infraestructura (Rol: Root Admin)
*En esta fase se usa el token del Administrador Maestro.*

**Paso 1: Inicializar la Base de Datos**
Crea las tablas maestras y el almacén de Blueprints. Solo se hace una vez por instalación.
```bash
curl -X POST "https://api.sentinel.io/exec?cmd=system.init_infra" \
     -H "x-admin-token: ADMIN_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{}'
```

**Paso 2: Definir el Mapa (Blueprint) del Desarrollador**
Aquí defines qué entidades existen y qué operaciones pueden hacer. 
*Ejemplo: Creamos una entidad `wallet` con una operación `add_funds` que suma en la ruta `finance.balance`.*
```bash
curl -X POST "https://api.sentinel.io/exec?cmd=dev.blueprint.define" \
     -H "x-admin-token: ADMIN_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "developer_name": "MiPlataforma",
       "map_definition": {
         "entities": {
           "wallet": {
             "storage_path": "finance.balance",
             "operations": {
               "add_funds": { "type": "sum" },
               "spend": { "type": "subtract" }
             }
           }
         }
       }
     }'
```

**Paso 3: Obtener el ID del Blueprint**
Lista los mapas para copiar el `id` del mapa que acabas de crear.
```bash
curl -X POST "https://api.sentinel.io/exec?cmd=dev.blueprint.list" \
     -H "x-admin-token: ADMIN_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{}'
```
*(Copia el `id` resultante, ej: `d3117c09...`)*

**Paso 4: Asignar el Mapa al Tenant**
Vincula el Blueprint al cliente final.
```bash
curl -X POST "https://api.sentinel.io/exec?cmd=dev.blueprint.assign" \
     -H "x-admin-token: ADMIN_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "tenant_id": "UUID_DEL_TENANT",
       "blueprint_id": "ID_DEL_BLUEPRINT_COPIADO"
     }'
```

---

### 💰 Fase B: Operación de Datos (Rol: Tenant / Desarrollador)
*A partir de aquí, se puede usar el token del Tenant.*

**Paso 5: Crear el primer registro (Upsert)**
Crea el registro inicial. **Importante**: No envíes `id` para que el sistema genere un UUID automático.
```bash
curl -X POST "https://api.sentinel.io/exec?cmd=data.upsert" \
     -H "x-admin-token: TOKEN_TENANT" \
     -H "Content-Type: application/json" \
     -d '{
       "entity": "wallet",
       "data": { "finance": { "balance": 100.0 } }
     }'
```

**Paso 6: Recuperar el UUID del registro**
Para operar sobre un registro, necesitas su ID. Búscalo con `data.query`.
```bash
curl -X POST "https://api.sentinel.io/exec?cmd=data.query" \
     -H "x-admin-token: TOKEN_TENANT" \
     -H "Content-Type: application/json" \
     -d '{ "entity": "wallet", "filters": {} }'
```
*(Copia el `_id` del resultado, ej: `0d426db9...`)*

**Paso 7: Ejecutar Operación Dinámica (El Poder del Mapa)**
Ahora ejecuta la acción `add_funds` definida en tu mapa. El sistema sabrá que debe sumar el valor en la ruta `finance.balance`.
```bash
curl -X POST "https://api.sentinel.io/exec?cmd=data.operate" \
     -H "x-admin-token: TOKEN_TENANT" \
     -H, "Content-Type: application/json" \
     -d '{
       "entity": "wallet",
       "id": "UUID_RECUPERADO",
       "operation": "add_funds",
       "value": 50.0
     }'
```

**Paso 8: Verificar el Resultado Final**
```bash
curl -X POST "https://api.sentinel.io/exec?cmd=data.get" \
     -H "x-admin-token: TOKEN_TENANT" \
     -H "Content-Type: application/json" \
     -d '{ "entity": "wallet", "id": "UUID_RECUPERADO" }'
```
*Resultado esperado: `{"finance": {"balance": 150.0}}`*

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
