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
CMAKE_BINARY_DIR = /home/vboxuser/SatelliteComSim/src/cFS/build/native/default_cpu1

# Include any dependencies generated for this target.
include time/CMakeFiles/time.dir/depend.make
# Include any dependencies generated by the compiler for this target.
include time/CMakeFiles/time.dir/compiler_depend.make

# Include the progress variables for this target.
include time/CMakeFiles/time.dir/progress.make

# Include the compile flags for this target's objects.
include time/CMakeFiles/time.dir/flags.make

time/CMakeFiles/time.dir/fsw/src/cfe_time_api.c.o: time/CMakeFiles/time.dir/flags.make
time/CMakeFiles/time.dir/fsw/src/cfe_time_api.c.o: /home/vboxuser/SatelliteComSim/src/cFS/cfe/modules/time/fsw/src/cfe_time_api.c
time/CMakeFiles/time.dir/fsw/src/cfe_time_api.c.o: time/CMakeFiles/time.dir/compiler_depend.ts
	@$(CMAKE_COMMAND) -E cmake_echo_color "--switch=$(COLOR)" --green --progress-dir=/home/vboxuser/SatelliteComSim/src/cFS/build/native/default_cpu1/CMakeFiles --progress-num=$(CMAKE_PROGRESS_1) "Building C object time/CMakeFiles/time.dir/fsw/src/cfe_time_api.c.o"
	cd /home/vboxuser/SatelliteComSim/src/cFS/build/native/default_cpu1/time && /usr/bin/cc $(C_DEFINES) $(C_INCLUDES) $(C_FLAGS) -MD -MT time/CMakeFiles/time.dir/fsw/src/cfe_time_api.c.o -MF CMakeFiles/time.dir/fsw/src/cfe_time_api.c.o.d -o CMakeFiles/time.dir/fsw/src/cfe_time_api.c.o -c /home/vboxuser/SatelliteComSim/src/cFS/cfe/modules/time/fsw/src/cfe_time_api.c

time/CMakeFiles/time.dir/fsw/src/cfe_time_api.c.i: cmake_force
	@$(CMAKE_COMMAND) -E cmake_echo_color "--switch=$(COLOR)" --green "Preprocessing C source to CMakeFiles/time.dir/fsw/src/cfe_time_api.c.i"
	cd /home/vboxuser/SatelliteComSim/src/cFS/build/native/default_cpu1/time && /usr/bin/cc $(C_DEFINES) $(C_INCLUDES) $(C_FLAGS) -E /home/vboxuser/SatelliteComSim/src/cFS/cfe/modules/time/fsw/src/cfe_time_api.c > CMakeFiles/time.dir/fsw/src/cfe_time_api.c.i

time/CMakeFiles/time.dir/fsw/src/cfe_time_api.c.s: cmake_force
	@$(CMAKE_COMMAND) -E cmake_echo_color "--switch=$(COLOR)" --green "Compiling C source to assembly CMakeFiles/time.dir/fsw/src/cfe_time_api.c.s"
	cd /home/vboxuser/SatelliteComSim/src/cFS/build/native/default_cpu1/time && /usr/bin/cc $(C_DEFINES) $(C_INCLUDES) $(C_FLAGS) -S /home/vboxuser/SatelliteComSim/src/cFS/cfe/modules/time/fsw/src/cfe_time_api.c -o CMakeFiles/time.dir/fsw/src/cfe_time_api.c.s

time/CMakeFiles/time.dir/fsw/src/cfe_time_task.c.o: time/CMakeFiles/time.dir/flags.make
time/CMakeFiles/time.dir/fsw/src/cfe_time_task.c.o: /home/vboxuser/SatelliteComSim/src/cFS/cfe/modules/time/fsw/src/cfe_time_task.c
time/CMakeFiles/time.dir/fsw/src/cfe_time_task.c.o: time/CMakeFiles/time.dir/compiler_depend.ts
	@$(CMAKE_COMMAND) -E cmake_echo_color "--switch=$(COLOR)" --green --progress-dir=/home/vboxuser/SatelliteComSim/src/cFS/build/native/default_cpu1/CMakeFiles --progress-num=$(CMAKE_PROGRESS_2) "Building C object time/CMakeFiles/time.dir/fsw/src/cfe_time_task.c.o"
	cd /home/vboxuser/SatelliteComSim/src/cFS/build/native/default_cpu1/time && /usr/bin/cc $(C_DEFINES) $(C_INCLUDES) $(C_FLAGS) -MD -MT time/CMakeFiles/time.dir/fsw/src/cfe_time_task.c.o -MF CMakeFiles/time.dir/fsw/src/cfe_time_task.c.o.d -o CMakeFiles/time.dir/fsw/src/cfe_time_task.c.o -c /home/vboxuser/SatelliteComSim/src/cFS/cfe/modules/time/fsw/src/cfe_time_task.c

