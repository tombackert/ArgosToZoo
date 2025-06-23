#include "my_ipc_controller.h"
#include <argos3/core/utility/logging/argos_log.h>

/*
 * Konstruktor: Initialisiert die Member-Variablen mit Nullzeigern.
 * Dies ist eine gute Praxis, um undefiniertes Verhalten zu vermeiden.
 */
CMyIPCController::CMyIPCController() :
   m_pcWheels(NULL) {}

/*
 * Initialisierungsmethode.
 */
void CMyIPCController::Init(TConfigurationNode& t_node) {
   try {
      /*
       * Hole den Zeiger auf den 'differential_steering' Aktuator.
       * Der String "differential_steering" muss mit dem Tag in der <actuators>-Sektion
       * der.argos-Datei übereinstimmen. ARGoS stellt diesen Zeiger zur Verfügung,
       * nachdem es die XML-Konfiguration geparst hat.[15]
       * Wenn der Aktuator in der XML-Datei nicht deklariert wurde, wird hier eine Ausnahme geworfen.
       */
      m_pcWheels = GetActuator<CCI_DifferentialSteeringActuator>("differential_steering");
   }
   catch(CARGoSException& ex) {
      THROW_ARGOSEXCEPTION_NESTED("Error while initializing CMyIPCController", ex);
   }
   /*
    * Zukünftig könnten hier Parameter für die IPC-Verbindung (z.B. Port, IP-Adresse)
    * aus dem <params>-Abschnitt der XML-Datei geparst werden.[15, 16]
    */
}

/*
 * Die Hauptlogikschleife.
 */
void CMyIPCController::ControlStep() {
   /*
    * Für diesen Prototyp implementieren wir ein einfaches Verhalten, um die
    * Funktionsfähigkeit zu testen: Der Roboter dreht sich im Kreis.
    * Später wird hier die IPC-Logik implementiert: Warten auf einen Befehl von Python,
    * diesen Befehl parsen und die Radgeschwindigkeiten entsprechend setzen.
    */
   m_pcWheels->SetLinearVelocity(5.0, -5.0);
}

/*
 * Reset-Methode. Für diesen einfachen Controller ist nichts zurückzusetzen.
 */
void CMyIPCController::Reset() {
   // Hier könnten Zustandsvariablen zurückgesetzt werden.
}

/*
 * Destroy-Methode. Für diesen einfachen Controller ist nichts zu bereinigen.
 * Später müsste hier z.B. die IPC-Verbindung (Socket) sauber geschlossen werden.
 */
void CMyIPCController::Destroy() {
   // Ressourcen freigeben.
}

/*
 * DIES IST DER ENTSCHEIDENDE SCHRITT FÜR DIE REGISTRIERUNG!
 * Das Makro REGISTER_CONTROLLER bindet die C++-Klasse CMyIPCController an den
 * String-Bezeichner "my_ipc_controller".
 * Dieser Bezeichner wird dann in der.argos-Datei als XML-Tag verwendet, um diesen
 * Controller zu instanziieren. Das Makro muss in der.cpp-Datei stehen.[7, 15]
 */
REGISTER_CONTROLLER(CMyIPCController, "my_ipc_controller")