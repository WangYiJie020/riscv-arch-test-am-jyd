# AGENTS.md

## Project Goal

This fork ports the old `riscv-arch-test-am` workflow onto the current
`riscv-arch-test` ACT4 tree. Preserve the old user-facing execution style where
possible, especially:

```sh
make ARCH=riscv32-jyd run
make ARCH=riscv32-jyd TEST_ISA=I ALL=add-00 run
make ARCH=riscv32-jyd TEST_ISA="I M" ALL="add-00 mul-00" run
```

The first supported Abstract-Machine target is `riscv32-jyd`.

## Abstract-Machine Rules

- Use `JYD_AM_HOME` only. Do not reintroduce `AM_HOME`.
- Default `JYD_AM_HOME` is `/home/wuser/gitclones/jyd/abstract-machine`.
- The compatibility entry point is `scripts/am_compat.py`, invoked by the root
  `Makefile` targets `run`, `image`, `gdb`, and `clean-am`.
- Generated AM compatibility files belong under `work/am-compat`,
  `work/am-riscv32-jyd`, or root `build/`; do not commit generated outputs.
- The migration note for users is `docs/abstract-machine-migration.md`.

## Test Flow

ACT4 tests are self-checking when built with a reference signature. The AM
compatibility runner must:

1. Select ACT4 tests from `tests/rv32i/<TEST_ISA>/*.S`.
2. Compile a signature-only ELF with `riscv32-unknown-linux-gnu-gcc`.
3. Run `sail_riscv_sim --rv32 --test-signature=...`.
4. Convert the Sail signature into `.word` assembler directives.
5. Rebuild the selected test through `${JYD_AM_HOME}/Makefile` with
   `RVTEST_SELFCHECK` and `SIGNATURE_FILE=...`.

Do not depend on ACT/UDB config generation for the AM compatibility path unless
there is a deliberate migration plan.

## Toolchain Requirements

- `riscv32-unknown-linux-gnu-gcc` must be on `PATH`; version `15.1.0` has been
  verified.
- `sail_riscv_sim` must be on `PATH`; Sail `0.11` has been verified with the
  direct `--rv32` invocation.
- AM's own makefiles may set `CROSS_COMPILE := riscv64-linux-gnu-`. The
  compatibility runner must pass `CROSS_COMPILE=riscv32-unknown-linux-gnu-` as
  a make command-line variable, not only as an environment variable, so it wins
  over AM makefile assignments.

This command verifies the compiler actually used by AM:

```sh
make -B -n -f work/am-compat/makefiles/Makefile.M-mul-00 \
  ARCH=riscv32-jyd CROSS_COMPILE=riscv32-unknown-linux-gnu- image
```

The output should use `riscv32-unknown-linux-gnu-gcc`, `ld`, `objdump`, and
`objcopy`.

## Known Pitfalls

- ACT4 test names changed. Selectors like `add-01` should map to the current
  `add-00` form where applicable. Accept `add-00`, `I-add-00`, and
  `I/I-add-00`.
- `tests/env/utils.h` uses `LA()` with `.align UNROLLSZ`. If the wrong
  assembler is used, padding in executable regions can become `0x00000000` and
  JYD simulation reports `invalid opcode`. With the verified
  `riscv32-unknown-linux-gnu-gcc 15.1.0` path, that padding becomes legal
  `0x00000013` NOP instructions.
- If `invalid opcode` reappears around `cleanup_epilogs` or failure-reporting
  code, first check the actual assembler/compiler used by AM before changing
  ACT4 macros.
- Linker warnings about the signature-only ELF having an RWX LOAD segment are
  currently expected and are not test failures by themselves.

## Verification Commands

Run focused checks after touching the compatibility path:

```sh
python3 -m py_compile scripts/am_compat.py
make ARCH=riscv32-jyd TEST_ISA=I ALL=add-00 run
make ARCH=riscv32-jyd TEST_ISA=M ALL=mul-00 run
make ARCH=riscv32-jyd TEST_ISA="I M" ALL="add-00 mul-00" run
```

For the padding issue specifically:

```sh
riscv32-unknown-linux-gnu-objdump -s \
  --start-address=0x800046a0 \
  --stop-address=0x800046d0 \
  build/M-mul-00-riscv32-jyd.elf
```

The bytes in the alignment gap should contain `13000000` words, not
`00000000`.

