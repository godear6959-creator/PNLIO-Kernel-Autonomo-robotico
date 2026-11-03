# Arquitectura operativa propuesta para el kernel robótico PNLIO

## Resumen

Este artículo presenta una arquitectura de ingeniería para convertir el concepto PNLIO v7.2 en un kernel robótico operable sobre hardware real. El diseño limita la autonomía mediante un indicador de coherencia del enlace de control, exige autorización humana por acción y separa la recomendación de la liberación final de actuadores. La contribución principal no es una simulación ni una certificación: es una descomposición verificable de componentes, interfaces, estados y controles que deben existir antes de considerar un despliegue físico.

El repositorio de partida contiene documentación conceptual y resultados de una simulación cuyo código no está incluido. En consecuencia, este artículo no atribuye funcionamiento real a la versión publicada. Describe una arquitectura objetivo y un plan de implementación y verificación en banco, hardware-in-the-loop y robot real.

## 1. Problema de ingeniería

Un robot autónomo combina sensores, comunicaciones, estimación de estado, planificación y actuadores. Cuando el canal de control se degrada, el sistema puede recibir órdenes incompletas, antiguas o manipuladas. Un diseño seguro no puede resolver esa incertidumbre concediendo más autoridad al software que la interpreta.

PNLIO propone una regla de control: la autonomía disponible debe depender del estado de confianza del enlace entre operador, kernel y plataforma. Si el enlace deja de ser confiable, el sistema reduce sus capacidades y termina en un estado que bloquea la liberación de actuadores. La regla solo es útil si está implementada en una ruta de seguridad independiente y si sus entradas son observables.

## 2. Principios de diseño

**Denegación por defecto.** Ninguna recomendación equivale a una orden de ejecución. Toda acción relevante necesita una autorización válida y específica.

**Separación de privilegios.** El proceso que interpreta datos o genera recomendaciones no obtiene acceso directo al actuador. El controlador de seguridad verifica la acción antes de liberarla.

**Localidad y continuidad.** La decisión de entrar en un estado seguro no depende de una nube, una API o una conexión remota. El robot debe poder bloquearse localmente cuando pierda comunicación o detecte un fallo.

**Trazabilidad verificable.** Las decisiones, transiciones y fallos deben quedar en un registro autenticado, con identidad, tiempo, secuencia y parámetros. La telemetría de conveniencia no puede sustituir al registro de seguridad.

**Recuperación conservadora.** La pérdida de confianza puede bloquear la autonomía inmediatamente. La recuperación requiere condiciones explícitas, comprobaciones y, cuando corresponda, una nueva autorización humana.

## 3. Arquitectura de componentes

### 3.1 Adaptadores de entrada

Los adaptadores reciben órdenes del operador, datos de sensores y telemetría. Cada mensaje se valida contra un esquema versionado. La validación incluye tamaño, tipo, rango, frescura, origen y secuencia. Los mensajes duplicados o fuera de orden se rechazan.

Esta capa convierte términos conceptuales como “ruido semántico” en verificaciones concretas. Un mensaje que no puede validarse no se interpreta por aproximación: se marca como no confiable y se propaga al motor de seguridad.

### 3.2 Motor de coherencia

El motor calcula el RCR a partir de tres señales normalizadas:

```text
RCR(t) = (1/N) · Σ [ I_base(i) · C_refleja(i) / (1 + H_entropia(i)) ]
```

`I_base` representa la intensidad de la intención recibida; `C_refleja` representa la coherencia estimada entre intención, contexto y respuesta; `H_entropia` representa degradación, ruido o incertidumbre del canal. Estas definiciones son de ingeniería solo después de fijar sensores, algoritmos, unidades, rangos y pruebas de calibración.

El cálculo se ejecuta con una ventana de tamaño fijo. Una suma acumulada evita recorrer la ventana completa en cada muestra. Las entradas se aceptan solo si cumplen la política de frescura y calidad. Si falta una entrada crítica, el motor devuelve un estado de incertidumbre, no un valor inventado.

### 3.3 Máquina de estados

El RCR no debe activar actuadores por sí solo. Alimenta una máquina de estados con prioridad de seguridad:

```text
                 fallo / pérdida de enlace / watchdog
                 ┌─────────────────────────────────────┐
                 v                                     │
[NORMAL] ── degradación ──> [RESTRINGIDO] ──> [SEGURO] ──> [FALLO]
   ^                            │                 │
   └──── recuperación validada ┴──── autorización ┘
```

Los nombres son funcionales; los umbrales y temporizadores deben derivarse de requisitos y verificarse. La máquina debe definir histéresis para evitar oscilaciones, una política de prioridad cuando existan varios fallos y un estado inicial seguro después de reinicio.

### 3.4 Servicio de autorización humana

Una autorización no es un permiso genérico para “operar”. Es un objeto ligado a una sola acción. Como mínimo contiene:

- identificador único de la acción;
- identidad y rol del operador;
- resumen de parámetros y límites;
- estado del robot y valor de coherencia observado;
- instante de emisión y caducidad;
- nonce o contador anti-replay;
- firma o MAC autenticado;
- decisión: autorizar, denegar o modificar.

El controlador debe volver a comprobar el estado al recibir la autorización. Una autorización válida cuando fue emitida puede ser inválida al ejecutarse si el enlace, el robot o el RCR cambiaron.

### 3.5 Controlador de seguridad y actuadores

El controlador de seguridad es el único componente que puede liberar la salida hacia el actuador. Debe recibir una orden ya autorizada, comprobar límites físicos y confirmar que no hay un estado de fallo. El watchdog, la parada de emergencia y el corte de potencia deben conservar una ruta independiente del proceso de recomendación.

