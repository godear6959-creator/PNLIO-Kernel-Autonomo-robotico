# Auditoría de seguridad y rendimiento

**Repositorio auditado:** `godear6959-creator/PNLIO-Kernel-Autonomo-robotico`
**Commit revisado:** `91a9ef7015714cbd5f58663ff8a36538bac1f163`
**Fecha de revisión:** 2026-11-01
**Alcance:** inventario del repositorio, revisión documental, análisis de la arquitectura propuesta y preparación de controles para una implementación no simulada.

## Conclusión ejecutiva

El repositorio no contiene código fuente, firmware, drivers, servicios, archivos de construcción, dependencias, configuración ejecutable, pruebas ni interfaz con hardware. Solo contiene `README.md`, `LICENSE` y dos PDF. Por tanto:

- no es posible realizar análisis estático o dinámico de código;
- no es posible medir rendimiento de un kernel;
- no es posible verificar el gate de autorización, el bypass, el rate-limiting ni el registro JSON en un sistema real;
- no existe evidencia en este repositorio de que el sistema haya operado sobre hardware;
- los resultados numéricos publicados son simulaciones no reproducibles desde este checkout porque no se incluye el código ni la semilla.

El principal riesgo no es una vulnerabilidad concreta del código: es la ausencia del código y de una especificación verificable de las interfaces de seguridad. El proyecto debe tratarse como **diseño conceptual**, no como software desplegable ni como sistema certificado.

## Inventario y reproducibilidad

| Elemento | Estado | Impacto |
|---|---|---|
| Código ejecutable | Ausente | No puede auditarse ni ejecutarse |
| Firmware o drivers | Ausente | No se puede comprobar el control de actuadores |
| `pyproject.toml`, `package.json`, `Cargo.toml`, Makefile o equivalente | Ausente | No hay cadena de construcción ni dependencias fijadas |
| Pruebas unitarias/integración/HIL | Ausentes | No hay evidencia verificable de propiedades de seguridad |
| Código de simulación | Ausente | Resultados no reproducibles desde el repositorio |
| Modelo de amenaza | No formalizado | No se conocen adversarios, activos, límites ni supuestos |
| Especificación de interfaces | Parcial | Se nombran TETRA/P25, AES-256/E2E y JSON, pero no hay contratos ni perfiles |
| Hardware de seguridad | No definido | No puede verificarse el corte independiente del software |
| Licencia | Apache-2.0 | Correctamente incluida; revisar que los futuros binarios preserven avisos |

Se calcularon las huellas SHA-256 de los archivos presentes en el checkout:

```text
LICENSE                                                bb4be66b4a549e4e412f5c9e065897303f3d5c425573a1897968ab42a95172dc
PNLIO_Framework_v7.2_Certificacion_Simulaciones.md.pdf 0ef4378488fcd3d81c2a77a75911264b77dcd4de5d55e9c770b1f244cdfd01e4
PNLIO_Sistema_Robotico_Simbiotico_v7_2.pdf             d37b2ca85a88ad6ab180ad08055dabaac637dd482ad0619f35088b864a03b9ae
README.md                                               74a6eb5333dca43493b0640357c6b270e28364ceb4cf8a4fb84500c25fcc4534
```

## Hallazgos de seguridad

### A1 — Crítico: no existe una barrera ejecutable entre recomendación y actuador

La documentación describe un gate humano y un bypass de nivel 3, pero no existe implementación que garantice que ningún otro canal pueda escribir en el actuador. La propiedad debe demostrarse con una arquitectura de privilegios: el proceso de recomendación no debe tener acceso directo al bus de actuadores; solo un controlador de seguridad independiente puede liberar una acción con una autorización válida, vinculada a una acción concreta, identidad, parámetros, caducidad y estado de salud.

**Corrección requerida:** separar físicamente o mediante un dominio de seguridad independiente el control de potencia/actuadores. Implementar denegación por defecto, doble comprobación de autorización y una línea de parada que no dependa exclusivamente del proceso principal.

### A2 — Crítico: el RCR no tiene entradas medibles

`I_base`, `C_refleja` y `H_entropia` aparecen en la fórmula, pero no se define cómo se miden, calibran, validan, acotan ante valores corruptos ni sincronizan temporalmente. Un atacante o un sensor defectuoso podría forzar un valor que mantenga la autonomía o provoque indisponibilidad.

