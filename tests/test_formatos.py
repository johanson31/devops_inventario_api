import os
import shutil
import tempfile
import unittest

from inventario_red import analisis, config, formatos
from inventario_red.modelo import validar_inventario


class TestFormatos(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.base, _ = validar_inventario(formatos.cargar(config.INVENTARIO_PRINCIPAL))

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_ida_y_vuelta_todos_los_formatos(self):
        for extension in (".json", ".yaml", ".csv", ".xml"):
            with self.subTest(formato=extension):
                ruta = formatos.exportar(self.base, os.path.join(self.tmp, "inv" + extension))
                leidos, errores = validar_inventario(formatos.cargar(ruta))
                self.assertEqual(errores, [])
                self.assertEqual(leidos, self.base)

    def test_exporta_con_permiso_640(self):
        ruta = formatos.exportar(self.base, os.path.join(self.tmp, "inv.json"))
        self.assertEqual(os.stat(ruta).st_mode & 0o777, 0o640)

    def test_consolida_directorio_de_sedes(self):
        registros = []
        for ruta in formatos.archivos_soportados(config.DIR_DATOS):
            registros.extend(formatos.cargar(ruta))
        validos, errores = validar_inventario(registros)
        self.assertEqual(errores, [])
        ubicaciones = analisis.resumir(validos)["por_ubicacion"]
        self.assertEqual(set(ubicaciones), {"Lima", "Arequipa", "Trujillo", "Cusco"})

    def test_archivo_con_errores(self):
        ruta = os.path.join(config.DIR_DATOS, "pruebas", "dispositivos_con_errores.csv")
        validos, errores = validar_inventario(formatos.cargar(ruta))
        self.assertEqual(len(validos), 2)
        self.assertEqual(len(errores), 5)

    def test_json_mal_formado(self):
        ruta = os.path.join(config.DIR_DATOS, "pruebas", "json_roto.json")
        with self.assertRaisesRegex(formatos.ErrorFormato, "línea 2"):
            formatos.cargar(ruta)

    def test_formato_no_soportado(self):
        with self.assertRaises(formatos.ErrorFormato):
            formatos.cargar("inventario.txt")


if __name__ == "__main__":
    unittest.main()
