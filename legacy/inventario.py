
# Inventario de dispositivos de red
# Evaluacion parcial - DevOps: Fundamentos

"""
dispositivo = {
    "nombre": "R01",
    "ip": "192.168.1.1",
    "tipo": "Router",
    "estado": "Activo"
}

# Mostrar los datos del dispositivo
print("INVENTARIO DE RED")
print("-----------------")
print("Nombre:", dispositivo["nombre"])
print("Dirección IP:", dispositivo["ip"])
print("Tipo:", dispositivo["tipo"])
print("Estado:", dispositivo["estado"])
"""

# Lista que almacena los dispositivos de la red
inventario = [
    {
        "nombre": "R01",
        "ip": "192.168.1.1",
        "tipo": "Router",
        "estado": "Activo"
    },
    {
        "nombre": "S01",
        "ip": "192.168.1.2",
        "tipo": "Switch",
        "estado": "Activo"
    },
    {
        "nombre": "SRV01",
        "ip": "192.168.1.10",
        "tipo": "Servidor",
        "estado": "Activo"
    },

    {
        "nombre": "R02",
        "ip": "192.168.1.4",
        "tipo": "Router",
        "estado": "Activo"
    }

]

# Mostrar el inventario completo
print("INVENTARIO DE DISPOSITIVOS DE RED")
print("=" * 40)

# Recorrer cada dispositivo de la lista automatizando
# el recorrido así se agreguen más dispositivos posteriormente
"""
for dispositivo in inventario:
    print("Nombre:", dispositivo["nombre"])
    print("Direccion IP:", dispositivo["ip"])
    print("Tipo:", dispositivo["tipo"])
    print("Estado:", dispositivo["estado"])
    print("-" * 40)
"""

# Agregamos función para la validación de errores
# Función para validar los datos del inventario
def validar_inventario(dispositivos):
    errores = 0

    # Verificar que el inventario no esté vacío
    if len(dispositivos) == 0:
        print("Error: el inventario está vacío.")
        return 1

    for dispositivo in dispositivos:
        # Verificar que existan los campos necesarios
        if (
            "nombre" not in dispositivo
            or "ip" not in dispositivo
            or "tipo" not in dispositivo
            or "estado" not in dispositivo
        ):
            print("Error: un dispositivo tiene campos incompletos.")
            errores += 1
            continue

        # Verificar que el estado sea válido
        if dispositivo["estado"] not in ["Activo", "Inactivo"]:
            print(
                "Error en:",
                dispositivo["nombre"],
                "estado no válido."
            )
            errores += 1

    return errores

# Ahora consultamos cuantos dispositivos se encuentran 
# activos e inactivos mediante una función

def mostrar_resumen(dispositivos):
    # Declaramos contadores
    activos = 0
    inactivos = 0

    # Contar los dispositivos según su estado
    for dispositivo in dispositivos:
        if dispositivo["estado"] == "Activo":
            activos += 1
        elif dispositivo["estado"] == "Inactivo":
            inactivos += 1

    # Mostrar los resultados
    print("RESUMEN DEL INVENTARIO DE RED")
    print("=" * 35)
    print("Total de dispositivos:", len(dispositivos))
    print("Dispositivos activos:", activos)
    print("Dispositivos inactivos:", inactivos)


# Ejecutar la función para mostrar con la validación
# Validar antes de mostrar el resumen
errores = validar_inventario(inventario)

if errores == 0:
    print("Validación correcta: todos los dispositivos tienen datos válidos.")
    mostrar_resumen(inventario)
else:
    print("Se encontraron", errores, "error(es).")
    print("Verifique que los datos del dispositivo esten completos y que su estado sea válido [Activo/Inactivo]")

