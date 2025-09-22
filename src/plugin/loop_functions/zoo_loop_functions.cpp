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
#include <random>

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
      m_eLogLevel(EnvDefaultLogLevel()),
      m_bSawFirstRequest(false),
      m_bHadPendingReply(false),
      m_unConsecutiveIdle(0) {
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
        // Determine port from XML attribute or environment variables
        int port = 5555;
        try {
            // Try attribute on <loop_functions> or parent nodes
            if (NodeAttributeExists(t_node, "port")) {
                GetNodeAttribute(t_node, "port", port);
            } else if (std::getenv("ARGOS_ZMQ_PORT")) {
                port = std::atoi(std::getenv("ARGOS_ZMQ_PORT"));
            } else if (std::getenv("ZOO_ZMQ_PORT")) {
                port = std::atoi(std::getenv("ZOO_ZMQ_PORT"));
            } else if (std::getenv("ZMQ_PORT")) {
                port = std::atoi(std::getenv("ZMQ_PORT"));
            }
        } catch (...) {
            // keep default
        }
        std::string endpoint = std::string("tcp://*:") + std::to_string(port);
        m_ptZmqSocket->bind(endpoint);
        LoopLog(ELogLevel::INFO,
                std::string("ZMQ server bound to ") + endpoint);
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

    // Perform randomized placement once at startup (deterministic via ARGoS
    // seed)
    RandomizeStartPositions();
}

void CZooLoopFunctions::PreStep() {
    LoopLog(ELogLevel::DEBUG, "PreStep()");
    if (m_ptZmqSocket) {
        int events = 0;
        size_t events_size = sizeof(events);
        try {
            zmq_getsockopt(m_ptZmqSocket->handle(), ZMQ_EVENTS, &events,
                           &events_size);
            bool can_reply =
                (events & ZMQ_POLLOUT) !=
                0;  // REP socket ready-to-send (has pending request)
            if (can_reply) {
                m_bHadPendingReply = true;
                m_unConsecutiveIdle = 0;
            } else {
                ++m_unConsecutiveIdle;
                m_bHadPendingReply = false;
            }
            // Compose one concise status line every tick (easier to scan)
            std::string phase;
            if (!m_bSawFirstRequest)
                phase = "WaitingForFirstRequest";
            else if (can_reply)
                phase = "PendingRequest";
            else
                phase = "Idle";
            LoopLog(ELogLevel::DEBUG,
                    "ZMQ status phase=" + phase +
                        " pending=" + std::string(can_reply ? "yes" : "no") +
                        " total_req=" + std::to_string(m_unTotalRequests) +
                        " total_rep=" + std::to_string(m_unTotalReplies) +
                        " idle_ticks=" + std::to_string(m_unConsecutiveIdle));
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
            } else if (cmd.rfind("set_loop_log_level:", 0) == 0) {
                std::string lvl =
                    cmd.substr(std::string("set_loop_log_level:").size());
                std::transform(lvl.begin(), lvl.end(), lvl.begin(), ::toupper);
                ELogLevel newLvl = m_eLogLevel;
                if (lvl == "DEBUG")
                    newLvl = ELogLevel::DEBUG;
                else if (lvl == "INFO")
                    newLvl = ELogLevel::INFO;
                else if (lvl == "WARN")
                    newLvl = ELogLevel::WARN;
                else if (lvl == "ERROR")
                    newLvl = ELogLevel::ERROR;
                m_eLogLevel = newLvl;
                LoopLog(ELogLevel::INFO,
                        std::string("Loop log level updated to ") + lvl);
            }
        }
        if (Enabled(ELogLevel::DEBUG)) {
            // Vollständige Observations (Agents, Proximity, Positionen,
            // Rewards) Achtung: kann sehr groß werden bei vielen Robotern.
            LoopLog(ELogLevel::DEBUG,
                    std::string("Observations JSON: ") + observations.dump());
        }
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
    // Re-randomize positions deterministically using current RNG state
    m_bPositionsRandomized = false;  // allow randomization again
    RandomizeStartPositions();
    // Establish baseline positions but ensure first step after reset has zero
    // reward
    (void)CollectObservations();
    m_bFirstStep = true;  // re-arm first-step reward suppression
    LoopLog(ELogLevel::INFO,
            "Reset: baseline established (rewards suppressed next step)");
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
    // NOTE (M3-02-FUP): This function MUST remain task-agnostic.
    // It only gathers raw sensor / position data. All MARL metrics & rewards
    // are computed Python-side in ArgosEnv._compute_metrics.
    json response;
    response["observations"]["schema"] = "compact_v1";
    json agents = json::array();
    json proximity = json::array();
    json position = json::array();
    for (size_t i = 0; i < m_vecControllers.size(); ++i) {
        std::string agent_id = "robot_" + std::to_string(i);
        agents.push_back(agent_id);
        json obs = m_vecControllers[i]->GetObservation();
        if (!obs.contains("proximity")) obs["proximity"] = json::array();
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
                    position.push_back({pos.GetX(), pos.GetY(), pos.GetZ()});
                    break;
                }
            }
        } catch (const std::exception&) {
            position.push_back({0.0, 0.0, 0.0});
        }
        proximity.push_back(obs["proximity"]);
    }
    response["observations"]["agents"] = agents;
    response["observations"]["proximity"] = proximity;
    response["observations"]["position"] = position;
    if (Enabled(ELogLevel::DEBUG)) {
        LoopLog(ELogLevel::DEBUG, std::string("Agents: ") + agents.dump());
        LoopLog(ELogLevel::DEBUG,
                std::string("Proximity shape: ") +
                    std::to_string(proximity.size()) + "x" +
                    (proximity.size() > 0 ? std::to_string(proximity[0].size())
                                          : "0"));
        LoopLog(ELogLevel::DEBUG, std::string("Positions: ") + position.dump());
    }
    if (m_bFirstStep) m_bFirstStep = false;
    return response;
}

