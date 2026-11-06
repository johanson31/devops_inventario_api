"""Logging con rotación y enmascarado de secretos.

Los logs son evidencia para diagnosticar fallos de la API, pero jamás deben
contener la API key ni el token: un filtro los reemplaza por '***'.
"""
import logging
import os
import re
from logging.handlers import RotatingFileHandler

from . import config

_PATRONES_SECRETOS = [
    # Solo se enmascaran valores con forma de secreto (8+ caracteres seguros),
    # así no se alteran mensajes como "Sin token: [401]".
    re.compile(r"(Bearer\s+)[A-Za-z0-9\-._~+/=]{8,}", re.IGNORECASE),
    re.compile(r"((?:api[_-]?key|access_token|token|x-api-key)[\"']?\s*[:=]\s*[\"']?)"
               r"[A-Za-z0-9\-._~+/=]{8,}", re.IGNORECASE),
]


class FiltroSecretos(logging.Filter):
    def filter(self, registro: logging.LogRecord) -> bool:
        mensaje = registro.getMessage()
        for patron in _PATRONES_SECRETOS:
            mensaje = patron.sub(r"\1***", mensaje)
        registro.msg, registro.args = mensaje, ()
        return True


def configurar(nombre: str = "inventario", archivo: str = "inventario.log",
               nivel_consola: int = logging.WARNING) -> logging.Logger:
    logger = logging.getLogger(nombre)
    if logger.handlers:  # evita handlers duplicados si se llama dos veces
        return logger
    logger.setLevel(logging.DEBUG)
    formato = logging.Formatter("%(asctime)s %(levelname)-8s %(name)s: %(message)s")

    os.makedirs(config.DIR_LOGS, exist_ok=True)
    a_archivo = RotatingFileHandler(os.path.join(config.DIR_LOGS, archivo),
                                    maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    a_archivo.setFormatter(formato)
    a_archivo.addFilter(FiltroSecretos())
    logger.addHandler(a_archivo)

    consola = logging.StreamHandler()
    consola.setLevel(nivel_consola)
    consola.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    consola.addFilter(FiltroSecretos())
    logger.addHandler(consola)
    return logger
