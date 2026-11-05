<!--PNLIO 2031 — ADÁN + SOLEDAD Kernel + EVA

Ecosistema local de asistencia en el hogar, instalable con un solo script en Ubuntu/Debian: un chat que lee documentos, un kernel con memoria, voz y visión, y un dashboard con búsqueda sobre documentos (RAG) y una capa de seguridad física. Los componentes de robótica operan solo en simulación.

Aviso. Este repositorio no es una certificación de seguridad, no valida hardware y no autoriza operar un robot físico. El acceso a hardware real está bloqueado en el código hasta contar con un driver verificado.

Autoría: Gonzalo Mauricio De la Rivera Arellano · Versiones: SOLEDAD Kernel 1.3.0 · EVA 2031 1.7.2 (etiqueta interna Kernel 7.11) · Actualizado: noviembre de 2026

Alcance

Asistencia civil local: consulta de documentos, memoria de conversación, percepción por cámara y micrófono, y un núcleo de navegación simulado con supervisor de seguridad. No está diseñado para armas, apuntado ni selección de blancos, y no se extenderá en esa dirección.

Estado: qué es diseño, qué está medido y qué es hipótesis
Tipo	Contenido
Diseño (lo que el código hace por construcción)	Supervisor de seguridad independiente del planificador; paros enganchados que solo se liberan con rearmar(); límites de velocidad y aceleración; rechazo de NaN; caducidad de órdenes y de datos del sensor; CSP como única vía hacia actuadores; modo SIMULACION fijo.
Medición	Ninguna publicada todavía. El instalador ejecuta una autoprueba de 15 comprobaciones sobre el núcleo robótico de SOLEDAD, pero este README no declara su resultado porque no se registró una ejecución con entorno y versión. Ver Autoprueba.
Hipótesis / pendiente	Funcionamiento con voz, micrófono y cámara reales en distintas máquinas; rendimiento con 8 GB de RAM; comportamiento con versiones recientes de Gradio, sentence-transformers y faster-whisper; cualquier uso con hardware.
Componentes
Componente	Qué hace	Cómo se abre
ADÁN 2031 Chat (chat_adan.py)	Chat local con Ollama (phi3:mini). Carga PDF, Word, Excel, TXT y CSV con /doc <ruta>.	~/pnlio2031/env/bin/python ~/pnlio2031/chat_adan.py
SOLEDAD Kernel v1.3 (kernel/soledad_kernel_v1_3.py)	Memoria SQLite con FTS5, síntesis de voz (pyttsx3), visión con OpenCV y modelo multimodal, y núcleo robótico simulado con supervisor de seguridad.	adan
EVA 2031 v1.7.2 (dashboard.py)	Dashboard Gradio: chat con RAG (FAISS + all-MiniLM-L6-v2), visión (moondream), voz, transcripción (faster-whisper small) y CSP (Intenciones → CSP → Actuadores).	eva, luego http://127.0.0.1:7860
Requisitos
Ubuntu o Debian con sudo.
12 GB libres en disco (el instalador lo comprueba).
8 GB de RAM recomendados. Con menos, ADÁN y SOLEDAD funcionan; EVA completa (embeddings + whisper + Ollama a la vez) queda justa.
Internet durante la instalación (apt, Ollama, modelos, paquetes de Python). Ver la nota sobre la primera ejecución de EVA en Límites conocidos.
Instalación

El instalador es un solo archivo, despliegue_pnlio2031.py, que contiene el código de los tres componentes.

bash
python3 despliegue_pnlio2031.py

Qué hace, en orden: comprueba disco y RAM; instala dependencias con apt; instala Ollama si falta y levanta el servicio (puerto 11434); descarga phi3:mini (~2.3 GB) y moondream (~1.8 GB); crea un entorno virtual en ~/pnlio2031/env; instala las librerías; escribe los tres componentes; crea los comandos adan y eva en ~/.local/bin y lanzadores de escritorio; ejecuta la autoprueba del núcleo robótico.

Si adan o eva no aparecen:

