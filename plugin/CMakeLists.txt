cmake_minimum_required(VERSION 3.8.0)
project(ArgosToZoo)

if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE "Release" CACHE STRING "Build type" FORCE)
endif()

find_package(ARGoS REQUIRED)

include_directories(${ARGOS_INCLUDE_DIRS})

add_subdirectory(controllers)