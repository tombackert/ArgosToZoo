/*
 * Loop functions implementation with filtered logging (FUP-10 C++ side)
 * (Previous notes: connection persistence, proper reset handling)
 */

#include "zoo_loop_functions.h"

#include <argos3/core/simulator/simulator.h>
#include <argos3/core/utility/logging/argos_log.h>

#include <algorithm>
#include <cstdlib>
#include <iostream>

// ---------------- Logging helpers -----------------
CZooLoopFunctions::ELogLevel CZooLoopFunctions::EnvDefaultLogLevel() {
    const char* env = std::getenv("ARGOS_LOOP_LOG_LEVEL");
    if (!env) return ELogLevel::INFO;
    std::string s(env);
    std::transform(s.begin(), s.end(), s.begin(), ::toupper);
    if (s == "DEBUG") return ELogLevel::DEBUG;
    if (s == "WARN") return ELogLevel::WARN;
    if (s == "ERROR") return ELogLevel::ERROR;
    return ELogLevel::INFO;
}

void CZooLoopFunctions::LoopLog(ELogLevel lvl, const std::string& msg) const {
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

// ---------------- Lifecycle -----------------
CZooLoopFunctions::CZooLoopFunctions()
    : m_ptZmqContext(nullptr),
      m_ptZmqSocket(nullptr),
      m_eLogLevel(EnvDefaultLogLevel()) {
}

CZooLoopFunctions::~CZooLoopFunctions() {
    Reset();
}

void CZooLoopFunctions::Init(TConfigurationNode& t_node) {
    LoopLog(ELogLevel::DEBUG, "Init()");
    m_ptZmqContext = new zmq::context_t(1);
    m_ptZmqSocket = new zmq::socket_t(*m_ptZmqContext, ZMQ_REP);
    int recv_timeout = -1;  // blocking read
    m_ptZmqSocket->set(zmq::sockopt::rcvtimeo, recv_timeout);
    try {
        m_ptZmqSocket->bind("tcp://*:5555");
        LoopLog(ELogLevel::INFO, "ZMQ server bound to tcp://*:5555");
        LoopLog(ELogLevel::INFO,
                "Waiting for initial connection from Python client...");
    } catch (zmq::error_t& ex) {
        THROW_ARGOSEXCEPTION("ZMQ error: " << ex.what());
    }
    // Discover controllers
    CSpace::TMapPerType& cFootbots = GetSpace().GetEntitiesByType("foot-bot");
    for (auto it = cFootbots.begin(); it != cFootbots.end(); ++it) {
        CFootBotEntity* pcFootBot = any_cast<CFootBotEntity*>(it->second);
        auto& ctrl = dynamic_cast<CMyIPCController&>(
            pcFootBot->GetControllableEntity().GetController());
        m_vecControllers.push_back(&ctrl);
    }
    LoopLog(ELogLevel::INFO, std::string("Discovered controllers: ") +
                                 std::to_string(m_vecControllers.size()));
    m_vecLastPositions.resize(m_vecControllers.size(), CVector3());
    m_bFirstStep = true;
}

void CZooLoopFunctions::PreStep() {
    LoopLog(ELogLevel::DEBUG, "PreStep()");
    if (m_ptZmqSocket) {
        int events = 0;
        size_t events_size = sizeof(events);
        try {
            zmq_getsockopt(m_ptZmqSocket->handle(), ZMQ_EVENTS, &events,
                           &events_size);
            bool is_connected = (events & ZMQ_POLLOUT) != 0;
            LoopLog(ELogLevel::DEBUG,
                    std::string("ZMQ status: ") +
                        (is_connected ? "Connected" : "Disconnected"));
        } catch (const zmq::error_t& e) {
            LoopLog(ELogLevel::ERROR,
                    std::string("ZMQ connection check failed: ") + e.what());
        }
    } else {
        LoopLog(ELogLevel::ERROR, "ZMQ socket not initialized");
    }
    // Apply pending actions (if any were received in previous PostStep)
    if (m_jActions.contains("payload") &&
        m_jActions["payload"].contains("actions")) {
        const auto& actions = m_jActions["payload"]["actions"];
        if (Enabled(ELogLevel::DEBUG))
            LoopLog(ELogLevel::DEBUG,
                    std::string("Actions payload: ") + actions.dump());
        for (size_t i = 0; i < m_vecControllers.size(); ++i) {
            std::string agent_id = "robot_" + std::to_string(i);
            if (actions.contains(agent_id)) {
                std::string command = actions[agent_id];
                LoopLog(ELogLevel::DEBUG, std::string("Set action ") +
                                              agent_id + " -> " + command);
                m_vecControllers[i]->SetAction(command);
            }
        }
    } else if (Enabled(ELogLevel::WARN)) {
        LoopLog(ELogLevel::WARN, "No actions in payload; skipping updates");
    }
}

void CZooLoopFunctions::PostStep() {
    LoopLog(ELogLevel::DEBUG, "PostStep()");
    json observations = CollectObservations();
    // Reward calculation (FUP-05)
    json rewards_json;
    if (m_bFirstStep) {
        for (size_t i = 0; i < m_vecControllers.size(); ++i) {
            rewards_json["robot_" + std::to_string(i)] = 0.0;
        }
        m_bFirstStep = false;
    } else {
        for (size_t i = 0; i < m_vecControllers.size(); ++i) {
            std::string agent_id = "robot_" + std::to_string(i);
            CVector3 lastPos = m_vecLastPositions[i];
            CVector3 curPos;
            curPos.SetX(observations["observations"][agent_id]["position"][0]
                            .get<double>());
            curPos.SetY(observations["observations"][agent_id]["position"][1]
                            .get<double>());
            Real dx = curPos.GetX() - lastPos.GetX();
            Real dy = curPos.GetY() - lastPos.GetY();
            Real dist = std::sqrt(dx * dx + dy * dy);
            Real maxProx = 0.0;
            for (const auto& v :
                 observations["observations"][agent_id]["proximity"]) {
                maxProx = std::max(maxProx, v.get<double>());
            }
            Real reward = dist - 0.5 * maxProx;
            rewards_json[agent_id] = reward;
        }
    }
    try {
        m_jActions = ReceiveRequest();
        if (Enabled(ELogLevel::DEBUG)) {
            std::string cmdShown = m_jActions.contains("command")
                                       ? m_jActions["command"].dump()
                                       : "<none>";
            LoopLog(ELogLevel::DEBUG,
                    std::string("Received command: ") + cmdShown);
        }
        if (m_jActions.contains("command")) {
            std::string cmd = m_jActions["command"].get<std::string>();
            if (cmd == "reset") {
                LoopLog(ELogLevel::DEBUG, "Process reset command");
                CSimulator::GetInstance().Reset();
                observations = CollectObservations();
            } else if (cmd == "close") {
                LoopLog(ELogLevel::DEBUG, "Process close command");
            }
        }
        observations["rewards"] = rewards_json;
        SendResponse(observations);
        if (Enabled(ELogLevel::DEBUG))
            LoopLog(ELogLevel::DEBUG,
                    std::string("Sent observations bytes=") +
                        std::to_string(observations.dump().size()));
    } catch (const zmq::error_t& e) {
        LoopLog(ELogLevel::ERROR, std::string("ZeroMQ error: ") + e.what());
    } catch (const std::exception& e) {
        LoopLog(ELogLevel::ERROR, std::string("Exception: ") + e.what());
    }
}

void CZooLoopFunctions::Reset() {
    for (CMyIPCController* pcController : m_vecControllers)
        pcController->Reset();
    (void)CollectObservations();  // establish baseline positions
    LoopLog(ELogLevel::INFO, "Reset: observations ready for next request");
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
        LoopLog(ELogLevel::INFO, "ZMQ resources cleaned up");
    } catch (const std::exception& e) {
        LoopLog(ELogLevel::ERROR, std::string("Cleanup error: ") + e.what());
    }
}

