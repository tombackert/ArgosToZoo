#include "my_ipc_controller.h"

#include <argos3/core/utility/logging/argos_log.h>

#include <algorithm>

/* Helper: map string env/config to log level */
static CMyIPCController::ELogLevel ControllerDefaultLogLevel() {
    const char* env = std::getenv("ARGOS_CONTROLLER_LOG_LEVEL");
    if (!env) return CMyIPCController::ELogLevel::INFO;
    std::string s(env);
    std::transform(s.begin(), s.end(), s.begin(), ::toupper);
    if (s == "DEBUG") return CMyIPCController::ELogLevel::DEBUG;
    if (s == "WARN") return CMyIPCController::ELogLevel::WARN;
    if (s == "ERROR") return CMyIPCController::ELogLevel::ERROR;
    return CMyIPCController::ELogLevel::INFO;
}

CMyIPCController::CMyIPCController()
    : m_pcWheels(NULL),
      m_pcProximity(NULL),
      m_sCurrentAction("stop"),
      m_sLastAppliedAction("stop"),
      m_eLogLevel(ControllerDefaultLogLevel()) {
}

void CMyIPCController::CppLog(ELogLevel lvl, const std::string& msg) const {
    if (!Enabled(lvl)) return;
    switch (lvl) {
        case ELogLevel::DEBUG:
            LOG << "[DBG] " << msg << std::endl;
            break;
        case ELogLevel::INFO:
            LOG << msg << std::endl;
            break;
        case ELogLevel::WARN:
            LOGERR << "[WARN] " << msg << std::endl;
            break;
        case ELogLevel::ERROR:
            LOGERR << "[ERR] " << msg << std::endl;
            break;
    }
}

/*
 * Initialization method.
 */
void CMyIPCController::Init(TConfigurationNode& t_node) {
    CppLog(ELogLevel::DEBUG, "Init()");
    try {
        m_pcWheels = GetActuator<CCI_DifferentialSteeringActuator>(
            "differential_steering");
        m_pcProximity =
            GetSensor<CCI_FootBotProximitySensor>("footbot_proximity");

    } catch (CARGoSException& ex) {
        THROW_ARGOSEXCEPTION_NESTED("Error initializing CMyIPCController", ex);
    }
}

/*
 * The main logic loop.
 * This method is called once per simulation step. It checks the current action
 * and sets the wheel velocities accordingly. Supported actions are
 * "left_speed", "right_speed", and "stop".
 */
void CMyIPCController::ControlStep() {
    // Only log action changes (reduces per-step noise)
    if (m_sCurrentAction != m_sLastAppliedAction) {
        CppLog(ELogLevel::DEBUG, std::string("Action -> ") + m_sCurrentAction);
        m_sLastAppliedAction = m_sCurrentAction;
    }
    if (m_sCurrentAction == "left_speed") {
        m_pcWheels->SetLinearVelocity(-20.0f, 20.0f);  // left
    } else if (m_sCurrentAction == "right_speed") {
        m_pcWheels->SetLinearVelocity(20.0f, -20.0f);  // right
    } else if (m_sCurrentAction == "forward_speed") {
        m_pcWheels->SetLinearVelocity(20.0f, 20.0f);  // forward
    } else if (m_sCurrentAction == "backward_speed") {
        m_pcWheels->SetLinearVelocity(-20.0f, -20.0f);  // backward
    } else if (m_sCurrentAction == "stop") {
        m_pcWheels->SetLinearVelocity(0.0f, 0.0f);  // stop
    } else {
        m_pcWheels->SetLinearVelocity(0.0f,
                                      0.0f);  // Unknown action -> stop robot
        CppLog(ELogLevel::WARN,
               std::string("Unknown action: ") + m_sCurrentAction + "; stop()");
    }
}

/*
 * Reset method. Resets the current action to "stop".
 */
void CMyIPCController::Reset() {
    CppLog(ELogLevel::DEBUG, "Reset()");
    m_sCurrentAction = "stop";
    m_sLastAppliedAction = "stop";
    CppLog(ELogLevel::INFO, "Controller reset");
}

/*
 * Destroy method.
 */
void CMyIPCController::Destroy() {
    CppLog(ELogLevel::INFO, "Controller destroyed");
}

/*
 * Sets the action command for the robot.
 * This method is used to set the current action based on a command string.
 */
void CMyIPCController::SetAction(const std::string& action_command) {
    if (action_command != m_sCurrentAction) {
        m_sCurrentAction = action_command;
    }
}

/*
 * Gets the current observation of the robot.
 * This method returns a JSON object containing the current state of the robot.
 */
json CMyIPCController::GetObservation() {
    const auto& tReadings = m_pcProximity->GetReadings();
    json observation;
    std::vector<double> readings_vector;
    for (size_t i = 0; i < tReadings.size(); ++i) {
        readings_vector.push_back(tReadings[i].Value);
    }
    observation["proximity"] = readings_vector;
    return observation;
}

/*
 * The macro REGISTER_CONTROLLER binds the C++ class CMyIPCController to the
 * string identifier "my_ipc_controller"
 */
REGISTER_CONTROLLER(CMyIPCController, "my_ipc_controller")