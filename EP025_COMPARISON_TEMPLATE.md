# EP025 comparison template

No hay preferencias inventadas. Para comparar desde CLI:

```powershell
python -m vlux_ci.cli --db data/vlux.sqlite proposals
python -m vlux_ci.cli --db data/vlux.sqlite proposals
python -m vlux_ci.cli --db data/vlux.sqlite proposal-feedback --a ID_A --b ID_B --winner A --clarity 4 --impact 4 --credibility 4 --retention 4 --commercial 5 --confidence .8 --evaluator nombre
```

También se puede usar el formulario `EP025 — comparación de propuestas` del dashboard. Evalúa claridad, impacto, credibilidad, potencial de retención y potencial comercial. Las preferencias humanas no se convierten automáticamente en aprobación ni en entrenamiento.
