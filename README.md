<!--
© 2026 Gonzalo Mauricio De la Rivera Arellano · Apache 2.0
SPDX-License-Identifier: Apache-2.0
-->

# PNLIO Kernel Autónomo Robótico (v7.2)

> Propuesta conceptual de un kernel de respuesta crítica que **limita la autonomía** de un sistema robótico según la coherencia de su enlace con el operador, con una **puerta de autorización humana** obligatoria.

**Estado: diseño conceptual y simulación abstracta.** Este repositorio contiene dos documentos en PDF y este README. **No contiene código ejecutable, firmware ni hardware.** Las cifras de la sección de resultados vienen de una simulación cuyo código no está publicado aquí.

## Contenido del repositorio

| Archivo | Qué es (según su título) |
|---|---|
| `PNLIO_Sistema_Robotico_Simbiotico_v7_2.pdf` | Documento del sistema: arquitectura del kernel |
| `PNLIO_Framework_v7.2_Certificacion_Simulaciones.md.pdf` | Documento de simulaciones |
| `README.md` | Este resumen |
| `LICENSE` | Apache License 2.0 |

## Idea central

El kernel calcula de forma continua un indicador de coherencia del enlace entre el operador y el sistema (el RCR, definido abajo). Cuando el indicador baja, el sistema **reduce su autonomía** y exige **autorización humana** para cada acción; en el peor caso, cierra por completo la puerta de ejecución y solo admite comando humano directo. En la terminología del proyecto, esa puerta se llama *Gate de Control de Fuego*.

## Arquitectura de cuatro capas

| Capa | Función |
|---|---|
| 1. Interfaz y comunicación | Enruta las intenciones del operador e inyecta la llamada "Realidad Cero" para reducir sesgos y ruido en el canal. |
| 2. Motor de coherencia | Evalúa el RCR en ventanas deslizantes (N = 8 a 16), detecta fricción y ajusta umbrales. |
| 3. Memoria simbiótica | Registro JSON local con historial de RCR, contexto de sesión y auditoría de autorizaciones. |
| 4. Defensa, ejecución y control | "Escudo entrópico", limitación de tasa y puerta de autorización humana. Los actuadores operan bajo autoridad humana, con desconexión (*bypass*) galvánica o lógica en el nivel 3. |

*Nota:* "Realidad Cero", "fricción ontológica" y "escudo entrópico" son conceptos propios del proyecto y no tienen todavía una definición operativa publicada.

## Modelo del RCR

Sobre una ventana deslizante de N ciclos:

$$RCR_{t} = \frac{1}{N} \sum_{i=t-N+1}^{t} \frac{I_{base,i} \cdot C_{refleja,i}}{1 + H_{entropia,i}}$$

- `I_base` en [0, 1]: intensidad de la intención del operador.
- `C_refleja` en [0, 1]: resonancia o coherencia del enlace.
- `H_entropia` ≥ 0: fricción por ruido, interferencia o degradación del canal.

**Dos advertencias:**
1. No está especificado **cómo se mide** cada una de las tres variables. Es la brecha principal de este diseño: sin eso, el RCR no se puede calcular sobre un sistema real.
2. Este RCR **no es el mismo** que el RCR de otros repositorios del proyecto (por ejemplo, el del Coherence Analyzer). Las cifras no son comparables entre sí.

## Protocolo de seguridad (fail-safe)

| Nivel | Condición | Acción del núcleo | Puerta de autorización |
|---|---|---|---|
| 1, leve | RCR entre 0.60 y 0.80 | Reinyecta parámetros y acelera el muestreo | Operativa en régimen normal |
| 2, crítico | RCR < 0.50 | Filtrado de ruido y reducción de autonomía | Exige re-autorización humana por cada acción |
| 3, catastrófico | RCR < 0.35 o fallo de hardware | Desconexión y aislamiento del núcleo | Cerrada; solo comando humano directo |

**Huecos de la especificación (por resolver):**
- No hay regla para RCR entre 0.50 y 0.60, ni para RCR mayor que 0.80.
- El escenario "nominal" tiene RCR medio de 0.618 y un 5.3 % de ciclos bajo 0.50; es decir, el funcionamiento normal ya dispara el nivel 2 de vez en cuando. Conviene decidir si eso es lo deseado.
- No se documenta cómo se eligieron los umbrales 0.35, 0.50, 0.60 y 0.80.

## Resultados de simulación reportados

Cuatro escenarios, 25 simulaciones por escenario (n = 100 en total), 40 ciclos cada una. Cifras tal como las reporta el autor:

| Escenario | RCR medio | Mínimo medio | % de ciclos < 0.50 | % de ciclos < 0.35 |
|---|---|---|---|---|
| Nominal (bajo ruido) | 0.618 | 0.454 | 5.3 % | 0.0 % |
| Ruido moderado | 0.391 | 0.218 | 90.7 % | 29.8 % |
| Alta interferencia | 0.244 | 0.083 | 99.9 % | 86.9 % |
| Degradación severa | 0.112 | 0.012 | 100.0 % | 99.9 % |

**Cómo leer estas cifras:**
- Son resultados de **un modelo de ruido supuesto**, no de un sistema real. Lo que muestran es cuán bajo queda el RCR para cada nivel de ruido elegido.
- El porcentaje bajo 0.35 es el porcentaje de ciclos en que la puerta se cierra **por definición** (la puerta se cierra cuando el RCR baja de 0.35). Que la puerta esté cerrada el 99.9 % del tiempo en degradación severa describe el nivel de ruido simulado; no demuestra por sí solo que el sistema sea seguro.
- No se define qué criterio hace "aprobar" un escenario, no hay intervalos de confianza ni se publica la semilla. Por eso se omitió aquí una columna de "aprobado" o "certificado": ninguna entidad externa certificó nada, son simulaciones del propio autor.

## Qué se puede y qué no se puede afirmar

**Se puede afirmar:** existe un diseño conceptual de un kernel que limita la autonomía según un indicador de coherencia, con autorización humana obligatoria, y hay una simulación abstracta que muestra el comportamiento del indicador bajo cuatro niveles de ruido.

**No se puede afirmar:** que el sistema sea seguro, validado, certificado, probado en hardware, ni apto para operar con personas o en entornos reales.

## Próximos pasos

1. Publicar el código de la simulación con su semilla.
2. Definir cómo se miden `I_base`, `C_refleja` y `H_entropia`.
3. Repetir la simulación con 15 a 20 semillas y reportar intervalos de confianza (por ejemplo, con *bootstrap*).
4. Derivar los umbrales a partir de datos y cubrir los huecos del protocolo.
5. Si se llega a hardware: pruebas por etapas (simulación, banco, campo controlado) con corte de energía por hardware independiente del software.

## Alcance

Este repositorio es **documentación conceptual** de una puerta de autorización humana para sistemas robóticos autónomos. No incluye código ni especificaciones de armas.

## Referencias

- Alberts, D. S., Garstka, J. J., & Stein, F. P. (1999). *Network Centric Warfare*. CCRP.
- Leveson, N. G. (2011). *Engineering a Safer World*. MIT Press.
- U.S. Department of Defense. *Directive 3000.09, Autonomy in Weapon Systems* (actualización de 2023).

## Licencia y autoría

Licencia Apache 2.0 (ver `LICENSE`).
© 2026 Gonzalo Mauricio De la Rivera Arellano · ORCID 0009-0001-9455-8416
