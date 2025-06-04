#ifndef ZEROMQ_BRIDGE_LOOP_FUNC_H
#define ZEROMQ_BRIDGE_LOOP_FUNC_H

#include <argos3/core/simulator/loop_functions.h>
#include <argos3/core/utility/configuration/argos_configuration.h>
#include <argos3/core/utility/logging/argos_log.h> // For ARGoS logging
#include <argos3/core/simulator/space/space.h>
#include <argos3/plugins/robots/foot-bot/simulator/footbot_entity.h> 

#include <zmq.hpp> // For cppzmq
#include "nlohmann/json.hpp" // For JSON serialization/deserialization

#include <string>
#include <vector>
#include <map>

// Use the argos namespace to avoid typing argos:: repeatedly
using namespace argos;
// Use nlohmann::json with a shorter alias
using json = nlohmann::json;

class CZeroMQBridgeLoopFunc : public CLoopFunctions {

public:
    CZeroMQBridgeLoopFunc();
    virtual ~CZeroMQBridgeLoopFunc();

    virtual void Init(TConfigurationNode& t_node);
    virtual void Reset();
    virtual void Destroy();
    virtual void PostStep();
    // virtual void PreStep(); // Uncomment if needed
    // virtual bool IsExperimentFinished(); // Uncomment if custom finish conditions are needed
    // virtual void PostExperiment(); // Uncomment if needed

private:
    // ZeroMQ members
    zmq::context_t* m_pzmqContext;
    zmq::socket_t* m_pzmqServerSocket;
    int m_nZmqPort;

    // Helper methods for processing requests from Python
    json ProcessGetSimulationTime();
    json ProcessGetAllRobotIds();
    json ProcessGetRobotState(const json& request_json);
    json ProcessGetAllRobotStates();
    // Add more command processors as needed

    // Helper to safely get a robot's embodied entity
    CEmbodiedEntity* GetRobotEmbodiedEntity(const std::string& robot_id);
};

#endif // ZEROMQ_BRIDGE_LOOP_FUNC_H