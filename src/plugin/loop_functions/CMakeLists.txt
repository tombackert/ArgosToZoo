add_library(zoo_loop_functions SHARED
   zoo_loop_functions.cpp)

target_link_libraries(zoo_loop_functions PUBLIC
   my_ipc_controller
   "/usr/local/lib/argos3/libargos3core_simulator.dylib"
   "/usr/local/lib/argos3/libargos3plugin_simulator_genericrobot.dylib"
   ${ZeroMQ_LIBRARIES}
)

target_include_directories(zoo_loop_functions PUBLIC
   "${CMAKE_SOURCE_DIR}/src/plugin/common"
   "${CMAKE_SOURCE_DIR}/src/plugin/controllers"
)