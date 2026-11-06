import logging
import unittest

from inventario_red.registro import FiltroSecretos


def filtrar(mensaje):
    registro = logging.LogRecord("t", logging.INFO, __file__, 1, mensaje, (), None)
    FiltroSecretos().filter(registro)
    return registro.getMessage()


class TestFiltroSecretos(unittest.TestCase):
    def test_enmascara_bearer_y_api_key(self):
        self.assertEqual(filtrar("Authorization: Bearer abcDEF123456xyz"), "Authorization: Bearer ***")
        self.assertEqual(filtrar("API_KEY=9f8e7d6c5b4a3210"), "API_KEY=***")
        self.assertIn("'access_token': '***'", filtrar("{'access_token': 'Zx9_long-secret-value'}"))

    def test_no_altera_mensajes_normales(self):
        texto = "diagnostico Sin token: [401] GET https://localhost:8443/api/v1/dispositivos"
        self.assertEqual(filtrar(texto), texto)


if __name__ == "__main__":
    unittest.main()
