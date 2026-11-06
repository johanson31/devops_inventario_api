import unittest

from inventario_red.modelo import Dispositivo, ErrorValidacion, validar_inventario, validar_registro


class TestModelo(unittest.TestCase):
    def test_normaliza_mayusculas_y_tipos(self):
        d = Dispositivo.desde_dict({"nombre": " r01 ", "ip": "192.168.1.1",
                                    "tipo": "router", "estado": "ACTIVO"})
        self.assertEqual((d.nombre, d.tipo, d.estado), ("R01", "Router", "Activo"))

    def test_ip_invalida(self):
        errores = validar_registro({"nombre": "R1", "ip": "192.168.1.300",
                                    "tipo": "Router", "estado": "Activo"})
        self.assertTrue(any("IP no válida" in e for e in errores))

    def test_campo_faltante(self):
        with self.assertRaises(ErrorValidacion):
            Dispositivo.desde_dict({"nombre": "R1", "tipo": "Router", "estado": "Activo"})

    def test_estado_y_tipo_no_permitidos(self):
        errores = validar_registro({"nombre": "X", "ip": "10.0.0.1", "tipo": "Mainframe",
                                    "estado": "Apagado"})
        self.assertEqual(len(errores), 2)

    def test_duplicados_en_inventario(self):
        base = {"tipo": "Router", "estado": "Activo"}
        validos, errores = validar_inventario([
            dict(base, nombre="R1", ip="10.0.0.1"),
            dict(base, nombre="R1", ip="10.0.0.2"),   # nombre repetido
            dict(base, nombre="R2", ip="10.0.0.1"),   # IP repetida
        ])
        self.assertEqual(len(validos), 1)
        self.assertEqual(len(errores), 2)


if __name__ == "__main__":
    unittest.main()
