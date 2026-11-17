# Security

- Sólo rutas locales explícitas; no se leen credenciales ni bases productivas.
- `permission_status` es obligatorio y por defecto `unknown`.
- No se publican videos, métricas de clientes ni modelos.
- El dashboard enlaza a localhost.
- El sistema no modifica Video OS, Blender, configuraciones globales ni procesos.
- Hashes prueban integridad, no autorización ni autenticidad.
- Revisar licencias y permisos antes de importar; borrar el archivo del dataset no está automatizado.
