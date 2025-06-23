add_library(my_ipc_controller SHARED
   my_ipc_controller.cpp)

# Wir verlinken manuell gegen die beiden benötigten ARGoS-Bibliotheken.
target_link_libraries(my_ipc_controller PUBLIC
   "/usr/local/lib/argos3/libargos3core_simulator.dylib"
   "/usr/local/lib/argos3/libargos3plugin_simulator_genericrobot.dylib")