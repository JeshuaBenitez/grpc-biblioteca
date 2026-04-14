import grpc
import library_pb2
import library_pb2_grpc


IDIOMAS_VALIDOS = {"es", "en", "fr"}


def consultar_ticket(stub):
    try:
        id_ticket = int(input("ID del ticket a consultar: "))
        respuesta = stub.ConsultarTicket(library_pb2.TicketID(id=id_ticket))
        print(f"Cliente: {respuesta.cliente}")
        print(f"Problema: {respuesta.problema}")
        print(f"Idioma: {respuesta.idioma}")
        print(f"Atendido: {'Sí' if respuesta.atendido else 'No'}")
    except ValueError:
        print("Debes ingresar un número válido.")
    except grpc.RpcError as e:
        print("Error:", e.details())


def listar_tickets(stub):
    try:
        print("\nListado de tickets:")
        for ticket in stub.ListarTickets(library_pb2.Vacio()):
            estado = "Atendido" if ticket.atendido else "Pendiente"
            print(
                f"{ticket.id} - {ticket.cliente} | {ticket.problema} | "
                f"Idioma: {ticket.idioma} | Estado: {estado}"
            )
    except grpc.RpcError as e:
        print("Error:", e.details())


def generar_tickets(stub):
    def generador_tickets():
        while True:
            id_texto = input("ID del ticket (Enter para terminar): ").strip()
            if not id_texto:
                break

            try:
                id_ticket = int(id_texto)
            except ValueError:
                print("El ID debe ser numérico.")
                continue

            cliente = input("Nombre del cliente: ").strip()
            problema = input("Problema reportado: ").strip()
            idioma = input("Idioma del ticket (es/en/fr): ").strip().lower()

            if not cliente or not problema:
                print("Cliente y problema son obligatorios.")
                continue

            if idioma not in IDIOMAS_VALIDOS:
                print("Idioma no válido. Solo se permite es, en o fr.")
                continue

            yield library_pb2.Ticket(
                id=id_ticket,
                cliente=cliente,
                problema=problema,
                idioma=idioma,
                atendido=False,
            )

    try:
        respuesta = stub.GenerarTickets(generador_tickets())
        print(f"Total registrados: {respuesta.total_registrados}")
    except grpc.RpcError as e:
        print("Error:", e.details())


def atender_tickets_tiempo_real(stub):
    def enviar_solicitudes():
        while True:
            escritorio = input("Nombre o número de escritorio (Enter para terminar): ").strip()
            if not escritorio:
                break

            idioma = input("Idioma que atiende el escritorio (es/en/fr): ").strip().lower()

            if idioma not in IDIOMAS_VALIDOS:
                print("Idioma no válido. Solo se permite es, en o fr.")
                continue

            yield library_pb2.SolicitudEscritorio(
                escritorio=escritorio,
                idioma=idioma,
            )

    try:
        respuestas = stub.AtenderTicketsTiempoReal(enviar_solicitudes())
        for respuesta in respuestas:
            print("Respuesta:", respuesta.mensaje)
    except grpc.RpcError as e:
        print("Error:", e.details())


def main():
    direccion = input("Dirección del servidor (ej. localhost:50052): ").strip()
    canal = grpc.insecure_channel(direccion)
    stub = library_pb2_grpc.BibliotecaServiceStub(canal)

    while True:
        print("\n--- Menú Call Center ---")
        print("1. Consultar ticket")
        print("2. Listar tickets")
        print("3. Generar tickets")
        print("4. Atender tickets por idioma")
        print("5. Salir")

        opcion = input("Selecciona una opción: ").strip()

        if opcion == "1":
            consultar_ticket(stub)
        elif opcion == "2":
            listar_tickets(stub)
        elif opcion == "3":
            generar_tickets(stub)
        elif opcion == "4":
            atender_tickets_tiempo_real(stub)
        elif opcion == "5":
            print("Hasta luego.")
            break
        else:
            print("Opción no válida.")


if __name__ == "__main__":
    main()