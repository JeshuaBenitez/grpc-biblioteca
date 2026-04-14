import grpc
import library_pb2
import library_pb2_grpc
import select
import sys
import time


def _parse_prioridad(texto: str) -> int | None:
    valor = texto.strip().lower()
    if valor == "alta":
        return library_pb2.ALTA
    if valor == "media":
        return library_pb2.MEDIA
    if valor == "baja":
        return library_pb2.BAJA
    return None


def _prioridad_a_texto(prioridad: int) -> str:
    if prioridad == library_pb2.ALTA:
        return "alta"
    if prioridad == library_pb2.MEDIA:
        return "media"
    if prioridad == library_pb2.BAJA:
        return "baja"
    return "no definida"


def crear_ticket(stub):
    try:
        cliente = input("Cliente: ").strip()
        descripcion = input("Descripcion del problema: ").strip()
        prioridad_texto = input("Prioridad (baja/media/alta): ").strip()
        prioridad = _parse_prioridad(prioridad_texto)

        if not cliente or not descripcion:
            print("Cliente y descripcion son obligatorios.")
            return
        if prioridad is None:
            print("Prioridad invalida.")
            return

        respuesta = stub.CrearTicket(
            library_pb2.SolicitudTicket(
                cliente=cliente,
                descripcion=descripcion,
                prioridad=prioridad,
            )
        )
        print(f"Ticket creado con ID: {respuesta.ticket_id}")
        print(respuesta.mensaje)
    except grpc.RpcError as e:
        print("Error:", e.details())


def _atender_siguiente(stub, escritorio_id: str):
    try:
        respuesta = stub.AtenderSiguiente(
            library_pb2.EscritorioRequest(escritorio_id=escritorio_id)
        )

        if not respuesta.hay_ticket:
            print(respuesta.mensaje)
            return

        ticket = respuesta.ticket
        print(respuesta.mensaje)
        print(
            f"Ticket {ticket.id} | Cliente: {ticket.cliente} | "
            f"Prioridad: {_prioridad_a_texto(ticket.prioridad)}"
        )
        print(f"Descripcion: {ticket.descripcion}")
    except grpc.RpcError as e:
        print("Error:", e.details())


def _consultar_pantalla_publica(stub):
    try:
        resumen = stub.ConsultarPendientes(library_pb2.Vacio())
        print("\n--- Pantalla Publica ---")
        print(f"Total pendientes: {resumen.total}")
        print(f"Alta: {resumen.altas}")
        print(f"Media: {resumen.medias}")
        print(f"Baja: {resumen.bajas}")
    except grpc.RpcError as e:
        print("Error:", e.details())


def _mostrar_lista_pendientes(stub):
    try:
        print("\nTickets pendientes (ordenados por prioridad):")
        hay_tickets = False
        for ticket in stub.ListarPendientes(library_pb2.Vacio()):
            hay_tickets = True
            print(
                f"{ticket.id} | {_prioridad_a_texto(ticket.prioridad)} | "
                f"{ticket.cliente} | {ticket.descripcion}"
            )
        if not hay_tickets:
            print("No hay tickets pendientes.")
    except grpc.RpcError as e:
        print("Error:", e.details())


def _leer_comando_timeout(segundos: int) -> str | None:
    listo, _, _ = select.select([sys.stdin], [], [], segundos)
    if not listo:
        return None
    return sys.stdin.readline().strip().lower()


def modo_escritorio(stub):
    escritorio_id = input("ID de escritorio: ").strip() or "Escritorio-1"
    print("\nModo escritorio activo.")
    print("Presiona Enter para atender otro ticket o escribe 'exit' para volver al menu.")

    while True:
        comando = input(f"[{escritorio_id}] > ").strip().lower()
        if comando == "exit":
            print("Saliendo de modo escritorio...")
            return
        if comando:
            print("Comando no valido. Usa Enter para atender o 'exit' para volver.")
            continue
        _atender_siguiente(stub, escritorio_id)


def modo_pantalla_publica_tiempo_real(stub):
    print("\nPantalla publica en tiempo real.")
    print("Actualizacion automatica cada 2 segundos. Escribe 'exit' y Enter para volver.")

    while True:
        _consultar_pantalla_publica(stub)
        print("[Esperando comando: 'exit' para salir | Enter para refrescar ya]", flush=True)
        comando = _leer_comando_timeout(2)
        if comando == "exit":
            print("Saliendo de pantalla publica...")
            return
        time.sleep(0.1)


def modo_lista_tickets_tiempo_real(stub):
    print("\nLista de tickets en tiempo real.")
    print("Actualizacion automatica cada 2 segundos.")
    print("Presiona Enter para volver al menu principal.")

    while True:
        _mostrar_lista_pendientes(stub)
        print("[Esperando: Enter para salir]", flush=True)
        comando = _leer_comando_timeout(2)
        if comando == "":
            print("Saliendo de lista de tickets...")
            return


def main():
    direccion = input("Dirección del servidor (ej. localhost:50052): ").strip()
    canal = grpc.insecure_channel(direccion)
    stub = library_pb2_grpc.SoporteTicketsServiceStub(canal)

    while True:
        print("\n--- Menu Soporte ---")
        print("1. Generar ticket")
        print("2. Atender siguiente ticket")
        print("3. Pantalla publica (pendientes por prioridad)")
        print("4. Listar tickets pendientes")
        print("5. Salir")

        opcion = input("Selecciona una opción: ").strip()

        if opcion == "1":
            crear_ticket(stub)
        elif opcion == "2":
            modo_escritorio(stub)
        elif opcion == "3":
            modo_pantalla_publica_tiempo_real(stub)
        elif opcion == "4":
            modo_lista_tickets_tiempo_real(stub)
        elif opcion == "5":
            print("Hasta luego.")
            break
        else:
            print("Opción no válida.")


if __name__ == "__main__":
    main()