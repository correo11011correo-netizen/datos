import json
from app.core.db import execute_raw
from app.core.redis_core import clear_cache
from typing import Any, Dict

async def cmd_seed_system(params: Dict[str, Any]) -> str:
    """
    Populates the system with basic initial data.
    Expected params: {'seed_data': { 'entity_name': [ {data}, {data} ] } }
    """
    seed_data = params.get("seed_data", {})
    if not seed_data:
        raise ValueError("seed_data is required")

    for entity_name, records in seed_data.items():
        # Ensure entity exists
        await cmd_create_entity({"name": entity_name})
        # Insert records
        for record in records:
            await cmd_insert_data({"entity": entity_name, "data": record})
            
    return "System seeded successfully with provided data."

async def cmd_format_all(params: Dict[str, Any]) -> str:
    """
    NUCLEAR COMMAND: Formats both PostgreSQL and Redis.
    """
    # Drop all tables in public schema
    execute_raw("""
        DO $$ DECLARE
            r RECORD;
        BEGIN
            FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP
                EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(r.tablename) || ' CASCADE';
            END LOOP;
        END $$;
    """)
    
    # Clear Redis
    clear_cache()
    
    return "System fully formatted. All data erased."

async def cmd_init_system(params: Dict[str, Any]) -> str:
    """
    Initializes the generic structure.
    """
    execute_raw("""
        CREATE TABLE IF NOT EXISTS metadata_entities (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            schema JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    return "Generic system initialized. Metadata table ready."

async def cmd_create_entity(params: Dict[str, Any]) -> str:
    """
    Creates a new generic entity table.
    Expected params: {'name': 'entity_name', 'schema': { ... }}
    """
    name = params.get("name")
    schema = params.get("schema", {})
    
    if not name:
        raise ValueError("Entity name is required")
    
    # Register metadata
    execute_raw(
        "INSERT INTO metadata_entities (name, schema) VALUES (:name, :schema)",
        {"name": name, "schema": json.dumps(schema)}
    )
    
    # Create physical table
    table_name = f"entity_{name.lower().replace(' ', '_')}"
    execute_raw(f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            entity_id INTEGER REFERENCES metadata_entities(id),
            data JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    return f"Entity '{name}' created successfully with table {table_name}."

async def cmd_insert_data(params: Dict[str, Any]) -> str:
    """
    Inserts a JSON record into a generic entity.
    Expected params: {'entity': 'entity_name', 'data': { ... }}
    """
    entity_name = params.get("entity")
    data = params.get("data")
    
    if not entity_name or data is None:
        raise ValueError("Entity name and data are required")
    
    # Get entity_id
    res = execute_raw("SELECT id FROM metadata_entities WHERE name = :name", {"name": entity_name}).fetchone()
    if not res:
        raise ValueError(f"Entity {entity_name} not found")
    
    entity_id = res[0]
    table_name = f"entity_{entity_name.lower().replace(' ', '_')}"
    
    execute_raw(
        f"INSERT INTO {table_name} (entity_id, data) VALUES (:eid, :data)",
        {"eid": entity_id, "data": json.dumps(data)}
    )
    
    return f"Data inserted into {entity_name} successfully."

async def cmd_query_entity(params: Dict[str, Any]) -> Any:
    """
    Queries records from a generic entity.
    Expected params: {'entity': 'entity_name'}
    """
    entity_name = params.get("entity")
    if not entity_name:
        raise ValueError("Entity name is required")
    
    table_name = f"entity_{entity_name.lower().replace(' ', '_')}"
    
    result = execute_raw(f"SELECT data FROM {table_name} ORDER BY created_at DESC").fetchall()
    return [row[0] for row in result]
