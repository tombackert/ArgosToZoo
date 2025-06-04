cmake_minimum_required(VERSION 3.10)
project(ARGoSZeroMQBridge)

set(CMAKE_CXX_STANDARD 17) # Or a suitable C++ standard
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Find ARGoS3 package
# This assumes ARGoS3 was installed in a way CMake can find it
# (e.g., CMAKE_PREFIX_PATH set or ARGoS3 provides CMake config files)
find_package(ARGoS REQUIRED)

# Find ZeroMQ package (libzmq)
# This might require ZeroMQ to be installed system-wide or providing a find script
find_package(cppzmq REQUIRED)

# Find nlohmann_json (header-only, often included as a submodule or fetched by CMake)
# Option 1: If installed system-wide or via CMake package
# find_package(nlohmann_json 3.2.0 REQUIRED) # Version might vary
# Option 2: If included directly (e.g., as a header in a known path or submodule)
# For simplicity, assume headers are accessible via include_directories.
# If using FetchContent or add_subdirectory for nlohmann_json:
# include(FetchContent)
# FetchContent_Declare(
#   nlohmann_json
#   GIT_REPOSITORY https://github.com/nlohmann/json.git
#   GIT_TAG v3.11.2 # Or desired version
# )
# FetchContent_MakeAvailable(nlohmann_json)

include_directories(
    ${ARGOS3_INCLUDE_DIRS}
    ${ZeroMQ_INCLUDE_DIRS}
    /opt/homebrew/include
    /opt/homebrew/Cellar/lua/5.4.7/include/lua
    # Add path to nlohmann/json headers if not found by find_package
    # For example, if it's in a 'third_party' subdirectory:
    # ${CMAKE_CURRENT_SOURCE_DIR}/third_party/json/single_include
    ${CMAKE_CURRENT_SOURCE_DIR}/include # For our own header
)

link_directories(/usr/local/lib/argos3)

# Define the plugin library
add_library(zeromq_bridge SHARED
    src/zb_loop_func.cpp
)

# Link libraries
target_link_libraries(zeromq_bridge PRIVATE
    argos3core_simulator       # ARGoS core library (actual library name)
    argos3plugin_simulator_footbot # Foot-Bot plugin library (für RTTI und Implementierung)
    cppzmq                    # ZeroMQ C++ binding
    # nlohmann_json::nlohmann_json # If found as a CMake target
)

# Optional: Set install path if you plan to install the plugin
# install(TARGETS zeromq_bridge DESTINATION ${ARGOS3_INSTALL_PLUGIN_DIR})