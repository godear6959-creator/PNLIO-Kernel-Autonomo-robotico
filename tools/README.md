# Herramientas opcionales

## `despliegue_adan2031.py`

Instalador opcional para preparar un entorno local de escritorio con Ollama,
`phi3:mini` y lectura de documentos PDF/Word/Excel. No forma parte del kernel
PNLIO, de la CSP RP2040 ni del camino de control de actuadores.

El script **no se ejecuta automáticamente** y requiere revisión del operador.
Puede realizar acciones de alto impacto en el sistema local: `sudo apt-get`,
instalación de Ollama mediante un script remoto, descarga de un modelo,
creación de un entorno virtual y escritura de un lanzador de escritorio.

Antes de ejecutarlo, revisar el código, la conectividad, el espacio disponible,
la procedencia del instalador remoto y las políticas de la máquina. Su chat
local no constituye una barrera de seguridad robótica y no debe recibir acceso
a GPIO, PWM, relés o actuadores.
