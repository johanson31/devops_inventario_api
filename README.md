# Inventario de Red Automatizado (DevOps: Fundamentos – IDAT)

Automatiza la gestión del inventario de dispositivos de red: consolida
inventarios de varias sedes en **JSON, YAML, CSV y XML**, los valida, genera
reportes y los contrasta con una **API REST sobre HTTPS** autenticada con
API key y token Bearer. Incluye scripts Linux para despliegue seguro y
diagnóstico de errores 4xx/5xx.

## Estructura

```
devops_parcial/
├── main.py                  CLI: validar | reporte | convertir | api | diagnostico | api-externa | menu
├── inventario_red/          paquete con la lógica (un módulo por responsabilidad)
│   ├── modelo.py            Dispositivo + reglas de validación (IP, tipo, estado, duplicados)
│   ├── formatos.py          lectores/escritores JSON, YAML, CSV, XML (escritura atómica)
│   ├── analisis.py          resumen, agrupación por tipo/sede/subred, detección de desvío
│   ├── cliente_api.py       cliente HTTPS: token, reintentos, timeouts, diagnóstico de errores
│   ├── crud.py              menú interactivo con persistencia (evolución de inventario_v2)
│   ├── registro.py          logs rotativos con enmascarado de secretos
│   └── config.py            configuración por variables de entorno / .env
├── api_simulada/servidor_https.py   API REST HTTPS local (TLS 1.2+, API key -> Bearer)
├── datos/                   inventario Lima (JSON) y sedes Arequipa (YAML), Trujillo (CSV), Cusco (XML)
│   └── pruebas/             archivos con errores intencionales
├── scripts/                 setup_entorno.sh, generar_certificado.sh, api.sh, auditar_permisos.sh
├── tests/                   pruebas unitarias e integración (unittest)
└── legacy/                  inventario.py e inventario_v2.py originales (trazabilidad)
```

## Puesta en marcha (Linux)

```bash
./scripts/setup_entorno.sh            # dependencias, .env (600), certificado TLS, permisos
sudo ./scripts/setup_entorno.sh --equipo   # grupo netops + usuario de servicio
./scripts/api.sh iniciar              # API HTTPS en https://localhost:8443/api/v1
python3 -m unittest discover -s tests -t . -v
```

## Uso

| Comando | Qué hace |
|---|---|
| `./main.py validar datos/pruebas/dispositivos_con_errores.csv` | lista cada error; código de salida 1 |
| `./main.py reporte datos/ --exportar reportes/inv.json reportes/inv.csv` | consolida las 4 sedes y resume |
| `./main.py convertir datos/sede_cusco.xml reportes/cusco.yaml` | conversión entre formatos |
| `./main.py api listar --estado Inactivo` | consulta la API con token |
| `./main.py api registrar --nombre AP01 --ip 192.168.1.50 --tipo AccessPoint` | alta vía POST (201) |
| `./main.py api sincronizar datos/dispositivos.json` | detecta desvío archivo ↔ API |
| `./main.py diagnostico` | reproduce 15 fallos (TLS, red, 400–429, 5xx, timeout) con causa y solución |
| `./main.py api-externa` | HTTPS real contra httpbin.org (CA pública) |
| `./main.py menu` | CRUD interactivo |

Códigos de salida: `0` correcto, `1` datos inválidos, `2` error de API o red.

## Decisiones técnicas

- **Seguridad de la API:** solo HTTPS con verificación de certificado (nunca
  `verify=False`); la API key está en `.env` (600, fuera de Git) y solo se usa
  para obtener un token Bearer de 5 minutos; los logs enmascaran secretos.
- **Confiabilidad:** `requests.Session` reutiliza la conexión TLS; reintentos
  con *backoff* solo en errores transitorios (429/502/503/504) y en métodos
  idempotentes; *timeouts* de conexión y lectura; renovación automática del
  token ante un 401.
- **Calidad del dato:** una sola fuente de reglas (`modelo.py`) usada por
  archivos, CRUD, cliente y servidor; las respuestas de la API también se validan.
- **Linux:** mínimo privilegio (750/640/600), `setgid` en `logs/` y `reportes/`,
  `umask 027`, usuario de servicio sin contraseña y tarea `cron` horaria.
- **Git:** flujo `main` / `develop` / `feature/*`, *merge* `--no-ff`, commits
  convencionales y versiones etiquetadas (`v1.0.0`, `v2.0.0`).
