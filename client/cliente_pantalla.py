import grpc
import library_pb2
import library_pb2_grpc


def imprimir_seccion(nombre: str, turnos):
    print(f"\n{nombre} (ultimos 3):")
    if not turnos:
        print("  Sin llamados")
        return
    for turno in turnos:
        print(f"  {turno.codigo} - {turno.paciente}")


def main():
    direccion = input("Direccion del servidor (ej. 192.168.1.10:50052): ").strip()
    canal = grpc.insecure_channel(direccion)
    stub = library_pb2_grpc.ConsultorioServiceStub(canal)

    print("Pantalla publica conectada. Esperando actualizaciones...\n")

    try:
        stream = stub.VerPantalla(library_pb2.PantallaRequest(incluir_todas=True))
        for estado in stream:
            print("\n" + "=" * 50)
            print(f"Version del tablero: {estado.version}")
            imprimir_seccion("Medicina general", estado.medicina_general)
            imprimir_seccion("Pediatria", estado.pediatria)
            imprimir_seccion("Odontologia", estado.odontologia)
            print("=" * 50)
    except grpc.RpcError as e:
        print("Conexion cerrada:", e.details())


if __name__ == "__main__":
    main()