time/CMakeFiles/time.dir/fsw/src/cfe_time_task.c.i: cmake_force
	@$(CMAKE_COMMAND) -E cmake_echo_color "--switch=$(COLOR)" --green "Preprocessing C source to CMakeFiles/time.dir/fsw/src/cfe_time_task.c.i"
	cd /home/vboxuser/SatelliteComSim/src/cFS/build/native/default_cpu1/time && /usr/bin/cc $(C_DEFINES) $(C_INCLUDES) $(C_FLAGS) -E /home/vboxuser/SatelliteComSim/src/cFS/cfe/modules/time/fsw/src/cfe_time_task.c > CMakeFiles/time.dir/fsw/src/cfe_time_task.c.i

time/CMakeFiles/time.dir/fsw/src/cfe_time_task.c.s: cmake_force
	@$(CMAKE_COMMAND) -E cmake_echo_color "--switch=$(COLOR)" --green "Compiling C source to assembly CMakeFiles/time.dir/fsw/src/cfe_time_task.c.s"
	cd /home/vboxuser/SatelliteComSim/src/cFS/build/native/default_cpu1/time && /usr/bin/cc $(C_DEFINES) $(C_INCLUDES) $(C_FLAGS) -S /home/vboxuser/SatelliteComSim/src/cFS/cfe/modules/time/fsw/src/cfe_time_task.c -o CMakeFiles/time.dir/fsw/src/cfe_time_task.c.s

time/CMakeFiles/time.dir/fsw/src/cfe_time_tone.c.o: time/CMakeFiles/time.dir/flags.make
time/CMakeFiles/time.dir/fsw/src/cfe_time_tone.c.o: /home/vboxuser/SatelliteComSim/src/cFS/cfe/modules/time/fsw/src/cfe_time_tone.c
time/CMakeFiles/time.dir/fsw/src/cfe_time_tone.c.o: time/CMakeFiles/time.dir/compiler_depend.ts
	@$(CMAKE_COMMAND) -E cmake_echo_color "--switch=$(COLOR)" --green --progress-dir=/home/vboxuser/SatelliteComSim/src/cFS/build/native/default_cpu1/CMakeFiles --progress-num=$(CMAKE_PROGRESS_3) "Building C object time/CMakeFiles/time.dir/fsw/src/cfe_time_tone.c.o"
	cd /home/vboxuser/SatelliteComSim/src/cFS/build/native/default_cpu1/time && /usr/bin/cc $(C_DEFINES) $(C_INCLUDES) $(C_FLAGS) -MD -MT time/CMakeFiles/time.dir/fsw/src/cfe_time_tone.c.o -MF CMakeFiles/time.dir/fsw/src/cfe_time_tone.c.o.d -o CMakeFiles/time.dir/fsw/src/cfe_time_tone.c.o -c /home/vboxuser/SatelliteComSim/src/cFS/cfe/modules/time/fsw/src/cfe_time_tone.c

time/CMakeFiles/time.dir/fsw/src/cfe_time_tone.c.i: cmake_force
	@$(CMAKE_COMMAND) -E cmake_echo_color "--switch=$(COLOR)" --green "Preprocessing C source to CMakeFiles/time.dir/fsw/src/cfe_time_tone.c.i"
	cd /home/vboxuser/SatelliteComSim/src/cFS/build/native/default_cpu1/time && /usr/bin/cc $(C_DEFINES) $(C_INCLUDES) $(C_FLAGS) -E /home/vboxuser/SatelliteComSim/src/cFS/cfe/modules/time/fsw/src/cfe_time_tone.c > CMakeFiles/time.dir/fsw/src/cfe_time_tone.c.i

time/CMakeFiles/time.dir/fsw/src/cfe_time_tone.c.s: cmake_force
	@$(CMAKE_COMMAND) -E cmake_echo_color "--switch=$(COLOR)" --green "Compiling C source to assembly CMakeFiles/time.dir/fsw/src/cfe_time_tone.c.s"
	cd /home/vboxuser/SatelliteComSim/src/cFS/build/native/default_cpu1/time && /usr/bin/cc $(C_DEFINES) $(C_INCLUDES) $(C_FLAGS) -S /home/vboxuser/SatelliteComSim/src/cFS/cfe/modules/time/fsw/src/cfe_time_tone.c -o CMakeFiles/time.dir/fsw/src/cfe_time_tone.c.s

