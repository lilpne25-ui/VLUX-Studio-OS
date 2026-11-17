# Model Card

**Modelos:** baseline `rules-v0.1`; candidato `logistic_numpy`.
**Entrada:** features objetivas/proxy del último análisis.
**Salida:** score de preferencia, no probabilidad de lead ni garantía comercial.
**Entrenamiento:** semilla fija, normalización, descenso de gradiente, holdout por episodio.
**Limitación:** requiere ejemplos humanos suficientes y dos o más episodios; de lo contrario `NO_TRAINING_INSUFFICIENT_DATA`.
**Promoción:** manual; el registro no sustituye el modelo anterior y conserva rollback por artefacto.
