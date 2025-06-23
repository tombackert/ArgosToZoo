#ifndef MY_IPC_CONTROLLER_H
#define MY_IPC_CONTROLLER_H

/*
 * Inkludieren der notwendigen ARGoS-Header.
 * - ci_controller.h: Definiert die Basisklasse CCI_Controller.[6, 7]
 * - ci_differential_steering_actuator.h: Definiert die Schnittstelle zur Steuerung der Räder.[6]
 */
#include <argos3/core/control_interface/ci_controller.h>
#include <argos3/plugins/robots/generic/control_interface/ci_differential_steering_actuator.h>

/*
 * Alle ARGoS-Klassen sind im 'argos'-Namespace.
 */
using namespace argos;

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

    /* Hier könnten zukünftig weitere Zeiger auf Sensoren oder IPC-relevante Member stehen */
};

#endif