time/CMakeFiles/time.dir/fsw/src/cfe_time_utils.c.o: time/CMakeFiles/time.dir/flags.make
time/CMakeFiles/time.dir/fsw/src/cfe_time_utils.c.o: /home/vboxuser/SatelliteComSim/src/cFS/cfe/modules/time/fsw/src/cfe_time_utils.c
time/CMakeFiles/time.dir/fsw/src/cfe_time_utils.c.o: time/CMakeFiles/time.dir/compiler_depend.ts
	@$(CMAKE_COMMAND) -E cmake_echo_color "--switch=$(COLOR)" --green --progress-dir=/home/vboxuser/SatelliteComSim/src/cFS/build/native/default_cpu1/CMakeFiles --progress-num=$(CMAKE_PROGRESS_4) "Building C object time/CMakeFiles/time.dir/fsw/src/cfe_time_utils.c.o"
	cd /home/vboxuser/SatelliteComSim/src/cFS/build/native/default_cpu1/time && /usr/bin/cc $(C_DEFINES) $(C_INCLUDES) $(C_FLAGS) -MD -MT time/CMakeFiles/time.dir/fsw/src/cfe_time_utils.c.o -MF CMakeFiles/time.dir/fsw/src/cfe_time_utils.c.o.d -o CMakeFiles/time.dir/fsw/src/cfe_time_utils.c.o -c /home/vboxuser/SatelliteComSim/src/cFS/cfe/modules/time/fsw/src/cfe_time_utils.c

time/CMakeFiles/time.dir/fsw/src/cfe_time_utils.c.i: cmake_force
	@$(CMAKE_COMMAND) -E cmake_echo_color "--switch=$(COLOR)" --green "Preprocessing C source to CMakeFiles/time.dir/fsw/src/cfe_time_utils.c.i"
	cd /home/vboxuser/SatelliteComSim/src/cFS/build/native/default_cpu1/time && /usr/bin/cc $(C_DEFINES) $(C_INCLUDES) $(C_FLAGS) -E /home/vboxuser/SatelliteComSim/src/cFS/cfe/modules/time/fsw/src/cfe_time_utils.c > CMakeFiles/time.dir/fsw/src/cfe_time_utils.c.i

time/CMakeFiles/time.dir/fsw/src/cfe_time_utils.c.s: cmake_force
	@$(CMAKE_COMMAND) -E cmake_echo_color "--switch=$(COLOR)" --green "Compiling C source to assembly CMakeFiles/time.dir/fsw/src/cfe_time_utils.c.s"
	cd /home/vboxuser/SatelliteComSim/src/cFS/build/native/default_cpu1/time && /usr/bin/cc $(C_DEFINES) $(C_INCLUDES) $(C_FLAGS) -S /home/vboxuser/SatelliteComSim/src/cFS/cfe/modules/time/fsw/src/cfe_time_utils.c -o CMakeFiles/time.dir/fsw/src/cfe_time_utils.c.s

time/CMakeFiles/time.dir/fsw/src/cfe_time_dispatch.c.o: time/CMakeFiles/time.dir/flags.make
time/CMakeFiles/time.dir/fsw/src/cfe_time_dispatch.c.o: /home/vboxuser/SatelliteComSim/src/cFS/cfe/modules/time/fsw/src/cfe_time_dispatch.c
time/CMakeFiles/time.dir/fsw/src/cfe_time_dispatch.c.o: time/CMakeFiles/time.dir/compiler_depend.ts
	@$(CMAKE_COMMAND) -E cmake_echo_color "--switch=$(COLOR)" --green --progress-dir=/home/vboxuser/SatelliteComSim/src/cFS/build/native/default_cpu1/CMakeFiles --progress-num=$(CMAKE_PROGRESS_5) "Building C object time/CMakeFiles/time.dir/fsw/src/cfe_time_dispatch.c.o"
	cd /home/vboxuser/SatelliteComSim/src/cFS/build/native/default_cpu1/time && /usr/bin/cc $(C_DEFINES) $(C_INCLUDES) $(C_FLAGS) -MD -MT time/CMakeFiles/time.dir/fsw/src/cfe_time_dispatch.c.o -MF CMakeFiles/time.dir/fsw/src/cfe_time_dispatch.c.o.d -o CMakeFiles/time.dir/fsw/src/cfe_time_dispatch.c.o -c /home/vboxuser/SatelliteComSim/src/cFS/cfe/modules/time/fsw/src/cfe_time_dispatch.c

