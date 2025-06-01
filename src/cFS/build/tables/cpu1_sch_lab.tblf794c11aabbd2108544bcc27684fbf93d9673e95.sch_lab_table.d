# Template for table configuration

cfetables: staging/cpu1/cf/sch_lab_table.tbl

staging/cpu1/cf/sch_lab_table.tbl: CFE_TABLE_SCID      := 0x42
staging/cpu1/cf/sch_lab_table.tbl: CFE_TABLE_PRID      := 1
staging/cpu1/cf/sch_lab_table.tbl: CFE_TABLE_CPUNAME   := cpu1
staging/cpu1/cf/sch_lab_table.tbl: CFE_TABLE_APPNAME   := sch_lab
staging/cpu1/cf/sch_lab_table.tbl: CFE_TABLE_BASENAME  := sch_lab_table

# Rules to build staging/cpu1/cf/sch_lab_table.tbl
elf/cpu1/sch_lab_table.c.o: /home/vboxuser/SatelliteComSim/src/cFS/build/native/default_cpu1/apps/sch_lab/libtblobj_cpu1_sch_lab.tblf794c11aabbd2108544bcc27684fbf93d9673e95.a
staging/cpu1/cf/sch_lab_table.tbl: elf/cpu1/sch_lab_table.c.o


