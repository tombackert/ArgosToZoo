## Folge-Issues: Ausbau Python Wrapper & PettingZoo Integration

Ziel: Der aktuelle Prototype (Start/Stop, rudimentäres step/reset über ZeroMQ) wird zu einer stabilen, testbaren, PettingZoo-kompatiblen Multi-Agent Umgebung ausgebaut. Die Issues sind priorisiert (P1 = kritisch).

Legende: Aufwand (T-shirt) = S (<2h), M (2–6h), L (6–12h), XL (>12h)

---

### 1. Konsistente Agenten-Discovery & Initialisierung
**ID:** FUP-01  
**Priorität:** P1  
**Aufwand:** M  
**Beschreibung:** `ArgosEnv` soll die Anzahl der Agents automatisch aus der Simulation ermitteln (z.B. via erster Observations-Reply oder Parsen der .argos XML). Entferne manuelle `num_agents` Übergabe oder validiere gegen Simulationszustand.  
**Akzeptanzkriterien:**  
- Beim ersten `reset()` werden `possible_agents` und `agents` korrekt auf die in ARGoS laufenden Roboter gesetzt.  
- Fehlermeldung falls Diskrepanz zwischen deklarierter und tatsächlicher Anzahl.  
**Abhängigkeiten:** Keine.  

### 2. Action Space Harmonisierung (Symbolisch -> Diskret)
**ID:** FUP-02  
**Priorität:** P1  
**Aufwand:** M  
**Beschreibung:** Aktuell werden String-Kommandos gesendet, während `action_space` ein kontinuierliches Box-Space ist. Definiere einen diskreten Action Space (z.B. STOP, FWD, BACK, LEFT, RIGHT, TURN_LEFT, TURN_RIGHT) oder ein kontinuierliches 2D Wheel-Speed Space und mappe konsistent.  
**Akzeptanzkriterien:**  
- `action_space(agent)` gibt konsistente Gymnasium Space zurück.  
- `step()` validiert Aktionen und serialisiert eindeutig.  
- Dokumentation der Mapping-Tabelle.  
**Abhängigkeiten:** FUP-01.  

### 3. Beobachtungs-Schema & Spaces Validieren
**ID:** FUP-03  
**Priorität:** P1  
**Aufwand:** M  
**Beschreibung:** Observation Space aktuell nur Platzhalter `proximity`. Prüfe C++ Controller `GetObservation()` (ergänzen falls nötig) und stelle sicher, dass Format & dtype mit `observation_space` übereinstimmen (z.B. Normalisierung 0..1, feste Länge).  
**Akzeptanzkriterien:**  
- `observation_space(agent)` passt exakt zur Struktur der tatsächlichen Observations.  
- Unit-Test: Form & dtype werden geprüft.  
**Abhängigkeiten:** FUP-01.  

### 4. Episoden- und Terminations-Logik
**ID:** FUP-04  
**Priorität:** P1  
**Aufwand:** M  
**Beschreibung:** Implementiere Termination / Truncation (z.B. `max_steps`, optional Zielkriterium). Leere `agents` Liste wenn alle done.  
**Akzeptanzkriterien:**  
- `terminations` oder `truncations` werden bei Erreichen von `max_steps` auf True gesetzt.  
- Nach Done: `env.agents == []`.  
- Parallel API Test (`parallel_api_test`) besteht.  
**Abhängigkeiten:** FUP-02, FUP-03.  

### 5. Reward-Funktion Basis
**ID:** FUP-05  
**Priorität:** P2  
**Aufwand:** M  
**Beschreibung:** Definiere erste, nachvollziehbare Reward-Heuristik (z.B. Vorwärts-Fortschritt, Kollisionen vermeiden). C++ oder Python berechnet Reward.  
**Akzeptanzkriterien:**  
- Nicht-konstanter Reward in Tests (Varianz > 0). ✅ `test_reward_variance` grün.  
- Dokumentierte Formel im Code. ✅ Kommentar in `zoo_loop_functions.cpp` & `argos_env.py`.  
**Formel:** `reward = dist_xy_since_last_step - 0.5 * max_proximity` (erster Step 0.0).  
**Follow-Up Ideen:** Zielgerichtete Komponenten (+Goal, -Energy), shaping via Potenzialfelder, Normalisierung pro Schritt.  
**Abhängigkeiten:** FUP-03, FUP-04.  

### 6. Deterministische Schritt-Synchronisation
**ID:** FUP-06  
**Priorität:** P1  
**Aufwand:** L  
**Beschreibung:** Stelle sicher, dass pro `env.step()` exakt ein Simulationsschritt ausgeführt wird. Option A: ARGoS pausiert / `StepExperiment()` (Headless/CLI). Option B: LoopFunctions blockiert bis Aktion empfangen wurde (Tick-Gate).  
**Akzeptanzkriterien:**  
- Zwei identische Seeds -> identische Folge von Observations/Rewards über N Schritte.  
- Performance messbar stabil (<5% Varianz Laufzeit bei N=1000 steps).  
**Abhängigkeiten:** FUP-04.  

### 7. Seed & Reproducibility
**ID:** FUP-07  
**Priorität:** P2  
**Aufwand:** M  
**Beschreibung:** Implementiere `reset(seed=...)`: Seed wird gespeichert & an C++ weitergegeben (sofern ARGoS deterministisch; sonst Doku von Limitierungen).  
**Akzeptanzkriterien:**  
- `parallel_seed_test` besteht (oder dokumentierte Ausnahme).  
**Abhängigkeiten:** FUP-06.  

