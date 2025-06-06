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

# Utility rule file for osal-apiguide.

# Include any custom commands dependencies for this target.
include docs/osal-apiguide/CMakeFiles/osal-apiguide.dir/compiler_depend.make

# Include the progress variables for this target.
include docs/osal-apiguide/CMakeFiles/osal-apiguide.dir/progress.make

docs/osal-apiguide/CMakeFiles/osal-apiguide: docs/osal-apiguide/html/index.html
	cd /home/vboxuser/SatelliteComSim/src/cFS/build/docs/osal-apiguide && echo OSAL\ API\ Guide:\ file:///home/vboxuser/SatelliteComSim/src/cFS/build/docs/osal-apiguide/html/index.html

docs/osal-apiguide/html/index.html: docs/osal-apiguide/osal-apiguide.doxyfile
docs/osal-apiguide/html/index.html: docs/osal-common.doxyfile
docs/osal-apiguide/html/index.html: docs/osal-public-api.doxyfile
docs/osal-apiguide/html/index.html: /home/vboxuser/SatelliteComSim/src/cFS/osal/docs/src/osal_frontpage.dox
docs/osal-apiguide/html/index.html: /home/vboxuser/SatelliteComSim/src/cFS/osal/docs/src/osal_fs.dox
docs/osal-apiguide/html/index.html: /home/vboxuser/SatelliteComSim/src/cFS/osal/docs/src/osal_timer.dox
	@$(CMAKE_COMMAND) -E cmake_echo_color "--switch=$(COLOR)" --blue --bold --progress-dir=/home/vboxuser/SatelliteComSim/src/cFS/build/CMakeFiles --progress-num=$(CMAKE_PROGRESS_1) "Generating html/index.html"
	cd /home/vboxuser/SatelliteComSim/src/cFS/build/docs/osal-apiguide && doxygen /home/vboxuser/SatelliteComSim/src/cFS/build/docs/osal-apiguide/osal-apiguide.doxyfile

docs/osal-public-api.doxyfile:
	@$(CMAKE_COMMAND) -E cmake_echo_color "--switch=$(COLOR)" --blue --bold --progress-dir=/home/vboxuser/SatelliteComSim/src/cFS/build/CMakeFiles --progress-num=$(CMAKE_PROGRESS_2) "Generating ../osal-public-api.doxyfile"
	cd /home/vboxuser/SatelliteComSim/src/cFS/build/docs/osal-apiguide && /usr/bin/cmake -DINCLUDE_DIRECTORIES="/home/vboxuser/SatelliteComSim/src/cFS/osal/src/os/inc /home/vboxuser/SatelliteComSim/src/cFS/build/osal_public_api/inc " -DCOMPILE_DEFINITIONS="" -DINPUT_TEMPLATE="/home/vboxuser/SatelliteComSim/src/cFS/osal/docs/src/osal-public-api.doxyfile.in" -DOUTPUT_FILE="/home/vboxuser/SatelliteComSim/src/cFS/build/docs/osal-public-api.doxyfile" -P /home/vboxuser/SatelliteComSim/src/cFS/osal/docs/src/generate-public-api-doxyfile.cmake

osal-apiguide: docs/osal-apiguide/CMakeFiles/osal-apiguide
osal-apiguide: docs/osal-apiguide/html/index.html
osal-apiguide: docs/osal-public-api.doxyfile
osal-apiguide: docs/osal-apiguide/CMakeFiles/osal-apiguide.dir/build.make
.PHONY : osal-apiguide

# Rule to build all files generated by this target.
docs/osal-apiguide/CMakeFiles/osal-apiguide.dir/build: osal-apiguide
.PHONY : docs/osal-apiguide/CMakeFiles/osal-apiguide.dir/build

docs/osal-apiguide/CMakeFiles/osal-apiguide.dir/clean:
	cd /home/vboxuser/SatelliteComSim/src/cFS/build/docs/osal-apiguide && $(CMAKE_COMMAND) -P CMakeFiles/osal-apiguide.dir/cmake_clean.cmake
.PHONY : docs/osal-apiguide/CMakeFiles/osal-apiguide.dir/clean

docs/osal-apiguide/CMakeFiles/osal-apiguide.dir/depend:
	cd /home/vboxuser/SatelliteComSim/src/cFS/build && $(CMAKE_COMMAND) -E cmake_depends "Unix Makefiles" /home/vboxuser/SatelliteComSim/src/cFS/cfe /home/vboxuser/SatelliteComSim/src/cFS/osal/docs/src /home/vboxuser/SatelliteComSim/src/cFS/build /home/vboxuser/SatelliteComSim/src/cFS/build/docs/osal-apiguide /home/vboxuser/SatelliteComSim/src/cFS/build/docs/osal-apiguide/CMakeFiles/osal-apiguide.dir/DependInfo.cmake "--color=$(COLOR)"
.PHONY : docs/osal-apiguide/CMakeFiles/osal-apiguide.dir/depend

