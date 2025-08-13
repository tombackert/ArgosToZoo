/*
* Problems to fix:
* - Connection wird nicht richtig gehalten
* - Reset wird nicht korrekt gemacht
* - Experiment kann derzeit nicht pausiert, gestoppt oder geresetet werden
*/






#include "zoo_loop_functions.h"
#include <argos3/core/simulator/simulator.h>
#include <argos3/core/utility/logging/argos_log.h>
#include <iostream>

CZooLoopFunctions::CZooLoopFunctions() :
    m_ptZmqContext(nullptr),
    m_ptZmqSocket(nullptr) {}

CZooLoopFunctions::~CZooLoopFunctions() {
    Reset();
}

void CZooLoopFunctions::Init(TConfigurationNode& t_node) {
    LOG << "[DEBUG] CZooLoopFunctions::Init()" << std::endl;
    // 1. ZeroMQ Server initialisieren
    m_ptZmqContext = new zmq::context_t(1);
    m_ptZmqSocket = new zmq::socket_t(*m_ptZmqContext, ZMQ_REP);
    
    // Timeout-Werte für den Socket setzen
    // Deterministic stepping: we block at the end of each simulation step until
    // the Python side provides the next command. Therefore we use a blocking
    // receive (no timeout) on the REP socket.
    int recv_timeout = -1; // blocking
    m_ptZmqSocket->set(zmq::sockopt::rcvtimeo, recv_timeout);
    
    try {
        m_ptZmqSocket->bind("tcp://*:5555");
        LOG << "[INFO] ZooLoopFunctions::Init(): ZMQ server bound to tcp://*:5555" << std::endl;
        
        // Warte auf die erste Anfrage vom Client, um den REP-Socket zu initialisieren
        LOG << "[INFO] ZooLoopFunctions::Init(): Waiting for initial connection from Python client..." << std::endl;
        // Nicht blockierend auf erste Nachricht warten - wird in PostStep behandelt
    } catch(zmq::error_t& ex) {
        THROW_ARGOSEXCEPTION("ZMQ error: " << ex.what());
    }

    // 2. Alle Roboter-Controller sammeln
    CSpace::TMapPerType& m_cFootbots = GetSpace().GetEntitiesByType("foot-bot");
    for (auto const& [key, val] : m_cFootbots) {
        CFootBotEntity* pcFootBot = any_cast<CFootBotEntity*>(val);
        CMyIPCController& cController = dynamic_cast<CMyIPCController&>(pcFootBot->GetControllableEntity().GetController());
        m_vecControllers.push_back(&cController);
    }
    LOG << "[INFO] ZooLoopFunctions::Init(): Found and stored " << m_vecControllers.size() << " controllers." << std::endl;
    // Initialize last positions vector
    m_vecLastPositions.resize(m_vecControllers.size(), CVector3());
    m_bFirstStep = true;
}

void CZooLoopFunctions::PreStep() {
    LOG << "[DEBUG] ZooLoopFunctions::PreStep()" << std::endl;
    
    // Überprüfe ZMQ-Verbindung
    if (m_ptZmqSocket) {
        int events = 0;
        size_t events_size = sizeof(events);
        
        try {
            // Verwende die ZMQ C-API direkt für die Verbindungsprüfung
            zmq_getsockopt(m_ptZmqSocket->handle(), ZMQ_EVENTS, &events, &events_size);
            bool is_connected = (events & ZMQ_POLLOUT) != 0;
            LOG << "[INFO] ZooLoopFunctions::PreStep(): ZMQ Connection status: " << (is_connected ? "Connected" : "Disconnected") << std::endl;
        } catch (const zmq::error_t& e) {
            LOGERR << "[ERROR] ZooLoopFunctions::PreStep(): ZMQ connection check failed: " << e.what() << std::endl;
        }
    } else {
        LOGERR << "[ERROR] ZooLoopFunctions::PreStep(): ZMQ socket is not initialized" << std::endl;
    }
    
    // 3. Aktionen an die Controller verteilen
    
    // Prüfe die korrekte JSON-Struktur: command->step->payload->actions
    if (m_jActions.contains("payload") && m_jActions["payload"].contains("actions")) {
        const auto& actions = m_jActions["payload"]["actions"];
        //LOG << "[DEBUG] m_jActions: " << m_jActions.dump() << std::endl;
        LOG << "[INFO] Actions: " << actions.dump() << std::endl;
        
        for (size_t i = 0; i < m_vecControllers.size(); ++i) {
            std::string agent_id = "robot_" + std::to_string(i);
            if (actions.contains(agent_id)) {
                std::string command = actions[agent_id];
                LOG << "[INFO] ZooLoopFunctions::PreStep(): Setting action for " << agent_id << ": " << command << std::endl;
                m_vecControllers[i]->SetAction(command);
            }
        }
    } else {
        LOG << "[WARNING] No actions found in m_jActions payload, skipping controller updates." << std::endl;
    }
}

