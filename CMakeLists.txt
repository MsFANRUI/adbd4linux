# SPDX-License-Identifier: GPL-3.0-only
cmake_minimum_required(VERSION 3.22)
project(roboparty_adbd LANGUAGES C CXX)

if(NOT CMAKE_SYSTEM_NAME STREQUAL "Linux")
    message(FATAL_ERROR "This port targets Linux")
endif()
if(CMAKE_SOURCE_DIR STREQUAL CMAKE_BINARY_DIR)
    message(FATAL_ERROR "Use an out-of-tree build: cmake -S . -B build")
endif()
set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS ON)
include(GNUInstallDirs)
find_package(Threads REQUIRED)
find_package(PkgConfig REQUIRED)
pkg_check_modules(BROTLI REQUIRED IMPORTED_TARGET libbrotlicommon libbrotlidec libbrotlienc)
pkg_check_modules(LZ4 REQUIRED IMPORTED_TARGET liblz4)
pkg_check_modules(ZSTD REQUIRED IMPORTED_TARGET libzstd)

# Recreate only the disposable source copy; upstream submodules stay pristine.
set(PORT_SOURCE "${CMAKE_CURRENT_BINARY_DIR}/source")
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS linux-port.patch)
file(REMOVE_RECURSE "${PORT_SOURCE}")
file(MAKE_DIRECTORY "${PORT_SOURCE}/deps")
foreach(part adb deps/core deps/libbase deps/logging)
    file(GLOB source_entries "${CMAKE_CURRENT_SOURCE_DIR}/${part}/*")
    if(NOT source_entries)
        message(FATAL_ERROR "Missing ${part}; run git submodule update --init --recursive")
    endif()
    get_filename_component(parent "${part}" DIRECTORY)
    file(COPY "${CMAKE_CURRENT_SOURCE_DIR}/${part}"
         DESTINATION "${PORT_SOURCE}/${parent}"
         PATTERN .git EXCLUDE PATTERN .gitignore EXCLUDE)
endforeach()
find_program(PATCH_EXECUTABLE patch REQUIRED)
execute_process(COMMAND "${PATCH_EXECUTABLE}" --batch --fuzz=0 --no-backup-if-mismatch -p1
                -i "${CMAKE_CURRENT_SOURCE_DIR}/linux-port.patch"
                WORKING_DIRECTORY "${PORT_SOURCE}" RESULT_VARIABLE patch_result)
if(NOT patch_result EQUAL 0)
    message(FATAL_ERROR "linux-port.patch does not apply to the pinned sources")
endif()

set(FMT_INSTALL OFF CACHE BOOL "" FORCE)
set(FMT_TEST OFF CACHE BOOL "" FORCE)
set(FMT_DOC OFF CACHE BOOL "" FORCE)
add_subdirectory(deps/fmtlib EXCLUDE_FROM_ALL)
configure_file(cmake/platform_tools_version.h.in platform_tools_version.h @ONLY)
configure_file(cmake/version.h.in build/version.h @ONLY)
include(cmake/Targets.cmake)
install(TARGETS adbd RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR})

# Linux targets do not provide Android's app_process entry point. Install the
# small scrcpy protocol shim alongside adbd so stock host scrcpy can launch it.
install(PROGRAMS scrcpy/app_process DESTINATION ${CMAKE_INSTALL_BINDIR})
install(PROGRAMS scrcpy/fake_server.py DESTINATION ${CMAKE_INSTALL_LIBDIR}/scrcpy-compat)
install(FILES scrcpy/test.h264 DESTINATION ${CMAKE_INSTALL_LIBDIR}/scrcpy-compat)

# Android command shims for the Linux desktop: screencap/screenrecord/input,
# getprop/setprop, wm, logcat, dumpsys and settings.
set(ANDROID_COMPAT_COMMANDS
    screencap screenrecord input getprop setprop wm logcat dumpsys settings)
foreach(command IN LISTS ANDROID_COMPAT_COMMANDS)
    install(PROGRAMS android-compat/bin/_wrapper
            DESTINATION ${CMAKE_INSTALL_BINDIR} RENAME ${command})
endforeach()
install(FILES
    android-compat/lib/common.py
    android-compat/lib/x11.py
    android-compat/lib/props.py
    android-compat/lib/screencap.py
    android-compat/lib/screenrecord.py
    android-compat/lib/input.py
    android-compat/lib/getprop.py
    android-compat/lib/setprop.py
    android-compat/lib/wm.py
    android-compat/lib/logcat.py
    android-compat/lib/dumpsys.py
    android-compat/lib/settings.py
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/android-compat)
