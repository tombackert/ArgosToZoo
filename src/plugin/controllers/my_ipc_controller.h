#ifndef MY_IPC_CONTROLLER_H
#define MY_IPC_CONTROLLER_H

// ARGoS headers
#include <argos3/core/control_interface/ci_controller.h>
#include <argos3/plugins/robots/generic/control_interface/ci_differential_steering_actuator.h>
#include <argos3/plugins/robots/foot-bot/control_interface/ci_footbot_proximity_sensor.h>


// JSON header
#include "../common/json.hpp"

using namespace argos;
using json = nlohmann::json;


/*
 * The controller class definition.
 * It inherits from CCI_Controller.
 */
class CMyIPCController : public CCI_Controller {

public:
    /* Class constructor */
    CMyIPCController();

    /* Class destructor */
    virtual ~CMyIPCController() {}

    /*
     * Initialization method.
     * It is called once when the controller is assigned to a robot.
     */
    virtual void Init(TConfigurationNode& t_node);

    /*
     * The main control loop of the controller.
     * It is called once per simulation step.
     */
    virtual void ControlStep();

    /*
     * Resets the internal state of the controller.
     * It is called when the reset button is pressed in the GUI.
     */
    virtual void Reset();

    /*
     * Cleanup method.
     * It is called when the controller is destroyed (e.g., at the end of an experiment).
     */
    virtual void Destroy();

    /*
     * Sets the action command for the robot.
     * This method is used to set the current action based on a command string.
     */
    void SetAction(const std::string& action_command);

    /*
     * Gets the current observation of the robot.
     * This method returns a JSON object containing the current state of the robot.
     */
    json GetObservation();

private:
    /* Pointer to the wheel actuator */
    CCI_DifferentialSteeringActuator* m_pcWheels;

    /* Pointer to the proximity sensor */
    CCI_FootBotProximitySensor* m_pcProximity;

    /* Holds the current action*/
    std::string m_sCurrentAction;
};

#endif