bash
export PATH="$HOME/.local/bin:$PATH"
Uso

SOLEDAD Kernel (adan)

Comando	Función
/ayuda, /estado, /fecha	Ayuda, estado de Ollama y modelos, fecha/hora del sistema
/voz on|off	Activa o desactiva la síntesis de voz
/vision, /ver TEXTO	Captura un fotograma y lo describe, o responde sobre lo que ve (requiere modelo multimodal: /modelo moondream)
/modelo NOMBRE	Cambia el modelo en la sesión
/recordar TEXTO, /memoria TEXTO	Guarda y busca notas (SQLite FTS5)
/historial, /limpiar	Mensajes recientes; borra los de la sesión (pide SI)
/robot estado	Estado del supervisor
/robot run X Y	Lleva el robot simulado al punto (X, Y) en metros
/robot paro	Paro de emergencia enganchado
/robot rearmar	Libera el paro; exige escribir SI para confirmar que el área está despejada
/robot autoprueba	Ejecuta las 15 comprobaciones del núcleo
/salir	Cierra

adan --autoprueba-robot ejecuta la autoprueba y termina con código 0 si todas pasan.

ADÁN Chat: /doc <ruta>, /docs, /limpiar, /salir. Cada documento se recorta a 10 000 caracteres porque phi3:mini tiene un contexto corto; el programa avisa cuando recorta.

EVA: chat con RAG, subida de documentos, análisis de cámara, transcripción de audio, botones de Paro de emergencia y Rearmar, y un control de movimiento que emite una Intención hacia la CSP.

Variables de entorno del kernel: PNLIO_OLLAMA_URL, PNLIO_MODEL, PNLIO_TIMEOUT, PNLIO_CONTEXT_MESSAGES, PNLIO_MEMORY_RESULTS, PNLIO_MOV_UMBRAL, PNLIO_CAM_WARMUP, PNLIO_DB_PATH. La base de datos de memoria queda en ~/.pnlio/soledad_memory.sqlite3.

Arquitectura de seguridad

Hay dos capas de seguridad, implementadas por separado en SOLEDAD y en EVA.

SOLEDAD: supervisor de seguridad

Orden del planificador → supervisor → actuador. El supervisor no depende del planificador. Estado seguro: velocidades en cero (robot móvil terrestre). Unidades SI. El reloj del núcleo es simulado.

Parámetro	Valor	Efecto
v_max / w_max	0.5 m/s / 1.0 rad/s	Tope de velocidad lineal y angular
a_max / alfa_max	0.5 m/s² / 2.0 rad/s²	Tope de aceleración; frenar es hasta 2× más rápido
timeout_orden	0.5 s	Sin órdenes nuevas → paro enganchado
timeout_sensor	0.5 s	Dato de distancia caducado o NaN → paro enganchado
d_parada	0.40 m	Obstáculo más cerca → paro enganchado
d_lento	1.20 m	Reducción lineal de velocidad hasta d_parada
v_cerca_persona	0.15 m/s	Tope si la cámara detecta movimiento significativo

También rechaza órdenes no finitas y dt inválido. El PID de giro tiene saturación, anti-windup por integración condicional y derivada filtrada sobre la medida.

El supervisor es la última línea de software. No sustituye un corte de energía por hardware independiente.

EVA: Capa de Seguridad Física (CSP)

Los módulos emiten Intenciones (mover, hablar, alertar, manipular) con urgencia 0 a 2. Solo la CSP decide si se ejecutan. Límites duros: velocidad máxima 0.5 m/s y zonas de exclusión escalera y cocina_fuego. Con el paro activo se veta todo. Las vetadas y las ejecutadas quedan en un registro de las últimas 50 entradas.

El punto de actuación (_ejecutar) hoy solo implementa hablar. Una Intención mover aprobada no mueve nada: queda registrada.

Autoprueba del núcleo robótico

Son 15 comprobaciones, cada una puede fallar:

