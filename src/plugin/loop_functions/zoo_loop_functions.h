#ifndef ZOO_LOOP_FUNCTIONS_H
#define ZOO_LOOP_FUNCTIONS_H

// Argos headers
#include <argos3/core/simulator/loop_functions.h>
#include <argos3/plugins/robots/foot-bot/simulator/footbot_entity.h>

// ZeroMQ headers
#include <zmq.hpp>

// Local headers
#include "my_ipc_controller.h" 

#include "../common/json.hpp"

using namespace argos;
using json = nlohmann::json;

class CZooLoopFunctions : public CLoopFunctions {

public:
    /**
     * Constructor
     * Initializes ZeroMQ context and socket.
     */
    CZooLoopFunctions();

    /**
     * Destructor
     * Cleans up ZeroMQ context and socket.
     */
    virtual ~CZooLoopFunctions();

    /**
     * Initializes the loop functions.
     * This method is called once at the beginning of the simulation.
     * It sets up the ZeroMQ context and socket, and initializes the controllers.
     */
    virtual void Init(TConfigurationNode& t_node);

    /**
     * Main control loop of the simulation.
     * This method is called once per simulation step.
     * It collects observations, receives requests, and sends responses.
     */
    virtual void PreStep();

    /**
     * Post-step method.
     * This method is called after the main control loop.
     * It can be used for any cleanup or finalization tasks.
     */
    virtual void PostStep();

    /**
     * Resets the loop functions.
     * This method is called when the reset button is pressed in the GUI.
     * It resets the ZeroMQ context and socket, and clears the controllers.
     */
    virtual void Reset();

    /**
     * Destroys the loop functions.
     * This method is called when the simulation ends.
     * It cleans up the ZeroMQ context and socket, and destroys the controllers.
     */
    virtual void Destroy();

private:
    /* ZeroMQ context and socket */
    zmq::context_t* m_ptZmqContext;
    zmq::socket_t* m_ptZmqSocket;

    /* Vector of controllers */
    std::vector<CMyIPCController*> m_vecControllers;

    /* Action commands communicated via ZeroMQ */
    json m_jActions;

    /* Helper methods for ZeroMQ communication */
    json CollectObservations();
    void SendResponse(const json& j_response);
    json ReceiveRequest();

    /* Internal state for reward calculation */
    std::vector<CVector3> m_vecLastPositions; // previous step positions
    bool m_bFirstStep = true;
};

#endif