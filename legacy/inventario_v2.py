
# ==========================================
# SISTEMA DE INVENTARIO DE DISPOSITIVOS DE RED
# Proyecto DevOps - Fundamentos
# ==========================================

# Inventario inicial de dispositivos
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


# ==========================================
# FUNCIONES DE VALIDACION
# ==========================================

def validar_inventario(dispositivos):

    errores = 0

    if len(dispositivos) == 0:
        print("Error: el inventario esta vacio.")
        return 1

    for dispositivo in dispositivos:

        if (
            "nombre" not in dispositivo
            or "ip" not in dispositivo
            or "tipo" not in dispositivo
            or "estado" not in dispositivo
        ):
            print("Error: existen campos incompletos.")
            errores += 1
            continue

        if dispositivo["estado"] not in ["Activo", "Inactivo"]:
            print("Error: estado no valido.")
            errores += 1

    return errores


def buscar_dispositivo(dispositivos, nombre):

    for dispositivo in dispositivos:

        if dispositivo["nombre"].lower() == nombre.lower():
            return dispositivo

    return None


# ==========================================
# READ: LISTAR DISPOSITIVOS
# ==========================================

def listar_dispositivos(dispositivos):

    print("\n===== INVENTARIO DE RED =====")

    if len(dispositivos) == 0:
        print("No existen dispositivos registrados.")
        return

    for dispositivo in dispositivos:

        print("-----------------------------")
        print("Nombre:", dispositivo["nombre"])
        print("IP:", dispositivo["ip"])
        print("Tipo:", dispositivo["tipo"])
        print("Estado:", dispositivo["estado"])


# ==========================================
# CREATE: REGISTRAR DISPOSITIVO
# ==========================================

def agregar_dispositivo(dispositivos):

    print("\n===== REGISTRAR DISPOSITIVO =====")

    nombre = input("Ingrese el nombre: ").strip()

    if nombre == "":
        print("Error: el nombre no puede estar vacio.")
        return

    if buscar_dispositivo(dispositivos, nombre) is not None:
        print("Error: el nombre ya esta registrado.")
        return

    ip = input("Ingrese la direccion IP: ").strip()

    if ip == "":
        print("Error: la IP no puede estar vacia.")
        return

    tipo = input("Ingrese el tipo (Router/Switch/Servidor): ").strip()

    if tipo == "":
        print("Error: el tipo no puede estar vacio.")
        return

    estado = input("Ingrese el estado (Activo/Inactivo): ").strip().capitalize()

    if estado not in ["Activo", "Inactivo"]:
        print("Error: debe ingresar Activo o Inactivo.")
        return

    nuevo_dispositivo = {
        "nombre": nombre,
        "ip": ip,
        "tipo": tipo,
        "estado": estado
    }

    dispositivos.append(nuevo_dispositivo)

    print("Dispositivo registrado correctamente.")


# ==========================================
# UPDATE: ACTUALIZAR DISPOSITIVO
# ==========================================

def actualizar_dispositivo(dispositivos):

    print("\n===== ACTUALIZAR DISPOSITIVO =====")

    nombre = input("Ingrese el nombre del dispositivo: ").strip()

    dispositivo = buscar_dispositivo(dispositivos, nombre)

    if dispositivo is None:
        print("Error: dispositivo no encontrado.")
        return

    print("\nDeje el campo vacio si desea conservar el dato actual.")

    print("Nombre actual:", dispositivo["nombre"])
    nuevo_nombre = input("Nuevo nombre: ").strip()

    if nuevo_nombre != "":
        existente = buscar_dispositivo(dispositivos, nuevo_nombre)

        if existente is not None and existente != dispositivo:
            print("Error: ese nombre ya esta registrado.")
            return

    print("IP actual:", dispositivo["ip"])
    nueva_ip = input("Nueva IP: ").strip()

    print("Tipo actual:", dispositivo["tipo"])
    nuevo_tipo = input("Nuevo tipo: ").strip()

    print("Estado actual:", dispositivo["estado"])
    nuevo_estado = input("Nuevo estado (Activo/Inactivo): ").strip()

    if nuevo_estado != "":
        nuevo_estado = nuevo_estado.capitalize()

        if nuevo_estado not in ["Activo", "Inactivo"]:
            print("Error: estado no valido.")
            return

    # Aplicar los cambios
    if nuevo_nombre != "":
        dispositivo["nombre"] = nuevo_nombre

    if nueva_ip != "":
        dispositivo["ip"] = nueva_ip

    if nuevo_tipo != "":
        dispositivo["tipo"] = nuevo_tipo

    if nuevo_estado != "":
        dispositivo["estado"] = nuevo_estado

    print("Dispositivo actualizado correctamente.")


# ==========================================
# DELETE: ELIMINAR DISPOSITIVO
# ==========================================

def eliminar_dispositivo(dispositivos):

    print("\n===== ELIMINAR DISPOSITIVO =====")

    nombre = input("Ingrese el nombre del dispositivo: ").strip()

    dispositivo = buscar_dispositivo(dispositivos, nombre)

    if dispositivo is None:
        print("Error: dispositivo no encontrado.")
        return

    print("Dispositivo:", dispositivo["nombre"])
    print("IP:", dispositivo["ip"])

    confirmacion = input("¿Confirma la eliminacion? (S/N): ").strip().upper()

    if confirmacion == "S":

        dispositivos.remove(dispositivo)

        print("Dispositivo eliminado correctamente.")

    else:
        print("Operacion cancelada.")


# ==========================================
# RESUMEN DEL INVENTARIO
# ==========================================

def mostrar_resumen(dispositivos):

    activos = 0
    inactivos = 0

    for dispositivo in dispositivos:

        if dispositivo["estado"] == "Activo":
            activos += 1

        elif dispositivo["estado"] == "Inactivo":
            inactivos += 1

    print("\n===== RESUMEN DEL INVENTARIO =====")
    print("Total de dispositivos:", len(dispositivos))
    print("Dispositivos activos:", activos)
    print("Dispositivos inactivos:", inactivos)


# ==========================================
# MENU PRINCIPAL
# ==========================================

def mostrar_menu():

    print("\n================================")
    print(" SISTEMA DE INVENTARIO DE RED")
    print("================================")
    print("1. Registrar dispositivo")
    print("2. Listar dispositivos")
    print("3. Actualizar dispositivo")
    print("4. Eliminar dispositivo")
    print("5. Mostrar resumen")
    print("6. Salir")
    print("================================")


def main():

    while True:

        mostrar_menu()

        opcion = input("Seleccione una opcion: ").strip()
        print("DEBUG: Opcion recibida:", repr(opcion))

        if opcion == "1":
            agregar_dispositivo(inventario)

        elif opcion == "2":
            listar_dispositivos(inventario)

        elif opcion == "3":
            actualizar_dispositivo(inventario)

        elif opcion == "4":
            eliminar_dispositivo(inventario)

        elif opcion == "5":

            errores = validar_inventario(inventario)

            if errores == 0:
                mostrar_resumen(inventario)
            else:
                print("No se puede generar el resumen.")

        elif opcion == "6":
            print("Saliendo del sistema...")
            break

        else:
            print("Opcion no valida. Intente nuevamente.")


# ==========================================
# EJECUCION DEL PROGRAMA
# ==========================================

if __name__ == "__main__":
    main()
