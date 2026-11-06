"""Cliente REST seguro para la API de inventario.

Decisiones de diseño:
  * Solo HTTPS y verificación TLS siempre activa (verify = CA de confianza).
    Nunca verify=False: eso expone el token a un ataque man-in-the-middle.
  * Autenticación en dos pasos: API key -> token Bearer de corta duración.
    La API key no viaja en cada solicitud; si el token vence (401) se renueva
    automáticamente una sola vez.
  * Session + HTTPAdapter: reutiliza conexiones TLS (más rápido) y aplica
    reintentos con backoff exponencial solo ante errores transitorios
    (429, 502, 503, 504), respetando la cabecera Retry-After.
  * Timeouts explícitos (conexión, lectura): una API colgada no bloquea el script.
  * Cada error se traduce a un diagnóstico con causa probable y solución.
"""
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from . import config
from .modelo import Dispositivo, validar_inventario

log = logging.getLogger("inventario.api")

DIAGNOSTICOS: Dict[int, Tuple[str, str]] = {
    400: ("Solicitud mal formada (JSON inválido o parámetros incorrectos)",
          "Validar el payload con json.dumps y revisar la documentación del endpoint"),
    401: ("Falta autenticación o el token venció",
          "Obtener un token nuevo con la API key y enviarlo en 'Authorization: Bearer'"),
    403: ("Credencial válida pero sin permiso, o API key incorrecta",
          "Verificar la API key en .env y los permisos/rol asignados en el servicio"),
    404: ("El recurso o la ruta no existe",
          "Revisar la URL base, la versión (/api/v1) y el identificador consultado"),
    405: ("Método HTTP no permitido en ese endpoint",
          "Usar el verbo correcto (GET para consultar, POST para crear)"),
    409: ("Conflicto: el recurso ya existe",
          "Consultar antes de crear o usar un nombre/IP distinto"),
    415: ("Tipo de contenido no soportado",
          "Enviar 'Content-Type: application/json' (requests lo hace con json=)"),
    422: ("Datos con formato correcto pero que no cumplen las reglas",
          "Corregir los campos indicados en 'errores' de la respuesta"),
    429: ("Límite de solicitudes excedido (rate limit)",
          "Esperar lo indicado en Retry-After; el cliente reintenta con backoff"),
    500: ("Error interno del servidor",
          "No es un fallo del cliente: revisar logs del servidor y reportar el request-id"),
    502: ("Bad Gateway: un proxy no obtuvo respuesta válida del backend",
          "Reintentar; si persiste revisar el servicio detrás del proxy"),
    503: ("Servicio no disponible (mantenimiento o sobrecarga)",
          "Reintentar con backoff respetando Retry-After"),
    504: ("Gateway Timeout: el backend tardó demasiado",
          "Reintentar más tarde o aumentar el timeout de lectura"),
}


class ErrorAPI(Exception):
    def __init__(self, mensaje: str, status: Optional[int] = None,
                 causa: str = "", solucion: str = "", detalle: Any = None):
        super().__init__(mensaje)
        self.status = status
        self.causa = causa
        self.solucion = solucion
        self.detalle = detalle

    def explicar(self) -> str:
        partes = ["[{}] {}".format(self.status or "RED", self)]
        if self.causa:
            partes.append("  Causa probable : " + self.causa)
        if self.solucion:
            partes.append("  Solución       : " + self.solucion)
        if self.detalle:
            partes.append("  Detalle        : {}".format(self.detalle))
        return "\n".join(partes)


def diagnosticar_respuesta(respuesta: requests.Response) -> ErrorAPI:
    causa, solucion = DIAGNOSTICOS.get(
        respuesta.status_code,
        ("Error HTTP no catalogado", "Revisar la documentación de la API"))
    try:
        detalle = respuesta.json()
    except ValueError:
        detalle = respuesta.text[:200]
    return ErrorAPI("{} {} -> HTTP {}".format(respuesta.request.method, respuesta.url,
                                              respuesta.status_code),
                    respuesta.status_code, causa, solucion, detalle)


