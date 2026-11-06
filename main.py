#!/usr/bin/env python3
"""Punto de entrada del sistema de inventario de red.

Ejemplos:
  ./main.py validar datos/pruebas/dispositivos_con_errores.csv
  ./main.py reporte datos/                      # consolida JSON+YAML+CSV+XML
  ./main.py convertir datos/sede_cusco.xml reportes/cusco.json
  ./main.py api salud | listar [--estado Inactivo] | obtener R01
  ./main.py api registrar --nombre FW02 --ip 192.168.1.253 --tipo Firewall
  ./main.py api sincronizar datos/dispositivos.json
  ./main.py diagnostico                         # escenarios 4xx/5xx/TLS/timeout
  ./main.py api-externa                         # HTTPS real contra httpbin.org
  ./main.py menu                                # CRUD interactivo

Códigos de salida: 0 = OK, 1 = datos inválidos, 2 = error de API/red.
"""
import argparse
import os
import sys
from datetime import datetime
from typing import List

import requests

from inventario_red import __version__, analisis, config, formatos, registro
from inventario_red.cliente_api import (ClienteInventarioAPI, ErrorAPI, crear_sesion,
                                        diagnosticar_excepcion, diagnosticar_respuesta)
from inventario_red.modelo import Dispositivo, ErrorValidacion, validar_inventario

# umask 027: archivos nuevos (logs, reportes) sin acceso para "otros"
os.umask(0o027)
log = registro.configurar()

SALIDA_OK, SALIDA_DATOS, SALIDA_API = 0, 1, 2


# ------------------------------------------------------------------ utilidades
def _rutas(entradas: List[str]) -> List[str]:
    rutas = []
    for entrada in entradas:
        rutas.extend(formatos.archivos_soportados(entrada) if os.path.isdir(entrada) else [entrada])
    return rutas


def _cargar_validado(entradas: List[str]):
    """Carga uno o varios archivos/directorios y valida el conjunto consolidado."""
    registros = []
    for ruta in _rutas(entradas):
        datos = formatos.cargar(ruta)
        print("  Leído {:<38} {:>3} registros".format(os.path.relpath(ruta), len(datos)))
        registros.extend(datos)
    return validar_inventario(registros)


# ------------------------------------------------------------------ comandos
def cmd_validar(args) -> int:
    validos, errores = _cargar_validado(args.archivos)
    print("\nVálidos: {}  |  Con errores: {}".format(len(validos), len(errores)))
    for error in errores:
        print("  ✗", error)
    return SALIDA_DATOS if errores else SALIDA_OK


def cmd_reporte(args) -> int:
    validos, errores = _cargar_validado(args.archivos)
    for error in errores:
        print("  Aviso, omitido:", error)
    print()
    print(analisis.formatear_tabla(validos))
    print()
    print(analisis.formatear_resumen(analisis.resumir(validos)))
    if args.exportar:
        for destino in args.exportar:
            formatos.exportar(validos, destino)
            print("Exportado:", destino)
    log.info("Reporte generado: %s dispositivos válidos, %s errores", len(validos), len(errores))
    return SALIDA_DATOS if errores and args.estricto else SALIDA_OK


def cmd_convertir(args) -> int:
    validos, errores = validar_inventario(formatos.cargar(args.origen))
    for error in errores:
        print("  Aviso, omitido:", error)
    formatos.exportar(validos, args.destino)
    print("{} -> {} ({} dispositivos)".format(args.origen, args.destino, len(validos)))
    return SALIDA_OK


def cmd_api(args) -> int:
    cliente = ClienteInventarioAPI()
    if args.accion == "salud":
        print(cliente.salud())
    elif args.accion == "listar":
        dispositivos = cliente.listar_dispositivos(args.estado)
        print(analisis.formatear_tabla(dispositivos))
        print("\nTotal recibido de la API:", len(dispositivos))
    elif args.accion == "obtener":
        print(cliente.obtener_dispositivo(args.nombre).a_dict())
    elif args.accion == "registrar":
        nuevo = Dispositivo.desde_dict({"nombre": args.nombre, "ip": args.ip, "tipo": args.tipo,
                                        "estado": args.estado, "ubicacion": args.ubicacion})
        print("Creado (201):", cliente.registrar_dispositivo(nuevo))
    elif args.accion == "sincronizar":
        local, _ = validar_inventario(formatos.cargar(args.archivo))
        remoto = cliente.listar_dispositivos()
        desvio = analisis.comparar(local, remoto)
        print("Solo en archivo local :", desvio["solo_local"] or "ninguno")
        print("Solo en la API        :", desvio["solo_api"] or "ninguno")
        print("Diferencias           :", desvio["diferencias"] or "ninguna")
        if any(desvio.values()):
            print("\n⚠ Se detectó desvío entre la fuente local y la API.")
            return SALIDA_DATOS
        print("\n✓ Inventario local y API sincronizados.")
    return SALIDA_OK


