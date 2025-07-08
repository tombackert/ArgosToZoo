#include "zoo_loop_functions.h"
#include <argos3/core/simulator/simulator.h>
#include <argos3/core/utility/logging/argos_log.h>

CZooLoopFunctions::CZooLoopFunctions() :
    m_ptZmqContext(nullptr),
    m_ptZmqSocket(nullptr) {}

CZooLoopFunctions::~CZooLoopFunctions() {}

void CZooLoopFunctions::Init(TConfigurationNode& t_node) {
    // 1. ZeroMQ Server initialisieren
    m_ptZmqContext = new zmq::context_t(1);
    m_ptZmqSocket = new zmq::socket_t(*m_ptZmqContext, ZMQ_REP);
    try {
        m_ptZmqSocket->bind("tcp://*:5555");
        LOG << "[INFO] ZooLoopFunctions: ZMQ server bound to tcp://*:5555" << std::endl;
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
    LOG << "[INFO] ZooLoopFunctions: Found and stored " << m_vecControllers.size() << " controllers." << std::endl;
}

void CZooLoopFunctions::PreStep() {
    // 3. Aktionen an die Controller verteilen
    if (m_jActions.contains("actions")) {
        for (size_t i = 0; i < m_vecControllers.size(); ++i) {
            std::string agent_id = "robot_" + std::to_string(i);
            if (m_jActions["actions"].contains(agent_id)) {
                std::string command = m_jActions["actions"][agent_id];
                m_vecControllers[i]->SetAction(command);
            }
        }
    }
}

void CZooLoopFunctions::PostStep() {
    // 1. Beobachtungen von allen Controllern sammeln
    json observations = CollectObservations();

    // 2. Beobachtungen an Python senden
    SendResponse(observations);

    // 3. Auf den nächsten Befehl von Python warten (blockierend!)
    // Die Simulation pausiert hier, bis Python den nächsten 'step' sendet.
    m_jActions = ReceiveRequest();

    // Auf "CLOSE"-Befehl prüfen
    if (m_jActions.contains("command") && m_jActions["command"] == "CLOSE") {
        CSimulator::GetInstance().Terminate();
    }
}

void CZooLoopFunctions::Reset() {
    // Initialzustand herstellen und erste Beobachtungen senden
    json observations = CollectObservations();
    SendResponse(observations);
    m_jActions = ReceiveRequest();
}

void CZooLoopFunctions::Destroy() {
    if (m_ptZmqSocket) {
        m_ptZmqSocket->close();
        delete m_ptZmqSocket;
    }
    if (m_ptZmqContext) {
        m_ptZmqContext->close();
        delete m_ptZmqContext;
    }
}

json CZooLoopFunctions::CollectObservations() {
    json observations;
    for (size_t i = 0; i < m_vecControllers.size(); ++i) {
        std::string agent_id = "robot_" + std::to_string(i);
        observations[agent_id] = m_vecControllers[i]->GetObservation();
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
    auto received = m_ptZmqSocket->recv(request, zmq::recv_flags::none); // Blockierend
    if (received.has_value() && received.value() > 0) {
        return json::parse(request.to_string());
    }
    return json();
}

REGISTER_LOOP_FUNCTIONS(CZooLoopFunctions, "zoo_loop_functions");