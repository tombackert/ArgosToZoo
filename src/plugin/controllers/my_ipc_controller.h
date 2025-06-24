#ifndef MY_IPC_CONTROLLER_H
#define MY_IPC_CONTROLLER_H

// ARGoS headers
#include <argos3/core/control_interface/ci_controller.h>
#include <argos3/plugins/robots/generic/control_interface/ci_differential_steering_actuator.h>

// ZeroMQ header (C++ wrapper)
#include <zmq.hpp>

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

private:
    /* Pointer to the wheel actuator */
    CCI_DifferentialSteeringActuator* m_pcWheels;

    // ZeroMQ members
    zmq::context_t* m_ptZmqContext;
    zmq::socket_t* m_ptZmqSocket;

    // Communication port
    std::string m_sPort;
};

#endif