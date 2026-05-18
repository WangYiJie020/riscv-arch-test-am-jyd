#!/usr/bin/env python3
"""Compatibility runner for the old Abstract-Machine workflow."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JYD_AM_HOME = Path("/home/wuser/gitclones/jyd/abstract-machine")
WORKDIR = REPO_ROOT / "work"
AM_WORKDIR = WORKDIR / "am-compat"

MARCH_RE = re.compile(r"^# MARCH:\s*(\S+)", re.MULTILINE)
TEST_FLEN_RE = re.compile(r"^#\s+FLEN:\s*(\d+)", re.MULTILINE)


@dataclass(frozen=True)
class ArchConfig:
    name: str
    xlen: int

    @property
    def include_dir(self) -> Path:
        return REPO_ROOT / "config/am" / self.name

    @property
    def workdir(self) -> Path:
        return WORKDIR / f"am-{self.name}"

    @property
    def linker_script(self) -> Path:
        return self.include_dir / "link.ld"


@dataclass(frozen=True)
class TestCase:
    extension: str
    path: Path

    @property
    def rel_path(self) -> Path:
        return self.path.relative_to(REPO_ROOT)

    @property
    def build_rel(self) -> Path:
        return self.path.relative_to(REPO_ROOT / "tests/rv32i").with_suffix("")

    @property
    def name(self) -> str:
        return self.path.stem

    @property
    def short_name(self) -> str:
        prefix = f"{self.extension}-"
        return self.name.removeprefix(prefix)


SUPPORTED_ARCHES = {
    "riscv32-jyd": ArchConfig(name="riscv32-jyd", xlen=32),
    "riscv32-nemu": ArchConfig(name="riscv32-nemu", xlen=32),
}


def split_words(value: str) -> list[str]:
    return [item for item in value.split() if item]


def normalize_selector(selector: str) -> set[str]:
    selectors = {selector}
    if selector.endswith("-01"):
        selectors.add(f"{selector[:-3]}-00")
    return selectors


def discover_tests(test_isa: list[str]) -> list[TestCase]:
    tests: list[TestCase] = []
    for extension in test_isa:
        test_dir = REPO_ROOT / "tests/rv32i" / extension
        if not test_dir.is_dir():
            raise SystemExit(f"Unsupported TEST_ISA entry: {extension}")
        tests.extend(TestCase(extension, path) for path in sorted(test_dir.glob("*.S")))
    return tests


def matches(test: TestCase, selector: str) -> bool:
    selectors = normalize_selector(selector)
    names = {
        test.name,
        test.short_name,
        str(test.build_rel),
        str(test.build_rel.with_suffix(".S")),
    }
    return bool(selectors & names)


def select_tests(test_isa: list[str], all_filter: list[str], exclude_filter: list[str]) -> list[TestCase]:
    discovered = discover_tests(test_isa)
    if all_filter:
        selected: list[TestCase] = []
        missing: list[str] = []
        for selector in all_filter:
            matches_for_selector = [test for test in discovered if matches(test, selector)]
            if matches_for_selector:
                selected.extend(matches_for_selector)
            else:
                missing.append(selector)
        if missing:
            raise SystemExit(f"No tests matched ALL selector(s): {' '.join(missing)}")
        discovered = selected

    if exclude_filter:
        discovered = [test for test in discovered if not any(matches(test, selector) for selector in exclude_filter)]

    seen: set[Path] = set()
    unique: list[TestCase] = []
    for test in discovered:
        if test.path not in seen:
            seen.add(test.path)
            unique.append(test)
    return unique


def ensure_jyd_am_home() -> Path:
    value = os.environ.get("JYD_AM_HOME", str(DEFAULT_JYD_AM_HOME))
    path = Path(value).expanduser()
    if not (path / "am/include/am.h").is_file():
        raise SystemExit(f"JYD_AM_HOME must point to a JYD Abstract-Machine repo: {path}")
    return path


def process_signature_file(sig_file: Path, xlen: int) -> None:
    datatype = ".word" if xlen == 32 else ".quad"
    trap_canary = "d3a91f6c" if xlen == 32 else "d3a91f6c8b47e25d"
    result_file = sig_file.with_suffix(".results")
    with result_file.open("w") as outfile:
        for line in sig_file.read_text().splitlines():
            if line.strip():
                outfile.write(f"{datatype} 0x{line}\n")
                if trap_canary in line:
                    outfile.write("mtrap_sigptr:\n")


def test_metadata(test: TestCase) -> tuple[str, int]:
    text = test.path.read_text()
    march_match = MARCH_RE.search(text)
    if march_match is None:
        raise SystemExit(f"Unable to find MARCH metadata in {test.rel_path}")
    flen_match = TEST_FLEN_RE.search(text)
    test_flen = int(flen_match.group(1)) if flen_match is not None else 32
    return march_match.group(1), test_flen


def require_exe(name: str) -> str:
    exe = shutil.which(name)
    if exe is None:
        raise SystemExit(f"Required executable not found on PATH: {name}")
    return exe


def generate_signature(test: TestCase, config: ArchConfig) -> None:
    march, test_flen = test_metadata(test)
    compiler = require_exe("riscv32-unknown-linux-gnu-gcc")
    sail = require_exe("sail_riscv_sim")

    build_base = config.workdir / "build" / test.build_rel
    build_base.parent.mkdir(parents=True, exist_ok=True)
    sig_elf = build_base.with_suffix(".sig.elf")
    sig_file = build_base.with_suffix(".sig")
    sig_log = build_base.with_suffix(".sig.log")

    compile_cmd = [
        compiler,
        f"-I{config.include_dir}",
        f"-I{REPO_ROOT / 'tests/env'}",
        f"-T{config.linker_script}",
        "-O0",
        "-g",
        "-mcmodel=medany",
        "-nostdlib",
        "-o",
        str(sig_elf),
        f"-march={march}",
        "-mabi=ilp32",
        "-DSIGNATURE",
        f"-DXLEN={config.xlen}",
        f"-DTEST_FLEN={test_flen}",
        str(test.path),
    ]
    subprocess.run(compile_cmd, cwd=REPO_ROOT, check=True)

    sail_cmd = [
        sail,
        f"--rv{config.xlen}",
        f"--test-signature={sig_file}",
        "--signature-granularity",
        "4",
        str(sig_elf),
    ]
    with sig_log.open("w") as log:
        subprocess.run(sail_cmd, cwd=REPO_ROOT, stdout=log, stderr=subprocess.STDOUT, check=True)

    process_signature_file(sig_file, config.xlen)


def generate_signatures(tests: list[TestCase], config: ArchConfig) -> None:
    for test in tests:
        generate_signature(test, config)


def write_shim() -> Path:
    shim = AM_WORKDIR / "rvtest_main.c"
    shim.parent.mkdir(parents=True, exist_ok=True)
    contents = """__attribute__((used, section(".rodata.mainargs")))
