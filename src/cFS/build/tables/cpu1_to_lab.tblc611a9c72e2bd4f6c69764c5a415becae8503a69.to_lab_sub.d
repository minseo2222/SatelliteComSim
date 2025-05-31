# Template for table configuration

cfetables: staging/cpu1/cf/to_lab_sub.tbl

staging/cpu1/cf/to_lab_sub.tbl: CFE_TABLE_SCID      := 0x42
staging/cpu1/cf/to_lab_sub.tbl: CFE_TABLE_PRID      := 1
staging/cpu1/cf/to_lab_sub.tbl: CFE_TABLE_CPUNAME   := cpu1
staging/cpu1/cf/to_lab_sub.tbl: CFE_TABLE_APPNAME   := to_lab
staging/cpu1/cf/to_lab_sub.tbl: CFE_TABLE_BASENAME  := to_lab_sub

# Rules to build staging/cpu1/cf/to_lab_sub.tbl
elf/cpu1/to_lab_sub.c.o: /home/vboxuser/SatelliteComSim/src/cFS/build/native/default_cpu1/apps/to_lab/libtblobj_cpu1_to_lab.tblc611a9c72e2bd4f6c69764c5a415becae8503a69.a
staging/cpu1/cf/to_lab_sub.tbl: elf/cpu1/to_lab_sub.c.o


