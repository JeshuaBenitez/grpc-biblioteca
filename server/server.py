from concurrent import futures
import json
import logging
import os
import threading
import time
from collections import deque

import grpc
import library_pb2
import library_pb2_grpc


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ESTADO_PATH = os.path.normpath(os.path.join(BASE_DIR, "../data/consultorio_estado.json"))
LOG_PATH = os.path.normpath(os.path.join(BASE_DIR, "logs/consultorio.log"))
ESPECIALIDADES = ("medicina_general", "pediatria", "odontologia")
PREFIJOS = {
    "medicina_general": "MG",
    "pediatria": "PD",
    "odontologia": "OD",
}

os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="[LOG] %(asctime)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)


def _estado_inicial() -> dict:
    return {
        "consecutivos": {esp: 0 for esp in ESPECIALIDADES},
        "colas": {esp: [] for esp in ESPECIALIDADES},
        "ultimos_llamados": {esp: [] for esp in ESPECIALIDADES},
    }


def _normalizar_especialidad(nombre: str) -> str:
    return (nombre or "").strip().lower().replace(" ", "_")


def _ticket_a_turno_llamado(ticket: dict, llamado_en: int | None = None) -> library_pb2.TurnoLlamado:
    return library_pb2.TurnoLlamado(
        codigo=ticket["codigo"],
        paciente=ticket["paciente"],
        especialidad=ticket["especialidad"],
        llamado_en=llamado_en if llamado_en is not None else int(time.time()),
    )


