import grpc
import library_pb2
import library_pb2_grpc


def consultar_libro(stub):
    try:
        id_libro = int(input("ID del libro a consultar: "))
        respuesta = stub.ConsultarLibro(library_pb2.LibroID(id=id_libro))
        print(f"Título: {respuesta.titulo}")
        print(f"Autor: {respuesta.autor}")
    except ValueError:
        print("Debes ingresar un número válido.")
    except grpc.RpcError as e:
        print("Error:", e.details())


def listar_libros(stub):
    try:
        print("\nListado de libros:")
        for libro in stub.ListarLibros(library_pb2.Vacio()):
            print(f"{libro.id} - {libro.titulo} ({libro.autor})")
    except grpc.RpcError as e:
        print("Error:", e.details())


def registrar_libros(stub):
    def generar_libros():
        while True:
            id_texto = input("ID del libro (Enter para terminar): ").strip()
            if not id_texto:
                break

            try:
                id_libro = int(id_texto)
            except ValueError:
                print("El ID debe ser numérico.")
                continue

            titulo = input("Título: ").strip()
            autor = input("Autor: ").strip()

            if not titulo or not autor:
                print("Título y autor son obligatorios.")
                continue

            yield library_pb2.Libro(
                id=id_libro,
                titulo=titulo,
                autor=autor,
            )

    try:
        respuesta = stub.RegistrarLibros(generar_libros())
        print(f"Total registrados: {respuesta.total_registrados}")
    except grpc.RpcError as e:
        print("Error:", e.details())


def transacciones_tiempo_real(stub):
    def enviar_transacciones():
        while True:
            tipo = input("Tipo (prestamo/devolucion, Enter para terminar): ").strip()
            if not tipo:
                break

            if tipo.lower() not in ("prestamo", "devolucion"):
                print("Tipo no válido.")
                continue

            try:
                id_libro = int(input("ID del libro: ").strip())
            except ValueError:
                print("El ID debe ser numérico.")
                continue

            usuario = input("Usuario: ").strip()
            if not usuario:
                print("El usuario no puede ir vacío.")
                continue

            yield library_pb2.Transaccion(
                tipo=tipo,
                id_libro=id_libro,
                usuario=usuario,
            )

    try:
        respuestas = stub.TransaccionesTiempoReal(enviar_transacciones())
        for respuesta in respuestas:
            print("Confirmación:", respuesta.mensaje)
    except grpc.RpcError as e:
        print("Error:", e.details())


def main():
    direccion = input("Dirección del servidor (ej. localhost:50052): ").strip()
    canal = grpc.insecure_channel(direccion)
    stub = library_pb2_grpc.BibliotecaServiceStub(canal)

    while True:
        print("\n--- Menú Biblioteca ---")
        print("1. Consultar libro")
        print("2. Listar libros")
        print("3. Registrar libros")
        print("4. Transacciones en tiempo real")
        print("5. Salir")

        opcion = input("Selecciona una opción: ").strip()

        if opcion == "1":
            consultar_libro(stub)
        elif opcion == "2":
            listar_libros(stub)
        elif opcion == "3":
            registrar_libros(stub)
        elif opcion == "4":
            transacciones_tiempo_real(stub)
        elif opcion == "5":
            print("Hasta luego.")
            break
        else:
            print("Opción no válida.")


if __name__ == "__main__":
    main()