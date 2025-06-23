#include <argos3/plugins/robots/foot-bot/simulator/footbot_entity.h>
#include "zb_loop_func.h"

CZeroMQBridgeLoopFunc::CZeroMQBridgeLoopFunc() :
    m_pzmqContext(nullptr),
    m_pzmqServerSocket(nullptr),
    m_nZmqPort(5555) // Default port, can be overridden by XML
{}

CZeroMQBridgeLoopFunc::~CZeroMQBridgeLoopFunc() {
    // Destroy() should handle cleanup, but as a fallback:
    if (m_pzmqServerSocket) {
        m_pzmqServerSocket->close();
        delete m_pzmqServerSocket;
    }
    if (m_pzmqContext) {
        delete m_pzmqContext;
    }
}

void CZeroMQBridgeLoopFunc::Init(TConfigurationNode& t_node) {
    try {
        // Parse parameters from the .argos file
        TConfigurationNode& tParams = GetNode(t_node, "params");
        GetNodeAttributeOrDefault(tParams, "zmq_port", m_nZmqPort, m_nZmqPort);

        // Initialize ZeroMQ context and server socket
        m_pzmqContext = new zmq::context_t(1); // 1 I/O thread
        m_pzmqServerSocket = new zmq::socket_t(*m_pzmqContext, zmq::socket_type::rep);

        std::string bind_addr = "tcp://*:" + std::to_string(m_nZmqPort);
        m_pzmqServerSocket->bind(bind_addr.c_str());

        LOG << " Server initialized and bound to " << bind_addr << std::endl;

    } catch (CARGoSException& ex) {
        THROW_ARGOSEXCEPTION_NESTED("Error initializing ZeroMQ bridge loop functions", ex);
    } catch (zmq::error_t& e) {
        THROW_ARGOSEXCEPTION("ZeroMQ Error during Init: " << e.what() << " (Error Code: " << e.num() << ")");
    }
}

void CZeroMQBridgeLoopFunc::Reset() {
    LOG << " Reset called." << std::endl;
    // Reset any custom state if necessary
}

void CZeroMQBridgeLoopFunc::Destroy() {
    LOG << " Destroying server..." << std::endl;
    if (m_pzmqServerSocket) {
        try {
            m_pzmqServerSocket->close();
        } catch (zmq::error_t& e) {
            LOGERR << " ZeroMQ error during socket close: " << e.what() << std::endl;
        }
        delete m_pzmqServerSocket;
        m_pzmqServerSocket = nullptr;
    }

    if (m_pzmqContext) {
        try {
        } catch (zmq::error_t& e) {
             LOGERR << " ZeroMQ error during context shutdown/close: " << e.what() << std::endl;
        }
        delete m_pzmqContext;
        m_pzmqContext = nullptr;
    }
    LOG << " Server destroyed." << std::endl;
}

void CZeroMQBridgeLoopFunc::PostStep() {
    if (!m_pzmqServerSocket) return; // Socket not initialized

    zmq::message_t request_msg;
    try {
        // Non-blocking receive
        auto recv_result = m_pzmqServerSocket->recv(request_msg, zmq::recv_flags::dontwait);

        if (recv_result && recv_result.value() > 0) {
            std::string request_str = request_msg.to_string();
            LOG << " Received request: " << request_str << std::endl;

            json request_json;
            try {
                request_json = json::parse(request_str);
            } catch (json::parse_error& e) {
                LOGERR << " JSON parse error: " << e.what() << std::endl;
                json error_response = {
                    {"status", "error"},
                    {"message", "Invalid JSON request: " + std::string(e.what())}
                };
                m_pzmqServerSocket->send(zmq::buffer(error_response.dump()), zmq::send_flags::none);
                return;
            }
            
            std::string command = request_json.value("command", "");
            json response_json;

            if (command == "GET_SIMULATION_TIME") {
                response_json = ProcessGetSimulationTime();
            } else if (command == "GET_ALL_ROBOT_IDS") {
                response_json = ProcessGetAllRobotIds();
            } else if (command == "GET_ROBOT_STATE") {
                response_json = ProcessGetRobotState(request_json);
            } else if (command == "GET_ALL_ROBOT_STATES") {
                response_json = ProcessGetAllRobotStates();
            } else {
                response_json["status"] = "error";
                response_json["message"] = "Unknown command: " + command;
                LOGERR << " Unknown command: " << command << std::endl;
            }

            std::string response_str = response_json.dump();
            m_pzmqServerSocket->send(zmq::buffer(response_str), zmq::send_flags::none);
            LOG << " Sent response: " << response_str << std::endl;
        }
        // No message received, or an error that isn't EAGAIN (which is handled by recv_result being false)
        // ZMQ_EAGAIN is normal for non-blocking, means no message pending.
    } catch (zmq::error_t& e) {
        // Only log if it's not EAGAIN, as EAGAIN is expected in non-blocking mode
        #ifdef ZMQ_EAGAIN
        int zmq_eagain = ZMQ_EAGAIN;
        #else
        int zmq_eagain = EAGAIN;
        #endif
        if (e.num() != zmq_eagain) {
            LOGERR << " ZeroMQ Error during PostStep recv/send: " << e.what() 
                   << " (Error Code: " << e.num() << ")" << std::endl;
            // Potentially try to send an error response if the error is on send,
            // but if recv failed, we might not be able to send.
            // If the socket is in a bad state, it might need to be reset or reinitialized,
            // which is complex to handle mid-simulation.
        }
    }
}

// Helper method implementations

