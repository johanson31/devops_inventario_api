# devops_inventario_api

Automatización del inventario de dispositivos de red: consolida inventarios de
varias sedes en **JSON, YAML, CSV y XML**, los valida, genera reportes y los
contrasta con una **API REST sobre HTTPS** autenticada con API key y token
Bearer. Incluye scripts Linux para desplegar el entorno con permisos mínimos y
un diagnóstico de errores 4xx/5xx.

Proyecto del curso **DevOps: Fundamentos** (IDAT).

---

## Contenido

- [Requisitos](#requisitos)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Instalación](#instalación)
- [Levantar la API](#levantar-la-api)
- [Uso del programa](#uso-del-programa)
- [Endpoints de la API](#endpoints-de-la-api)
- [Uso con Postman o curl](#uso-con-postman-o-curl)
- [Pruebas](#pruebas)
- [Seguridad y permisos](#seguridad-y-permisos)
- [Flujo de trabajo con Git](#flujo-de-trabajo-con-git)
- [Solución de problemas](#solución-de-problemas)

---

## Requisitos

| Componente | Versión probada |
|---|---|
| Sistema operativo | Ubuntu 20.04 (VM DEVASC-LABVM) |
| Python | 3.8 o superior |
| Librerías | `requests >= 2.22`, `PyYAML >= 5.3` (ver `requirements.txt`) |
| Herramientas | `git`, `openssl`, `curl` |

## Estructura del proyecto

```
devops_inventario_api/
├── main.py                  CLI: validar | reporte | convertir | api | diagnostico | api-externa | menu
├── inventario_red/          paquete con la lógica (un módulo por responsabilidad)
│   ├── modelo.py            Dispositivo + reglas de validación (IP, tipo, estado, duplicados)
│   ├── formatos.py          lectura/escritura JSON, YAML, CSV, XML (escritura atómica)
│   ├── analisis.py          resumen por tipo/sede/subred y comparación archivo ↔ API
│   ├── cliente_api.py       cliente HTTPS: token, reintentos, timeouts, diagnóstico de errores
│   ├── crud.py              menú interactivo con persistencia
│   ├── registro.py          logs rotativos con enmascarado de secretos
│   └── config.py            configuración por variables de entorno / .env
├── api_simulada/
│   └── servidor_https.py    API REST HTTPS (TLS 1.2+, API key → token Bearer)
├── datos/                   Lima (JSON) · Arequipa (YAML) · Trujillo (CSV) · Cusco (XML)
│   └── pruebas/             archivos con errores intencionales (validación)
├── scripts/
│   ├── setup_entorno.sh     prepara el entorno: .env, certificado, permisos, grupo, cron
│   ├── generar_certificado.sh
│   ├── api.sh               iniciar | detener | estado de la API
│   └── auditar_permisos.sh  revisa permisos y secretos
├── tests/                   pruebas unitarias e integración (unittest)
├── legacy/                  versiones iniciales: inventario.py, inventario_v2.py
├── requirements.txt
└── .env.example             plantilla de configuración
```

Los archivos `.env`, `certs/`, `logs/` y `reportes/` se generan al ejecutar
`setup_entorno.sh` y **no se versionan** (ver `.gitignore`).

## Instalación

```bash
git clone https://github.com/johanson31/devops_inventario_api.git
cd devops_inventario_api

# (opcional) entorno virtual para no tocar el Python del sistema
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# prepara el entorno: verifica dependencias, crea .env (600) con una API key
# aleatoria, genera el certificado TLS y aplica permisos
./scripts/setup_entorno.sh

# (opcional, con sudo) grupo netops + cuenta de servicio devops_prueba
sudo ./scripts/setup_entorno.sh --equipo

# (opcional) reporte consolidado cada hora con cron
./scripts/setup_entorno.sh --cron
```

> Si `./script` responde *Permission denied*, ejecuta antes
> `chmod 750 main.py scripts/*.sh api_simulada/servidor_https.py`.

## Levantar la API

```bash
./scripts/api.sh iniciar     # en segundo plano → https://localhost:8443/api/v1
./scripts/api.sh estado      # PID y puerto en escucha
./scripts/api.sh detener
```

Comprobación rápida:

```bash
curl -s --cacert certs/servidor.crt https://localhost:8443/api/v1/salud
# {"estado": "ok", "servicio": "inventario-red", "version": "1.0"}
```

Para ver cada solicitud en pantalla, ejecútala en primer plano (se detiene con Ctrl+C):

```bash
python3 api_simulada/servidor_https.py            # solo localhost (por defecto)
python3 api_simulada/servidor_https.py --host 0.0.0.0 --puerto 8443   # accesible desde fuera de la VM
```

Logs: `logs/api_servidor.log` (servidor) y `logs/inventario.log` (cliente).

## Uso del programa

| Comando | Qué hace |
|---|---|
| `./main.py validar datos/pruebas/dispositivos_con_errores.csv` | Valida un archivo y lista cada error (código de salida 1 si hay errores) |
| `./main.py reporte datos/` | Consolida las 4 sedes y muestra el resumen |
| `./main.py reporte datos/ --exportar reportes/inv.json reportes/inv.csv` | Además exporta a los formatos indicados |
| `./main.py convertir datos/sede_cusco.xml reportes/cusco.yaml` | Convierte entre JSON, YAML, CSV y XML |
| `./main.py api salud` | Estado de la API |
| `./main.py api listar [--estado Activo\|Inactivo]` | Lista dispositivos (obtiene el token automáticamente) |
| `./main.py api obtener R01` | Consulta un dispositivo |
| `./main.py api registrar --nombre AP01 --ip 192.168.1.50 --tipo AccessPoint` | Registra un dispositivo (POST → 201) |
| `./main.py api sincronizar datos/dispositivos.json` | Detecta diferencias entre el archivo local y la API |
| `./main.py diagnostico` | Reproduce 15 errores (TLS, red, 400–429, 500, 503, timeout) con causa y solución |
| `./main.py api-externa` | Prueba HTTPS real contra httpbin.org (requiere Internet) |
| `./main.py menu` | CRUD interactivo |

Códigos de salida: `0` correcto · `1` datos inválidos · `2` error de API o de red.

Tipos válidos: `Router`, `Switch`, `Servidor`, `Firewall`, `AccessPoint`.
Estados válidos: `Activo`, `Inactivo`.

## Endpoints de la API

Base: `https://localhost:8443/api/v1`

| Método | Ruta | Autenticación | Respuestas |
|---|---|---|---|
| GET | `/salud` | ninguna | 200 |
| POST | `/auth/token` | cabecera `X-API-Key` | 200 (token, 300 s), 401, 403 |
| GET | `/dispositivos[?estado=Activo]` | `Authorization: Bearer <token>` | 200, 401 |
| GET | `/dispositivos/<nombre>` | Bearer | 200, 404 |
| POST | `/dispositivos` | Bearer + JSON | 201, 400, 409, 415, 422 |
| GET | `/simular/429` · `/simular/500` · `/simular/503` | Bearer | errores simulados |
| GET | `/simular/lento?segundos=N` | Bearer | respuesta demorada (timeouts) |

Cuerpo de ejemplo para el POST:

```json
{"nombre": "AP05", "ip": "192.168.1.55", "tipo": "AccessPoint", "estado": "Activo", "ubicacion": "Lima"}
```

## Uso con Postman o curl

1. La API key está en `.env` (`grep API_KEY .env`).
2. El certificado es autofirmado: en Postman, **Settings → Certificates → CA certificates**
   → `certs/servidor.crt` (mantén activa la verificación SSL).
3. Obtener token: `POST /auth/token` con cabecera `X-API-Key`.
   Para guardarlo automáticamente, en **Scripts → Post-response**:
   ```javascript
   pm.environment.set("token", pm.response.json().access_token);
   ```
4. Usar `{{token}}` en **Authorization → Bearer Token** en las demás solicitudes.

Con curl:

```bash
KEY=$(grep API_KEY .env | cut -d= -f2)
TOKEN=$(curl -s --cacert certs/servidor.crt -X POST -H "X-API-Key: $KEY" \
        https://localhost:8443/api/v1/auth/token | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
curl -s --cacert certs/servidor.crt -H "Authorization: Bearer $TOKEN" https://localhost:8443/api/v1/dispositivos
```

Desde fuera de la VM: inicia la API con `--host 0.0.0.0` y agrega en VirtualBox
un reenvío de puertos TCP 8443 → 8443.

## Pruebas

```bash
python3 -m unittest discover -s tests -t . -v
```

20 pruebas: validación del modelo, ida y vuelta entre los 4 formatos, archivos con
errores, cliente HTTPS contra la API real (token, 403, 404, 409, renovación del
token, TLS sin CA, reintentos ante 503) y enmascarado de secretos en logs.

## Seguridad y permisos

| Elemento | Permiso | Motivo |
|---|---|---|
| Directorios | 750 | el grupo `netops` lee; otros usuarios no |
| Código y datos | 640 | solo el propietario modifica |
| `main.py`, `*.sh` | 750 | solo los puntos de entrada son ejecutables |
| `.env`, `certs/servidor.key` | 600 | secretos: solo el propietario |
| `logs/`, `reportes/` | 2770 (setgid) | lo generado hereda el grupo `netops` |

- Solo HTTPS con verificación de certificado (nunca `verify=False`), TLS 1.2 como mínimo.
- La API key se usa una sola vez para obtener un token de 5 minutos.
- Reintentos con backoff solo ante 429/502/503/504 y en métodos GET; timeouts de 3 s / 10 s.
- Los logs enmascaran tokens y claves.
- `./scripts/auditar_permisos.sh` verifica todo lo anterior.