time/CMakeFiles/time.dir/fsw/src/cfe_time_dispatch.c.i: cmake_force
	@$(CMAKE_COMMAND) -E cmake_echo_color "--switch=$(COLOR)" --green "Preprocessing C source to CMakeFiles/time.dir/fsw/src/cfe_time_dispatch.c.i"
	cd /home/vboxuser/SatelliteComSim/src/cFS/build/native/default_cpu1/time && /usr/bin/cc $(C_DEFINES) $(C_INCLUDES) $(C_FLAGS) -E /home/vboxuser/SatelliteComSim/src/cFS/cfe/modules/time/fsw/src/cfe_time_dispatch.c > CMakeFiles/time.dir/fsw/src/cfe_time_dispatch.c.i

time/CMakeFiles/time.dir/fsw/src/cfe_time_dispatch.c.s: cmake_force
	@$(CMAKE_COMMAND) -E cmake_echo_color "--switch=$(COLOR)" --green "Compiling C source to assembly CMakeFiles/time.dir/fsw/src/cfe_time_dispatch.c.s"
	cd /home/vboxuser/SatelliteComSim/src/cFS/build/native/default_cpu1/time && /usr/bin/cc $(C_DEFINES) $(C_INCLUDES) $(C_FLAGS) -S /home/vboxuser/SatelliteComSim/src/cFS/cfe/modules/time/fsw/src/cfe_time_dispatch.c -o CMakeFiles/time.dir/fsw/src/cfe_time_dispatch.c.s

# Object files for target time
time_OBJECTS = \
"CMakeFiles/time.dir/fsw/src/cfe_time_api.c.o" \
"CMakeFiles/time.dir/fsw/src/cfe_time_task.c.o" \
"CMakeFiles/time.dir/fsw/src/cfe_time_tone.c.o" \
"CMakeFiles/time.dir/fsw/src/cfe_time_utils.c.o" \
"CMakeFiles/time.dir/fsw/src/cfe_time_dispatch.c.o"

# External object files for target time
time_EXTERNAL_OBJECTS =

time/libtime.a: time/CMakeFiles/time.dir/fsw/src/cfe_time_api.c.o
time/libtime.a: time/CMakeFiles/time.dir/fsw/src/cfe_time_task.c.o
time/libtime.a: time/CMakeFiles/time.dir/fsw/src/cfe_time_tone.c.o
time/libtime.a: time/CMakeFiles/time.dir/fsw/src/cfe_time_utils.c.o
time/libtime.a: time/CMakeFiles/time.dir/fsw/src/cfe_time_dispatch.c.o
time/libtime.a: time/CMakeFiles/time.dir/build.make
time/libtime.a: time/CMakeFiles/time.dir/link.txt
	@$(CMAKE_COMMAND) -E cmake_echo_color "--switch=$(COLOR)" --green --bold --progress-dir=/home/vboxuser/SatelliteComSim/src/cFS/build/native/default_cpu1/CMakeFiles --progress-num=$(CMAKE_PROGRESS_6) "Linking C static library libtime.a"
	cd /home/vboxuser/SatelliteComSim/src/cFS/build/native/default_cpu1/time && $(CMAKE_COMMAND) -P CMakeFiles/time.dir/cmake_clean_target.cmake
	cd /home/vboxuser/SatelliteComSim/src/cFS/build/native/default_cpu1/time && $(CMAKE_COMMAND) -E cmake_link_script CMakeFiles/time.dir/link.txt --verbose=$(VERBOSE)

# Rule to build all files generated by this target.
time/CMakeFiles/time.dir/build: time/libtime.a
.PHONY : time/CMakeFiles/time.dir/build

time/CMakeFiles/time.dir/clean:
	cd /home/vboxuser/SatelliteComSim/src/cFS/build/native/default_cpu1/time && $(CMAKE_COMMAND) -P CMakeFiles/time.dir/cmake_clean.cmake
.PHONY : time/CMakeFiles/time.dir/clean

time/CMakeFiles/time.dir/depend:
	cd /home/vboxuser/SatelliteComSim/src/cFS/build/native/default_cpu1 && $(CMAKE_COMMAND) -E cmake_depends "Unix Makefiles" /home/vboxuser/SatelliteComSim/src/cFS/cfe /home/vboxuser/SatelliteComSim/src/cFS/cfe/modules/time /home/vboxuser/SatelliteComSim/src/cFS/build/native/default_cpu1 /home/vboxuser/SatelliteComSim/src/cFS/build/native/default_cpu1/time /home/vboxuser/SatelliteComSim/src/cFS/build/native/default_cpu1/time/CMakeFiles/time.dir/DependInfo.cmake "--color=$(COLOR)"
.PHONY : time/CMakeFiles/time.dir/depend