def cmd_diagnostico(args) -> int:
    """Reproduce errores típicos de una API REST y muestra causa y solución."""
    base = config.API_BASE_URL.rstrip("/")
    ca = config.API_CA_CERT
    sin_reintentos = requests.Session()  # para ver cada código tal cual
    token = None

    def obtener_token():
        r = sin_reintentos.post(base + "/auth/token", headers={"X-API-Key": config.API_KEY},
                                verify=ca, timeout=5)
        r.raise_for_status()
        return r.json()["access_token"]

    escenarios = [
        ("TLS con CA del sistema (cert autofirmado)",
         lambda: requests.get(base + "/salud", timeout=5)),
        ("Puerto equivocado / servicio caído",
         lambda: requests.get(base.replace(":8443", ":8499") + "/salud", verify=ca, timeout=3)),
        ("Sin token", lambda: sin_reintentos.get(base + "/dispositivos", verify=ca, timeout=5)),
        ("API key incorrecta",
         lambda: sin_reintentos.post(base + "/auth/token", headers={"X-API-Key": "clave-erronea"},
                                     verify=ca, timeout=5)),
        ("Token inventado/expirado",
         lambda: sin_reintentos.get(base + "/dispositivos", verify=ca, timeout=5,
                                    headers={"Authorization": "Bearer token-vencido"})),
        ("Recurso inexistente",
         lambda: sin_reintentos.get(base + "/dispositivos/NOEXISTE", verify=ca, timeout=5,
                                    headers={"Authorization": "Bearer " + token})),
        ("Método no permitido",
         lambda: sin_reintentos.delete(base + "/dispositivos", verify=ca, timeout=5,
                                       headers={"Authorization": "Bearer " + token})),
        ("JSON mal formado",
         lambda: sin_reintentos.post(base + "/dispositivos", data="{nombre: R9", verify=ca, timeout=5,
                                     headers={"Authorization": "Bearer " + token,
                                              "Content-Type": "application/json"})),
        ("Content-Type incorrecto",
         lambda: sin_reintentos.post(base + "/dispositivos", data="nombre=R9", verify=ca, timeout=5,
                                     headers={"Authorization": "Bearer " + token})),
        ("Datos inválidos (IP/estado)",
         lambda: sin_reintentos.post(base + "/dispositivos", verify=ca, timeout=5,
                                     json={"nombre": "X1", "ip": "300.1.1.1", "tipo": "Router",
                                           "estado": "Roto"},
                                     headers={"Authorization": "Bearer " + token})),
        ("Duplicado (nombre existente)",
         lambda: sin_reintentos.post(base + "/dispositivos", verify=ca, timeout=5,
                                     json={"nombre": "R01", "ip": "192.168.1.1", "tipo": "Router",
                                           "estado": "Activo"},
                                     headers={"Authorization": "Bearer " + token})),
        ("Rate limit", lambda: sin_reintentos.get(base + "/simular/429", verify=ca, timeout=5,
                                                  headers={"Authorization": "Bearer " + token})),
        ("Error interno", lambda: sin_reintentos.get(base + "/simular/500", verify=ca, timeout=5,
                                                     headers={"Authorization": "Bearer " + token})),
        ("503 con reintentos y backoff",
         lambda: crear_sesion(2).get(base + "/simular/503", verify=ca, timeout=5,
                                     headers={"Authorization": "Bearer " + token})),
        ("Timeout de lectura (servidor lento)",
         lambda: sin_reintentos.get(base + "/simular/lento?segundos=4", verify=ca, timeout=(3, 1.5),
                                    headers={"Authorization": "Bearer " + token})),
    ]

    try:
        token = obtener_token()
    except requests.RequestException as exc:
        print(diagnosticar_excepcion(exc, base).explicar())
        print("\n¿Está corriendo la API? -> python3 api_simulada/servidor_https.py &")
        return SALIDA_API

    print("DIAGNÓSTICO DE ERRORES REST API ({})\n".format(base))
    for numero, (titulo, accion) in enumerate(escenarios, start=1):
        print("{:>2}. {}".format(numero, titulo))
        try:
            respuesta = accion()
            error = None if respuesta.ok else diagnosticar_respuesta(respuesta)
        except requests.RequestException as exc:
            error = diagnosticar_excepcion(exc, getattr(exc.request, "url", None) or base)
        texto = error.explicar() if error else "[200] OK"
        print("    " + texto.replace("\n", "\n    "))
        log.info("diagnostico %s: %s", titulo, texto.splitlines()[0])
    print("\nDetalle con request-id en logs/inventario.log y logs/api_servidor.log")
    return SALIDA_OK


