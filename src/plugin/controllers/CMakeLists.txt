add_library(my_ipc_controller SHARED
   my_ipc_controller.cpp)

target_link_libraries(my_ipc_controller PUBLIC
   "/usr/local/lib/argos3/libargos3core_simulator.dylib"
   "/usr/local/lib/argos3/libargos3plugin_simulator_genericrobot.dylib"
   ${ZeroMQ_LIBRARIES}
)

target_include_directories(my_ipc_controller PUBLIC
   "${CMAKE_SOURCE_DIR}/src/plugin/common")