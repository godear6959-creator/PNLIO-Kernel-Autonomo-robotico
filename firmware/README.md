# CSP RP2040

Firmware MicroPython de referencia para la Capa de Seguridad Física (CSP) de PNLIO.

## Función

La CSP recibe heartbeat e intentos autenticados del kernel, aplica límites locales y controla una habilitación de actuadores. Si el heartbeat caduca, el estado del kernel es inseguro, un sensor excede su límite o se acciona el E-STOP, la CSP desenergiza PWM y relé.

## Requisitos de integración

- Raspberry Pi Pico/RP2040 con MicroPython.
- Relé o MOSFET de habilitación configurado fail-to-off.
- Cadena E-STOP normalmente cerrada que corte físicamente la habilitación.
- Bumper y sensores de corriente/temperatura calibrados.
- Clave HMAC provisionada fuera del código fuente.
- Hash del firmware generado durante el build.

## Protocolo

Las tramas usan `$MENSAJE*CRC16` y HMAC sobre el mensaje sin CRC. Los nonces se mantienen en memoria y se rechazan si ya se utilizaron. CRC no es autenticación.

La implementación de referencia todavía requiere pruebas de interoperabilidad con el adaptador del kernel, pruebas eléctricas y medición temporal. No debe considerarse firmware certificado.