void CZooLoopFunctions::PostStep() {
    LOG << "[DEBUG] CZooLoopFunctions::PostStep()" << std::endl;

    // Collect observations (includes positions) for the step that just finished.
    json observations = CollectObservations();
    // Compute rewards
    // Reward design (FUP-05):
    //   For each agent i at timestep t>0 we compute:
    //       progress_i = euclidean_distance( (x_t, y_t), (x_{t-1}, y_{t-1}) )
    //       collision_proxy_i = max(proximity_readings_i)
    //       reward_i = progress_i - 0.5 * collision_proxy_i
    //   Rationale:
    //     - progress encourages forward (any) movement in the plane
    //     - max proximity rises when near obstacles -> subtraction discourages collisions / crowding
    //     - weight 0.5 is an initial heuristic chosen to ensure early variance without dominating progress
    //   First step after reset uses reward 0.0 (no previous position baseline). Future tuning / shaping
    //   (e.g. goal seeking, energy penalties) can extend this formula while keeping the interface stable.
    json rewards_json;
    if (m_bFirstStep) {
        // First step: reward = 0, set baseline positions
        for (size_t i = 0; i < m_vecControllers.size(); ++i) {
            std::string agent_id = "robot_" + std::to_string(i);
            rewards_json[agent_id] = 0.0;
            // baseline stored inside CollectObservations already
        }
        m_bFirstStep = false;
    } else {
        for (size_t i = 0; i < m_vecControllers.size(); ++i) {
            std::string agent_id = "robot_" + std::to_string(i);
            // Distance moved in XY plane since last step
            CVector3 lastPos = m_vecLastPositions[i];
            CVector3 curPos;
            curPos.SetX(observations["observations"][agent_id]["position"][0].get<double>());
            curPos.SetY(observations["observations"][agent_id]["position"][1].get<double>());
            // forward progress magnitude
            Real dx = curPos.GetX() - lastPos.GetX();
            Real dy = curPos.GetY() - lastPos.GetY();
            Real dist = std::sqrt(dx*dx + dy*dy);
            // collision proxy: max proximity reading
            Real maxProx = 0.0;
            for (const auto& v : observations["observations"][agent_id]["proximity"]) {
                maxProx = std::max(maxProx, v.get<double>());
            }
            // Reward heuristic: progress - collision_penalty
            Real reward = dist - 0.5 * maxProx; // weight collision penalty
            rewards_json[agent_id] = reward;
        }
    }

    try {
        // Deterministic synchronization: block until the Python client sends the next
        // command (step/reset/close). For a normal 'step' the actions will be applied
        // in the NEXT simulation tick (1-step latency), which keeps protocol simple.
        m_jActions = ReceiveRequest(); // blocking (recv)
        LOG << "[DEBUG] Received command: " << (m_jActions.contains("command") ? m_jActions["command"].dump() : "<none>") << std::endl;

        // Handle reset BEFORE sending observations so that reset requests receive
        // post-reset observations (fresh state) deterministically.
        if (m_jActions.contains("command")) {
            std::string cmd = m_jActions["command"].get<std::string>();
            if (cmd == "reset") {
                LOG << "[DEBUG] Processing reset command (synchronous)." << std::endl;
                CSimulator::GetInstance().Reset();
                // After reset collect fresh observations (initial state)
                observations = CollectObservations();
            } else if (cmd == "close") {
                LOG << "[DEBUG] Processing close command." << std::endl;
                // We still send current observations; Python will close afterwards.
            }
        }

    // Attach rewards
    observations["rewards"] = rewards_json;
    // Send response with observations + rewards (send)
    SendResponse(observations);
        LOG << "[DEBUG] Sent observations (size=" << observations.dump().size() << ")" << std::endl;
    } catch (const zmq::error_t& e) {
        LOGERR << "[ERROR] PostStep() ZeroMQ error: " << e.what() << std::endl;
    } catch (const std::exception& e) {
        LOGERR << "[ERROR] PostStep() Exception: " << e.what() << std::endl;
    }
}

