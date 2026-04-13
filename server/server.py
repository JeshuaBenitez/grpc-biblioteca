from concurrent import futures
import json
import os
import threading
import time

import grpc
import library_pb2
import library_pb2_grpc


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LIBROS_PATH = os.path.normpath(os.path.join(BASE_DIR, "../data/libros.json"))

lock = threading.Lock()


def cargar_libros() -> dict[int, dict]:
    """Carga el JSON y lo convierte a un diccionario indexado por id."""
    if not os.path.exists(LIBROS_PATH):
        return {}

    with lock:
        with open(LIBROS_PATH, "r", encoding="utf-8") as f:
            libros_lista = json.load(f)

    return {libro["id"]: libro for libro in libros_lista}


def guardar_libros(libros_dict: dict[int, dict]) -> None:
    """Guarda el diccionario en el JSON."""
    with lock:
        with open(LIBROS_PATH, "w", encoding="utf-8") as f:
            json.dump(list(libros_dict.values()), f, indent=2, ensure_ascii=False)


def log_operacion(mensaje: str) -> None:
    print(f"[LOG] {time.strftime('%Y-%m-%d %H:%M:%S')} - {mensaje}")


class BibliotecaServiceServicer(library_pb2_grpc.BibliotecaServiceServicer):
    def ConsultarLibro(self, request, context):
        """Unary RPC: recibe un ID y devuelve un libro."""
        libros = cargar_libros()
        libro = libros.get(request.id)

        if libro is None:
            log_operacion(f"Consulta fallida para libro ID {request.id}")
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details("Libro no encontrado")
            return library_pb2.Libro()

        log_operacion(f"Consulta de libro ID {request.id}")
        return library_pb2.Libro(
            id=libro["id"],
            titulo=libro["titulo"],
            autor=libro["autor"],
        )

    def ListarLibros(self, request, context):
        """Server Streaming RPC: envía todos los libros uno por uno."""
        libros = cargar_libros()

        for libro in libros.values():
            log_operacion(f"Enviando libro ID {libro['id']}")
            yield library_pb2.Libro(
                id=libro["id"],
                titulo=libro["titulo"],
                autor=libro["autor"],
            )

    def RegistrarLibros(self, request_iterator, context):
        """Client Streaming RPC: recibe varios libros y responde con un resumen."""
        libros = cargar_libros()
        total = 0

        for libro in request_iterator:
            libros[libro.id] = {
                "id": libro.id,
                "titulo": libro.titulo,
                "autor": libro.autor,
            }
            total += 1
            log_operacion(f"Libro registrado ID {libro.id} - {libro.titulo}")

        guardar_libros(libros)

        return library_pb2.ResumenRegistro(total_registrados=total)

    def TransaccionesTiempoReal(self, request_iterator, context):
        """Bidirectional Streaming RPC: recibe transacciones y responde confirmaciones."""
        for transaccion in request_iterator:
            tipo = transaccion.tipo.strip().lower()
            id_libro = transaccion.id_libro
            usuario = transaccion.usuario.strip()

            if tipo == "prestamo":
                mensaje = f"{usuario} ha tomado prestado el libro {id_libro}"
            elif tipo == "devolucion":
                mensaje = f"{usuario} ha devuelto el libro {id_libro}"
            else:
                mensaje = f"Transacción desconocida para el libro {id_libro}"

            log_operacion(mensaje)
            yield library_pb2.Confirmacion(mensaje=mensaje)


def servir():
    servidor = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    library_pb2_grpc.add_BibliotecaServiceServicer_to_server(
        BibliotecaServiceServicer(),
        servidor,
    )

    servidor.add_insecure_port("[::]:50052")
    servidor.start()
    print("Servidor Biblioteca gRPC escuchando en puerto 50052...")
    servidor.wait_for_termination()


if __name__ == "__main__":
    servir()