"""Configuración centralizada.

Los secretos (API key) NUNCA se escriben en el código: se leen de variables de
entorno o de un archivo .env con permiso 600 que está excluido de Git.
"""
import os
import stat
import warnings
from typing import Dict

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUTA_ENV = os.path.join(BASE_DIR, ".env")


def cargar_env(ruta: str = RUTA_ENV) -> Dict[str, str]:
    """Carga pares CLAVE=valor de .env sin sobrescribir variables ya exportadas."""
    valores: Dict[str, str] = {}
    if not os.path.isfile(ruta):
        return valores

    modo = stat.S_IMODE(os.stat(ruta).st_mode)
    if modo & 0o077:
        warnings.warn("{} tiene permisos {:o}; se recomienda chmod 600".format(ruta, modo))

    with open(ruta, encoding="utf-8") as archivo:
        for linea in archivo:
            linea = linea.strip()
            if not linea or linea.startswith("#") or "=" not in linea:
                continue
            clave, valor = linea.split("=", 1)
            valores[clave.strip()] = valor.strip().strip('"').strip("'")
    for clave, valor in valores.items():
        os.environ.setdefault(clave, valor)
    return valores


cargar_env()

API_BASE_URL = os.getenv("API_BASE_URL", "https://localhost:8443/api/v1")
API_KEY = os.getenv("API_KEY", "")
API_CA_CERT = os.getenv("API_CA_CERT", os.path.join(BASE_DIR, "certs", "servidor.crt"))
API_TIMEOUT_CONEXION = float(os.getenv("API_TIMEOUT_CONEXION", "3.05"))
API_TIMEOUT_LECTURA = float(os.getenv("API_TIMEOUT_LECTURA", "10"))
API_REINTENTOS = int(os.getenv("API_REINTENTOS", "3"))

API_EXTERNA_URL = os.getenv("API_EXTERNA_URL", "https://httpbin.org")
API_EXTERNA_TOKEN = os.getenv("API_EXTERNA_TOKEN", "")

DIR_DATOS = os.path.join(BASE_DIR, "datos")
DIR_LOGS = os.path.join(BASE_DIR, "logs")
DIR_REPORTES = os.path.join(BASE_DIR, "reportes")
INVENTARIO_PRINCIPAL = os.path.join(DIR_DATOS, "dispositivos.json")
