# Chorus sobre MySQL/MariaDB

Chorus usa **SQLite solo para tests**. Desarrollo y producción usan MySQL/MariaDB.

## Configuración

En `osap.toml`:

```toml
[storage]
database_url = "mysql+pymysql://usuario:password@127.0.0.1:3306/osap_chorus"
root = "var/private"
```

O por entorno:

```powershell
$env:CHORUS_DATABASE_URL = "mysql+pymysql://usuario:password@127.0.0.1:3306/osap_chorus"
```

Si `database_url` está vacío, se usa `database_path` (SQLite) para la suite de tests.

## Esquema

- `migrations/mysql/001_schema.sql`: esquema completo MySQL.
- `app/db.py`: adaptador; traduce `?` → `%s`, `INSERT OR IGNORE` → `INSERT IGNORE`,
  `BEGIN IMMEDIATE` y omite `PRAGMA`.
- Las migraciones SQLite se conservan para tests.

## Migrar datos

```powershell
python script/migrate_sqlite_to_mysql.py `
  --sqlite var/chorus.sqlite3 `
  --url "mysql+pymysql://usuario:password@127.0.0.1:3306/osap_chorus"
```

El script crea el esquema, copia todas las tablas conservando IDs y aborta si MySQL
ya tiene datos (usar `--replace` solo en desarrollo). No modifica el SQLite.

## Producción

1. Crear base `osap_chorus` y usuario con permisos solo sobre ella.
2. Copiar y migrar datos desde el SQLite de producción.
3. Configurar `CHORUS_DATABASE_URL` en el servicio systemd.
4. Reiniciar Chorus y verificar `/health`, agenda y mensajes.
