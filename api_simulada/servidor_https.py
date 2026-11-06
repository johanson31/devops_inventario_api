#!/usr/bin/env python3
"""API REST de inventario sobre HTTPS (solo librería estándar).

Simula el servicio externo de la organización para poder probar y depurar el
cliente sin depender de Internet. Reproduce a propósito los escenarios de
error que el cliente debe saber diagnosticar.

Endpoints (prefijo /api/v1):
  GET  /salud                      sin autenticación
  POST /auth/token                 cabecera X-API-Key  -> token Bearer (5 min)
  GET  /dispositivos[?estado=]     Bearer
  GET  /dispositivos/<nombre>      Bearer
  POST /dispositivos               Bearer + JSON  (201, 400, 409, 415, 422)
  GET  /simular/<codigo>           Bearer; fuerza 429, 500 o 503
  GET  /simular/lento?segundos=N   Bearer; respuesta demorada (timeouts)

Uso:  python3 api_simulada/servidor_https.py [--puerto 8443]
"""
import argparse
import hmac
import json
import logging
import os
import secrets
import ssl
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from inventario_red import config, formatos  # noqa: E402
from inventario_red.modelo import Dispositivo, validar_inventario, validar_registro  # noqa: E402

PREFIJO = "/api/v1"
DURACION_TOKEN = 300
LIMITE_POR_MINUTO = 120

log = logging.getLogger("api_simulada")


class Estado:
    """Estado compartido entre hilos, protegido con un candado."""

    def __init__(self, ruta_datos: str):
        self.candado = threading.Lock()
        self.dispositivos, errores = validar_inventario(formatos.cargar(ruta_datos))
        for error in errores:
            log.warning("Dato inicial omitido: %s", error)
        self.tokens = {}          # token -> expiración
        self.solicitudes = {}     # ip cliente -> [marcas de tiempo]


