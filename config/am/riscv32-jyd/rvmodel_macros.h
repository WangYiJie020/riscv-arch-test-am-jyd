#ifndef _RVMODEL_MACROS_H
#define _RVMODEL_MACROS_H

#define RVMODEL_DATA_SECTION

#define RVMODEL_HALT_PASS \
  li a0, 0;              \
  call halt;

#define RVMODEL_HALT_FAIL \
  li a0, 1;              \
  call halt;

#define RVMODEL_IO_WRITE_STR(_R1, _R2, _R3, _STR_PTR) \
1:                                                    ;\
  lbu _R1, 0(_STR_PTR)                                ;\
  beqz _R1, 2f                                        ;\
  la _R2, _my_ext_serial_port                         ;\
  sb _R1, 0(_R2)                                      ;\
  addi _STR_PTR, _STR_PTR, 1                          ;\
  j 1b                                                ;\
2:

#define RVMODEL_ACCESS_FAULT_ADDRESS 0x00000000

#define RVMODEL_SET_MEXT_INT(_R1, _R2)
#define RVMODEL_CLR_MEXT_INT(_R1, _R2)
#define RVMODEL_SET_MSW_INT(_R1, _R2)
#define RVMODEL_CLR_MSW_INT(_R1, _R2)
#define RVMODEL_SET_SEXT_INT(_R1, _R2)
#define RVMODEL_CLR_SEXT_INT(_R1, _R2)
#define RVMODEL_SET_SSW_INT(_R1, _R2)
#define RVMODEL_CLR_SSW_INT(_R1, _R2)
#define RVMODEL_INTERRUPT_LATENCY 10
#define RVMODEL_TIMER_INT_SOON_DELAY 100

#endif
