# Abstract-Machine Migration

This fork keeps the old `riscv-arch-test-am` command style while using the
current ACT4 test tree.

## Environment

Only `JYD_AM_HOME` is used for Abstract-Machine:

```sh
export JYD_AM_HOME=/home/wuser/gitclones/jyd/abstract-machine
```

The compatibility runner defaults to that path if `JYD_AM_HOME` is not set.
`AM_HOME` is no longer used.

The runner expects these tools on `PATH`:

```sh
riscv32-unknown-linux-gnu-gcc
riscv32-unknown-linux-gnu-objdump
sail_riscv_sim
```

## Commands

The old command shape is preserved for the first supported target,
`riscv32-jyd`:

```sh
make ARCH=riscv32-jyd run
make ARCH=riscv32-jyd TEST_ISA=I ALL=add-00 run
make ARCH=riscv32-jyd TEST_ISA="I M" ALL="add-00 mul-00" run
make ARCH=riscv32-jyd clean-am
```

`TEST_ISA` is a whitespace-separated list of extension directories under
`tests/rv32i`. `ALL` and `EXCLUDE_TEST` accept the current ACT4 names
(`add-00`, `I-add-00`, `I/I-add-00`) and also map old `*-01` names to the
new `*-00` form where applicable.

## What Changed From The Old Port

The old port compiled files directly from paths like:

```text
riscv-test-suite/rv32i_m/I/src/add-01.S
```

The current upstream tree uses generated ACT4 tests, for example:

```text
tests/rv32i/I/I-add-00.S
```

ACT4 tests are self-checking when built with a reference signature. The AM
compatibility runner therefore compiles a signature-only ELF for each selected
test, runs it with `sail_riscv_sim --rv32`, converts the signature to assembler
directives, then rebuilds the selected test through `${JYD_AM_HOME}/Makefile`
with:

```text
RVTEST_SELFCHECK
SIGNATURE_FILE=<generated .results file>
```

The final linked image, `.bin`, `.data.bin`, `.data.coe`, and disassembly are
still produced by the JYD AM platform rules.

## Current Scope

The implemented compatibility target is `riscv32-jyd`. It is intended first
for `I` tests and for extensions whose instructions are accepted by
`${JYD_AM_HOME}/scripts/riscv32-jyd.mk`. If an extension fails to assemble,
check that the AM `-march` string supports it before treating the failure as a
DUT failure.
