# Architecture: ARGoS-PettingZoo Bridge

This document describes the technical architecture that enables communication between the C++-based ARGoS simulator and an external Python control script.

## Component Overview

The system consists of two decoupled main components connected via inter-process communication (IPC):

1. **ARGoS Simulator (Server Side):**
   * **Language:** C++
   * **Role:** Serves as the simulation environment, handling physical simulation, sensor data generation, and execution of actuator commands.
   * **Core:** A custom **controller plugin** (`my_ipc_controller`), compiled as a dynamic library (`.dylib`). Each simulated robot receives an instance of this controller.

2. **Python Control (Client Side):**
   * **Language:** Python
   * **Role:** Acts as the "brain" of the robots. It implements decision logic (manually or later via a MARL algorithm) and sends control commands to the simulator.
   * **Core:** A Python script (`manual_control.py`) that establishes the connection to the controllers in the simulator.

## Communication Bridge

Communication between the two processes is implemented using a carefully selected technology stack.

* **Messaging Library: ZeroMQ (ØMQ)**
  * ZeroMQ is used as a lightweight, high-performance messaging layer that abstracts network programming complexity.
  * It enables seamless communication between different programming languages (C++ and Python) without a central message broker.

* **Communication Pattern: Request-Reply (REQ/REP)**
  * The system uses ZeroMQ’s REQ/REP pattern, enforcing a strict synchronous message exchange.
  * **Python Client (REQ Socket):** Sends a request (control command) and waits for a reply.
  * **C++ Controller (REP Socket):** Waits for a request, processes it, and sends a reply (status/sensor data).
  * This pattern ensures each command is acknowledged, simplifying the logic.

* **Data Format: JSON**
  * All messages between C++ and Python are exchanged as JSON-formatted strings.
  * JSON was chosen for its readability and excellent parser support in both languages, easing development and debugging.

## Multi-Agent Scaling

To control multiple robots simultaneously, the following architecture is used:

1. **Dedicated Ports:** Each robot controller in ARGoS binds to a unique TCP port (e.g., 5555, 5556, ...).
2. **XML Configuration:** Ports are assigned to robots in the `.argos` configuration file. Each robot has a separate controller configuration with a unique `id` and `port` parameter.
3. **Python Client Management:** The Python client manages a list of sockets, each connected to a specific robot’s port. Commands are sent iteratively to all sockets to control the entire fleet.

## Control Flow

The typical control flow for a simulation step is as follows:

1. The ARGoS simulator runs and cyclically calls the `ControlStep()` method for each robot controller.
2. Within `ControlStep()`, the C++ controller non-blockingly (`zmq::recv_flags::dontwait`) checks for new messages from the Python client to prevent the simulation from freezing.
3. The Python client sends a JSON object (e.g., `{"left_speed": 10.0, "right_speed": 5.0}`) to the corresponding port.
4. The C++ controller receives the message, parses the JSON, and sets the robot’s wheel speeds accordingly.
5. The C++ controller sends a confirmation JSON message (e.g., `{"status": "ok"}`) back to the Python client.
6. The Python client receives the confirmation and can send the next command.
