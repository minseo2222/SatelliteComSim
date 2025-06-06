# Install script for directory: /home/vboxuser/SatelliteComSim/src/cFS/psp

# Set the install prefix
if(NOT DEFINED CMAKE_INSTALL_PREFIX)
  set(CMAKE_INSTALL_PREFIX "/exe")
endif()
string(REGEX REPLACE "/$" "" CMAKE_INSTALL_PREFIX "${CMAKE_INSTALL_PREFIX}")

# Set the install configuration name.
if(NOT DEFINED CMAKE_INSTALL_CONFIG_NAME)
  if(BUILD_TYPE)
    string(REGEX REPLACE "^[^A-Za-z0-9_]+" ""
           CMAKE_INSTALL_CONFIG_NAME "${BUILD_TYPE}")
  else()
    set(CMAKE_INSTALL_CONFIG_NAME "debug")
  endif()
  message(STATUS "Install configuration: \"${CMAKE_INSTALL_CONFIG_NAME}\"")
endif()

# Set the component getting installed.
if(NOT CMAKE_INSTALL_COMPONENT)
  if(COMPONENT)
    message(STATUS "Install component: \"${COMPONENT}\"")
    set(CMAKE_INSTALL_COMPONENT "${COMPONENT}")
  else()
    set(CMAKE_INSTALL_COMPONENT)
  endif()
endif()

# Install shared libraries without execute permission?
if(NOT DEFINED CMAKE_INSTALL_SO_NO_EXE)
  set(CMAKE_INSTALL_SO_NO_EXE "1")
endif()

# Is this installation the result of a crosscompile?
if(NOT DEFINED CMAKE_CROSSCOMPILING)
  set(CMAKE_CROSSCOMPILING "FALSE")
endif()

# Set default install directory permissions.
if(NOT DEFINED CMAKE_OBJDUMP)
  set(CMAKE_OBJDUMP "/usr/bin/objdump")
endif()

if(NOT CMAKE_INSTALL_LOCAL_ONLY)
  # Include the install script for each subdirectory.
  include("/home/vboxuser/SatelliteComSim/src/cFS/build/native/default_cpu1/psp/pc-linux-impl/cmake_install.cmake")
  include("/home/vboxuser/SatelliteComSim/src/cFS/build/native/default_cpu1/psp/pc-linux-shared/cmake_install.cmake")
  include("/home/vboxuser/SatelliteComSim/src/cFS/build/native/default_cpu1/psp/soft_timebase-pc-linux-impl/cmake_install.cmake")
  include("/home/vboxuser/SatelliteComSim/src/cFS/build/native/default_cpu1/psp/timebase_posix_clock-pc-linux-impl/cmake_install.cmake")
  include("/home/vboxuser/SatelliteComSim/src/cFS/build/native/default_cpu1/psp/eeprom_mmap_file-pc-linux-impl/cmake_install.cmake")
  include("/home/vboxuser/SatelliteComSim/src/cFS/build/native/default_cpu1/psp/ram_notimpl-pc-linux-impl/cmake_install.cmake")
  include("/home/vboxuser/SatelliteComSim/src/cFS/build/native/default_cpu1/psp/port_notimpl-pc-linux-impl/cmake_install.cmake")
  include("/home/vboxuser/SatelliteComSim/src/cFS/build/native/default_cpu1/psp/iodriver-pc-linux-impl/cmake_install.cmake")
  include("/home/vboxuser/SatelliteComSim/src/cFS/build/native/default_cpu1/psp/linux_sysmon-pc-linux-impl/cmake_install.cmake")

endif()

