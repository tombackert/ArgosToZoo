#include "my_ipc_controller.h"
#include <argos3/core/utility/logging/argos_log.h>


CMyIPCController::CMyIPCController() :
   m_pcWheels(NULL),
   m_ptZmqContext(NULL),
   m_ptZmqSocket(NULL),
   m_sPort("5555") {}

/*
 * Initialization method.
 */
void CMyIPCController::Init(TConfigurationNode& t_node) {
   try {
      m_pcWheels = GetActuator<CCI_DifferentialSteeringActuator>("differential_steering");

      // Read the port from the <params> section of the XML file.
      // If not present, the default value "5555" is used.
      GetNodeAttributeOrDefault(t_node, "port", m_sPort, m_sPort);

      // Initialize ZeroMQ
      m_ptZmqContext = new zmq::context_t(1);
      m_ptZmqSocket = new zmq::socket_t(*m_ptZmqContext, ZMQ_REP);

      // Bind the socket to the dynamic address
      std::string strBindAddr = "tcp://*:" + m_sPort;
      m_ptZmqSocket->bind(strBindAddr);
      LOG << "[INFO] IPC Controller initialized and bound to " << strBindAddr << std::endl;

   } catch(CARGoSException& ex) {
      THROW_ARGOSEXCEPTION_NESTED("Error initializing CMyIPCController", ex);
   } catch(zmq::error_t& ex) {
      THROW_ARGOSEXCEPTION("ZeroMQ error: " << ex.what());
   }
}

/*
 * The main logic loop.
 */
void CMyIPCController::ControlStep() {
   try {
      // Try to receive a message in a non-blocking way.
      zmq::message_t request;
      auto received = m_ptZmqSocket->recv(request, zmq::recv_flags::dontwait);

      // Check if a message was received.
      // `received` is an std::optional and has a value only if recv was successful.
      if (received.has_value() && received.value() > 0) {
         // A message was received, process it.
         json command = json::parse(request.to_string());
         Real fLeftSpeed = command.value("left_speed", 0.0);
         Real fRightSpeed = command.value("right_speed", 0.0);
         m_pcWheels->SetLinearVelocity(fLeftSpeed, fRightSpeed);

         json response;
         response["status"] = "ok";
         m_ptZmqSocket->send(zmq::buffer(response.dump()), zmq::send_flags::none);
      }
      // If no message was received, do nothing and return control to ARGoS.
      // This prevents the simulation from freezing.

   } catch(json::parse_error& ex) {
      LOGERR << " JSON parse error: " << ex.what() << std::endl;
      json error_response;
      error_response["status"] = "error";
      error_response["message"] = "Invalid JSON format";
      m_ptZmqSocket->send(zmq::buffer(error_response.dump()), zmq::send_flags::none);
   } catch(zmq::error_t& ex) {
      // Ignore "Resource temporarily unavailable" errors, which are expected with non-blocking sockets.
      if (ex.num()!= ETIMEDOUT && ex.num()!= EAGAIN) {
         LOGERR << " ZeroMQ error: " << ex.what() << std::endl;
      }
   }
}

/*
 * Reset method.
 */
void CMyIPCController::Reset() {
   // Nothing to reset in this simple controller.
}

/*
 * Destroy method.
 */
void CMyIPCController::Destroy() {
   // Clean up ZeroMQ resources
   if (m_ptZmqSocket) {
      m_ptZmqSocket->close();
      delete m_ptZmqSocket;
  }
  if (m_ptZmqContext) {
      m_ptZmqContext->close();
      delete m_ptZmqContext;
  }
  LOG << "[INFO] IPC Controller destroyed." << std::endl;
}

/*
 * The macro REGISTER_CONTROLLER binds the C++ class CMyIPCController to the
 * string identifier "my_ipc_controller"
 */
REGISTER_CONTROLLER(CMyIPCController, "my_ipc_controller")