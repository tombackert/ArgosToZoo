cmake_minimum_required(VERSION 3.8.0)
project(ArgosToZoo)

if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE "Release" CACHE STRING "Build type" FORCE)
endif()

find_package(ARGoS REQUIRED)
find_package(cppzmq REQUIRED)

include_directories(${ARGOS_INCLUDE_DIRS} "${CMAKE_SOURCE_DIR}/src/plugin/common")

add_subdirectory(src/plugin)