**Corrección requerida:** definir un contrato de datos versionado, unidades, rangos, procedencia, marca temporal, calidad, frescura, tratamiento de valores faltantes y comportamiento ante sensor no confiable. El valor no disponible debe producir una transición segura, no una extrapolación silenciosa.

### A3 — Alto: autorización y telemetría no están protegidas contra replay o manipulación

El documento menciona logs JSON y recomienda hash, pero un hash aislado no autentica al emisor ni impide reordenamiento, truncamiento o replay. Tampoco se especifica gestión de claves.

**Corrección requerida:** usar mensajes con identificador único, contador monotónico o nonce, expiración, hash encadenado o firma/MAC autenticado, protección anti-replay, almacenamiento resistente a manipulación y rotación de claves. Registrar tanto autorizaciones aceptadas como rechazadas, expiradas, modificadas y anuladas.

### A4 — Alto: ambigüedad de estados y umbrales

La especificación no define el comportamiento entre `0.50` y `0.60`, ni por encima de `0.80`. Tampoco define histéresis, persistencia temporal, prioridad entre fallo de hardware y RCR, ni transición de recuperación. Un sistema real podría oscilar entre estados o recuperar autonomía demasiado pronto.

**Corrección requerida:** modelar una máquina de estados explícita con transiciones, entradas, salidas, temporizadores, histéresis, watchdog, estado inicial y política de recuperación manual. En caso de conflicto, debe ganar el estado más restrictivo.

### A5 — Alto: el gate depende de una sola ruta humana no especificada

No hay definición de identidad del operador, autenticación multifactor, autorización por rol, presentación de los parámetros exactos, consentimiento informado, tiempo máximo de respuesta ni comportamiento ante pérdida del enlace.

**Corrección requerida:** diseñar una interfaz de autorización con identidad criptográfica, challenge/response, resumen inmutable de la acción, límites de validez, confirmación de parámetros y denegación segura por timeout o pérdida de comunicación.

### A6 — Alto: canal de comunicación y configuración sin contrato de seguridad

Se mencionan TETRA/P25 y AES-256/E2E, pero no se fija protocolo, modo de autenticación, negociación, gestión de claves, protección de metadatos ni compatibilidad operativa. No debe asumirse que el nombre de una red o de un cifrado equivale a seguridad integral.

**Corrección requerida:** documentar threat model y perfil criptográfico, separar plano de control del plano de datos, autenticar extremos, validar tamaño y esquema de mensajes, aplicar límites de tasa y registrar fallos sin filtrar secretos.

### A7 — Medio: persistencia JSON no es adecuada como memoria forense por defecto

Un archivo JSON local puede truncarse ante pérdida de energía, corromperse bajo concurrencia o permitir borrado/edición por el mismo proceso que lo genera. La especificación tampoco define retención, espacio máximo, sincronización de reloj ni recuperación.

**Corrección requerida:** usar escritura transaccional o una base de datos embebida con WAL, cuotas, rotación, checksum/MAC, sincronización temporal y exportación forense. La memoria operativa y el registro de seguridad deben tener dominios de permisos distintos.

### A8 — Medio: falta de defensa contra denegación de servicio

El sistema podría ser llevado repetidamente a nivel 2/3 mediante entradas ruidosas, inundación de solicitudes, saturación del almacenamiento o agotamiento de CPU. El rate-limiting se menciona, pero no se especifican cuotas ni prioridad de mensajes de parada.

**Corrección requerida:** reservar capacidad para heartbeat, parada y autorización; aplicar límites por emisor y clase de mensaje; usar colas acotadas y backpressure; descartar primero datos no críticos; medir latencia y pérdida.

## Riesgos de rendimiento

No se puede medir rendimiento sin implementación. Aun así, la arquitectura presenta estos puntos de diseño:

