# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 wentywenty
# Source selection derived from nmeum/android-tools and standalone-linux-adbd.
add_compile_definitions(_GNU_SOURCE _FILE_OFFSET_BITS=64 _LARGEFILE64_SOURCE)
add_compile_options(-Wno-attributes)

function(port_library name directory)
    set(sources ${ARGN})
    list(TRANSFORM sources PREPEND "${PORT_SOURCE}/${directory}/")
    add_library(${name} STATIC ${sources})
    target_include_directories(${name} PUBLIC
        "${PORT_SOURCE}/thirdparty/core/include"
        "${PORT_SOURCE}/thirdparty/core/libcutils/include"
        "${PORT_SOURCE}/thirdparty/libbase/include"
        "${PORT_SOURCE}/thirdparty/logging/liblog/include")
endfunction()

port_library(android_log thirdparty/logging/liblog
    log_event_list.cpp log_event_write.cpp logger_name.cpp logger_read.cpp
    logger_write.cpp properties.cpp logprint.cpp)
target_compile_definitions(android_log PRIVATE LIBLOG_LOG_TAG=1006 FAKE_LOG_DEVICE=1)

port_library(android_base thirdparty/libbase
    chrono_utils.cpp cmsg.cpp file.cpp hex.cpp logging.cpp mapped_file.cpp
    parsebool.cpp parsenetaddress.cpp posix_strerror_r.cpp process.cpp properties.cpp
    result.cpp stringprintf.cpp strings.cpp threads.cpp errors_unix.cpp)
target_link_libraries(android_base PUBLIC fmt::fmt android_log)

port_library(android_cutils thirdparty/core/libcutils
    android_get_control_file.cpp ashmem-host.cpp config_utils.cpp fs.cpp hashmap.cpp
    iosched_policy.cpp load_file.cpp multiuser.cpp native_handle.cpp properties.cpp
    record_stream.cpp socket_inaddr_any_server_unix.cpp socket_local_client_unix.cpp
    socket_local_server_unix.cpp socket_network_client_unix.cpp sockets_unix.cpp
    sockets.cpp str_parms.cpp strlcpy.c trace-host.cpp)
target_include_directories(android_cutils PRIVATE "${PORT_SOURCE}/thirdparty/core/libutils/include")
target_link_libraries(android_cutils PUBLIC android_base android_log)

set(daemon_sources
    adb.cpp adb_io.cpp adb_listeners.cpp adb_mdns.cpp adb_trace.cpp adb_unique_fd.cpp
    adb_utils.cpp apacket_reader.cpp fdevent/fdevent.cpp fdevent/fdevent_epoll.cpp
    services.cpp shell_service_protocol.cpp sockets.cpp socket_spec.cpp
    sysdeps/env.cpp sysdeps/errno.cpp sysdeps/posix/network.cpp sysdeps_unix.cpp
    transport.cpp transport_fd.cpp types.cpp daemon/file_sync_service.cpp
    daemon/logging.cpp daemon/main.cpp daemon/services.cpp daemon/shell_service.cpp
    daemon/transport_socket_server.cpp daemon/usb.cpp daemon/usb_ffs.cpp
    daemon/linux_stubs.cpp)
list(TRANSFORM daemon_sources PREPEND "${PORT_SOURCE}/thirdparty/adb/")
add_executable(adbd ${daemon_sources} "${PORT_SOURCE}/thirdparty/core/libasyncio/AsyncIO.cpp")
target_compile_definitions(adbd PRIVATE
    ADB_HOST=0 ADB_STANDALONE_LINUX=1 ADB_LINUX_USB=1
    ANDROID_BASE_UNIQUE_FD_DISABLE_IMPLICIT_CONVERSION=1)
target_include_directories(adbd PRIVATE
    "${CMAKE_CURRENT_BINARY_DIR}" "${PORT_SOURCE}/thirdparty/adb"
    "${PORT_SOURCE}/thirdparty/adb/libs/libadbd_fs/include"
    "${PORT_SOURCE}/thirdparty/core/diagnose_usb/include"
    "${PORT_SOURCE}/thirdparty/core/libasyncio/include")
target_link_libraries(adbd PRIVATE android_cutils android_base android_log
    PkgConfig::BROTLI PkgConfig::LZ4 PkgConfig::ZSTD Threads::Threads resolv util)
