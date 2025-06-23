#ifndef MY_IPC_CONTROLLER_H
#define MY_IPC_CONTROLLER_H

// ARGoS-Header
#include <argos3/core/control_interface/ci_controller.h>
#include <argos3/plugins/robots/generic/control_interface/ci_differential_steering_actuator.h>

// ZeroMQ Header (C++-Wrapper)
#include <zmq.hpp>

// JSON Header
#include "nlohmann/json.hpp"

using namespace argos;
using json = nlohmann::json;


/*
 * Die Definition der Controller-Klasse.
 * Sie erbt von CCI_Controller.
 */
class CMyIPCController : public CCI_Controller {

public:
    /* Klassenkonstruktor */
    CMyIPCController();

    /* Klassendestruktor */
    virtual ~CMyIPCController() {}

    /*
     * Initialisierungsmethode.
     * Wird einmalig aufgerufen, wenn der Controller einem Roboter zugewiesen wird.
     * Hier werden Zeiger auf Aktuatoren und Sensoren geholt und Parameter aus der XML-Datei gelesen.
     */
    virtual void Init(TConfigurationNode& t_node);

    /*
     * Die Hauptlogikschleife des Controllers.
     * Wird in jedem Simulationsschritt einmal aufgerufen.
     */
    virtual void ControlStep();

    /*
     * Setzt den internen Zustand des Controllers zurück.
     * Wird aufgerufen, wenn im GUI der Reset-Knopf gedrückt wird.
     */
    virtual void Reset();

    /*
     * Methode zur Bereinigung.
     * Wird aufgerufen, wenn der Controller zerstört wird (z.B. am Ende des Experiments).
     */
    virtual void Destroy();

private:
    /* Zeiger auf den Aktuator für die Räder */
    CCI_DifferentialSteeringActuator* m_pcWheels;

    // ZeroMQ-Member
    zmq::context_t* m_ptZmqContext;
    zmq::socket_t* m_ptZmqSocket;

    // Port für die Kommunikation
    std::string m_sPort;
};

#endif