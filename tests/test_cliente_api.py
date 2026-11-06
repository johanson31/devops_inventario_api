"""Pruebas de integración: levanta la API HTTPS real en un hilo y la consume."""
import os
import shutil
import subprocess
import tempfile
import threading
import unittest

import requests

from inventario_red import config
from inventario_red.cliente_api import ClienteInventarioAPI, ErrorAPI, crear_sesion
from inventario_red.modelo import Dispositivo

from api_simulada.servidor_https import crear_servidor

CLAVE = "clave-de-pruebas-unitarias"


class TestClienteAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which("openssl"):
            raise unittest.SkipTest("openssl no disponible")
        cls.tmp = tempfile.mkdtemp()
        cls.crt, cls.key = os.path.join(cls.tmp, "t.crt"), os.path.join(cls.tmp, "t.key")
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
                        "-keyout", cls.key, "-out", cls.crt, "-subj", "/CN=localhost",
                        "-addext", "subjectAltName=DNS:localhost,IP:127.0.0.1"],
                       check=True, capture_output=True)
        cls.servidor = crear_servidor(0, cls.crt, cls.key, CLAVE, config.INVENTARIO_PRINCIPAL)
        cls.url = "https://localhost:{}/api/v1".format(cls.servidor.server_address[1])
        threading.Thread(target=cls.servidor.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.servidor.shutdown()
        cls.servidor.server_close()
        shutil.rmtree(cls.tmp)

    def cliente(self, clave=CLAVE):
        return ClienteInventarioAPI(self.url, clave, self.crt, timeout=(3, 5))

    def test_rechaza_http_plano(self):
        with self.assertRaises(ValueError):
            ClienteInventarioAPI("http://localhost:8443/api/v1", CLAVE)

    def test_listar_y_filtrar(self):
        self.assertGreaterEqual(len(self.cliente().listar_dispositivos()), 5)
        self.assertTrue(all(d.estado == "Activo"
                            for d in self.cliente().listar_dispositivos("Activo")))

    def test_api_key_incorrecta_da_403(self):
        with self.assertRaises(ErrorAPI) as ctx:
            self.cliente("otra-clave").listar_dispositivos()
        self.assertEqual(ctx.exception.status, 403)

    def test_token_vencido_se_renueva(self):
        c = self.cliente()
        c.listar_dispositivos()
        c._token = "token-invalido"          # simula expiración del lado del servidor
        self.assertTrue(c.listar_dispositivos())  # 401 -> renueva -> 200

    def test_404_y_registro_201_409(self):
        c = self.cliente()
        with self.assertRaises(ErrorAPI) as ctx:
            c.obtener_dispositivo("NOEXISTE")
        self.assertEqual(ctx.exception.status, 404)
        nuevo = Dispositivo.desde_dict({"nombre": "TST1", "ip": "172.16.0.1",
                                        "tipo": "Switch", "estado": "Activo"})
        self.assertEqual(c.registrar_dispositivo(nuevo)["nombre"], "TST1")
        with self.assertRaises(ErrorAPI) as ctx:
            c.registrar_dispositivo(nuevo)
        self.assertEqual(ctx.exception.status, 409)

    def test_tls_sin_ca_falla(self):
        with self.assertRaises(requests.exceptions.SSLError):
            requests.get(self.url + "/salud", timeout=3)

    def test_reintentos_503(self):
        c = self.cliente()
        token = c._token_vigente()
        r = crear_sesion(1).get(self.url + "/simular/503", verify=self.crt, timeout=5,
                                headers={"Authorization": "Bearer " + token})
        self.assertEqual(r.status_code, 503)


if __name__ == "__main__":
    unittest.main()