def diagnosticar_excepcion(exc: requests.RequestException, url: str) -> ErrorAPI:
    """Traduce errores de red/TLS (sin código HTTP) a un diagnóstico accionable."""
    if isinstance(exc, requests.exceptions.SSLError):
        return ErrorAPI("Fallo TLS con {}".format(url), None,
                        "Certificado no confiable, vencido o con nombre (SAN) distinto al host",
                        "Indicar la CA correcta en API_CA_CERT; nunca usar verify=False",
                        str(exc)[:160])
    if isinstance(exc, requests.exceptions.ConnectTimeout):
        return ErrorAPI("Tiempo de conexión agotado con {}".format(url), None,
                        "Host inalcanzable o firewall descartando paquetes",
                        "Probar conectividad: ping, curl -v, revisar ruta/firewall")
    if isinstance(exc, requests.exceptions.ReadTimeout):
        return ErrorAPI("El servidor no respondió a tiempo ({})".format(url), None,
                        "Servicio lento o sobrecargado",
                        "Aumentar API_TIMEOUT_LECTURA o revisar el rendimiento del servicio")
    if isinstance(exc, requests.exceptions.ConnectionError):
        return ErrorAPI("No se pudo conectar con {}".format(url), None,
                        "Servicio detenido, puerto incorrecto o DNS que no resuelve",
                        "Verificar con 'ss -tlnp | grep <puerto>' y 'curl -v <url>'")
    if isinstance(exc, requests.exceptions.RetryError):
        return ErrorAPI("Se agotaron los reintentos con {}".format(url), None,
                        "Error transitorio persistente (429/5xx)",
                        "Esperar y reintentar; revisar estado del servicio", str(exc)[:160])
    return ErrorAPI("Error de solicitud: {}".format(exc), None)


def crear_sesion(reintentos: int = config.API_REINTENTOS) -> requests.Session:
    parametros = dict(total=reintentos, backoff_factor=0.5,
                      status_forcelist=(429, 502, 503, 504),
                      respect_retry_after_header=True, raise_on_status=False)
    metodos = frozenset({"GET", "HEAD", "OPTIONS"})  # solo idempotentes
    try:
        politica = Retry(allowed_methods=metodos, **parametros)   # urllib3 >= 1.26
    except TypeError:
        politica = Retry(method_whitelist=metodos, **parametros)  # urllib3 < 1.26 (VM DEVASC)
    sesion = requests.Session()
    adaptador = HTTPAdapter(max_retries=politica)
    sesion.mount("https://", adaptador)
    sesion.headers.update({"Accept": "application/json",
                           "User-Agent": "inventario-red/2.0 (DevOps Fundamentos)"})
    return sesion


