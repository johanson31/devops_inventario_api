"""CRUD interactivo del inventario (evolución de legacy/inventario_v2.py).

Mejoras respecto a v2:
  * Persistencia: los cambios se guardan en datos/dispositivos.json
    (antes se perdían al cerrar el programa).
  * Reglas de validación únicas (modelo.py): IP real, tipo permitido,
    nombre e IP sin duplicar.
  * Manejo de Ctrl+C / Ctrl+D sin trazas de error.
  * Se eliminó el print de DEBUG que quedó en la versión anterior.
"""
import logging
from typing import Callable, Dict, Optional, Tuple

from . import analisis, config, formatos
from .modelo import ESTADOS_VALIDOS, TIPOS_VALIDOS, Dispositivo, ErrorValidacion, validar_inventario

log = logging.getLogger("inventario.crud")


class Inventario:
    def __init__(self, ruta: str = config.INVENTARIO_PRINCIPAL):
        self.ruta = ruta
        self.dispositivos, errores = validar_inventario(formatos.cargar(ruta))
        for error in errores:
            print("Aviso, registro omitido:", error)

    def buscar(self, nombre: str) -> Optional[Dispositivo]:
        nombre = nombre.strip().upper()
        return next((d for d in self.dispositivos if d.nombre == nombre), None)

    def _ip_en_uso(self, ip: str, excepto: Optional[Dispositivo] = None) -> bool:
        return any(d.ip == ip and d is not excepto for d in self.dispositivos)

    def agregar(self, datos: Dict[str, str]) -> Dispositivo:
        nuevo = Dispositivo.desde_dict(datos)
        if self.buscar(nuevo.nombre):
            raise ErrorValidacion(["el nombre {} ya está registrado".format(nuevo.nombre)])
        if self._ip_en_uso(nuevo.ip):
            raise ErrorValidacion(["la IP {} ya está asignada".format(nuevo.ip)])
        self.dispositivos.append(nuevo)
        self.guardar()
        log.info("Alta de %s (%s)", nuevo.nombre, nuevo.ip)
        return nuevo

    def actualizar(self, nombre: str, cambios: Dict[str, str]) -> Dispositivo:
        actual = self.buscar(nombre)
        if actual is None:
            raise ErrorValidacion(["dispositivo {} no encontrado".format(nombre)])
        propuesta = actual.a_dict()
        propuesta.update({k: v for k, v in cambios.items() if v.strip()})
        nuevo = Dispositivo.desde_dict(propuesta)
        otro = self.buscar(nuevo.nombre)
        if otro is not None and otro is not actual:
            raise ErrorValidacion(["el nombre {} ya está registrado".format(nuevo.nombre)])
        if self._ip_en_uso(nuevo.ip, excepto=actual):
            raise ErrorValidacion(["la IP {} ya está asignada".format(nuevo.ip)])
        self.dispositivos[self.dispositivos.index(actual)] = nuevo
        self.guardar()
        log.info("Actualización de %s -> %s", nombre, nuevo.a_dict())
        return nuevo

    def eliminar(self, nombre: str) -> Dispositivo:
        actual = self.buscar(nombre)
        if actual is None:
            raise ErrorValidacion(["dispositivo {} no encontrado".format(nombre)])
        self.dispositivos.remove(actual)
        self.guardar()
        log.info("Baja de %s", actual.nombre)
        return actual

    def guardar(self) -> None:
        formatos.exportar(self.dispositivos, self.ruta)


# ------------------------------------------------------------------ interfaz
def _pedir(texto: str) -> str:
    return input(texto).strip()


def _opcion_registrar(inv: Inventario) -> None:
    datos = {
        "nombre": _pedir("Nombre: "),
        "ip": _pedir("Dirección IP: "),
        "tipo": _pedir("Tipo {}: ".format("/".join(TIPOS_VALIDOS))),
        "estado": _pedir("Estado {}: ".format("/".join(ESTADOS_VALIDOS))),
        "ubicacion": _pedir("Ubicación: "),
    }
    print("Registrado:", inv.agregar(datos).nombre)


def _opcion_listar(inv: Inventario) -> None:
    print(analisis.formatear_tabla(inv.dispositivos) if inv.dispositivos
          else "No existen dispositivos registrados.")


def _opcion_actualizar(inv: Inventario) -> None:
    actual = inv.buscar(_pedir("Nombre del dispositivo: "))
    if actual is None:
        print("Dispositivo no encontrado.")
        return
    print("Deje vacío para conservar el valor actual.")
    cambios = {campo: _pedir("{} [{}]: ".format(campo.capitalize(), valor))
               for campo, valor in actual.a_dict().items()}
    print("Actualizado:", inv.actualizar(actual.nombre, cambios).a_dict())


def _opcion_eliminar(inv: Inventario) -> None:
    actual = inv.buscar(_pedir("Nombre del dispositivo: "))
    if actual is None:
        print("Dispositivo no encontrado.")
        return
    if _pedir("¿Eliminar {} ({})? (S/N): ".format(actual.nombre, actual.ip)).upper() == "S":
        inv.eliminar(actual.nombre)
        print("Eliminado.")
    else:
        print("Operación cancelada.")


def _opcion_resumen(inv: Inventario) -> None:
    print(analisis.formatear_resumen(analisis.resumir(inv.dispositivos)))


OPCIONES: Dict[str, Tuple[str, Callable[[Inventario], None]]] = {
    "1": ("Registrar dispositivo", _opcion_registrar),
    "2": ("Listar dispositivos", _opcion_listar),
    "3": ("Actualizar dispositivo", _opcion_actualizar),
    "4": ("Eliminar dispositivo", _opcion_eliminar),
    "5": ("Mostrar resumen", _opcion_resumen),
}


def menu(ruta: str = config.INVENTARIO_PRINCIPAL) -> None:
    inv = Inventario(ruta)
    while True:
        print("\n" + "=" * 34 + "\n SISTEMA DE INVENTARIO DE RED\n" + "=" * 34)
        for clave, (texto, _) in OPCIONES.items():
            print("{}. {}".format(clave, texto))
        print("6. Salir")
        try:
            opcion = _pedir("Seleccione una opción: ")
        except (EOFError, KeyboardInterrupt):
            print("\nSaliendo del sistema...")
            return
        if opcion == "6":
            print("Saliendo del sistema...")
            return
        if opcion not in OPCIONES:
            print("Opción no válida. Intente nuevamente.")
            continue
        try:
            OPCIONES[opcion][1](inv)
        except ErrorValidacion as exc:
            print("Error:", exc)
        except (EOFError, KeyboardInterrupt):
            print("\nOperación cancelada.")
