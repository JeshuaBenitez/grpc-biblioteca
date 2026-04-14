from concurrent import futures
import json
import logging
import os
import threading
import time

import grpc
import library_pb2
import library_pb2_grpc


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.normpath(os.path.join(BASE_DIR, "../data/tickets.json"))
LOG_PATH = os.path.normpath(os.path.join(BASE_DIR, "../data/servidor_soporte.log"))

lock = threading.Lock()


PRIORITY_WEIGHT = {
    library_pb2.ALTA: 3,
    library_pb2.MEDIA: 2,
    library_pb2.BAJA: 1,
    library_pb2.PRIORIDAD_NO_DEFINIDA: 0,
}


def _priority_to_str(priority: int) -> str:
    if priority == library_pb2.ALTA:
        return "alta"
    if priority == library_pb2.MEDIA:
        return "media"
    if priority == library_pb2.BAJA:
        return "baja"
    return "no_definida"


def _configure_logger() -> logging.Logger:
    logger = logging.getLogger("soporte")
    logger.setLevel(logging.INFO)

    if logger.handlers:
        return logger

    formatter = logging.Formatter("[%(asctime)s] %(levelname)s - %(message)s")

    file_handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger


LOGGER = _configure_logger()


def _empty_store() -> dict:
    return {"next_id": 1, "tickets": []}


def _sort_pending(tickets: list[dict]) -> None:
    tickets.sort(
        key=lambda ticket: (
            -PRIORITY_WEIGHT.get(ticket["prioridad"], 0),
            ticket["fecha_creacion"],
            ticket["id"],
        )
    )


def _count_pending_by_priority(tickets: list[dict]) -> dict[str, int]:
    bajas = medias = altas = 0
    for ticket in tickets:
        if ticket["estado"] != "pendiente":
            continue
        if ticket["prioridad"] == library_pb2.ALTA:
            altas += 1
        elif ticket["prioridad"] == library_pb2.MEDIA:
            medias += 1
        elif ticket["prioridad"] == library_pb2.BAJA:
            bajas += 1
    return {"bajas": bajas, "medias": medias, "altas": altas, "total": bajas + medias + altas}


def _ticket_to_proto(ticket: dict) -> library_pb2.Ticket:
    return library_pb2.Ticket(
        id=ticket["id"],
        cliente=ticket["cliente"],
        descripcion=ticket["descripcion"],
        prioridad=ticket["prioridad"],
        estado=ticket["estado"],
        fecha_creacion=ticket["fecha_creacion"],
        fecha_atencion=ticket["fecha_atencion"],
    )


def load_store() -> dict:
    if not os.path.exists(DATA_PATH):
        return _empty_store()

    with lock:
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            store = json.load(f)

    if "next_id" not in store or "tickets" not in store:
        return _empty_store()

    _sort_pending(store["tickets"])
    return store


def save_store(store: dict) -> None:
    with lock:
        with open(DATA_PATH, "w", encoding="utf-8") as f:
            json.dump(store, f, indent=2, ensure_ascii=False)


class SoporteTicketsServiceServicer(library_pb2_grpc.SoporteTicketsServiceServicer):
    def CrearTicket(self, request, context):
        prioridad = request.prioridad
        if prioridad not in (library_pb2.BAJA, library_pb2.MEDIA, library_pb2.ALTA):
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details("Prioridad invalida. Usa baja, media o alta")
            return library_pb2.RespuestaTicket()

        cliente = request.cliente.strip()
        descripcion = request.descripcion.strip()
        if not cliente or not descripcion:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details("Cliente y descripcion son obligatorios")
            return library_pb2.RespuestaTicket()

        store = load_store()
        ticket_id = int(store["next_id"])
        now = int(time.time())

        new_ticket = {
            "id": ticket_id,
            "cliente": cliente,
            "descripcion": descripcion,
            "prioridad": prioridad,
            "estado": "pendiente",
            "fecha_creacion": now,
            "fecha_atencion": 0,
        }

        store["tickets"].append(new_ticket)
        store["next_id"] = ticket_id + 1
        _sort_pending(store["tickets"])
        save_store(store)

        LOGGER.info(
            "Ticket creado id=%s cliente=%s prioridad=%s",
            ticket_id,
            cliente,
            _priority_to_str(prioridad),
        )

        return library_pb2.RespuestaTicket(
            ticket_id=ticket_id,
            mensaje=f"Ticket {ticket_id} registrado con prioridad {_priority_to_str(prioridad)}",
        )


    def AtenderSiguiente(self, request, context):
        escritorio_id = request.escritorio_id.strip() or "Escritorio-sin-id"
        store = load_store()

        pending_tickets = [t for t in store["tickets"] if t["estado"] == "pendiente"]
        _sort_pending(pending_tickets)

        if not pending_tickets:
            LOGGER.info("%s solicito ticket pero no habia pendientes", escritorio_id)
            return library_pb2.TicketAsignado(
                hay_ticket=False,
                mensaje="No hay tickets pendientes",
            )

        selected_id = pending_tickets[0]["id"]
        selected_ticket = None
        for ticket in store["tickets"]:
            if ticket["id"] == selected_id:
                ticket["estado"] = "atendido"
                ticket["fecha_atencion"] = int(time.time())
                selected_ticket = ticket
                break

        save_store(store)

        LOGGER.info(
            "%s atendio ticket id=%s prioridad=%s cliente=%s",
            escritorio_id,
            selected_ticket["id"],
            _priority_to_str(selected_ticket["prioridad"]),
            selected_ticket["cliente"],
        )

        return library_pb2.TicketAsignado(
            hay_ticket=True,
            mensaje=f"{escritorio_id} atiende ticket {selected_ticket['id']}",
            ticket=_ticket_to_proto(selected_ticket),
        )


    def ConsultarPendientes(self, request, context):
        store = load_store()
        counts = _count_pending_by_priority(store["tickets"])
        LOGGER.info(
            "Pantalla publica consultada: total=%s altas=%s medias=%s bajas=%s",
            counts["total"],
            counts["altas"],
            counts["medias"],
            counts["bajas"],
        )
        return library_pb2.ResumenPendientes(
            total=counts["total"],
            bajas=counts["bajas"],
            medias=counts["medias"],
            altas=counts["altas"],
        )

    def ListarPendientes(self, request, context):
        store = load_store()
        pending = [t for t in store["tickets"] if t["estado"] == "pendiente"]
        _sort_pending(pending)
        for ticket in pending:
            yield _ticket_to_proto(ticket)


def servir():
    store = load_store()
    save_store(store)

    servidor = grpc.server(futures.ThreadPoolExecutor(max_workers=12))
    library_pb2_grpc.add_SoporteTicketsServiceServicer_to_server(
        SoporteTicketsServiceServicer(),
        servidor,
    )

    servidor.add_insecure_port("[::]:50052")
    servidor.start()
    LOGGER.info("Servidor de soporte gRPC escuchando en puerto 50052")
    servidor.wait_for_termination()


if __name__ == "__main__":
    servir()