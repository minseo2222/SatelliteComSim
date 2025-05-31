# Template for table configuration

cfetables: staging/cpu1/cf/sample_app_tbl.tbl

staging/cpu1/cf/sample_app_tbl.tbl: CFE_TABLE_SCID      := 0x42
staging/cpu1/cf/sample_app_tbl.tbl: CFE_TABLE_PRID      := 1
staging/cpu1/cf/sample_app_tbl.tbl: CFE_TABLE_CPUNAME   := cpu1
staging/cpu1/cf/sample_app_tbl.tbl: CFE_TABLE_APPNAME   := sample_app
staging/cpu1/cf/sample_app_tbl.tbl: CFE_TABLE_BASENAME  := sample_app_tbl

# Rules to build staging/cpu1/cf/sample_app_tbl.tbl
elf/cpu1/sample_app_tbl.c.o: /home/vboxuser/SatelliteComSim/src/cFS/build/native/default_cpu1/apps/sample_app/libtblobj_cpu1_sample_app.tbl7dfe5c3adb288c11976a8c96454fb3a99c97dc29.a
staging/cpu1/cf/sample_app_tbl.tbl: elf/cpu1/sample_app_tbl.c.o


