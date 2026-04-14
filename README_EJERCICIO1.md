# Ejercicio 1 - Sistema de turnos para consultorio (gRPC)

Este proyecto implementa los 4 tipos de comunicacion gRPC para un consultorio con 3 areas:

- medicina_general
- pediatria
- odontologia

## Tipos de RPC usados

- Unary: `GenerarTurno`
- Client Streaming: `RegistrarTurnosLote`
- Server Streaming: `VerPantalla`
- Bidirectional Streaming: `AtencionTiempoReal`

## Estructura usada

- `proto/library.proto`
- `server/server.py`
- `client/menu_cliente.py` (cliente de ventanilla)
- `client/cliente_escritorio.py`
- `client/cliente_pantalla.py`
- `data/consultorio_estado.json`

## 1) Instalar dependencias

Desde la raiz `grpc-biblioteca`:

```powershell
pip install -r requirements.txt
```

## 2) Generar stubs (si cambias el proto)

```powershell
python -m grpc_tools.protoc -Iproto --python_out=server --grpc_python_out=server proto/library.proto
python -m grpc_tools.protoc -Iproto --python_out=client --grpc_python_out=client proto/library.proto
```

## 3) Ejecutar servidor

```powershell
cd server
python server.py
```

Servidor escucha en `0.0.0.0:50052`.

## 4) Ejecutar clientes independientes

Abre 3 terminales (o mas) en otras PCs de la red local.

### Cliente 1: VENTANILLA (genera turnos)

```powershell
cd client
python menu_cliente.py
```

### Cliente 2: ESCRITORIO por especialidad (atiende su cola)

```powershell
cd client
python cliente_escritorio.py
```

### Cliente 3: PANTALLA publica (ultimos 3 llamados por area)

```powershell
cd client
python cliente_pantalla.py
```

## Notas de red local

- Si cliente y servidor estan en maquinas distintas, en los clientes usa `IP_DEL_SERVIDOR:50052`.
- Permite el puerto `50052` en firewall de Windows para conexiones entrantes.

## Persistencia y concurrencia

- Persistencia simulada en `data/consultorio_estado.json`.
- Concurrencia con `threading.Condition` y `threading.Lock`.
- Log de servidor en consola y en `server/logs/consultorio.log`.