def cmd_api_externa(args) -> int:
    """Consume un servicio público real por HTTPS (CA pública, sin autofirmados)."""
    base = config.API_EXTERNA_URL.rstrip("/")
    token = config.API_EXTERNA_TOKEN or "token-de-laboratorio"
    sesion = crear_sesion(2)
    pruebas = [
        ("GET con Bearer válido", "GET", "/bearer", {"Authorization": "Bearer " + token}),
        ("GET sin token", "GET", "/bearer", {}),
        ("POST JSON (eco de payload)", "POST", "/anything/dispositivos", {}),
        ("Ruta inexistente", "GET", "/status/404", {}),
        ("Servicio caído (503, reintentos)", "GET", "/status/503", {}),
    ]
    print("API EXTERNA {} (verificación TLS con CA públicas)\n".format(base))
    for titulo, metodo, ruta, cabeceras in pruebas:
        try:
            r = sesion.request(metodo, base + ruta, headers=cabeceras, timeout=(5, 15),
                               json={"nombre": "R01", "ip": "192.168.1.1"} if metodo == "POST" else None)
            if r.ok:
                cuerpo = r.json()
                # nunca se imprime el token, aunque el servicio lo devuelva en eco
                extracto = cuerpo.get("json") or {k: v for k, v in list(cuerpo.items())[:2]
                                                  if "token" not in k.lower()}
                print("✓ {:<34} HTTP {} {}".format(titulo, r.status_code, extracto))
            else:
                print("✗ {:<34} HTTP {} -> {}".format(titulo, r.status_code,
                                                      diagnosticar_respuesta(r).causa))
        except requests.RequestException as exc:
            print("✗ {:<34} {}".format(titulo, diagnosticar_excepcion(exc, base + ruta).causa))
    return SALIDA_OK


def cmd_menu(args) -> int:
    from inventario_red.crud import menu
    menu(args.archivo)
    return SALIDA_OK


# ------------------------------------------------------------------ CLI
def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="main.py", description="Inventario de red - DevOps")
    parser.add_argument("--version", action="version", version="%(prog)s " + __version__)
    sub = parser.add_subparsers(dest="comando")
    sub.required = True

    p = sub.add_parser("validar", help="valida uno o más archivos/directorios")
    p.add_argument("archivos", nargs="+")
    p.set_defaults(func=cmd_validar)

    p = sub.add_parser("reporte", help="consolida y resume el inventario")
    p.add_argument("archivos", nargs="+")
    p.add_argument("--exportar", nargs="*", metavar="RUTA",
                   help="ej.: reportes/inventario.json reportes/inventario.csv")
    p.add_argument("--estricto", action="store_true", help="código 1 si hay registros inválidos")
    p.set_defaults(func=cmd_reporte)

    p = sub.add_parser("convertir", help="convierte entre JSON/YAML/CSV/XML")
    p.add_argument("origen")
    p.add_argument("destino")
    p.set_defaults(func=cmd_convertir)

    p = sub.add_parser("api", help="consume la API REST HTTPS de inventario")
    acciones = p.add_subparsers(dest="accion")
    acciones.required = True
    acciones.add_parser("salud")
    a = acciones.add_parser("listar")
    a.add_argument("--estado", choices=["Activo", "Inactivo"])
    a = acciones.add_parser("obtener")
    a.add_argument("nombre")
    a = acciones.add_parser("registrar")
    a.add_argument("--nombre", required=True)
    a.add_argument("--ip", required=True)
    a.add_argument("--tipo", required=True)
    a.add_argument("--estado", default="Activo")
    a.add_argument("--ubicacion", default="Lima")
    a = acciones.add_parser("sincronizar")
    a.add_argument("archivo")
    p.set_defaults(func=cmd_api)

    sub.add_parser("diagnostico", help="reproduce y explica errores de la API").set_defaults(
        func=cmd_diagnostico)
    sub.add_parser("api-externa", help="prueba un servicio HTTPS público").set_defaults(
        func=cmd_api_externa)

    p = sub.add_parser("menu", help="CRUD interactivo")
    p.add_argument("--archivo", default=config.INVENTARIO_PRINCIPAL)
    p.set_defaults(func=cmd_menu)
    return parser


def main(argv=None) -> int:
    args = construir_parser().parse_args(argv)
    log.info("Inicio: %s", " ".join(sys.argv[1:]))
    try:
        return args.func(args)
    except formatos.ErrorFormato as exc:
        print("Error de archivo:", exc, file=sys.stderr)
        return SALIDA_DATOS
    except ErrorValidacion as exc:
        print("Datos inválidos:", exc, file=sys.stderr)
        return SALIDA_DATOS
    except ErrorAPI as exc:
        print(exc.explicar(), file=sys.stderr)
        return SALIDA_API
    except ValueError as exc:  # configuración inválida (URL no HTTPS, falta API_KEY)
        print("Configuración:", exc, file=sys.stderr)
        return SALIDA_API
    except KeyboardInterrupt:
        print("\nInterrumpido por el usuario.", file=sys.stderr)
        return 130
    finally:
        log.info("Fin (%s)", datetime.now().isoformat(timespec="seconds"))


if __name__ == "__main__":
    sys.exit(main())
