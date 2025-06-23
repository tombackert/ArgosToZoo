#include "my_ipc_controller.h"
#include <argos3/core/utility/logging/argos_log.h>


CMyIPCController::CMyIPCController() :
   m_pcWheels(NULL),
   m_ptZmqContext(NULL),
   m_ptZmqSocket(NULL) {}

/*
 * Initialisierungsmethode.
 */
void CMyIPCController::Init(TConfigurationNode& t_node) {
   try {
      m_pcWheels = GetActuator<CCI_DifferentialSteeringActuator>("differential_steering");

      // 1. Initialisiere den ZeroMQ-Kontext
      m_ptZmqContext = new zmq::context_t(1);

      // 2. Erstelle einen REP(ly)-Socket
      m_ptZmqSocket = new zmq::socket_t(*m_ptZmqContext, ZMQ_REP);

      // 3. Binde den Socket an einen Port. ARGoS agiert als Server.
      m_ptZmqSocket->bind("tcp://*:5555");
      LOG << "[INFO] IPC Controller initialisiert und an tcp://*:5555 gebunden" << std::endl;

   } catch(CARGoSException& ex) {
      THROW_ARGOSEXCEPTION_NESTED("Error initializing CMyIPCController", ex);
   } catch(zmq::error_t& ex) {
      THROW_ARGOSEXCEPTION("ZeroMQ error: " << ex.what());
   }
}

/*
 * Die Hauptlogikschleife.
 */
void CMyIPCController::ControlStep() {
   try {
      // 1. Warte auf eine Anfrage vom Python-Client (blockierend)
      zmq::message_t request;
      m_ptZmqSocket->recv(request, zmq::recv_flags::none);

      // 2. Parse die Anfrage als JSON
      json command = json::parse(request.to_string());
      
      // 3. Extrahiere die Geschwindigkeitswerte
      Real fLeftSpeed = command.value("left_speed", 0.0);
      Real fRightSpeed = command.value("right_speed", 0.0);

      // 4. Setze die Geschwindigkeit der Räder
      m_pcWheels->SetLinearVelocity(fLeftSpeed, fRightSpeed);

      // 5. Erstelle eine Antwort (z.B. mit Status)
      json response;
      response["status"] = "ok";
      // Hier könnten später Sensordaten hinzugefügt werden
      // response["proximity"] =...;

      // 6. Sende die Antwort zurück an den Python-Client
      m_ptZmqSocket->send(zmq::buffer(response.dump()), zmq::send_flags::none);

   } catch(json::parse_error& ex) {
      LOGERR << " JSON parse error: " << ex.what() << std::endl;
      // Sende eine Fehlermeldung zurück
      json error_response;
      error_response["status"] = "error";
      error_response["message"] = "Invalid JSON format";
      m_ptZmqSocket->send(zmq::buffer(error_response.dump()), zmq::send_flags::none);
   } catch(zmq::error_t& ex) {
      LOGERR << " ZeroMQ error: " << ex.what() << std::endl;
   }
}

/*
 * Reset-Methode. Für diesen einfachen Controller ist nichts zurückzusetzen.
 */
void CMyIPCController::Reset() {
   // Hier könnten Zustandsvariablen zurückgesetzt werden.
}

/*
 * Destroy-Methode. Für diesen einfachen Controller ist nichts zu bereinigen.
 * Später müsste hier z.B. die IPC-Verbindung (Socket) sauber geschlossen werden.
 */
void CMyIPCController::Destroy() {
   // Räume die ZeroMQ-Ressourcen sauber auf
   if (m_ptZmqSocket) {
      m_ptZmqSocket->close();
      delete m_ptZmqSocket;
  }
  if (m_ptZmqContext) {
      m_ptZmqContext->close();
      delete m_ptZmqContext;
  }
  LOG << "[INFO] IPC Controller zerstört." << std::endl;
}

/*
 * DIES IST DER ENTSCHEIDENDE SCHRITT FÜR DIE REGISTRIERUNG!
 * Das Makro REGISTER_CONTROLLER bindet die C++-Klasse CMyIPCController an den
 * String-Bezeichner "my_ipc_controller".
 * Dieser Bezeichner wird dann in der.argos-Datei als XML-Tag verwendet, um diesen
 * Controller zu instanziieren. Das Makro muss in der.cpp-Datei stehen.[7, 15]
 */
REGISTER_CONTROLLER(CMyIPCController, "my_ipc_controller")