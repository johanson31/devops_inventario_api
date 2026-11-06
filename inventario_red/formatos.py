"""Lectura y escritura de inventarios en JSON, YAML, CSV y XML.

Se usa un "despachador" por extensión: agregar un formato nuevo solo requiere
registrar su lector y su escritor, sin tocar el resto del programa.
Todas las funciones devuelven/reciben datos crudos (listas de dict); la
validación es responsabilidad de modelo.py.
"""
import csv
import json
import os
import tempfile
import xml.etree.ElementTree as ET
from typing import Any, Callable, Dict, List

import yaml

from .modelo import Dispositivo

COLUMNAS = ["nombre", "ip", "tipo", "estado", "ubicacion"]
PERMISO_REPORTES = 0o640  # propietario rw, grupo r, otros nada


class ErrorFormato(Exception):
    """Archivo inexistente, ilegible o con sintaxis inválida."""


# ---------------------------------------------------------------- lectura
def _extraer_lista(contenido: Any, origen: str) -> List[Dict[str, Any]]:
    """Acepta tanto una lista directa como {'inventario': {'dispositivos': [...]}}."""
    if isinstance(contenido, dict):
        contenido = contenido.get("inventario", contenido)
        if isinstance(contenido, dict):
            contenido = contenido.get("dispositivos", [])
    if not isinstance(contenido, list):
        raise ErrorFormato("{}: se esperaba una lista de dispositivos".format(origen))
    return contenido


def _leer_json(ruta: str) -> List[Dict[str, Any]]:
    with open(ruta, encoding="utf-8") as archivo:
        try:
            return _extraer_lista(json.load(archivo), ruta)
        except json.JSONDecodeError as exc:
            raise ErrorFormato("{}: JSON inválido en línea {} columna {} ({})".format(
                ruta, exc.lineno, exc.colno, exc.msg))


def _leer_yaml(ruta: str) -> List[Dict[str, Any]]:
    with open(ruta, encoding="utf-8") as archivo:
        try:
            # safe_load: nunca construye objetos Python arbitrarios desde el archivo
            return _extraer_lista(yaml.safe_load(archivo), ruta)
        except yaml.YAMLError as exc:
            raise ErrorFormato("{}: YAML inválido ({})".format(ruta, exc))


def _leer_csv(ruta: str) -> List[Dict[str, Any]]:
    # utf-8-sig elimina el BOM que agrega Excel al guardar CSV
    with open(ruta, encoding="utf-8-sig", newline="") as archivo:
        lector = csv.DictReader(archivo)
        faltantes = {"nombre", "ip", "tipo", "estado"} - set(lector.fieldnames or [])
        if faltantes:
            raise ErrorFormato("{}: faltan columnas {}".format(ruta, sorted(faltantes)))
        return [dict(fila) for fila in lector]


def _leer_xml(ruta: str) -> List[Dict[str, Any]]:
    try:
        raiz = ET.parse(ruta).getroot()
    except ET.ParseError as exc:
        raise ErrorFormato("{}: XML inválido ({})".format(ruta, exc))
    sede = raiz.get("sede")
    registros = []
    for nodo in raiz.iter("dispositivo"):
        registro = {hijo.tag: (hijo.text or "").strip() for hijo in nodo}
        registro.update(nodo.attrib)  # permite <dispositivo estado="Activo">
        if sede and not registro.get("ubicacion"):
            registro["ubicacion"] = sede
        registros.append(registro)
    return registros


LECTORES: Dict[str, Callable[[str], List[Dict[str, Any]]]] = {
    ".json": _leer_json,
    ".yaml": _leer_yaml,
    ".yml": _leer_yaml,
    ".csv": _leer_csv,
    ".xml": _leer_xml,
}


def cargar(ruta: str) -> List[Dict[str, Any]]:
    """Carga un archivo de inventario detectando el formato por su extensión."""
    extension = os.path.splitext(ruta)[1].lower()
    if extension not in LECTORES:
        raise ErrorFormato("{}: formato '{}' no soportado {}".format(
            ruta, extension, sorted(LECTORES)))
    if not os.path.isfile(ruta):
        raise ErrorFormato("{}: el archivo no existe".format(ruta))
    if not os.access(ruta, os.R_OK):
        raise ErrorFormato("{}: sin permiso de lectura (revise con ls -l)".format(ruta))
    return LECTORES[extension](ruta)


def archivos_soportados(directorio: str) -> List[str]:
    """Lista (ordenada) los archivos de inventario de un directorio, sin recursión."""
    return sorted(
        os.path.join(directorio, nombre)
        for nombre in os.listdir(directorio)
        if os.path.splitext(nombre)[1].lower() in LECTORES
    )


# ---------------------------------------------------------------- escritura
def _escribir_json(datos: List[Dict[str, str]], archivo) -> None:
    json.dump({"inventario": {"dispositivos": datos}}, archivo, indent=2, ensure_ascii=False)
    archivo.write("\n")


def _escribir_yaml(datos: List[Dict[str, str]], archivo) -> None:
    yaml.safe_dump({"inventario": {"dispositivos": datos}}, archivo,
                   allow_unicode=True, sort_keys=False)


def _escribir_csv(datos: List[Dict[str, str]], archivo) -> None:
    escritor = csv.DictWriter(archivo, fieldnames=COLUMNAS)
    escritor.writeheader()
    escritor.writerows(datos)


def _escribir_xml(datos: List[Dict[str, str]], archivo) -> None:
    raiz = ET.Element("inventario")
    for registro in datos:
        nodo = ET.SubElement(raiz, "dispositivo")
        for campo in COLUMNAS:
            ET.SubElement(nodo, campo).text = registro.get(campo, "")
    _indentar(raiz)
    archivo.write('<?xml version="1.0" encoding="UTF-8"?>\n')
    archivo.write(ET.tostring(raiz, encoding="unicode"))
    archivo.write("\n")


def _indentar(elemento: ET.Element, nivel: int = 0) -> None:
    """Sangría legible (ET.indent solo existe desde Python 3.9; la VM usa 3.8)."""
    sangria = "\n" + "  " * nivel
    if len(elemento):
        if not (elemento.text or "").strip():
            elemento.text = sangria + "  "
        for hijo in elemento:
            _indentar(hijo, nivel + 1)
        if not (hijo.tail or "").strip():
            hijo.tail = sangria
    if nivel and not (elemento.tail or "").strip():
        elemento.tail = sangria


ESCRITORES = {
    ".json": _escribir_json,
    ".yaml": _escribir_yaml,
    ".yml": _escribir_yaml,
    ".csv": _escribir_csv,
    ".xml": _escribir_xml,
}


def exportar(dispositivos: List[Dispositivo], ruta: str) -> str:
    """Escribe el inventario en el formato indicado por la extensión de `ruta`.

    La escritura es atómica: se genera un temporal y luego se reemplaza el
    destino con os.replace, así un fallo a mitad no deja un archivo corrupto.
    """
    extension = os.path.splitext(ruta)[1].lower()
    if extension not in ESCRITORES:
        raise ErrorFormato("{}: formato de salida no soportado".format(ruta))

    destino = os.path.dirname(os.path.abspath(ruta))
    os.makedirs(destino, exist_ok=True)
    datos = [d.a_dict() for d in dispositivos]

    descriptor, temporal = tempfile.mkstemp(dir=destino, suffix=".tmp")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as archivo:
            ESCRITORES[extension](datos, archivo)
        os.chmod(temporal, PERMISO_REPORTES)
        os.replace(temporal, ruta)
    except Exception:
        if os.path.exists(temporal):
            os.remove(temporal)
        raise
    return ruta
