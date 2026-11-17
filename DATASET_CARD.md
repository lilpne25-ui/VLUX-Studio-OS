# Dataset Card

**Nombre:** VLUX Creative Intelligence Dataset v0.1
**Propósito:** evaluar señales audiovisuales y preferencias humanas; no inferir clientes potenciales sin métricas verificadas.
**Procedencia:** archivos locales declarados por el operador, con hash SHA-256, permisos y origen.
**Esquema:** `videos`, `analyses`, `feedback`, `metrics`; schema `0.1`.
**Etiquetas:** preferencias A/B y puntuaciones humanas; no son etiquetas automáticas.
**Riesgos:** sesgo de evaluador, proxies visuales imperfectos, fuga por versiones relacionadas. Se evita fuga con holdout por episodio.
**Privacidad:** no cargar material sin autorización; no publicar la base.
