cmake_minimum_required(VERSION 3.16)
project(melonds_python LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release CACHE STRING "" FORCE)
endif()

# melonDS core only: no Qt/SDL frontend, no OpenGL, no GDB stub
set(BUILD_QT_SDL OFF CACHE BOOL "" FORCE)
set(ENABLE_OGLRENDERER OFF CACHE BOOL "" FORCE)
set(ENABLE_GDBSTUB OFF CACHE BOOL "" FORCE)
set(ENABLE_LTO_RELEASE OFF CACHE BOOL "" FORCE)
add_subdirectory(melonDS EXCLUDE_FROM_ALL)

add_library(melonds_py SHARED
    native/melonds_shim.cpp
    native/Platform.cpp
)
target_include_directories(melonds_py PRIVATE native)
target_link_libraries(melonds_py PRIVATE core ${CMAKE_DL_LIBS})

set(MDS_LIB_DIR "${CMAKE_CURRENT_SOURCE_DIR}/melonds_python/_lib")
set_target_properties(melonds_py PROPERTIES
    CXX_VISIBILITY_PRESET hidden
    VISIBILITY_INLINES_HIDDEN ON
    LIBRARY_OUTPUT_DIRECTORY "${MDS_LIB_DIR}"
    RUNTIME_OUTPUT_DIRECTORY "${MDS_LIB_DIR}"   # Windows puts DLLs here
    LIBRARY_OUTPUT_DIRECTORY_RELEASE "${MDS_LIB_DIR}"
    RUNTIME_OUTPUT_DIRECTORY_RELEASE "${MDS_LIB_DIR}"
)

if (MINGW)
    # self-contained DLL: no libstdc++/libgcc/winpthread DLLs needed next to it
    target_link_options(melonds_py PRIVATE -static-libgcc -static-libstdc++ -static)
endif()