NaN provoca paro · 2. paro enganchado ignora órdenes buenas · 3. rearmar() libera el paro · 4. aceleración limitada a a_max·dt · 5. orden caducada provoca paro · 6. sensor caducado provoca paro · 7. obstáculo bajo d_parada provoca paro · 8. anti-windup acota la integral · 9. el PID rechaza dt ≤ 0 · 10. run alcanza el objetivo en simulación · 11. run se detiene ante un obstáculo · 12. planificador colgado provoca paro · 13. sensor congelado provoca paro · 14. run rechazado con paro enganchado · 15. con persona cerca va más lento.

Para registrar una medición, ejecuta adan --autoprueba-robot y anota aquí el resultado con fecha, versión de Python y sistema operativo. Cifras de una sola ejecución no se extrapolan: son pruebas deterministas del diseño, no una estimación de fiabilidad en el mundo real.

Límites conocidos

Revisados leyendo el código; no se ejecutaron para escribir este README.

Valores simulados en EVA. Batería (LiFePO4 48 V, 83 %), geofence y postura del panel son constantes del código, no lecturas de sensores. Mostrar "ESTABLE" no significa nada sobre un robot real.
Primera ejecución de EVA con Internet. all-MiniLM-L6-v2 y el modelo small de whisper se descargan al primer uso, no durante la instalación. Sin conexión en esa primera vez, el RAG falla y la transcripción queda desactivada sin aviso claro. "100 % local" es cierto después de esa descarga.
Alertas por palabra clave. EVA lanza una alerta si la respuesta del modelo de visión contiene "peligro", "fuego", "caída" o "tirado"; una frase como "no hay peligro" también la dispara. Además, alertar solo se registra: no hace nada más.
Dos capas de seguridad distintas. La CSP de EVA no tiene caducidad de órdenes, límites de aceleración ni confirmación al rearmar (el botón rearma de inmediato; SOLEDAD pide SI). El estado compartido del kernel de EVA (registro, cola, paro) no usa bloqueos entre hilos.
Valores reconstruidos. Tres valores se reconstruyeron tras truncarse en un PDF anterior y están marcados RECONSTRUIDO en el código: la ruta IMAGE_PATH, lim_salida del PID de giro y temperature del modelo. Conviene confirmarlos contra la intención original.
Paquete de voz. El instalador pide espeakng; en Debian/Ubuntu el paquete suele llamarse espeak-ng. Verifica el nombre antes de publicar (puede ser un artefacto del PDF de origen).
Dependencias sin versión fijada. Gradio, sentence-transformers y faster-whisper se instalan en su última versión; el dashboard usa gr.Chatbot(type="tuples"), que puede cambiar entre versiones de Gradio. Fijar versiones queda pendiente.
Instalación de Ollama con curl … | sh: revisa el script antes de ejecutarlo si te importa la cadena de suministro.
Mensaje fijo. El instalador imprime "(15/15)" sin leer el resultado real; lo que determina el éxito es el código de salida.
Archivos del repositorio
Archivo	Contenido
README.md	Este documento
despliegue_pnlio2031.py	Instalador unificado (pendiente de subir; hoy está como PDF de referencia)
PNLIO_Framework_v7.2_Certificacion_Simulaciones.md.pdf	Documento histórico v7.2
PNLIO_Sistema_Robotico_Simbiotico_v7_2.pdf	Documento histórico v7.2

Sobre v7.2: el sistema descrito allí (RCR, niveles de falla, certificación Monte Carlo) es una línea anterior. Sus cifras no se reproducen en este README y no deben citarse como validación de seguridad: las simulaciones comprobaban que el gate se cierra cuando la métrica baja, no que la métrica refleje una degradación real. Las partes de v7.2 con control de fuego no forman parte del ecosistema actual.

Licencia

Apache License 2.0. El repositorio debe incluir LICENSE (texto completo) y NOTICE (copyright y atribución) — pendiente de agregar. Las dependencias deben tener licencia compatible con Apache 2.0 (MIT, BSD o Apache; no GPLv2 ni AGPL): revisa cada una antes de publicar.

© 2026 Gonzalo Mauricio De la Rivera Arellano · Apache 2.0
