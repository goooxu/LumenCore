# LumenCore third-party resolution (fetch at configure time when enabled).

option(LUMENCORE_FETCH_DEPS
  "Fetch OptiX headers, PhysX, stb, pybind11 at configure/build time"
  ON)

include(FetchContent)
# Allow FetchContent_Populate for header-only deps (CMake 3.30+).
if(POLICY CMP0169)
  cmake_policy(SET CMP0169 OLD)
endif()

# pybind11
FetchContent_Declare(
  pybind11
  GIT_REPOSITORY https://github.com/pybind/pybind11.git
  GIT_TAG v2.13.6
)
FetchContent_MakeAvailable(pybind11)

include(${CMAKE_CURRENT_LIST_DIR}/FetchOptiX.cmake)
include(${CMAKE_CURRENT_LIST_DIR}/FetchStb.cmake)
include(${CMAKE_CURRENT_LIST_DIR}/FetchPhysX.cmake)