El diseño recomendado no permite que una actualización de software del motor de coherencia modifique por sí sola los límites físicos o desactive el estado seguro. La configuración de seguridad debe estar protegida, versionada y sometida a revisión.

### 3.6 Registro forense

El registro debe ser append-only desde el punto de vista del proceso operativo. Cada evento incluye secuencia, tiempo sincronizado o calidad de reloj, identidad, tipo, parámetros relevantes, resultado y referencia al evento anterior. El registro necesita integridad criptográfica, límites de almacenamiento, rotación y recuperación tras pérdida de energía.

El registro no debe bloquear indefinidamente la ruta de parada. Si el almacenamiento se llena, la política debe preservar eventos de seguridad y señalizar la degradación.

## 4. Secuencia de funcionamiento

1. El operador o un sensor produce una entrada.
2. El adaptador autentica y valida el mensaje.
3. El motor de coherencia actualiza el estado con datos frescos.
4. El planificador genera una recomendación limitada por el estado de la máquina.
5. El servicio de autorización muestra al operador la acción exacta y sus parámetros.
6. El operador autoriza, deniega o modifica la solicitud.
7. El controlador de seguridad comprueba identidad, nonce, caducidad, estado, RCR, límites y ausencia de fallos.
8. Solo si todas las comprobaciones pasan, libera la salida al actuador.
9. La decisión y el resultado se registran con integridad verificable.
10. Cualquier caída del watchdog, pérdida de enlace, dato inválido o fallo crítico bloquea la salida.

Este flujo es aplicable a un robot físico únicamente después de implementar y verificar cada componente. La descripción no constituye evidencia de que el repositorio actual ya lo haga.

## 5. Rendimiento y determinismo

El camino de seguridad debe tener un presupuesto temporal conocido. El cálculo RCR debe usar memoria fija y coste acotado. Las colas deben tener una capacidad máxima. Las operaciones de almacenamiento y telemetría deben desacoplarse de la decisión sin perder los eventos críticos.

Las pruebas de rendimiento deben publicar P50, P95 y P99 de latencia, jitter, tiempo hasta estado seguro, tiempo de corte de potencia, uso máximo de CPU y RAM, ocupación de colas, pérdida de mensajes y comportamiento tras reinicio. Las mediciones deben realizarse en el hardware objetivo y bajo carga.

## 6. Amenazas principales y controles

**Replay o duplicación de autorizaciones.** Nonce, contador monotónico, caducidad y almacenamiento del último estado aceptado.

**Manipulación del enlace.** Autenticación de extremos, integridad de mensajes, separación de planos y rechazo de esquemas desconocidos.

**Sensor defectuoso o adversarial.** Límites, plausibilidad, frescura, redundancia cuando sea necesaria y transición segura ante incertidumbre.

**Denegación de servicio.** Rate-limiting por origen, colas acotadas, prioridad para parada y watchdog local.

**Corrupción del registro.** WAL o escritura transaccional, hash encadenado o MAC, permisos separados y exportación verificable.

**Compromiso del proceso de recomendación.** Separación de privilegios, sandboxing, firma de artefactos, arranque verificado y ausencia de acceso directo al actuador.

## 7. Verificación en hardware real

La verificación debe comenzar con actuadores sin carga peligrosa y progresar hacia una integración controlada. Las pruebas mínimas incluyen pérdida y recuperación de enlace, mensajes duplicados, mensajes fuera de rango, reloj incorrecto, almacenamiento lleno, reinicio durante una autorización, corte de energía, fallo del watchdog, sensor congelado, saturación de CPU y actualización rechazada por firma.

Después deben ejecutarse pruebas HIL y pruebas con el robot en un entorno restringido. La propiedad crítica no es que un escenario promedio produzca un RCR bajo. La propiedad crítica es que ninguna ruta no autorizada pueda liberar el actuador y que el estado seguro se alcance dentro del tiempo requerido bajo fallos definidos.

## 8. Límites y estado del proyecto

La versión publicada describe capas, un RCR y un flujo HITL, pero no proporciona los artefactos necesarios para afirmar implementación real. No hay código que auditar ni pruebas que repetir. Las simulaciones reportadas deben conservarse como resultados históricos hasta que se publique su código, semilla, parámetros y protocolo.

Tampoco debe llamarse “certificación” a una tabla producida por el propio autor. La certificación exige criterios formales, evidencia independiente y un marco aplicable. ISO 10218-1:2025, además, excluye varios ámbitos relevantes para la clasificación C4ISR declarada en los documentos, por lo que no debe citarse como certificación automática de este sistema.

## Conclusión

PNLIO puede madurar desde un concepto de autonomía limitada hacia un kernel robótico verificable si convierte sus términos abstractos en contratos de datos, estados, límites físicos y pruebas de fallo. La arquitectura recomendada conserva la idea central —la autonomía disminuye cuando disminuye la confianza y la ejecución requiere autoridad humana—, pero coloca el control final en un componente de seguridad independiente.

El estado honesto de la versión revisada es: **arquitectura propuesta para implementación física, todavía no implementada ni validada en hardware**.

## Referencias

[1]: https://csrc.nist.gov/pubs/sp/800/218/final "NIST SP 800-218, Secure Software Development Framework Version 1.1"
[2]: https://csrc.nist.gov/pubs/sp/800/82/r3/final "NIST SP 800-82 Rev. 3, Guide to Operational Technology Security"
[3]: https://www.iso.org/standard/73933.html "ISO 10218-1:2025 Robotics — Safety requirements — Part 1: Industrial robots"