CEmbodiedEntity* CZeroMQBridgeLoopFunc::GetRobotEmbodiedEntity(const std::string& robot_id) {
    try {
        CSpace& cSpace = GetSpace();
        // Assuming robot IDs are unique and directly usable with GetEntity.
        // If using GetEntitiesByType, you'd iterate.
        // For this example, let's assume foot-bots. This needs to be generic or configurable.
        CFootBotEntity* pcFootBot = nullptr; // Use the actual robot type used in simulation
        try {
             pcFootBot = &dynamic_cast<CFootBotEntity&>(cSpace.GetEntity(robot_id));
        } catch(CARGoSException& ex) {
            // If not a footbot, or entity not found by that ID directly
            // Try iterating through known robot types if GetEntity fails or is not appropriate
            LOGERR << " Robot with ID '" << robot_id << "' not found or not a CFootBotEntity." << std::endl;
            return nullptr;
        }
       
        if (pcFootBot) {
            return &(pcFootBot->GetEmbodiedEntity());
        }
    } catch (CARGoSException& ex) {
        LOGERR << " Error getting robot '" << robot_id << "': " << ex.what() << std::endl;
    }
    return nullptr;
}


json CZeroMQBridgeLoopFunc::ProcessGetSimulationTime() {
    json response;
    response["status"] = "success";
    response["time"] = GetSpace().GetSimulationClock();
    return response;
}

json CZeroMQBridgeLoopFunc::ProcessGetAllRobotIds() {
    json response;
    std::vector<std::string> robot_ids;
    try {
        CSpace& cSpace = GetSpace();
        // Example: Get all foot-bots. This should be generalized or configured for other robot types.
        CSpace::TMapPerType& tFootBotMap = cSpace.GetEntitiesByType("foot-bot");
        for (CSpace::TMapPerType::iterator it = tFootBotMap.begin(); it!= tFootBotMap.end(); ++it) {
            robot_ids.push_back(it->first); // it->first is the ID of the entity
        }
        response["status"] = "success";
        response["ids"] = robot_ids;
    } catch (CARGoSException& ex) {
        LOGERR << " Error getting all robot IDs: " << ex.what() << std::endl;
        response["status"] = "error";
        response["message"] = "Error retrieving robot IDs: " + std::string(ex.what());
    }
    return response;
}

json CZeroMQBridgeLoopFunc::ProcessGetRobotState(const json& request_json) {
    json response;
    std::string robot_id = request_json.value("robot_id", "");
    if (robot_id.empty()) {
        response["status"] = "error";
        response["message"] = "Missing robot_id in GET_ROBOT_STATE request";
        return response;
    }

    CEmbodiedEntity* pEmbodiedEntity = GetRobotEmbodiedEntity(robot_id);
    if (pEmbodiedEntity) {
        const CVector3& cPos = pEmbodiedEntity->GetOriginAnchor().Position;
        const CQuaternion& cOri = pEmbodiedEntity->GetOriginAnchor().Orientation;

        response["status"] = "success";
        response["robot_id"] = robot_id;
        response["position"] = {{"x", cPos.GetX()}, {"y", cPos.GetY()}, {"z", cPos.GetZ()}};
        response["orientation"] = {{"x", cOri.GetX()}, {"y", cOri.GetY()}, {"z", cOri.GetZ()}, {"w", cOri.GetW()}};
    } else {
        response["status"] = "error";
        response["message"] = "Robot with ID '" + robot_id + "' not found or has no embodied entity.";
    }
    return response;
}

json CZeroMQBridgeLoopFunc::ProcessGetAllRobotStates() {
    json response;
    json robot_states_array = json::array();
    try {
        CSpace& cSpace = GetSpace();
        CSpace::TMapPerType& tEntityMap = cSpace.GetEntitiesByType("foot-bot"); // Generalize this
        for (CSpace::TMapPerType::iterator it = tEntityMap.begin(); it!= tEntityMap.end(); ++it) {
            CEmbodiedEntity* pEmbodiedEntity = nullptr;
            CEntity* pEntity = any_cast<CEntity*>(it->second);
            CFootBotEntity* pcFootBot = dynamic_cast<CFootBotEntity*>(pEntity);
            if(pcFootBot) {
                pEmbodiedEntity = &(pcFootBot->GetEmbodiedEntity());
            }

            if (pEmbodiedEntity) {
                const CVector3& cPos = pEmbodiedEntity->GetOriginAnchor().Position;
                const CQuaternion& cOri = pEmbodiedEntity->GetOriginAnchor().Orientation;
                json single_robot_state;
                single_robot_state["robot_id"] = it->first;
                single_robot_state["position"] = {{"x", cPos.GetX()}, {"y", cPos.GetY()}, {"z", cPos.GetZ()}};
                single_robot_state["orientation"] = {{"x", cOri.GetX()}, {"y", cOri.GetY()}, {"z", cOri.GetZ()}, {"w", cOri.GetW()}};
                robot_states_array.push_back(single_robot_state);
            }
        }
        response["status"] = "success";
        response["states"] = robot_states_array;
    } catch (CARGoSException& ex) {
        LOGERR << " Error in ProcessGetAllRobotStates: " << ex.what() << std::endl;
        response["status"] = "error";
        response["message"] = "Error retrieving all robot states: " + std::string(ex.what());
    }
    return response;
}


// Register the loop functions with ARGoS
REGISTER_LOOP_FUNCTIONS(CZeroMQBridgeLoopFunc, "zeromq_bridge_loop_functions");