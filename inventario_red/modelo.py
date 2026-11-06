"""Modelo de dominio: el dispositivo de red y sus reglas de validación.

Centralizar aquí las reglas evita duplicarlas: las usan los lectores de
archivos, el CRUD interactivo, el cliente de la API y el servidor simulado.
"""
import ipaddress
from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, List, Tuple

TIPOS_VALIDOS = ("Router", "Switch", "Servidor", "Firewall", "AccessPoint")
ESTADOS_VALIDOS = ("Activo", "Inactivo")
CAMPOS_OBLIGATORIOS = ("nombre", "ip", "tipo", "estado")


class ErrorValidacion(ValueError):
    """Se lanza cuando un registro no cumple las reglas del modelo."""

    def __init__(self, errores: List[str]):
        self.errores = errores
        super().__init__("; ".join(errores))


def _normalizar(valor: str, permitidos: Iterable[str]) -> str:
    """Devuelve el valor permitido que coincide sin distinguir mayúsculas."""
    mapa = {p.lower(): p for p in permitidos}
    return mapa.get(valor.strip().lower(), "")


def validar_registro(datos: Dict[str, Any]) -> List[str]:
    """Valida un diccionario crudo y devuelve la lista de errores (vacía si es válido)."""
    if not isinstance(datos, dict):
        return ["el registro no es un objeto clave/valor"]

    errores = []
    etiqueta = str(datos.get("nombre") or "<sin nombre>").strip()

    for campo in CAMPOS_OBLIGATORIOS:
        valor = datos.get(campo)
        if valor is None or str(valor).strip() == "":
            errores.append("{}: falta el campo '{}'".format(etiqueta, campo))
    if errores:
        return errores

    try:
        ipaddress.ip_address(str(datos["ip"]).strip())
    except ValueError:
        errores.append("{}: IP no válida '{}'".format(etiqueta, datos["ip"]))

    if not _normalizar(str(datos["tipo"]), TIPOS_VALIDOS):
        errores.append("{}: tipo '{}' no permitido {}".format(
            etiqueta, datos["tipo"], list(TIPOS_VALIDOS)))

    if not _normalizar(str(datos["estado"]), ESTADOS_VALIDOS):
        errores.append("{}: estado '{}' no válido [Activo/Inactivo]".format(
            etiqueta, datos["estado"]))

    return errores


@dataclass
class Dispositivo:
    nombre: str
    ip: str
    tipo: str
    estado: str
    ubicacion: str = "Sin asignar"

    @classmethod
    def desde_dict(cls, datos: Dict[str, Any]) -> "Dispositivo":
        """Crea un Dispositivo normalizado o lanza ErrorValidacion."""
        errores = validar_registro(datos)
        if errores:
            raise ErrorValidacion(errores)
        return cls(
            nombre=str(datos["nombre"]).strip().upper(),
            ip=str(ipaddress.ip_address(str(datos["ip"]).strip())),
            tipo=_normalizar(str(datos["tipo"]), TIPOS_VALIDOS),
            estado=_normalizar(str(datos["estado"]), ESTADOS_VALIDOS),
            ubicacion=str(datos.get("ubicacion") or "Sin asignar").strip(),
        )

    def a_dict(self) -> Dict[str, str]:
        return asdict(self)

    @property
    def activo(self) -> bool:
        return self.estado == "Activo"


def validar_inventario(registros: Iterable[Dict[str, Any]]) -> Tuple[List[Dispositivo], List[str]]:
    """Valida una colección completa.

    Además de las reglas por registro, detecta nombres e IPs duplicados,
    errores que solo se ven al mirar el inventario como un todo.
    """
    validos: List[Dispositivo] = []
    errores: List[str] = []
    nombres, ips = set(), set()

    for posicion, registro in enumerate(registros, start=1):
        try:
            dispositivo = Dispositivo.desde_dict(registro)
        except ErrorValidacion as exc:
            errores.extend("registro {}: {}".format(posicion, e) for e in exc.errores)
            continue

        if dispositivo.nombre in nombres:
            errores.append("registro {}: nombre duplicado '{}'".format(posicion, dispositivo.nombre))
            continue
        if dispositivo.ip in ips:
            errores.append("registro {}: IP duplicada '{}' ({})".format(
                posicion, dispositivo.ip, dispositivo.nombre))
            continue

        nombres.add(dispositivo.nombre)
        ips.add(dispositivo.ip)
        validos.append(dispositivo)

    return validos, errores
