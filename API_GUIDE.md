# 🛡️ DB-Sentinel API Developer Guide (Blueprint Edition)

Bienvenido a la documentación técnica de **DB-Sentinel**. Este sistema implementa una arquitectura de **Command Dispatcher** sobre PostgreSQL (JSONB), donde la lógica de administración y almacenamiento no está programada en el código, sino definida por el desarrollador mediante **Blueprints (Mapas de Operaciones)**.

---

## 🚀 Guía de Inicio Rápido: El "Camino del Desarrollador"

Este es el flujo moderno de auto-servicio. Permite crear una "oficina privada" aislada y configurarla totalmente sin intervención del administrador.

### Paso 1: Crear tu Espacio de Trabajo (Bootstrapping)
Ejecuta este comando una sola vez para generar tu identidad en el sistema. El sistema creará automáticamente tu Tenant, un Token API único y un Blueprint vacío.

```bash
curl -X POST "https://api.sentinel.io/exec?cmd=dev.setup.workspace" 
     -H "x-admin-token: ADMIN_SECRET_TOKEN" 
     -H "Content-Type: application/json" 
     -d '{
       "developer_name": "TuNombre",
       "workspace_name": "MiProyectoPrivado"
     }'
```
**⚠️ Importante:** Guarda el `api_token` resultante. A partir de ahora, **ya no usarás el token de administrador**, sino tu propio token en el header `x-admin-token`.

### Paso 2: Organizar tu Oficina (Definir el Blueprint)
Usa tu nuevo token para definir qué entidades existen en tu base de datos y qué operaciones pueden hacer.

```bash
curl -X POST "https://api.sentinel.io/exec?cmd=dev.blueprint.define" 
     -H "x-admin-token: TU_NUEVO_TOKEN" 
     -H "Content-Type: application/json" 
     -d '{
       "developer_name": "TuNombre",
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

### Paso 3: Operar con Datos
Ahora que tienes un mapa, puedes empezar a guardar y procesar información.

**A. Crear un registro (Upsert):**
```bash
curl -X POST "https://api.sentinel.io/exec?cmd=data.upsert" 
     -H "x-admin-token: TU_NUEVO_TOKEN" 
     -H "Content-Type: application/json" 
     -d '{
       "entity": "wallet",
       "data": { "finance": { "balance": 100.0 } }
     }'
```

**B. Recuperar el ID del registro:**
```bash
curl -X POST "https://api.sentinel.io/exec?cmd=data.query" 
     -H "x-admin-token: TU_NUEVO_TOKEN" 
     -H "Content-Type: application/json" 
     -d '{ "entity": "wallet", "filters": {} }'
```
*(Copia el `_id` del resultado, ej: `0d426db9...`)*

**C. Ejecutar una Operación Dinámica (Suma de saldo):**
El sistema leerá tu Blueprint, verá que `add_funds` es una suma en `finance.balance` y lo ejecutará atómicamente.
```bash
curl -X POST "https://api.sentinel.io/exec?cmd=data.operate" 
     -H "x-admin-token: TU_NUEVO_TOKEN" 
     -H "Content-Type: application/json" 
     -d '{
       "entity": "wallet",
       "id": "UUID_RECUPERADO",
       "operation": "add_funds",
       "value": 50.0
     }'
```

---

## 🛠️ Administración de Infraestructura (Rol: Root Admin)

Si eres el administrador del servidor, solo necesitas realizar un paso antes de que los desarrolladores puedan usar el auto-servicio.

### Inicializar el Sistema
Crea las tablas maestras y el almacén universal de datos. Solo se ejecuta una vez por instalación.
```bash
curl -X POST "https://api.sentinel.io/exec?cmd=system.init_infra" 
     -H "x-admin-token: ADMIN_SECRET_TOKEN" 
     -H "Content-Type: application/json" 
     -d '{}'
```

---

## 📖 Conceptos Core

### 🧩 ¿Qué es un Blueprint?
A diferencia de las bases de datos SQL tradicionales, DB-Sentinel no tiene esquemas fijos. Un **Blueprint** es un archivo JSONB que actúa como el "Manual de Instrucciones" para un Tenant.

**Componentes de un Mapa:**
1.  **Entidades**: "Tablas virtuales" (ej: `wallet`, `user_profile`).
2.  **Rutas (`storage_path`)**: Indica exactamente dónde vive el dato dentro del JSONB (ej: `"finance.balance"`).
3.  **Operaciones**: Acciones predefinidas que el motor sabe ejecutar (ej: `sum`, `subtract`).

### 🔑 Autenticación y Seguridad
El sistema utiliza un único header para todas las solicitudes: `x-admin-token`.

- **Token Maestro**: Permite ejecutar comandos de sistema (`system.*`) y crear nuevos espacios de trabajo.
- **Token de Tenant**: Permite gestionar el propio Blueprint y operar sobre los datos del tenant vinculado. No puede acceder a datos de otros tenants.

---

## 🔌 Referencia de la API

### Endpoint Maestro: `/exec`
Toda la potencia del sistema se accede a través de un único punto.
- **URL**: `https://<tu-dominio>/exec`
- **Método**: `POST`
- **Query Param**: `cmd=<nombre_del_comando>`
- **Body**: JSON con los parámetros.

### Catálogo de Comandos

#### 🛠️ `dev.*` (Configuración y Mapas)
- `dev.setup.workspace`: Crea Tenant $ightarrow$ Token $ightarrow$ Blueprint.
- `dev.blueprint.define`: Define la estructura de datos y operaciones.
- `dev.blueprint.list`: Lista los mapas disponibles.

#### 📦 `data.*` (Motor de Datos)
- `data.upsert`: Crea o actualiza un registro.
- `data.get`: Recupera un registro por ID.
- `data.query`: Busca registros usando filtros JSONB.
- `data.operate`: Ejecuta una operación dinámica definida en el mapa.
- `data.delete`: Elimina un registro.

#### 💰 `plan.*` y `fin.*` (Negocio y Finanzas)
- `plan.define` / `plan.set`: Gestión de niveles de suscripción.
- `fin.transaction.create`: Registro de transacciones financieras.
- `fin.ledger.balance`: Cálculo de saldos mediante historial de movimientos.

#### 🎨 `sdui.*` (Server-Driven UI)
- `sdui.set_theme`: Configura colores y branding del tenant.
- `sdui.set_layout`: Define la estructura de la interfaz desde el servidor.

#### ⚙️ `system.*` e `infra.*` (Mantenimiento - Root Only)
- `system.init_infra`: Inicializa la base de datos.
- `infra.backup.snapshot`: Crea un respaldo de una entidad.

---

## ⚠️ Errores y Debugging

El sistema es **auto-documentado**. Si envías un comando incorrecto, la API te responderá con un **Fuzzy Match** sugiriéndote el comando correcto y un ejemplo de uso.

**Códigos Comunes:**
- `NO_BLUEPRINT_ASSIGNED`: Intentaste operar datos sin haber definido un mapa primero.
- `INSUFFICIENT_PERMISSIONS`: Intentaste usar un comando de sistema con un token de tenant.
- `BLUEPRINT_ENTITY_NOT_FOUND`: La entidad no existe en tu definición de mapa.

**Tip Pro:** Visita `GET /api/commands` para ver la lista completa de comandos disponibles en tiempo real y sus esquemas de parámetros.