const char mainargs[64] = "the_insert-arg_rule_in_Makefile_will_insert_mainargs_here";
"""
    if not shim.exists() or shim.read_text() != contents:
        shim.write_text(contents)
    return shim.relative_to(REPO_ROOT)


def signature_file(test: TestCase, config: ArchConfig) -> Path:
    return config.workdir / "build" / test.build_rel.with_suffix(".results")


def sanitized_cpath() -> str | None:
    cpath = os.environ.get("CPATH")
    if not cpath:
        return None

    compat_include = AM_WORKDIR / "include"
    entries: list[str] = []
    for entry in cpath.split(os.pathsep):
        if not entry:
            continue
        try:
            entry_path = Path(entry).expanduser().resolve()
        except OSError:
            entries.append(entry)
            continue
        if entry_path != compat_include:
            entries.append(entry)
    return os.pathsep.join(entries) if entries else None


def remove_stale_compat_deps(jyd_am_home: Path) -> None:
    compat_include = str((AM_WORKDIR / "include").resolve())
    for dep_file in jyd_am_home.glob("*/build/**/*.d"):
        try:
            if compat_include in dep_file.read_text():
                dep_file.unlink()
        except OSError:
            pass


def write_am_makefile(test: TestCase, config: ArchConfig, jyd_am_home: Path, command: str) -> Path:
    makefile = AM_WORKDIR / "makefiles" / f"Makefile.{test.name}"
    makefile.parent.mkdir(parents=True, exist_ok=True)
    sig = signature_file(test, config)
    if not sig.is_file():
        raise SystemExit(f"Missing ACT signature results for {test.name}: {sig}")

    shim = write_shim()
    contents = f"""JYD_AM_HOME ?= {jyd_am_home}
