import zmq


def main():
    """A client that controls multiple ARGoS robots simultaneously."""
    context = zmq.Context()
    ports = ["5555"]
    #ports = ["5555", "5556", "5557", "5558", "5559"]
    
    sockets = []

    print("Connecting to ARGoS servers...")
    for port in ports:
        socket = context.socket(zmq.REQ)
        socket.connect(f"tcp://localhost:{port}")
        sockets.append(socket)
        print(f"  - Connected to port {port}")

    try:
        while True:
            cmd = input("Command (w/a/s/d/stop/exit): ").strip().lower()

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
                print("Unknown command.")
                continue

            command = {"left_speed": left_speed, "right_speed": right_speed}

            # Send the command to all robots
            for i, socket in enumerate(sockets):
                print(f"Sending command to robot {i} on port {ports[i]}: {command}")
                socket.send_json(command)

            # Wait for the response from all robots
            for i, socket in enumerate(sockets):
                response = socket.recv_json()
                print(f"Response from robot {i} received: {response}")
            
    except KeyboardInterrupt:
        print("\nExiting client.")
    finally:
        for socket in sockets:
            socket.close()
        context.term()

if __name__ == "__main__":
    main()