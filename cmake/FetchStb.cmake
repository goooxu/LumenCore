# Fetch stb (stb_image.h) for HDR env-map loading.
# Override with -DSTB_INCLUDE_DIR=/path

if(STB_INCLUDE_DIR AND EXISTS "${STB_INCLUDE_DIR}/stb_image.h")
  message(STATUS "Using pre-set STB_INCLUDE_DIR=${STB_INCLUDE_DIR}")
else()
  if(LUMENCORE_FETCH_DEPS)
    include(FetchContent)
    FetchContent_Declare(
      stb
      GIT_REPOSITORY https://github.com/nothings/stb.git
      GIT_TAG master
      GIT_SHALLOW TRUE
    )
    FetchContent_GetProperties(stb)
    if(NOT stb_POPULATED)
      message(STATUS "Fetching stb (nothings/stb)...")
      FetchContent_Populate(stb)
    endif()
    set(STB_INCLUDE_DIR "${stb_SOURCE_DIR}" CACHE PATH "stb headers directory" FORCE)
  elseif(EXISTS "${CMAKE_SOURCE_DIR}/third_party/stb_image.h")
    set(STB_INCLUDE_DIR "${CMAKE_SOURCE_DIR}/third_party" CACHE PATH "stb headers directory")
  elseif(EXISTS "${CMAKE_SOURCE_DIR}/third_party/stb/stb_image.h")
    set(STB_INCLUDE_DIR "${CMAKE_SOURCE_DIR}/third_party/stb" CACHE PATH "stb headers directory")
  endif()
endif()

if(NOT EXISTS "${STB_INCLUDE_DIR}/stb_image.h")
  message(FATAL_ERROR
    "stb_image.h not found.\n"
    "Enable LUMENCORE_FETCH_DEPS=ON or pass -DSTB_INCLUDE_DIR=...")
endif()
message(STATUS "stb headers: ${STB_INCLUDE_DIR}")
