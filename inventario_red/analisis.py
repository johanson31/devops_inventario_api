"""Análisis del inventario: resúmenes, agrupaciones y detección de desvíos."""
import ipaddress
from collections import Counter
from typing import Dict, List

from .modelo import Dispositivo


def subred(ip: str, prefijo: int = 24) -> str:
    """Red a la que pertenece una IP (por defecto /24)."""
    return str(ipaddress.ip_network("{}/{}".format(ip, prefijo), strict=False))


def resumir(dispositivos: List[Dispositivo]) -> Dict[str, object]:
    total = len(dispositivos)
    activos = sum(1 for d in dispositivos if d.activo)
    return {
        "total": total,
        "activos": activos,
        "inactivos": total - activos,
        "disponibilidad": round(activos * 100.0 / total, 1) if total else 0.0,
        "por_tipo": dict(Counter(d.tipo for d in dispositivos).most_common()),
        "por_ubicacion": dict(Counter(d.ubicacion for d in dispositivos).most_common()),
        "por_subred": dict(sorted(Counter(subred(d.ip) for d in dispositivos).items())),
        "inactivos_detalle": [d.nombre for d in dispositivos if not d.activo],
    }


def formatear_resumen(resumen: Dict[str, object]) -> str:
    lineas = [
        "=" * 46,
        " RESUMEN DEL INVENTARIO DE RED",
        "=" * 46,
        " Total de dispositivos : {}".format(resumen["total"]),
        " Activos               : {}".format(resumen["activos"]),
        " Inactivos             : {}".format(resumen["inactivos"]),
        " Disponibilidad        : {}%".format(resumen["disponibilidad"]),
    ]
    for titulo, clave in (("Por tipo", "por_tipo"), ("Por ubicación", "por_ubicacion"),
                          ("Por subred", "por_subred")):
        lineas.append("-" * 46)
        lineas.append(" " + titulo)
        for nombre, cantidad in resumen[clave].items():
            lineas.append("   {:<22} {:>3}".format(nombre, cantidad))
    if resumen["inactivos_detalle"]:
        lineas.append("-" * 46)
        lineas.append(" Requieren atención: " + ", ".join(resumen["inactivos_detalle"]))
    lineas.append("=" * 46)
    return "\n".join(lineas)


def formatear_tabla(dispositivos: List[Dispositivo]) -> str:
    cabecera = "{:<8} {:<15} {:<12} {:<9} {}".format("NOMBRE", "IP", "TIPO", "ESTADO", "UBICACION")
    filas = [cabecera, "-" * len(cabecera)]
    for d in sorted(dispositivos, key=lambda x: ipaddress.ip_address(x.ip)):
        filas.append("{:<8} {:<15} {:<12} {:<9} {}".format(d.nombre, d.ip, d.tipo, d.estado, d.ubicacion))
    return "\n".join(filas)


def comparar(local: List[Dispositivo], remoto: List[Dispositivo]) -> Dict[str, List[str]]:
    """Detecta el desvío (drift) entre el inventario local y el de la API."""
    idx_local = {d.nombre: d for d in local}
    idx_remoto = {d.nombre: d for d in remoto}
    cambios = []
    for nombre in sorted(set(idx_local) & set(idx_remoto)):
        a, b = idx_local[nombre], idx_remoto[nombre]
        for campo in ("ip", "tipo", "estado"):
            if getattr(a, campo) != getattr(b, campo):
                cambios.append("{}: {} local={} api={}".format(
                    nombre, campo, getattr(a, campo), getattr(b, campo)))
    return {
        "solo_local": sorted(set(idx_local) - set(idx_remoto)),
        "solo_api": sorted(set(idx_remoto) - set(idx_local)),
        "diferencias": cambios,
    }