### 8. Fehler- & Timeout-Resilienz (REQ/REP Recovery)
**ID:** FUP-08  
**Priorität:** P2  
**Aufwand:** M  
**Beschreibung:** Robustere Wiederherstellung bei Timeout / verlorener Socket-State (Dummy-Drain, Reconnect-Handshake „ping“).  
**Akzeptanzkriterien:**  
- Simulierte Unterbrechung (Kill Python/ZMQ) -> Reconnect ohne ARGoS Neustart möglich. ✅ `test_timeout_recovery` grün.  
- Testskript demonstriert Recovery. ✅ Socket-Close -> automatischer Reconnect & weitere Steps möglich.  
**Abhängigkeiten:** Basis, optional FUP-06.  

### 9. Multi-Agent Socket Architektur Skalieren
**ID:** FUP-09  
**Priorität:** P3  
**Aufwand:** L  
**Beschreibung:** Entweder (a) ein zentraler REP-Socket (heute) bleibt, oder (b) pro Agent eigener Socket. Entscheiden & implementieren. Bei (a): Batch-Action/Observation optimieren.  
**Akzeptanzkriterien:**  
- Skalierungstest mit >=10 Agents ohne Deadlocks.  
- Durchsatz / Latenz Benchmarks dokumentiert.  
**Abhängigkeiten:** FUP-06.  

### 10. Logging & Monitoring Cleanup
**ID:** FUP-10  
**Priorität:** P3  
**Aufwand:** S  
**Beschreibung:** Reduziere Debug-Spam, einstellbare Log-Level, optional strukturiertes JSON-Log.  
**Akzeptanzkriterien:**  
- Environment kann in „quiet“ Modus laufen (nur WARN/ERROR).  
**Abhängigkeiten:** Keine.  

### 11. Test-Suite Integration (CI-Layer)
**ID:** FUP-11  
**Priorität:** P2  
**Aufwand:** M  
**Beschreibung:** Automatisierte Tests: `parallel_api_test`, Seed-Test, Performance Benchmark (optional), einfache Reward-Invarianz, Timeout-Recovery.  
**Akzeptanzkriterien:**  
- `pytest -q` grün; PettingZoo Tests laufen via Script.  
- README Abschnitt „Testing“.  
**Abhängigkeiten:** FUP-04 bis FUP-08 (schrittweise).  

### 12. Ressourcen-Freigabe & Graceful Shutdown
**ID:** FUP-12  
**Priorität:** P2  
**Aufwand:** S  
**Beschreibung:** Sicherstellen: Threads join, Pipes geleert (`communicate()`), Prozess-Endstatus geprüft, doppelte Terminate robust.  
**Akzeptanzkriterien:**  
- Kein Zombie-Prozess nach `env.close()` (ps Test). ✅ `test_graceful_shutdown` grün.  
- Mehrfaches `close()` ohne Exception. ✅ Idempotenz-Flag `_closed`.  
**Abhängigkeiten:** Basis.  

### 13. Dokumentation & Developer Guide
**ID:** FUP-13  
**Priorität:** P2  
**Aufwand:** M  
**Beschreibung:** Ausführliche Doku: Action Mapping, Timing/Sync, Reward, Seeding, Fehlerfälle, Skalierung.  
**Akzeptanzkriterien:**  
- Abschnitt im `docs/` + README Update.  
- Beispiel-Notebook oder Skript Nutzung mit Random Policy.  
**Abhängigkeiten:** FUP-02..FUP-07.  

### 14. Performance Profiling & Optimierung (Optional für später)
**ID:** FUP-14  
**Priorität:** P4  
**Aufwand:** L  
**Beschreibung:** Benchmark Step-Throughput (steps/sec) vs. Anzahl Agents. Optimierung (Batch JSON, ZeroMQ Optionen, evtl. binäres Format).  
**Akzeptanzkriterien:**  
- Benchmark Report + Identifizierte Bottlenecks + >=20% Verbesserung gegenüber Basis.  
**Abhängigkeiten:** FUP-09.  

### 15. RL-Kompatibilität Smoke Test
**ID:** FUP-15  
**Priorität:** P3  
**Aufwand:** M  
**Beschreibung:** Mini-Training (Random / Heuristik / Simple Policy Gradient) über N Episoden, prüft Lernsignal (Reward Trend).  
**Akzeptanzkriterien:**  
- Script zeigt Reward-Kurven Logging (z.B. CSV / TensorBoard).  
**Abhängigkeiten:** FUP-05, FUP-11.  

---

## Empfohlene Reihenfolge (Roadmap Sprintweise)
1. Sprint A: FUP-01, FUP-02, FUP-03, FUP-04 (Basis-API stabil) - DONE
2. Sprint B: FUP-06, FUP-07, FUP-05 (Determinismus + Reward) - DONE
3. Sprint C: FUP-08, FUP-12, FUP-11, FUP-10 (Robustheit + Tests) - TODO
4. Sprint D: FUP-09, FUP-13, FUP-15 (Skalierung + Doku + RL Smoke) - TODO
5. Optional: FUP-14 (Performance Tuning)  

---

## Querverweise / Risiken
- Ohne deterministische Synchronisation (FUP-06) schlagen Seed-Tests fehl.  
- Reward erst definieren nachdem Observation & Action stabil (FUP-02/03).  
- Multi-Socket Architektur früh entscheiden (FUP-09) um Refactoring später zu minimieren.  
- Performance Optimierung lohnt erst nach funktionaler Reife (FUP-14).  

---

## Notizen zur Umsetzung
Falls GitHub-Issues erstellt werden, nutze obige IDs als Titel-Präfix (z.B. `FUP-01: Agenten-Discovery & Initialisierung`). Jeder Issue-Body sollte die Akzeptanzkriterien und ggf. offene Design-Notes enthalten.

---

Erstellt automatisch als Planungsgrundlage. Bei Änderungen an Architektur bitte Reihenfolge & Abhängigkeiten aktualisieren.
