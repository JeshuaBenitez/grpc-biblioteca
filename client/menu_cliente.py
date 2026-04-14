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


def generar_turno(stub):
    try:
        paciente = input("Nombre del paciente: ").strip()
        especialidad = pedir_especialidad()
        respuesta = stub.GenerarTurno(
            library_pb2.SolicitudTurno(paciente=paciente, especialidad=especialidad)
        )
        print(
            f"Turno generado: {respuesta.codigo} | {respuesta.especialidad} | "
            f"posicion en fila: {respuesta.posicion}"
        )
    except grpc.RpcError as e:
        print("Error:", e.details())


def registrar_turnos_lote(stub):
    def generar_solicitudes():
        print("Carga por lote. Deja paciente vacío para terminar.")
        while True:
            paciente = input("Paciente: ").strip()
            if not paciente:
                break
            especialidad = pedir_especialidad()
            if especialidad not in ESPECIALIDADES:
                print("Especialidad inválida, se omite.")
                continue
            yield library_pb2.SolicitudTurno(paciente=paciente, especialidad=especialidad)

    try:
        respuesta = stub.RegistrarTurnosLote(generar_solicitudes())
        print(f"Total registrados: {respuesta.total_registrados}")
        for ticket in respuesta.tickets:
            print(f"- {ticket.codigo} | {ticket.paciente} | {ticket.especialidad}")
    except grpc.RpcError as e:
        print("Error:", e.details())


def main():
    direccion = input("Dirección del servidor (ej. 192.168.1.10:50052): ").strip()
    canal = grpc.insecure_channel(direccion)
    stub = library_pb2_grpc.ConsultorioServiceStub(canal)

    while True:
        print("\n--- Cliente VENTANILLA ---")
        print("1. Generar turno")
        print("2. Registrar turnos por lote")
        print("3. Salir")

        opcion = input("Selecciona una opción: ").strip()

        if opcion == "1":
            generar_turno(stub)
        elif opcion == "2":
            registrar_turnos_lote(stub)
        elif opcion == "3":
            print("Hasta luego.")
            break
        else:
            print("Opción no válida.")


if __name__ == "__main__":
    main()