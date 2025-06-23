cmake_minimum_required(VERSION 3.10)
project(ArgosToZoo)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Find ARGoS, ZeroMQ, and other dependencies
find_package(ARGoS REQUIRED)
find_package(cppzmq REQUIRED)
find_package(nlohmann_json REQUIRED)

# Include directories for ARGoS
set(HOMEBREW_INCLUDE_DIR "/opt/homebrew/include" CACHE PATH "Path to Homebrew include directory")
set(LUA_INCLUDE_DIR "/opt/homebrew/Cellar/lua/5.4.7/include/lua" CACHE PATH "Path to Lua include directory")

include_directories(
    ${ARGOS3_INCLUDE_DIRS}
    ${ZeroMQ_INCLUDE_DIRS}
    ${HOMEBREW_INCLUDE_DIR}
    ${LUA_INCLUDE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/include
)

link_directories(/usr/local/lib/argos3)

# Define the plugin library
add_library(zeromq_bridge SHARED
    loop_functions/zb_loop_func.cpp
)

# Link libraries
target_link_libraries(zeromq_bridge PRIVATE
    argos3core_simulator
    argos3plugin_simulator_footbot
    cppzmq                    
    nlohmann_json::nlohmann_json 
)