class EstadoConsultorio:
    def __init__(self, estado_path: str):
        self.estado_path = estado_path
        self.lock = threading.Lock()
        self.condicion = threading.Condition(self.lock)
        self.version = 0
        self.consecutivos = {esp: 0 for esp in ESPECIALIDADES}
        self.colas = {esp: deque() for esp in ESPECIALIDADES}
        self.ultimos_llamados = {esp: deque(maxlen=3) for esp in ESPECIALIDADES}
        self._cargar_desde_json()

    def _cargar_desde_json(self) -> None:
        if not os.path.exists(self.estado_path):
            self._guardar_en_json(_estado_inicial())

        with open(self.estado_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        for esp in ESPECIALIDADES:
            self.consecutivos[esp] = int(data.get("consecutivos", {}).get(esp, 0))
            self.colas[esp] = deque(data.get("colas", {}).get(esp, []))
            self.ultimos_llamados[esp] = deque(data.get("ultimos_llamados", {}).get(esp, []), maxlen=3)

    def _serializar_estado(self) -> dict:
        return {
            "consecutivos": self.consecutivos,
            "colas": {esp: list(self.colas[esp]) for esp in ESPECIALIDADES},
            "ultimos_llamados": {esp: list(self.ultimos_llamados[esp]) for esp in ESPECIALIDADES},
        }

    def _guardar_en_json(self, data: dict | None = None) -> None:
        payload = data if data is not None else self._serializar_estado()
        with open(self.estado_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

    def _crear_ticket(self, paciente: str, especialidad: str) -> dict:
        self.consecutivos[especialidad] += 1
        numero = self.consecutivos[especialidad]
        codigo = f"{PREFIJOS[especialidad]}-{numero:03d}"
        ticket = {
            "codigo": codigo,
            "paciente": paciente,
            "especialidad": especialidad,
            "posicion": len(self.colas[especialidad]) + 1,
            "creado_en": int(time.time()),
        }
        self.colas[especialidad].append(ticket)
        return ticket

    def generar_turno(self, paciente: str, especialidad: str) -> dict:
        with self.condicion:
            ticket = self._crear_ticket(paciente=paciente, especialidad=especialidad)
            self.version += 1
            self._guardar_en_json()
            self.condicion.notify_all()
            return ticket

    def registrar_lote(self, solicitudes: list[tuple[str, str]]) -> list[dict]:
        creados = []
        with self.condicion:
            for paciente, especialidad in solicitudes:
                creados.append(self._crear_ticket(paciente=paciente, especialidad=especialidad))
            if creados:
                self.version += 1
                self._guardar_en_json()
                self.condicion.notify_all()
        return creados

    def llamar_siguiente(self, especialidad: str) -> tuple[dict | None, int]:
        with self.condicion:
            if not self.colas[especialidad]:
                return None, 0

            ticket = self.colas[especialidad].popleft()
            llamado = {
                "codigo": ticket["codigo"],
                "paciente": ticket["paciente"],
                "especialidad": especialidad,
                "llamado_en": int(time.time()),
            }
            self.ultimos_llamados[especialidad].append(llamado)
            self.version += 1
            self._guardar_en_json()
            self.condicion.notify_all()
            return llamado, len(self.colas[especialidad])

    def estado_pantalla(self) -> tuple[library_pb2.EstadoPantalla, int]:
        with self.lock:
            payload = {
                "medicina_general": [
                    _ticket_a_turno_llamado(item, item.get("llamado_en"))
                    for item in self.ultimos_llamados["medicina_general"]
                ],
                "pediatria": [
                    _ticket_a_turno_llamado(item, item.get("llamado_en"))
                    for item in self.ultimos_llamados["pediatria"]
                ],
                "odontologia": [
                    _ticket_a_turno_llamado(item, item.get("llamado_en"))
                    for item in self.ultimos_llamados["odontologia"]
                ],
                "version": self.version,
            }
            return library_pb2.EstadoPantalla(**payload), self.version

    def esperar_cambio(self, ultima_version: int, timeout: float = 15.0) -> int:
        with self.condicion:
            self.condicion.wait_for(lambda: self.version != ultima_version, timeout=timeout)
            return self.version


def log_operacion(mensaje: str) -> None:
    logging.info(mensaje)


estado = EstadoConsultorio(ESTADO_PATH)


class ConsultorioServiceServicer(library_pb2_grpc.ConsultorioServiceServicer):
    def GenerarTurno(self, request, context):
        paciente = request.paciente.strip()
        especialidad = _normalizar_especialidad(request.especialidad)

        if not paciente:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details("El nombre del paciente es obligatorio")
            return library_pb2.Ticket()

        if especialidad not in ESPECIALIDADES:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details("Especialidad inválida")
            return library_pb2.Ticket()

        ticket = estado.generar_turno(paciente=paciente, especialidad=especialidad)
        log_operacion(f"Turno generado {ticket['codigo']} para {paciente} en {especialidad}")
        return library_pb2.Ticket(**ticket)

    def RegistrarTurnosLote(self, request_iterator, context):
        solicitudes = []
        for solicitud in request_iterator:
            paciente = solicitud.paciente.strip()
            especialidad = _normalizar_especialidad(solicitud.especialidad)
            if not paciente or especialidad not in ESPECIALIDADES:
                continue
            solicitudes.append((paciente, especialidad))

        tickets = estado.registrar_lote(solicitudes)
        for ticket in tickets:
            log_operacion(
                f"Turno generado por lote {ticket['codigo']} para {ticket['paciente']} en {ticket['especialidad']}"
            )

        return library_pb2.ResumenRegistro(
            total_registrados=len(tickets),
            tickets=[library_pb2.Ticket(**ticket) for ticket in tickets],
        )

    def VerPantalla(self, request, context):
        ultima_version = -1
        while context.is_active():
            snapshot, version = estado.estado_pantalla()
            if version != ultima_version:
                ultima_version = version
                if request.incluir_todas:
                    yield snapshot
                else:
                    filtro = set(_normalizar_especialidad(e) for e in request.especialidades)
                    yield library_pb2.EstadoPantalla(
                        medicina_general=snapshot.medicina_general if "medicina_general" in filtro else [],
                        pediatria=snapshot.pediatria if "pediatria" in filtro else [],
                        odontologia=snapshot.odontologia if "odontologia" in filtro else [],
                        version=snapshot.version,
                    )
            estado.esperar_cambio(ultima_version)

    def AtencionTiempoReal(self, request_iterator, context):
        for evento in request_iterator:
            escritorio = evento.escritorio_id.strip() or "escritorio"
            especialidad = _normalizar_especialidad(evento.especialidad)
            accion = evento.accion.strip().lower()

            if especialidad not in ESPECIALIDADES:
                yield library_pb2.EventoServidor(
                    tipo="error",
                    mensaje=f"Especialidad inválida para {escritorio}",
                    pendientes=0,
                )
                continue

            if accion == "solicitar_siguiente":
                llamado, pendientes = estado.llamar_siguiente(especialidad)
                if llamado is None:
                    mensaje = f"{escritorio}: no hay turnos pendientes en {especialidad}"
                    log_operacion(mensaje)
                    yield library_pb2.EventoServidor(
                        tipo="sin_turnos",
                        mensaje=mensaje,
                        pendientes=pendientes,
                    )
                    continue

                mensaje = (
                    f"{escritorio} llama {llamado['codigo']} - {llamado['paciente']} en {especialidad}"
                )
                log_operacion(mensaje)
                yield library_pb2.EventoServidor(
                    tipo="turno_llamado",
                    mensaje=mensaje,
                    turno=_ticket_a_turno_llamado(llamado, llamado["llamado_en"]),
                    pendientes=pendientes,
                )
                continue

            if accion == "ping":
                mensaje = f"{escritorio} conectado a {especialidad}"
                log_operacion(mensaje)
                yield library_pb2.EventoServidor(tipo="ok", mensaje=mensaje)
            else:
                yield library_pb2.EventoServidor(
                    tipo="error",
                    mensaje=f"Acción desconocida: {accion}",
                    pendientes=0,
                )


def servir():
    servidor = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    library_pb2_grpc.add_ConsultorioServiceServicer_to_server(
        ConsultorioServiceServicer(),
        servidor,
    )

    servidor.add_insecure_port("[::]:50052")
    servidor.start()
    print("Servidor Consultorio gRPC escuchando en puerto 50052...")
    log_operacion(f"Servidor iniciado. Estado: {ESTADO_PATH}")
    servidor.wait_for_termination()


if __name__ == "__main__":
    servir()