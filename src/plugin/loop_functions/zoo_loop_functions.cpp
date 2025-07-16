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
    LOG << "[DEBUG] CZooLoopFunctions::Init() called" << std::endl;
    // 1. ZeroMQ Server initialisieren
    m_ptZmqContext = new zmq::context_t(1);
    m_ptZmqSocket = new zmq::socket_t(*m_ptZmqContext, ZMQ_REP);
    try {
        m_ptZmqSocket->bind("tcp://*:5555");
        LOG << "[INFO] ZooLoopFunctions::Init(): ZMQ server bound to tcp://*:5555" << std::endl;
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
}

void CZooLoopFunctions::PreStep() {
    LOG << "[DEBUG] ZooLoopFunctions::PreStep() called" << std::endl;
    
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
    LOG << "[DEBUG] Actions: " << m_jActions.dump() << std::endl;
    if (m_jActions.contains("actions")) {
        for (size_t i = 0; i < m_vecControllers.size(); ++i) {
            std::string agent_id = "robot_" + std::to_string(i);
            if (m_jActions["actions"].contains(agent_id)) {
                std::string command = m_jActions["actions"][agent_id];
                LOG << "[INFO] ZooLoopFunctions::PreStep(): Setting action for " << agent_id << ": " << command << std::endl;
                m_vecControllers[i]->SetAction(command);
            }
        }
    } else {
        LOG << "[INFO] No actions found in m_jActions, skipping controller updates." << std::endl;
    }
}

void CZooLoopFunctions::PostStep() {
    LOG << "[DEBUG] ZooLoopFunctions::PostStep() called" << std::endl;
    
    // 1. Beobachtungen von allen Controllern sammeln
    json observations = CollectObservations();

    try {
        // 2. Beobachtungen an Python senden
        SendResponse(observations);
        LOG << "[DEBUG] ZooLoopFunctions::PostStep() Sent observations to Python: " << observations.dump() << std::endl;
        

        // 3. Auf den nächsten Befehl von Python warten (nicht-blockierend mit Timeout)
        // Verwende zmq_poll mit einem Timeout, um ein Blockieren zu vermeiden
        zmq::pollitem_t items[] = {
            { m_ptZmqSocket->handle(), 0, ZMQ_POLLIN, 0 }
        };
        
        // Warte mit Timeout von 100ms
        zmq::poll(items, 1, std::chrono::milliseconds(100));
        
        // Wenn Daten verfügbar sind, empfange sie
        if (items[0].revents & ZMQ_POLLIN) {
            m_jActions = ReceiveRequest();
            LOG << "[DEBUG] ZooLoopFunctions::PostStep() Received actions from Python: " << m_jActions.dump() << std::endl;
        } else {
            // Keine Daten verfügbar, keine Aktion durchführen
            LOG << "[INFO] No Python client connected or no data available" << std::endl;
        }
    } catch (const zmq::error_t& e) {
        // ZeroMQ-Fehler abfangen und protokollieren
        LOGERR << "[ERROR] ZooLoopFunctions::PostStep() ZeroMQ error: " << e.what() << std::endl;
    } catch (const std::exception& e) {
        // Andere Ausnahmen abfangen
        LOGERR << "[EXEPTION] ZooLoopFunctions::PostStep() Exeption: " << e.what() << std::endl;
    }

    // Auf "reset" oder "close" Befehl prüfen
    if (m_jActions.contains("command")) {
        if (m_jActions["command"] == "reset") {
            LOG << "[DEBUG] Resetting simulation" << std::endl;
            CSimulator::GetInstance().Reset();
        } else if (m_jActions["command"] == "close") {
            std::cout << "[DEBUG] Terminating simulation" << std::endl;
            CSimulator::GetInstance().Terminate();
        }
    }
}

void CZooLoopFunctions::Reset() {
    LOG << "[DEBUG] ZooLoopFunctions::Reset() called" << std::endl;
    // Alle Controller zurücksetzen
    for (CMyIPCController* pcController : m_vecControllers) {
        pcController->Reset();
    }
    // Initialzustand herstellen und erste Beobachtungen senden
    json observations = CollectObservations();
    LOG << "[INFO] ZooLoopFunctions: Reset called. Observations:" << observations << std::endl;
    SendResponse(observations);
    m_jActions = ReceiveRequest();
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
    LOG << "[DEBUG] ZooLoopFunctions::CollectObservations() called" << std::endl;
    json observations;
    for (size_t i = 0; i < m_vecControllers.size(); ++i) {
        std::string agent_id = "robot_" + std::to_string(i);
        observations[agent_id] = m_vecControllers[i]->GetObservation();
    }
    json response;
    LOG << "[DEBUG] ZooLoopFunctions::CollectObservations() collected observations: " << observations.dump() << std::endl;
    response["observations"] = observations;
    return response;
}

void CZooLoopFunctions::SendResponse(const json& j_response) {
    LOG << "[DEBUG] ZooLoopFunctions::SendResponse() called with response: " << j_response.dump() << std::endl;
    std::string response_str = j_response.dump();
    m_ptZmqSocket->send(zmq::buffer(response_str), zmq::send_flags::none);
}

json CZooLoopFunctions::ReceiveRequest() {
    zmq::message_t request;
    auto received = m_ptZmqSocket->recv(request, zmq::recv_flags::none); // Blockierend
    LOG << "[DEBUG] ZooLoopFunctions::ReceiveRequest() called, received bytes: " << (received.has_value() ? std::to_string(received.value()) : "none") << std::endl;
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