void CZooLoopFunctions::Reset() {
    //LOG << "[DEBUG] ZooLoopFunctions::Reset()" << std::endl;
    // Alle Controller zurücksetzen
    for (CMyIPCController* pcController : m_vecControllers) {
        pcController->Reset();
    }
    
    // Initialzustand herstellen, aber noch nicht senden (warten auf Anfrage)
    json observations = CollectObservations();
    LOG << "[INFO] ZooLoopFunctions::Reset(). Observations collected and ready to send on next request." << std::endl;
    
    // Warten auf die nächste Anfrage vom Client wird in PostStep behandelt
    // Keine Antwort ohne vorherige Anfrage senden (REP-Socket Regel)
}

void CZooLoopFunctions::Destroy() {
    try {
        if (m_ptZmqSocket) {
            m_ptZmqSocket->close();
            delete m_ptZmqSocket;
            m_ptZmqSocket = nullptr;
        }
        if (m_ptZmqContext) {
            m_ptZmqContext->close();
            delete m_ptZmqContext;
            m_ptZmqContext = nullptr;
        }
        LOGERR << "[INFO] ZooLoopFunctions: ZMQ resources cleaned up successfully" << std::endl;
    } catch (const std::exception& e) {
        LOGERR << "[ERROR] Error during ZooLoopFunctions cleanup: " << e.what() << std::endl;
    }
}

json CZooLoopFunctions::CollectObservations() {
    //LOG << "[DEBUG] ZooLoopFunctions::CollectObservations()" << std::endl;
    json observations;
    for (size_t i = 0; i < m_vecControllers.size(); ++i) {
        std::string agent_id = "robot_" + std::to_string(i);
        json obs = m_vecControllers[i]->GetObservation();
        // Add position (x,y,z) of foot-bot
        // Access entity again for position
        // We can access via controller pointer -> get parent entity name? Simpler: fetch entity list again
        try {
            CSpace::TMapPerType& m_cFootbots = GetSpace().GetEntitiesByType("foot-bot");
            auto it = m_cFootbots.begin();
            size_t idx = 0;
            for (; it != m_cFootbots.end(); ++it, ++idx) {
                if (idx == i) {
                    CFootBotEntity* pcFootBot = any_cast<CFootBotEntity*>(it->second);
                    const CVector3& pos = pcFootBot->GetEmbodiedEntity().GetOriginAnchor().Position;
                    obs["position"] = { pos.GetX(), pos.GetY(), pos.GetZ() };
                    // Update last positions buffer after using old value (handled in reward computation)
                    m_vecLastPositions[i] = pos;
                    break;
                }
            }
        } catch(const std::exception&){ /* ignore */ }
        observations[agent_id] = obs;
    }
    json response;
    //LOG << "[DEBUG] Observations: " << observations.dump() << std::endl;
    response["observations"] = observations;
    return response;
}

void CZooLoopFunctions::SendResponse(const json& j_response) {
    //LOG << "[DEBUG] ZooLoopFunctions::SendResponse()" << std::endl;
    //LOG << "[DEBUG] Response: " << j_response.dump() << std::endl;
    std::string response_str = j_response.dump();
    m_ptZmqSocket->send(zmq::buffer(response_str), zmq::send_flags::none);
}

json CZooLoopFunctions::ReceiveRequest() {
    zmq::message_t request;
    auto received = m_ptZmqSocket->recv(request, zmq::recv_flags::none); // Blockierend, aber mit Timeout dank sockopt::rcvtimeo
    LOG << "[DEBUG] ZooLoopFunctions::ReceiveRequest(), received bytes: " << (received.has_value() ? std::to_string(received.value()) : "none") << std::endl;
    if (received.has_value() && received.value() > 0) {
        try {
            return json::parse(request.to_string());
        } catch (const json::parse_error& e) {
            LOGERR << "[ERROR] Failed to parse JSON from request: " << e.what() << std::endl;
        }
    }
    return json();
}

REGISTER_LOOP_FUNCTIONS(CZooLoopFunctions, "zoo_loop_functions");