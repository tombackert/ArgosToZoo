#include "my_ipc_controller.h"
#include <argos3/core/utility/logging/argos_log.h>


CMyIPCController::CMyIPCController() :
   m_pcWheels(NULL),
   m_pcProximity(NULL),
   m_sCurrentAction("stop") {}

/*
 * Initialization method.
 */
void CMyIPCController::Init(TConfigurationNode& t_node) {
   LOG << "[DEBUG] CMyIPCController::Init()" << std::endl;
   try {
      m_pcWheels = GetActuator<CCI_DifferentialSteeringActuator>("differential_steering");
      m_pcProximity = GetSensor<CCI_FootBotProximitySensor>("footbot_proximity");
      
   } catch(CARGoSException& ex) {
      THROW_ARGOSEXCEPTION_NESTED("Error initializing CMyIPCController", ex);
   }
}

/*
 * The main logic loop.
 * This method is called once per simulation step. It checks the current action and sets the wheel velocities accordingly.
 * Supported actions are "left_speed", "right_speed", and "stop".
 */
void CMyIPCController::ControlStep() {
   LOG << "[DEBUG] MyIPCController::ControlStep()" << std::endl;
   LOG << "[ACTION] MyIPCController::ControlStep() Action: " << m_sCurrentAction << std::endl;
   if (m_sCurrentAction == "left_speed") {
      m_pcWheels->SetLinearVelocity(-5.0f, 5.0f); // left
   } else if (m_sCurrentAction == "right_speed") {
      m_pcWheels->SetLinearVelocity(5.0f, -5.0f); // right
   } else if (m_sCurrentAction == "forward_speed") {
      m_pcWheels->SetLinearVelocity(5.0f, 5.0f); // forward
   } else if (m_sCurrentAction == "backward_speed") {
      m_pcWheels->SetLinearVelocity(-5.0f, -5.0f); // backward
   } else if (m_sCurrentAction == "stop") {
      m_pcWheels->SetLinearVelocity(0.0f, 0.0f); // stop
   } else { 
      m_pcWheels->SetLinearVelocity(0.0f, 0.0f); // Unknown action -> stop robot
      LOGERR << "[WARNING] Unknown action: " << m_sCurrentAction << ". Setting wheels to stop.." << std::endl;
   }
}

/*
 * Reset method. Resets the current action to "stop".
 */
void CMyIPCController::Reset() {
   LOG << "[DEBUG] MyIPCController::Reset()" << std::endl;
   m_sCurrentAction = "stop";
   LOG << "[INFO] MyIPCController reseted." << std::endl;
}

/*
 * Destroy method.
 */
void CMyIPCController::Destroy() {
  LOG << "[INFO] MyIPCController destroyed." << std::endl;
}

/*
 * Sets the action command for the robot.
 * This method is used to set the current action based on a command string.
 */
void CMyIPCController::SetAction(const std::string& action_command) {
   LOG << "[DEBUG] MyIPCController::SetAction()" << std::endl;
   m_sCurrentAction = action_command;
   LOG << "[DEBUG] Action set to: " << m_sCurrentAction << std::endl;
}

/*
 * Gets the current observation of the robot.
 * This method returns a JSON object containing the current state of the robot.
 */
json CMyIPCController::GetObservation() {
   LOG << "[DEBUG] MyIPCController::GetObservation()" << std::endl;
   const auto& tReadings = m_pcProximity->GetReadings();
   json observation;
   std::vector<double> readings_vector;
   for (size_t i = 0; i < tReadings.size(); ++i) {
       readings_vector.push_back(tReadings[i].Value);
   }
   observation["proximity"] = readings_vector;
   //LOG << "[INFO] MyIPCController observation: " << observation.dump() << std::endl;
   return observation;
}

/*
 * The macro REGISTER_CONTROLLER binds the C++ class CMyIPCController to the
 * string identifier "my_ipc_controller"
 */
REGISTER_CONTROLLER(CMyIPCController, "my_ipc_controller")