# 🛡️ DB-Sentinel API Developer Guide (Blueprint Edition)

Bienvenido a la documentación técnica de **DB-Sentinel**. Este sistema implementa una arquitectura de **Command Dispatcher** sobre PostgreSQL (JSONB), donde la lógica de administración y almacenamiento no está programada en el código, sino definida por el desarrollador mediante **Blueprints (Mapas de Operaciones)**.

---

## 🚀 Guía de Inicio Rápido: El "Camino del Desarrollador"

Este es el flujo moderno de auto-servicio. Permite crear una "oficina privada" aislada y configurarla totalmente sin intervención del administrador y sin necesidad de tokens previos.

### Paso 1: Crear tu Espacio de Trabajo (Bootstrapping)
Ejecuta este comando una sola vez para generar tu identidad en el sistema. El sistema creará automáticamente tu Tenant, un Token API único y un Blueprint vacío. **Este paso es abierto y no requiere autenticación.**

```bash
curl -X POST "https://api.sentinel.io/exec?cmd=dev.setup.workspace" 
     -H "Content-Type: application/json" 
     -d '{
       "developer_name": "TuNombre",
       "workspace_name": "MiProyectoPrivado"
     }'
```
**⚠️ Importante:** Recibirás un `api_token` único. **Guarda este token muy bien**. A partir de este momento, este es tu identificador personal y debes usarlo en el header `x-admin-token` para todas las operaciones posteriores.

### Paso 2: Organizar tu Oficina (Definir el Blueprint)
Usa tu nuevo token para definir qué entidades existen en tu base de datos y qué operaciones pueden hacer.
...

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

## ⚖️ Términos de Uso y Responsabilidad

**DB-Sentinel es un Proveedor de Infraestructura de Datos (Data-as-a-Service), NO un proveedor de lógica de negocio.**

Para garantizar la estabilidad del sistema, es fundamental comprender la división de responsabilidades:

1.  **Nuestra Responsabilidad (Infraestructura):** Garantizamos que los comandos de datos (`data.*`), la gestión de Blueprints (`dev.*`) y el sistema de autenticación funcionen correctamente. Si un comando de infraestructura falla o devuelve un error de sistema (ej: `INTERNAL_ERROR`, `DATABASE_CONNECTION_FAILURE`), es nuestra responsabilidad corregirlo.
2.  **Tu Responsabilidad (Lógica de Negocio):** Tú defines el Blueprint y cómo se usan los datos. Si el resultado de una operación es incorrecto debido a una mala definición del mapa, una ruta de almacenamiento errónea o un flujo de negocio mal diseñado, **esto no es un fallo del sistema, sino un error de implementación del desarrollador**.

**⚠️ Política de Reportes:**
Solo se aceptarán reportes de errores que afecten la **infraestructura**. No se procesarán quejas sobre comportamientos de lógica de negocio que dependan de la configuración del Blueprint del Tenant.

---

## 🚩 Sistema de Reportes Técnicos

Si detectas un bug real en la infraestructura (un error 500, un TypeError en el core, o un fallo en los comandos `data.*`), puedes notificarlo directamente al administrador.

### Comando: `dev.report.submit`
Permite enviar un reporte técnico vinculado a tu Tenant.

**Parámetros:**
- `category`: `"BUG"`, `"IMPROVEMENT"`, o `"CRITICAL"`.
- `title`: Título breve del problema.
- `description`: Detalle técnico, pasos para reproducir y el error recibido.

**Ejemplo de uso:**
```bash
curl -X POST "https://api.sentinel.io/exec?cmd=dev.report.submit" 
     -H "x-admin-token: TU_TOKEN" 
     -H "Content-Type: application/json" 
     -d '{
       "category": "BUG",
       "title": "Error de UUID en upsert",
       "description": "Al usar un identifier personalizado, el sistema lanza un error de sintaxis de UUID en PostgreSQL."
     }'
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

## ⚡ Tiempo Real con WebSockets (Real-Time)

Para que tu aplicación se sienta "viva" (como un chat o una plataforma de trading), DB-Sentinel incluye un motor de eventos basado en Redis. Cada vez que se ejecuta un comando de datos (`data.*`), el sistema dispara una notificación instantánea.

### Cómo conectarse al flujo de eventos
Puedes abrir una conexión WebSocket para recibir avisos en tiempo real sobre cualquier cambio en tu espacio de trabajo.

- **URL**: `wss://<tu-dominio>/ws/{tu_api_token}`
- **Funcionamiento**: Una vez conectado, el servidor te enviará un mensaje JSON cada vez que ocurra una actualización en tu tenant.

**Ejemplo de evento recibido:**
```json
{
  "command": "data.operate",
  "params": { "entity": "wallet", "operation": "add_funds", "value": 50.0 },
  "status": "success"
}
```
*Con esto, tu frontend puede actualizar el saldo o mostrar un mensaje de "Nuevo mensaje recibido" instantáneamente.*

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
ightarrow$ Blueprint.
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