json CZooLoopFunctions::CollectObservations() {
    json observations;
    for (size_t i = 0; i < m_vecControllers.size(); ++i) {
        std::string agent_id = "robot_" + std::to_string(i);
        json obs = m_vecControllers[i]->GetObservation();
        try {
            CSpace::TMapPerType& footbots =
                GetSpace().GetEntitiesByType("foot-bot");
            auto it = footbots.begin();
            size_t idx = 0;
            for (; it != footbots.end(); ++it, ++idx) {
                if (idx == i) {
                    CFootBotEntity* pcFootBot =
                        any_cast<CFootBotEntity*>(it->second);
                    const CVector3& pos = pcFootBot->GetEmbodiedEntity()
                                              .GetOriginAnchor()
                                              .Position;
                    obs["position"] = {pos.GetX(), pos.GetY(), pos.GetZ()};
                    m_vecLastPositions[i] = pos;
                    break;
                }
            }
        } catch (const std::exception&) {
        }
        observations[agent_id] = obs;
    }
    json response;
    response["observations"] = observations;
    return response;
}

void CZooLoopFunctions::SendResponse(const json& j_response) {
    std::string response_str = j_response.dump();
    m_ptZmqSocket->send(zmq::buffer(response_str), zmq::send_flags::none);
}

json CZooLoopFunctions::ReceiveRequest() {
    zmq::message_t request;
    auto received = m_ptZmqSocket->recv(request, zmq::recv_flags::none);
    if (Enabled(ELogLevel::DEBUG))
        LoopLog(ELogLevel::DEBUG,
                std::string("ReceiveRequest bytes=") +
                    (received.has_value() ? std::to_string(received.value())
                                          : "none"));
    if (received.has_value() && received.value() > 0) {
        try {
            return json::parse(request.to_string());
        } catch (const json::parse_error& e) {
            LoopLog(ELogLevel::ERROR,
                    std::string("Failed to parse JSON: ") + e.what());
        }
    }
    return json();
}

REGISTER_LOOP_FUNCTIONS(CZooLoopFunctions, "zoo_loop_functions");
