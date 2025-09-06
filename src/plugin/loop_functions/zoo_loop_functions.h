#ifndef ZOO_LOOP_FUNCTIONS_H
#define ZOO_LOOP_FUNCTIONS_H

// Argos headers
#include <argos3/core/simulator/loop_functions.h>
#include <argos3/plugins/robots/foot-bot/simulator/footbot_entity.h>

// ZeroMQ headers
#include <zmq.hpp>

// Local headers
#include "../common/json.hpp"
#include "my_ipc_controller.h"

using namespace argos;
using json = nlohmann::json;

class CZooLoopFunctions : public CLoopFunctions {
public:
    enum class ELogLevel { DEBUG = 0, INFO = 1, WARN = 2, ERROR = 3 };
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
     * It sets up the ZeroMQ context and socket, and initializes the
     * controllers.
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
    /* Randomize starting positions/orientations with min separation */
    void RandomizeStartPositions();
    Real m_fMinSeparation = 0.2f;         // meters (center-to-center)
    bool m_bPositionsRandomized = false;  // guard to avoid double-randomization
                                          // within same Init/Reset frame
    /* Logging helpers */
    void LoopLog(ELogLevel lvl, const std::string& msg) const;
    bool Enabled(ELogLevel lvl) const {
        return static_cast<int>(lvl) >= static_cast<int>(m_eLogLevel);
    }
    static ELogLevel EnvDefaultLogLevel();

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

    /* Internal state (no task-specific reward logic; Python owns MARL) */
    std::vector<CVector3>
        m_vecLastPositions;    // retained only if future kinematics needed
    bool m_bFirstStep = true;  // legacy flag (can be removed later)
    ELogLevel m_eLogLevel;
    // Connection state tracking for clearer ZMQ status logs
    bool m_bSawFirstRequest = false;  // true after first successful recv
    bool m_bHadPendingReply = false;  // last tick had POLLOUT (ready to send)
    std::size_t m_unConsecutiveIdle = 0;  // counts ticks without pending reply
    std::size_t m_unTotalRequests =
        0;  // successfully received (parsed) requests
    std::size_t m_unTotalReplies = 0;  // responses sent
};

#endif