void CZooLoopFunctions::SendResponse(const json& j_response) {
    std::string response_str = j_response.dump();
    m_ptZmqSocket->send(zmq::buffer(response_str), zmq::send_flags::none);
    ++m_unTotalReplies;
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
            m_bSawFirstRequest = true;
            ++m_unTotalRequests;
            return json::parse(request.to_string());
        } catch (const json::parse_error& e) {
            LoopLog(ELogLevel::ERROR,
                    std::string("Failed to parse JSON: ") + e.what());
        }
    }
    return json();
}

REGISTER_LOOP_FUNCTIONS(CZooLoopFunctions, "zoo_loop_functions");

/* ------------------------------------------------------------ */
/* Randomized placement logic                                    */
/* ------------------------------------------------------------ */
void CZooLoopFunctions::RandomizeStartPositions() {
    if (m_bPositionsRandomized) return;
    // Access global RNG from simulator for deterministic reproducibility
    CRandom::CRNG* pcRNG = CRandom::CreateRNG("argos");
    if (!pcRNG) {
        LoopLog(ELogLevel::WARN,
                "RandomizeStartPositions: RNG not available; skipping");
        return;
    }
    // Fetch all foot-bot entities
    CSpace::TMapPerType& cFootbots = GetSpace().GetEntitiesByType("foot-bot");
    const size_t unN = cFootbots.size();
    if (unN == 0) return;
    // Arena bounds (assume centered box): query Space size
    const CVector3& cArenaSize = GetSpace().GetArenaSize();
    // We'll sample x in [-sx/2+margin, sx/2-margin], y similarly
    const Real margin = 0.3f;  // Avoid spawning partly outside
    const Real minX = -cArenaSize.GetX() / 2 + margin;
    const Real maxX = cArenaSize.GetX() / 2 - margin;
    const Real minY = -cArenaSize.GetY() / 2 + margin;
    const Real maxY = cArenaSize.GetY() / 2 - margin;
    std::vector<CVector3> vecChosen;
    vecChosen.reserve(unN);
    const size_t maxTrialsPerRobot = 500;  // fail-safe
    for (size_t i = 0; i < unN; ++i) {
        bool placed = false;
        for (size_t trial = 0; trial < maxTrialsPerRobot; ++trial) {
            Real rx = pcRNG->Uniform(CRange<Real>(minX, maxX));
            Real ry = pcRNG->Uniform(CRange<Real>(minY, maxY));
            CVector3 cand(rx, ry, 0);
            bool ok = true;
            for (const auto& prev : vecChosen) {
                if ((cand - prev).Length() < m_fMinSeparation) {
                    ok = false;
                    break;
                }
            }
            if (ok) {
                vecChosen.push_back(cand);
                placed = true;
                break;
            }
        }
        if (!placed) {
            LoopLog(ELogLevel::WARN,
                    "RandomizeStartPositions: could not place all robots with "
                    "min separation; proceeding partially");
            break;  // proceed with what we have; remaining keep original
                    // positions
        }
    }
    // Apply positions (and random orientations) to first vecChosen.size()
    // robots
    size_t idx = 0;
    for (auto it = cFootbots.begin();
         it != cFootbots.end() && idx < vecChosen.size(); ++it, ++idx) {
        CFootBotEntity* pcFB = any_cast<CFootBotEntity*>(it->second);
        CEmbodiedEntity& body = pcFB->GetEmbodiedEntity();
        const CVector3& pos = vecChosen[idx];
        // Random yaw in [-pi, pi]
        CRadians yaw =
            pcRNG->Uniform(CRange<CRadians>(-CRadians::PI, CRadians::PI));
        CQuaternion qOrient;
        qOrient.FromEulerAngles(CRadians(0), CRadians(0),
                                yaw);  // roll, pitch, yaw
        body.MoveTo(pos, qOrient, false);
    }
    m_bPositionsRandomized = true;
    LoopLog(ELogLevel::INFO,
            std::string("RandomizeStartPositions: placed ") +
                std::to_string(vecChosen.size()) +
                " robots (min_sep=" + std::to_string(m_fMinSeparation) + ")");
}
