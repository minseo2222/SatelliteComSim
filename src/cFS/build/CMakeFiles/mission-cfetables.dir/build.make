# CMAKE generated file: DO NOT EDIT!
# Generated by "Unix Makefiles" Generator, CMake Version 3.28

# Delete rule output on recipe failure.
.DELETE_ON_ERROR:

#=============================================================================
# Special targets provided by cmake.

# Disable implicit rules so canonical targets will work.
.SUFFIXES:

# Disable VCS-based implicit rules.
% : %,v

# Disable VCS-based implicit rules.
% : RCS/%

# Disable VCS-based implicit rules.
% : RCS/%,v

# Disable VCS-based implicit rules.
% : SCCS/s.%

# Disable VCS-based implicit rules.
% : s.%

.SUFFIXES: .hpux_make_needs_suffix_list

# Command-line flag to silence nested $(MAKE).
$(VERBOSE)MAKESILENT = -s

#Suppress display of executed commands.
$(VERBOSE).SILENT:

# A target that is always out of date.
cmake_force:
.PHONY : cmake_force

#=============================================================================
# Set environment variables for the build.

# The shell in which to execute make rules.
SHELL = /bin/sh

# The CMake executable.
CMAKE_COMMAND = /usr/bin/cmake

# The command to remove a file.
RM = /usr/bin/cmake -E rm -f

# Escaping for special characters.
EQUALS = =

# The top-level source directory on which CMake was run.
CMAKE_SOURCE_DIR = /home/vboxuser/SatelliteComSim/src/cFS/cfe

# The top-level build directory on which CMake was run.
CMAKE_BINARY_DIR = /home/vboxuser/SatelliteComSim/src/cFS/build

# Utility rule file for mission-cfetables.

# Include any custom commands dependencies for this target.
include CMakeFiles/mission-cfetables.dir/compiler_depend.make

# Include the progress variables for this target.
include CMakeFiles/mission-cfetables.dir/progress.make

mission-cfetables: CMakeFiles/mission-cfetables.dir/build.make
.PHONY : mission-cfetables

# Rule to build all files generated by this target.
CMakeFiles/mission-cfetables.dir/build: mission-cfetables
.PHONY : CMakeFiles/mission-cfetables.dir/build

CMakeFiles/mission-cfetables.dir/clean:
	$(CMAKE_COMMAND) -P CMakeFiles/mission-cfetables.dir/cmake_clean.cmake
.PHONY : CMakeFiles/mission-cfetables.dir/clean

CMakeFiles/mission-cfetables.dir/depend:
	cd /home/vboxuser/SatelliteComSim/src/cFS/build && $(CMAKE_COMMAND) -E cmake_depends "Unix Makefiles" /home/vboxuser/SatelliteComSim/src/cFS/cfe /home/vboxuser/SatelliteComSim/src/cFS/cfe /home/vboxuser/SatelliteComSim/src/cFS/build /home/vboxuser/SatelliteComSim/src/cFS/build /home/vboxuser/SatelliteComSim/src/cFS/build/CMakeFiles/mission-cfetables.dir/DependInfo.cmake "--color=$(COLOR)"
.PHONY : CMakeFiles/mission-cfetables.dir/depend