NAME = {test.name}
SRCS = {test.rel_path} {shim}
LD_ENTRY_POINT = rvtest_entry_point
LDFLAGS += -u mainargs
INC_PATH += {REPO_ROOT / "tests/env"} {config.include_dir}
ASFLAGS += -DRVTEST_SELFCHECK -DXLEN={config.xlen} -DTEST_FLEN=32 -DSIGNATURE_FILE=\\\"{sig}\\\"
include ${{JYD_AM_HOME}}/Makefile
"""
    if not makefile.exists() or makefile.read_text() != contents:
        makefile.write_text(contents)
    return makefile


def run_am_test(test: TestCase, arch: str, jyd_am_home: Path, command: str) -> bool:
    config = SUPPORTED_ARCHES[arch]
    makefile = write_am_makefile(test, config, jyd_am_home, command)
    remove_stale_compat_deps(jyd_am_home)
    env = {
        **os.environ,
        "JYD_AM_HOME": str(jyd_am_home),
        "CROSS_COMPILE": "riscv32-unknown-linux-gnu-",
    }
    cpath = sanitized_cpath()
    if cpath is None:
        env.pop("CPATH", None)
    else:
        env["CPATH"] = cpath
    result = subprocess.run(
        [
            "make",
            "-s",
            "-f",
            str(makefile),
            f"ARCH={arch}",
            "CROSS_COMPILE=riscv32-unknown-linux-gnu-",
            command,
        ],
        cwd=REPO_ROOT,
        env=env,
    )
    return result.returncode == 0


def clean_am(arch: str) -> int:
    shutil.rmtree(AM_WORKDIR, ignore_errors=True)
    config = SUPPORTED_ARCHES.get(arch)
    if config is not None:
        shutil.rmtree(config.workdir, ignore_errors=True)
    for path in (REPO_ROOT / "build").glob(f"*-{arch}*"):
        if path.is_file() or path.is_symlink():
            path.unlink()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run riscv-arch-test through JYD Abstract-Machine")
    parser.add_argument("command", choices=["run", "image", "gdb", "clean-am"])
    parser.add_argument("--arch", required=True)
    parser.add_argument("--test-isa", default="I M")
    parser.add_argument("--all", default="")
    parser.add_argument("--exclude-test", default="")
    args = parser.parse_args()

    config = SUPPORTED_ARCHES.get(args.arch)
    if config is None:
        supported = " ".join(sorted(SUPPORTED_ARCHES))
        raise SystemExit(f"AM compatibility supports ARCH in {{{supported}}}, got {args.arch}")

    if args.command == "clean-am":
        return clean_am(args.arch)

    jyd_am_home = ensure_jyd_am_home()
    tests = select_tests(split_words(args.test_isa), split_words(args.all), split_words(args.exclude_test))
    if not tests:
        print("No tests selected.")
        return 0

    generate_signatures(tests, config)

    results: list[tuple[TestCase, bool]] = []
    print(f"test list [{len(tests)} item(s)]:", " ".join(test.short_name for test in tests))
    for test in tests:
        ok = run_am_test(test, args.arch, jyd_am_home, args.command)
        results.append((test, ok))

    for test, ok in results:
        status = "PASS" if ok else "***FAIL***"
        print(f"[{test.short_name:>14}] {status}")

    failed = [test for test, ok in results if not ok]
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