1. **Ventana deslizante:** calcular el promedio RCR recorriendo `N = 8–16` elementos es barato, pero debe mantenerse una suma acumulada para garantizar tiempo O(1) por muestra y evitar asignaciones en el camino crítico.
2. **Registro síncrono:** escribir JSON o calcular hashes en el mismo hilo que libera actuadores puede introducir jitter. El camino de seguridad debe tener una decisión acotada; el registro debe usar una cola acotada y confirmación de persistencia según el nivel de riesgo.
3. **Criptografía en el camino crítico:** autenticar cada autorización es necesario, pero la verificación debe medirse en el hardware objetivo y no bloquear el watchdog. Preparar claves, tamaños máximos y presupuestos de latencia.
4. **Comunicación degradada:** un timeout de red no debe bloquear el control local. El nodo debe poder entrar a un estado seguro sin esperar a la nube, API o operador remoto.
5. **Recuperación:** recalcular todo el historial desde JSON en cada arranque empeora el tiempo de recuperación. Mantener un snapshot de estado y un log incremental verificable.
6. **Asignaciones y memoria:** el futuro firmware debe evitar memoria dinámica no acotada en bucles de control. Fijar tamaños máximos para mensajes, colas, historial y contexto.

### Presupuesto mínimo recomendado para la futura implementación

Antes de declarar aptitud operativa, medir en hardware objetivo y publicar, al menos, latencia de decisión P50/P95/P99, jitter, tiempo de entrada al estado seguro, tiempo de corte independiente de potencia, pérdida de mensajes, uso máximo de CPU/RAM, ocupación de almacenamiento y comportamiento bajo saturación. Los límites deben ser requisitos, no resultados elegidos después de observar una prueba.

## Recomendación de arquitectura no simulada

La futura implementación debería dividirse en:

- **Controlador de seguridad independiente:** watchdog, estado seguro, E-stop y autorización final del actuador.
- **Motor de coherencia:** cálculo validado del RCR con entradas tipadas y controles de frescura.
- **Orquestador de acciones:** genera recomendaciones, pero carece de permiso directo sobre actuadores.
- **Servicio de autorización:** autentica al operador y emite tokens de una sola acción, con caducidad y parámetros ligados.
- **Registro forense:** almacenamiento append-only autenticado, separado de la ruta de decisión.
- **Adaptadores de hardware:** interfaces concretas, con validación de rango, límites físicos y simulador solo para pruebas; el simulador no debe presentarse como implementación real.

## Plan de corrección priorizado

1. Publicar código, arquitectura de despliegue, dependencias fijadas y pruebas reproducibles.
2. Especificar una máquina de estados segura y resolver todos los intervalos de umbral.
3. Definir el contrato medible del RCR y separar señal de control de telemetría.
4. Implementar autorización criptográfica anti-replay y registro forense autenticado.
5. Diseñar y probar el corte de hardware independiente del software.
6. Añadir análisis de amenazas, pruebas de fuzzing de mensajes, pruebas de pérdida de energía y pruebas HIL.
7. Medir latencia y consumo en hardware objetivo; no usar la simulación como sustituto.
8. Ejecutar revisión independiente de seguridad funcional, ciberseguridad y factores humanos.

## Referencias técnicas

- NIST SP 800-218 define prácticas de alto nivel para reducir vulnerabilidades durante el ciclo de desarrollo seguro.[1]
- NIST SP 800-82 describe amenazas y contramedidas para sistemas de control industrial, teniendo en cuenta rendimiento, fiabilidad y seguridad operacional.[2]
- ISO 10218-1:2025 trata requisitos de seguridad para robots industriales, pero su propia página de alcance excluye, entre otros, usos militares, policiales, robots móviles y robots de servicio; no constituye por sí sola una vía de certificación para este proyecto.[3]

[1]: https://csrc.nist.gov/pubs/sp/800/218/final "NIST SP 800-218, Secure Software Development Framework Version 1.1"
[2]: https://csrc.nist.gov/pubs/sp/800/82/r3/final "NIST SP 800-82 Rev. 3, Guide to Operational Technology Security"
[3]: https://www.iso.org/standard/73933.html "ISO 10218-1:2025 Robotics — Safety requirements — Part 1: Industrial robots"

## Veredicto

**Estado actual: no desplegable; diseño conceptual documentado.** No se identificó una vulnerabilidad explotable de código porque no hay código que analizar. Sí se identificaron bloqueos críticos de seguridad y rendimiento que deben resolverse antes de afirmar que existe un kernel robótico operativo o que una puerta de autorización ha sido verificada.
