#include "my_ipc_controller.h"
#include <argos3/core/utility/logging/argos_log.h>


CMyIPCController::CMyIPCController() :
   m_pcWheels(NULL),
   m_ptZmqContext(NULL),
   m_ptZmqSocket(NULL),
   m_sPort("5555") {}

/*
 * Initialisierungsmethode.
 */
void CMyIPCController::Init(TConfigurationNode& t_node) {
   try {
      m_pcWheels = GetActuator<CCI_DifferentialSteeringActuator>("differential_steering");

      // Lese den Port aus dem <params>-Abschnitt der XML-Datei.
      // Wenn nicht vorhanden, wird der Standardwert "5555" verwendet.
      GetNodeAttributeOrDefault(t_node, "port", m_sPort, m_sPort);

      // Initialisiere ZeroMQ
      m_ptZmqContext = new zmq::context_t(1);
      m_ptZmqSocket = new zmq::socket_t(*m_ptZmqContext, ZMQ_REP);

      // Binde den Socket an die dynamische Adresse
      std::string strBindAddr = "tcp://*:" + m_sPort;
      m_ptZmqSocket->bind(strBindAddr);
      LOG << "[INFO] IPC Controller initialisiert und an " << strBindAddr << " gebunden" << std::endl;

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
      // 1. Versuche, eine Nachricht NICHT-BLOCKIEREND zu empfangen.
      zmq::message_t request;
      auto received = m_ptZmqSocket->recv(request, zmq::recv_flags::dontwait);

      // 2. Prüfe, ob eine Nachricht empfangen wurde.
      // `received` ist ein std::optional. Es hat nur dann einen Wert, wenn recv erfolgreich war.
      if (received.has_value() && received.value() > 0) {
         // Eine Nachricht wurde empfangen, verarbeite sie.
         json command = json::parse(request.to_string());
         Real fLeftSpeed = command.value("left_speed", 0.0);
         Real fRightSpeed = command.value("right_speed", 0.0);
         m_pcWheels->SetLinearVelocity(fLeftSpeed, fRightSpeed);

         json response;
         response["status"] = "ok";
         m_ptZmqSocket->send(zmq::buffer(response.dump()), zmq::send_flags::none);
      }
      // 3. Wenn keine Nachricht empfangen wurde, tue nichts und gib die Kontrolle sofort an ARGoS zurück.
      // Das verhindert das Einfrieren der Simulation.

   } catch(json::parse_error& ex) {
      LOGERR << " JSON parse error: " << ex.what() << std::endl;
      json error_response;
      error_response["status"] = "error";
      error_response["message"] = "Invalid JSON format";
      m_ptZmqSocket->send(zmq::buffer(error_response.dump()), zmq::send_flags::none);
   } catch(zmq::error_t& ex) {
      // Ignoriere "Resource temporarily unavailable"-Fehler, die bei dontwait normal sind.
      if (ex.num()!= ETIMEDOUT && ex.num()!= EAGAIN) {
         LOGERR << " ZeroMQ error: " << ex.what() << std::endl;
      }
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