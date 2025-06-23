import zmq
import json

def main():
    """Ein Client, der zwei ARGoS-Roboter gleichzeitig steuert."""
    context = zmq.Context()
    ports = ["5555", "5556"]
    sockets = []

    print("Verbinde mit ARGoS-Servern...")
    for port in ports:
        socket = context.socket(zmq.REQ)
        socket.connect(f"tcp://localhost:{port}")
        sockets.append(socket)
        print(f"  - Verbunden mit Port {port}")

    try:
        while True:
            cmd = input("Kommando (w/a/s/d/stop/exit): ").strip().lower()

            if cmd == "exit":
                break
            
            left_speed, right_speed = 0.0, 0.0
            if cmd == 'w':
                left_speed, right_speed = 10.0, 10.0
            elif cmd == 's':
                left_speed, right_speed = -10.0, -10.0
            elif cmd == 'a':
                left_speed, right_speed = -5.0, 5.0
            elif cmd == 'd':
                left_speed, right_speed = 5.0, -5.0
            elif cmd == 'stop':
                left_speed, right_speed = 0.0, 0.0
            else:
                print("Unbekanntes Kommando.")
                continue

            command = {"left_speed": left_speed, "right_speed": right_speed}

            # Sende das Kommando an alle Roboter
            for i, socket in enumerate(sockets):
                print(f"Sende Kommando an Roboter {i} auf Port {ports[i]}: {command}")
                socket.send_json(command)

            # Warte auf die Antwort von allen Robotern
            for i, socket in enumerate(sockets):
                response = socket.recv_json()
                print(f"Antwort von Roboter {i} erhalten: {response}")
            
    except KeyboardInterrupt:
        print("\nClient wird beendet.")
    finally:
        for socket in sockets:
            socket.close()
        context.term()

if __name__ == "__main__":
    main()