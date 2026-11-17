# Integration

La integración inicial es read-only y por CLI. Importa un MP4 explícito, lee metadatos por FFprobe y devuelve JSON en stdout. Un bridge futuro puede leer manifiestos de episodios y guiones mediante adaptadores de ruta, sin importar automáticamente archivos productivos.

Recomendación exportable: conservar el JSON de `baseline`/`train` y adjuntarlo a la revisión humana de Video OS. No existe todavía un escritor ni un hook sobre el pipeline.
