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
    int recv_timeout = 100; // Millisekunden
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
    LOG << "[DEBUG] ZooLoopFunctions::PostStep()" << std::endl;
    
    // Sammle aktuelle Beobachtungen
    json observations = CollectObservations();
    
    try {
        // ZMQ REQ-REP Protokoll: Erst empfangen, dann antworten
        // Prüfe, ob Anfragen vom Client vorhanden sind
        zmq::pollitem_t items[] = {
            { m_ptZmqSocket->handle(), 0, ZMQ_POLLIN, 0 }
        };
        
        // Warte mit kurzem Timeout auf Anfragen
        zmq::poll(items, 1, std::chrono::milliseconds(1));
        
        if (items[0].revents & ZMQ_POLLIN) {
            // 1. Zuerst Anfrage vom Client empfangen
            m_jActions = ReceiveRequest();
            LOG << "[DEBUG] ZooLoopFunctions::PostStep() Received actions from Python: " << std::endl;
            LOG << "[DEBUG] Received actions: " << m_jActions.dump() << std::endl;

            // 2. Dann mit aktuellen Beobachtungen antworten
            SendResponse(observations);
            LOG << "[DEBUG] ZooLoopFunctions::PostStep() Sent observations to Python: " << std::endl;
            LOG << "[DEBUG] Sent observations: " << observations.dump() << std::endl;
            
            // Verbindungsstatus aktualisieren
            int events = 0;
            size_t events_size = sizeof(events);
            zmq_getsockopt(m_ptZmqSocket->handle(), ZMQ_EVENTS, &events, &events_size);
            bool is_connected = (events & ZMQ_POLLOUT) != 0;
            LOG << "[INFO] ZooLoopFunctions::PostStep(): ZMQ Connection status: " << (is_connected ? "Connected" : "Disconnected") << std::endl;
        } else {
            // Keine Anfrage verfügbar
            LOG << "[INFO] No request from Python client detected" << std::endl;
        }
    } catch (const zmq::error_t& e) {
        // ZeroMQ-Fehler abfangen und protokollieren
        LOGERR << "[ERROR] ZooLoopFunctions::PostStep() ZeroMQ error: " << e.what() << std::endl;
    } catch (const std::exception& e) {
        // Andere Ausnahmen abfangen
        LOGERR << "[ERROR] ZooLoopFunctions::PostStep() Exception: " << e.what() << std::endl;
    }
    
    // Auf "reset" oder "close" Befehl prüfen
    if (m_jActions.contains("command")) {
        if (m_jActions["command"] == "reset") {
            LOG << "[DEBUG] Resetting simulation" << std::endl;
            CSimulator::GetInstance().Reset();
        } else if (m_jActions["command"] == "close") {
            LOG << "[DEBUG] Terminating simulation" << std::endl;
            CSimulator::GetInstance().Terminate();
        }
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
        observations[agent_id] = m_vecControllers[i]->GetObservation();
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