class ClienteInventarioAPI:
    def __init__(self, base_url: str = config.API_BASE_URL, api_key: str = config.API_KEY,
                 ca_cert: str = config.API_CA_CERT,
                 timeout: Tuple[float, float] = (config.API_TIMEOUT_CONEXION,
                                                 config.API_TIMEOUT_LECTURA),
                 sesion: Optional[requests.Session] = None):
        if not base_url.lower().startswith("https://"):
            raise ValueError("Por seguridad solo se permiten URLs HTTPS: " + base_url)
        if not api_key:
            raise ValueError("Falta API_KEY (defínala en .env o como variable de entorno)")
        self.base_url = base_url.rstrip("/")
        self._api_key = api_key
        self.verify = ca_cert or True
        self.timeout = timeout
        self.sesion = sesion or crear_sesion()
        self._token: Optional[str] = None
        self._token_expira = 0.0

    # ------------------------------------------------------------ autenticación
    def autenticar(self) -> None:
        url = self.base_url + "/auth/token"
        try:
            respuesta = self.sesion.post(url, headers={"X-API-Key": self._api_key},
                                         timeout=self.timeout, verify=self.verify)
        except requests.RequestException as exc:
            raise diagnosticar_excepcion(exc, url)
        if respuesta.status_code != 200:
            raise diagnosticar_respuesta(respuesta)
        datos = respuesta.json()
        self._token = datos["access_token"]
        # margen de 30 s para no usar un token a punto de vencer
        self._token_expira = time.time() + int(datos.get("expires_in", 300)) - 30
        log.info("Token obtenido; expira en %s s", datos.get("expires_in"))

    def _token_vigente(self) -> str:
        if not self._token or time.time() >= self._token_expira:
            self.autenticar()
        return self._token  # type: ignore[return-value]

    # ------------------------------------------------------------ núcleo HTTP
    def _solicitar(self, metodo: str, ruta: str, reintento_auth: bool = True,
                   **kwargs: Any) -> Any:
        url = self.base_url + ruta
        cabeceras = kwargs.pop("headers", {})
        cabeceras["Authorization"] = "Bearer " + self._token_vigente()
        inicio = time.monotonic()
        try:
            respuesta = self.sesion.request(metodo, url, headers=cabeceras,
                                            timeout=self.timeout, verify=self.verify, **kwargs)
        except requests.RequestException as exc:
            error = diagnosticar_excepcion(exc, url)
            log.error("%s %s falló: %s", metodo, url, error)
            raise error
        duracion = (time.monotonic() - inicio) * 1000
        log.info("%s %s -> %s (%.0f ms) request-id=%s", metodo, url, respuesta.status_code,
                 duracion, respuesta.headers.get("X-Request-ID", "-"))

        if respuesta.status_code == 401 and reintento_auth:
            log.warning("Token rechazado (401); se renueva y se reintenta una vez")
            self._token = None
            return self._solicitar(metodo, ruta, reintento_auth=False,
                                   headers={k: v for k, v in cabeceras.items()
                                            if k != "Authorization"}, **kwargs)
        if not respuesta.ok:
            error = diagnosticar_respuesta(respuesta)
            log.error(error.explicar().replace("\n", " | "))
            raise error
        if respuesta.status_code == 204:
            return None
        if "application/json" not in respuesta.headers.get("Content-Type", ""):
            raise ErrorAPI("Respuesta no JSON desde {}".format(url), respuesta.status_code,
                           "El endpoint devolvió HTML/texto (proxy, página de error)",
                           "Verificar la URL base y el Content-Type del servicio")
        return respuesta.json()

    # ------------------------------------------------------------ operaciones
    def salud(self) -> Dict[str, Any]:
        url = self.base_url + "/salud"
        try:
            respuesta = self.sesion.get(url, timeout=self.timeout, verify=self.verify)
        except requests.RequestException as exc:
            raise diagnosticar_excepcion(exc, url)
        if not respuesta.ok:
            raise diagnosticar_respuesta(respuesta)
        return respuesta.json()

    def listar_dispositivos(self, estado: Optional[str] = None) -> List[Dispositivo]:
        params = {"estado": estado} if estado else None
        datos = self._solicitar("GET", "/dispositivos", params=params)
        if not isinstance(datos, dict) or "dispositivos" not in datos:
            raise ErrorAPI("Estructura de respuesta inesperada", 200,
                           "El contrato de la API cambió", "Revisar la versión de la API",
                           str(datos)[:160])
        # Validar la respuesta: no se confía ciegamente en datos externos
        validos, errores = validar_inventario(datos["dispositivos"])
        for error in errores:
            log.warning("Registro inválido recibido de la API: %s", error)
        return validos

    def obtener_dispositivo(self, nombre: str) -> Dispositivo:
        datos = self._solicitar("GET", "/dispositivos/" + requests.utils.quote(nombre))
        return Dispositivo.desde_dict(datos)

    def registrar_dispositivo(self, dispositivo: Dispositivo) -> Dict[str, Any]:
        return self._solicitar("POST", "/dispositivos", json=dispositivo.a_dict())
