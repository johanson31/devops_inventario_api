"""Paquete inventario_red: automatización del inventario de dispositivos de red.

Módulos:
    modelo       -> entidad Dispositivo y reglas de validación
    formatos     -> lectura/escritura JSON, YAML, CSV y XML
    analisis     -> resúmenes, agrupaciones y detección de diferencias
    cliente_api  -> cliente REST seguro (HTTPS + token) con diagnóstico de errores
    crud         -> menú interactivo (evolución de inventario_v2.py)
    registro     -> configuración de logs con enmascarado de secretos
    config       -> configuración desde variables de entorno / archivo .env
"""

__version__ = "2.0.0"
