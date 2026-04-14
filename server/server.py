from concurrent import futures
import json
import os
import threading
import time

import grpc
import library_pb2
import library_pb2_grpc


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TICKETS_PATH = os.path.normpath(os.path.join(BASE_DIR, "../data/tickets.json"))

lock = threading.Lock()
IDIOMAS_VALIDOS = {"es", "en", "fr"}


def cargar_tickets() -> dict[int, dict]:
    """Carga el JSON y lo convierte a un diccionario indexado por id."""
    if not os.path.exists(TICKETS_PATH):
        return {}

    with lock:
        with open(TICKETS_PATH, "r", encoding="utf-8") as f:
            tickets_lista = json.load(f)

    return {ticket["id"]: ticket for ticket in tickets_lista}


def guardar_tickets(tickets_dict: dict[int, dict]) -> None:
    """Guarda el diccionario en el JSON."""
    with lock:
        with open(TICKETS_PATH, "w", encoding="utf-8") as f:
            json.dump(list(tickets_dict.values()), f, indent=2, ensure_ascii=False)


def log_operacion(mensaje: str) -> None:
    print(f"[LOG] {time.strftime('%Y-%m-%d %H:%M:%S')} - {mensaje}")


class BibliotecaServiceServicer(library_pb2_grpc.BibliotecaServiceServicer):
    def ConsultarTicket(self, request, context):
        """Unary RPC: recibe un ID y devuelve un ticket."""
        tickets = cargar_tickets()
        ticket = tickets.get(request.id)

        if ticket is None:
            log_operacion(f"Consulta fallida para ticket ID {request.id}")
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details("Ticket no encontrado")
            return library_pb2.Ticket()

        log_operacion(f"Consulta de ticket ID {request.id}")
        return library_pb2.Ticket(
            id=ticket["id"],
            cliente=ticket["cliente"],
            problema=ticket["problema"],
            idioma=ticket["idioma"],
            atendido=ticket.get("atendido", False),
        )

    def ListarTickets(self, request, context):
        """Server Streaming RPC: envía todos los tickets uno por uno."""
        tickets = cargar_tickets()

        for ticket in tickets.values():
            log_operacion(f"Enviando ticket ID {ticket['id']}")
            yield library_pb2.Ticket(
                id=ticket["id"],
                cliente=ticket["cliente"],
                problema=ticket["problema"],
                idioma=ticket["idioma"],
                atendido=ticket.get("atendido", False),
            )

    def GenerarTickets(self, request_iterator, context):
        """Client Streaming RPC: recibe varios tickets y responde con un resumen."""
        tickets = cargar_tickets()
        total = 0

        for ticket in request_iterator:
            idioma = ticket.idioma.strip().lower()

            if idioma not in IDIOMAS_VALIDOS:
                log_operacion(f"Ticket rechazado ID {ticket.id}: idioma inválido '{idioma}'")
                continue

            tickets[ticket.id] = {
                "id": ticket.id,
                "cliente": ticket.cliente,
                "problema": ticket.problema,
                "idioma": idioma,
                "atendido": False,
            }
            total += 1
            log_operacion(
                f"Ticket registrado ID {ticket.id} - Cliente: {ticket.cliente} - Idioma: {idioma}"
            )

        guardar_tickets(tickets)

        return library_pb2.ResumenRegistro(total_registrados=total)

    def AtenderTicketsTiempoReal(self, request_iterator, context):
        """
        Bidirectional Streaming RPC:
        cada escritorio solicita atención por idioma y el servidor entrega
        solo tickets de ese idioma.
        """
        for solicitud in request_iterator:
            escritorio = solicitud.escritorio.strip()
            idioma = solicitud.idioma.strip().lower()

            if idioma not in IDIOMAS_VALIDOS:
                mensaje = (
                    f"Escritorio {escritorio}: idioma inválido '{idioma}'. "
                    f"Use es, en o fr."
                )
                log_operacion(mensaje)
                yield library_pb2.ConfirmacionAtencion(mensaje=mensaje)
                continue

            tickets = cargar_tickets()
            ticket_encontrado = None

            for ticket_id, ticket in tickets.items():
                if (
                    ticket["idioma"].strip().lower() == idioma
                    and not ticket.get("atendido", False)
                ):
                    ticket_encontrado = ticket
                    tickets[ticket_id]["atendido"] = True
                    guardar_tickets(tickets)
                    break

            if ticket_encontrado:
                mensaje = (
                    f"Escritorio {escritorio} atendió ticket {ticket_encontrado['id']} "
                    f"de {ticket_encontrado['cliente']} "
                    f"(idioma: {ticket_encontrado['idioma']}, problema: {ticket_encontrado['problema']})"
                )
            else:
                mensaje = (
                    f"Escritorio {escritorio}: no hay tickets disponibles para el idioma '{idioma}'"
                )

            log_operacion(mensaje)
            yield library_pb2.ConfirmacionAtencion(mensaje=mensaje)


def servir():
    servidor = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    library_pb2_grpc.add_BibliotecaServiceServicer_to_server(
        BibliotecaServiceServicer(),
        servidor,
    )

    servidor.add_insecure_port("[::]:50052")
    servidor.start()
    print("Servidor Call Center gRPC escuchando en puerto 50052...")
    servidor.wait_for_termination()


if __name__ == "__main__":
    servir()