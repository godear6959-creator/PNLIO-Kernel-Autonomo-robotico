<!--
© 2026 Gonzalo Mauricio De la Rivera Arellano · Apache 2.0
SPDX-License-Identifier: Apache-2.0
-->

# PNLIO Kernel Autónomo Robótico

## Estado actual

Este repositorio contiene una **especificación conceptual** de un kernel de control para un sistema robótico con autonomía limitada y autorización humana obligatoria. No contiene código ejecutable, firmware, drivers, esquemas eléctricos, archivos de construcción ni pruebas sobre hardware.

Por esa razón, el proyecto **no debe presentarse como un kernel desplegable, sistema certificado o robot probado en campo**. Los resultados numéricos incluidos en los documentos PDF proceden de una simulación cuyo código y semilla no están publicados en este repositorio.

El objetivo de esta revisión es convertir la idea en una especificación suficientemente clara para que pueda implementarse y verificarse en hardware real, sin confundir el diseño con una simulación.

## Objetivo de ingeniería

El kernel propuesto debe interponerse entre la generación de una recomendación y cualquier actuador con capacidad de producir un efecto relevante. Su responsabilidad es reducir o bloquear la autonomía cuando el enlace de control no sea confiable y exigir una autorización humana explícita, autenticada, limitada a una acción concreta y con caducidad.

El kernel no debe tener permiso directo e irrestricto sobre los actuadores. La decisión final debe pasar por un controlador de seguridad independiente, con estado seguro por defecto y una ruta de parada que no dependa únicamente del proceso principal.

## Arquitectura propuesta

### 1. Interfaz y comunicación

Recibe órdenes, telemetría y señales de estado mediante mensajes versionados. Cada mensaje debe incluir origen autenticado, identificador, marca temporal, contador o nonce, versión de esquema y nivel de calidad. Los mensajes inválidos, antiguos, duplicados o fuera de rango se rechazan.

Los conceptos propios del proyecto, como “Realidad Cero”, deben sustituirse en una implementación por reglas observables: normalización de entradas, validación de esquema, detección de frescura, límites de tamaño y separación entre datos de operador y datos no confiables.

### 2. Motor de coherencia

Calcula el Ratio de Coherencia Refleja (RCR) sobre una ventana de muestras:

```text
RCR(t) = (1/N) · Σ [ I_base(i) · C_refleja(i) / (1 + H_entropia(i)) ]
```

La fórmula no es operativa hasta definir cómo se obtienen, calibran y validan sus entradas. La futura interfaz debe fijar unidades, rangos, frescura, procedencia, tratamiento de valores faltantes y respuesta ante sensores defectuosos.

El cálculo debe ser acotado y determinista. Para una ventana deslizante conviene mantener una suma acumulada, con coste O(1) por muestra, memoria fija y sin asignaciones dinámicas en el camino crítico.

### 3. Memoria y auditoría

La memoria operativa puede mantener el historial reciente del RCR, pero el registro de seguridad debe ser separado, append-only y autenticado. Debe registrar autorizaciones aceptadas, rechazadas, expiradas, modificadas y anuladas, además de fallos de comunicación, cambios de estado, reinicios y entradas al modo seguro.

Un archivo JSON sin integridad, control de concurrencia, recuperación ante pérdida de energía y control de permisos no es suficiente como registro forense.

### 4. Control de ejecución

El orquestador puede generar una recomendación, pero no debe escribir directamente en el bus de actuadores. El controlador de seguridad valida:

- identidad y rol del operador;
- identificador único de la acción;
- parámetros exactos y límites físicos;
- RCR y estado del sistema en el momento de la autorización;
- caducidad y protección contra replay;
- estado de sensores, comunicaciones y watchdog;
- ausencia de un fallo de nivel superior.

Si una comprobación falla, la salida es denegación y transición al estado seguro correspondiente.

## Máquina de estados mínima

La especificación original deja sin resolver algunos intervalos. Una implementación debe reemplazar los umbrales aislados por estados explícitos, con histéresis y temporizadores:

- **NORMAL:** recomendación permitida dentro de límites; ninguna acción relevante se ejecuta sin autorización válida.
- **RESTRINGIDO:** se reduce la autonomía y se exige reautorización por acción.
- **SEGURO:** se bloquea la liberación de actuadores y se admite solo recuperación autorizada o mando mecánico definido.
- **FALLO:** se activa el corte independiente y se requiere inspección antes de recuperar.

Los valores `0.50`, `0.60`, `0.80` y `0.35` son parámetros pendientes de justificación mediante requisitos, datos y pruebas. No deben considerarse umbrales certificados.

## Implementación no simulada: ruta de verificación

La implementación debe avanzar por etapas, manteniendo separados los artefactos de prueba y los componentes destinados al robot real:

1. especificación de interfaces y threat model;
2. implementación del motor en un entorno reproducible con pruebas unitarias;
3. integración con hardware de laboratorio y actuadores sin carga peligrosa;
4. pruebas de pérdida de energía, mensajes duplicados, valores corruptos, saturación y pérdida de enlace;
5. verificación del corte de hardware independiente del software;
6. pruebas HIL y revisión de seguridad funcional, ciberseguridad y factores humanos;
7. despliegue controlado únicamente después de una revisión independiente.

Una simulación puede apoyar las pruebas, pero no demuestra el comportamiento del robot real ni sustituye la verificación de las líneas de seguridad.

## Estructura recomendada para la próxima versión

```text
src/
  coherence/       # cálculo RCR y validación de entradas
  authorization/   # tokens de una sola acción y anti-replay
  state_machine/   # estados, transiciones y watchdog
  actuator_guard/  # controlador de seguridad y límites
  transport/       # adaptadores autenticados de comunicación
  audit/           # log append-only y exportación forense
firmware/
  safety_controller/
tests/
  unit/
  integration/
  hil/
docs/
  threat-model.md
  interfaces.md
  state-machine.md
  verification-plan.md
```

## Documentos incluidos

- `PNLIO_Sistema_Robotico_Simbiotico_v7_2.pdf`: arquitectura conceptual original.
- `PNLIO_Framework_v7.2_Certificacion_Simulaciones.md.pdf`: resultados reportados de simulación; no reproducibles desde este repositorio.
- `AUDITORIA_SEGURIDAD_RENDIMIENTO.md`: auditoría del estado actual y plan de corrección.
- `ARTICULO_TECNICO_ARQUITECTURA_REAL.md`: explicación técnica de la arquitectura propuesta para una implementación física.
- `LICENSE`: Apache License 2.0.

## Alcance y límites

La propuesta está orientada a control seguro, autorización humana y trazabilidad. Este repositorio no contiene especificaciones de armas ni debe interpretarse como autorización para construir o desplegar sistemas de fuerza. Antes de cualquier uso sobre personas, infraestructura crítica o entornos públicos se requiere una evaluación legal, de seguridad funcional, de ciberseguridad y de factores humanos realizada por terceros competentes.

## Licencia y autoría

Apache License 2.0.
© 2026 Gonzalo Mauricio De la Rivera Arellano · ORCID 0009-0001-9455-8416
