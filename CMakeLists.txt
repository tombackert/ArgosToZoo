cmake_minimum_required(VERSION 3.8.0)
project(ArgosToZoo)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE "Release" CACHE STRING "Build type" FORCE)
endif()

find_package(ARGoS REQUIRED)
find_package(cppzmq REQUIRED)

include_directories(${ARGOS_INCLUDE_DIRS} "${CMAKE_SOURCE_DIR}/src/plugin/common")

add_subdirectory(src/plugin)