class Manejador(BaseHTTPRequestHandler):
    server_version = "InventarioAPI/1.0"
    sys_version = ""  # no revelar la versión de Python en la cabecera Server

    # ------------------------------------------------------------ utilidades
    @property
    def estado(self) -> Estado:
        return self.server.estado  # type: ignore[attr-defined]

    def log_message(self, formato, *args):  # redirige al logger con request-id
        log.info("%s %s", self.address_string(), formato % args)

    def _responder(self, codigo: int, cuerpo=None, cabeceras=None):
        datos = b"" if cuerpo is None else json.dumps(cuerpo, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("X-Request-ID", self.request_id)
        self.send_header("Strict-Transport-Security", "max-age=31536000")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        for clave, valor in (cabeceras or {}).items():
            self.send_header(clave, valor)
        if datos:
            self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(datos)))
        self.end_headers()
        self.wfile.write(datos)

    def _error(self, codigo: int, mensaje: str, **extra):
        cuerpo = {"error": mensaje, "codigo": codigo, "request_id": self.request_id}
        cuerpo.update({k: v for k, v in extra.items() if k != "cabeceras"})
        self._responder(codigo, cuerpo, extra.get("cabeceras"))

    def _limite_excedido(self) -> bool:
        ahora = time.time()
        with self.estado.candado:
            marcas = [t for t in self.estado.solicitudes.get(self.client_address[0], [])
                      if ahora - t < 60]
            marcas.append(ahora)
            self.estado.solicitudes[self.client_address[0]] = marcas
            return len(marcas) > LIMITE_POR_MINUTO

    def _autorizado(self) -> bool:
        cabecera = self.headers.get("Authorization", "")
        if not cabecera.startswith("Bearer "):
            self._error(401, "Falta el token Bearer", cabeceras={"WWW-Authenticate": "Bearer"})
            return False
        token = cabecera[len("Bearer "):].strip()
        with self.estado.candado:
            expira = self.estado.tokens.get(token)
        if expira is None or expira < time.time():
            self._error(401, "Token inválido o expirado",
                        cabeceras={"WWW-Authenticate": 'Bearer error="invalid_token"'})
            return False
        return True

    def _preparar(self):
        self.request_id = uuid.uuid4().hex[:12]
        self.ruta = urlparse(self.path)
        if self._limite_excedido():
            self._error(429, "Demasiadas solicitudes", cabeceras={"Retry-After": "30"})
            return False
        if not self.ruta.path.startswith(PREFIJO):
            self._error(404, "Ruta no encontrada: " + self.ruta.path)
            return False
        self.recurso = self.ruta.path[len(PREFIJO):].rstrip("/") or "/"
        return True

    # ------------------------------------------------------------ verbos
    def do_GET(self):
        if not self._preparar():
            return
        if self.recurso == "/salud":
            return self._responder(200, {"estado": "ok", "servicio": "inventario-red",
                                         "version": "1.0"})
        if not self._autorizado():
            return
        if self.recurso == "/dispositivos":
            filtro = parse_qs(self.ruta.query).get("estado", [""])[0].capitalize()
            with self.estado.candado:
                lista = [d.a_dict() for d in self.estado.dispositivos
                         if not filtro or d.estado == filtro]
            return self._responder(200, {"total": len(lista), "dispositivos": lista})
        if self.recurso.startswith("/dispositivos/"):
            nombre = unquote(self.recurso.split("/", 2)[2]).upper()
            with self.estado.candado:
                encontrado = next((d for d in self.estado.dispositivos if d.nombre == nombre), None)
            if encontrado is None:
                return self._error(404, "Dispositivo {} no existe".format(nombre))
            return self._responder(200, encontrado.a_dict())
        if self.recurso == "/simular/lento":
            segundos = min(float(parse_qs(self.ruta.query).get("segundos", ["5"])[0]), 30)
            time.sleep(segundos)
            return self._responder(200, {"mensaje": "respuesta tras {} s".format(segundos)})
        if self.recurso.startswith("/simular/"):
            codigo = self.recurso.rsplit("/", 1)[1]
            if codigo == "429":
                return self._error(429, "Rate limit simulado", cabeceras={"Retry-After": "1"})
            if codigo == "500":
                return self._error(500, "Fallo interno simulado (excepción no controlada)")
            if codigo == "503":
                return self._error(503, "Servicio en mantenimiento", cabeceras={"Retry-After": "1"})
        return self._error(404, "Recurso no encontrado: " + self.recurso)

    def do_POST(self):
        if not self._preparar():
            return
        if self.recurso == "/auth/token":
            return self._emitir_token()
        if not self._autorizado():
            return
        if self.recurso != "/dispositivos":
            return self._error(405, "POST no permitido en " + self.recurso,
                               cabeceras={"Allow": "GET"})
        if "application/json" not in self.headers.get("Content-Type", ""):
            return self._error(415, "Se requiere Content-Type: application/json")
        try:
            largo = int(self.headers.get("Content-Length", "0"))
            cuerpo = json.loads(self.rfile.read(largo).decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            return self._error(400, "JSON inválido: {}".format(exc))
        errores = validar_registro(cuerpo)
        if errores:
            return self._error(422, "Datos no válidos", errores=errores)
        nuevo = Dispositivo.desde_dict(cuerpo)
        with self.estado.candado:
            if any(d.nombre == nuevo.nombre or d.ip == nuevo.ip for d in self.estado.dispositivos):
                conflicto = True
            else:
                conflicto = False
                self.estado.dispositivos.append(nuevo)
        if conflicto:
            return self._error(409, "Ya existe un dispositivo con ese nombre o IP")
        self._responder(201, nuevo.a_dict(),
                        {"Location": "{}/dispositivos/{}".format(PREFIJO, nuevo.nombre)})

    def do_PUT(self):
        self._metodo_no_permitido()

    def do_DELETE(self):
        self._metodo_no_permitido()

    def _metodo_no_permitido(self):
        if self._preparar():
            self._error(405, "Método {} no permitido".format(self.command),
                        cabeceras={"Allow": "GET, POST"})

    def _emitir_token(self):
        clave = self.headers.get("X-API-Key", "")
        if not clave:
            return self._error(401, "Falta la cabecera X-API-Key")
        # compare_digest evita ataques de temporización al comparar secretos
        if not hmac.compare_digest(clave.encode(), self.server.api_key.encode()):  # type: ignore
            log.warning("API key rechazada desde %s", self.client_address[0])
            return self._error(403, "API key inválida")
        token = secrets.token_urlsafe(32)
        with self.estado.candado:
            ahora = time.time()
            self.estado.tokens = {t: e for t, e in self.estado.tokens.items() if e > ahora}
            self.estado.tokens[token] = ahora + DURACION_TOKEN
        self._responder(200, {"access_token": token, "token_type": "Bearer",
                              "expires_in": DURACION_TOKEN})


def crear_servidor(puerto: int, certificado: str, llave: str, api_key: str,
                   datos: str, host: str = "127.0.0.1") -> ThreadingHTTPServer:
    servidor = ThreadingHTTPServer((host, puerto), Manejador)
    contexto = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    contexto.minimum_version = ssl.TLSVersion.TLSv1_2  # descarta TLS 1.0/1.1
    contexto.load_cert_chain(certificado, llave)
    servidor.socket = contexto.wrap_socket(servidor.socket, server_side=True)
    servidor.estado = Estado(datos)  # type: ignore[attr-defined]
    servidor.api_key = api_key       # type: ignore[attr-defined]
    return servidor


def main() -> None:
    parser = argparse.ArgumentParser(description="API REST HTTPS simulada de inventario")
    parser.add_argument("--host", default="127.0.0.1",
                        help="interfaz de escucha (por defecto solo local)")
    parser.add_argument("--puerto", type=int, default=8443)
    parser.add_argument("--cert", default=os.path.join(BASE_DIR, "certs", "servidor.crt"))
    parser.add_argument("--llave", default=os.path.join(BASE_DIR, "certs", "servidor.key"))
    parser.add_argument("--datos", default=config.INVENTARIO_PRINCIPAL)
    args = parser.parse_args()

    os.makedirs(config.DIR_LOGS, exist_ok=True)
    manejadores = [logging.FileHandler(os.path.join(config.DIR_LOGS, "api_servidor.log"))]
    if sys.stderr.isatty():  # en segundo plano (nohup) basta con el archivo
        manejadores.append(logging.StreamHandler())
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=manejadores)
    if not config.API_KEY:
        sys.exit("ERROR: defina API_KEY en .env (ejecute scripts/setup_entorno.sh)")
    for ruta in (args.cert, args.llave):
        if not os.path.isfile(ruta):
            sys.exit("ERROR: no existe {} (ejecute scripts/generar_certificado.sh)".format(ruta))

    servidor = crear_servidor(args.puerto, args.cert, args.llave, config.API_KEY, args.datos, args.host)
    log.info("API escuchando en https://%s:%s%s", args.host, args.puerto, PREFIJO)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        log.info("Servidor detenido por el usuario")
    finally:
        servidor.server_close()


if __name__ == "__main__":
    main()
