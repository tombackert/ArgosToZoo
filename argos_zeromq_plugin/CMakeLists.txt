cmake_minimum_required(VERSION 3.10)
project(ARGoSZeroMQBridge)

set(CMAKE_CXX_STANDARD 17) # Suitable C++ standard
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Find ARGoS3 package
# This assumes ARGoS3 was installed in a way CMake can find it
# (e.g., CMAKE_PREFIX_PATH set or ARGoS3 provides CMake config files)
find_package(ARGoS3 REQUIRED)

find_package(ZeroMQ REQUIRED)

find_package(nlohmann_json 3.2.0 REQUIRED) # Check version as needed


include_directories(
    ${ARGOS3_INCLUDE_DIRS}
    ${ZeroMQ_INCLUDE_DIRS}
    # Add path to nlohmann/json headers if not found by find_package
    # For example, if it's in a 'third_party' subdirectory:
    # ${CMAKE_CURRENT_SOURCE_DIR}/third_party/json/single_include
    ${CMAKE_CURRENT_SOURCE_DIR}/include # For our own header
)

# Define the plugin library
add_library(zeromq_bridge SHARED
    src/zeromq_bridge_loop_func.cpp
)

# Link libraries
target_link_libraries(zeromq_bridge PRIVATE
    ARGoS3::core       # ARGoS core library
    ZeroMQ::ZeroMQ     # ZeroMQ library (target name might vary based on FindZeroMQ.cmake)
    # nlohmann_json::nlohmann_json # If found as a CMake target
)

# Optional: Set install path if you plan to install the plugin
# install(TARGETS zeromq_bridge DESTINATION ${ARGOS3_INSTALL_PLUGIN_DIR})