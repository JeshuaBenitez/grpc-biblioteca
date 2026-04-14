import queue
import threading

import grpc
import library_pb2
import library_pb2_grpc


ESPECIALIDADES = ("medicina_general", "pediatria", "odontologia")


def pedir_especialidad() -> str:
    print("Especialidades disponibles:")
    print("1. medicina_general")
    print("2. pediatria")
    print("3. odontologia")
    opcion = input("Selecciona especialidad: ").strip()
    if opcion == "1":
        return "medicina_general"
    if opcion == "2":
        return "pediatria"
    if opcion == "3":
        return "odontologia"
    return opcion.lower().replace(" ", "_")


def main():
    direccion = input("Direccion del servidor (ej. 192.168.1.10:50052): ").strip()
    escritorio_id = input("ID del escritorio (ej. MG-1): ").strip() or "escritorio"
    especialidad = pedir_especialidad()

    if especialidad not in ESPECIALIDADES:
        print("Especialidad invalida")
        return

    canal = grpc.insecure_channel(direccion)
    stub = library_pb2_grpc.ConsultorioServiceStub(canal)

    eventos = queue.Queue()
    detener = threading.Event()

    def generador_eventos():
        # Primer evento para registrar el escritorio en el servidor.
        yield library_pb2.EventoEscritorio(
            escritorio_id=escritorio_id,
            especialidad=especialidad,
            accion="ping",
        )
        while not detener.is_set():
            evento = eventos.get()
            if evento is None:
                break
            yield evento

    def escuchar_respuestas(respuestas):
        try:
            for respuesta in respuestas:
                print(f"\n[Servidor] {respuesta.tipo}: {respuesta.mensaje}")
                if respuesta.turno.codigo:
                    print(
                        f"Turno llamado: {respuesta.turno.codigo} | "
                        f"Paciente: {respuesta.turno.paciente} | "
                        f"Pendientes: {respuesta.pendientes}"
                    )
        except grpc.RpcError as e:
            print(f"Conexion finalizada: {e.details()}")

    respuestas = stub.AtencionTiempoReal(generador_eventos())
    hilo_respuestas = threading.Thread(target=escuchar_respuestas, args=(respuestas,), daemon=True)
    hilo_respuestas.start()

    while True:
        print("\n--- Cliente ESCRITORIO ---")
        print("1. Solicitar siguiente turno")
        print("2. Salir")
        opcion = input("Opcion: ").strip()

        if opcion == "1":
            eventos.put(
                library_pb2.EventoEscritorio(
                    escritorio_id=escritorio_id,
                    especialidad=especialidad,
                    accion="solicitar_siguiente",
                )
            )
        elif opcion == "2":
            break
        else:
            print("Opcion invalida")

    detener.set()
    eventos.put(None)
    print("Cliente escritorio finalizado")


if __name__ == "__main__":
    main()
