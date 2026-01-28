#!/usr/bin/env python3
"""
ascmhl_generate_and_verify

Generate an ASC MHL history for an input directory (writes ./ascmhl/*.mhl + chain XML),
then ALWAYS verify the directory contents against that history.

Requires:
  pip install ascmhl
"""

from __future__ import annotations

import argparse
import getpass
import glob
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Any, Callable, Optional, Sequence, Tuple


@dataclass
class CliResult:
    exit_code: int
    output: str


def _try_import_click_cli() -> Optional[Tuple[Callable[..., Any], str]]:
    candidates = [
        ("ascmhl.cli", "cli"),
        ("ascmhl.cli", "main"),
        ("ascmhl.__main__", "cli"),
        ("ascmhl.__main__", "main"),
        ("ascmhl.commandline", "cli"),
        ("ascmhl.main", "cli"),
    ]
    for mod_name, attr in candidates:
        try:
            mod = __import__(mod_name, fromlist=[attr])
            cli_obj = getattr(mod, attr)
            return cli_obj, f"{mod_name}:{attr}"
        except Exception:
            continue
    return None


def _try_import_click_cli_debug() -> Optional[Tuple[Callable[..., Any], str]]:
    candidates = [
        ("ascmhl_debug.cli", "cli"),
        ("ascmhl_debug.__main__", "cli"),
        ("ascmhl_debug.__main__", "main"),
        ("ascmhl.debug_cli", "cli"),
        ("ascmhl.debug", "cli"),
        ("ascmhl.debug.__main__", "cli"),
    ]
    for mod_name, attr in candidates:
        try:
            mod = __import__(mod_name, fromlist=[attr])
            cli_obj = getattr(mod, attr)
            return cli_obj, f"{mod_name}:{attr}"
        except Exception:
            continue
    return None


def _run_click(cli_obj: Callable[..., Any], args: Sequence[str]) -> CliResult:
    from click.testing import CliRunner

    runner = CliRunner(mix_stderr=False)
    res = runner.invoke(cli_obj, list(args), catch_exceptions=False)
    return CliResult(exit_code=res.exit_code, output=res.output or "")


def _run_subprocess(exe: str, args: Sequence[str]) -> CliResult:
    if shutil.which(exe) is None:
        raise FileNotFoundError(f"Executable not found on PATH: {exe}")

    p = subprocess.run(
        [exe, *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    return CliResult(exit_code=p.returncode, output=p.stdout or "")


def _find_outputs(root_dir: str) -> dict:
    out_dir = os.path.join(root_dir, "ascmhl")
    results = {"ascmhl_dir": out_dir, "mhl_files": [], "chain_files": []}

    if not os.path.isdir(out_dir):
        return results

    results["mhl_files"] = sorted(glob.glob(os.path.join(out_dir, "*.mhl")))

    chain_globs = [
        os.path.join(out_dir, "*chain*.xml"),
        os.path.join(out_dir, "*.xml"),
    ]
    chain = []
    for g in chain_globs:
        chain.extend(glob.glob(g))

    chain = sorted(set(chain), key=lambda p: (("chain" not in os.path.basename(p).lower()), p))
    results["chain_files"] = chain
    return results


def _invoke_ascmhl(args: Sequence[str]) -> Tuple[CliResult, str]:
    cli = _try_import_click_cli()
    if cli is not None:
        cli_obj, where = cli
        return _run_click(cli_obj, args), f"library(click) {where}"
    return _run_subprocess("ascmhl", args), "subprocess ascmhl"


def _invoke_ascmhl_debug(args: Sequence[str]) -> Tuple[CliResult, str]:
    dbg = _try_import_click_cli_debug()
    if dbg is not None:
        dbg_obj, where = dbg
        return _run_click(dbg_obj, args), f"library(click) {where}"
    return _run_subprocess("ascmhl-debug", args), "subprocess ascmhl-debug"


def run(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        prog="ascmhl-generate-and-verify",
        description="Generate ASC MHL (.mhl + chain xml) for a directory using ascmhl, then verify it.",
    )
    ap.add_argument("input_dir", help="Root directory to hash + create ASC MHL history for.")

    ap.add_argument(
        "--hash-format",
        default="xxh3",
        help="Hash algorithm (e.g. xxh3, xxh128, xxh64, md5, sha1, sha256, c4). Default: xxh3",
    )
    ap.add_argument("--no-directory-hashes", action="store_true", help="Skip directory hashes (files only).")
    ap.add_argument("--detect-renaming", action="store_true", help="Enable renamed-file detection (if supported).")
    ap.add_argument("--ignore", action="append", default=[], help="Ignore pattern (repeatable).")
    ap.add_argument("--ignore-file", help="Path to ignore-pattern file (as per ascmhl create -ii).")

    ap.add_argument("--location", help="Creatorinfo location.")
    ap.add_argument("--comment", help="Creatorinfo comment.")
    ap.add_argument("--author-name", help="Creatorinfo author name. Default: login user.")
    ap.add_argument("--author-email", help="Creatorinfo author email.")
    ap.add_argument("--author-phone", help="Creatorinfo author phone.")
    ap.add_argument("--author-role", help="Creatorinfo author role.")
    ap.add_argument("-v", "--verbose", action="store_true", help="Verbose output from ascmhl.")

    args = ap.parse_args(argv)

    root_dir = os.path.abspath(args.input_dir)
    if not os.path.isdir(root_dir):
        print(f"ERROR: input_dir is not a directory: {root_dir}", file=sys.stderr)
        return 2

    author_name = args.author_name or getpass.getuser()

    # --- CREATE ---
    create_args: list[str] = ["create"]
    if args.verbose:
        create_args.append("--verbose")

    create_args.extend(["--hash-format", args.hash_format])

    if args.no_directory_hashes:
        create_args.append("--no_directory_hashes")
    if args.detect_renaming:
        create_args.append("--detect-renaming")

    for pat in args.ignore:
        create_args.extend(["-i", pat])
    if args.ignore_file:
        create_args.extend(["-ii", args.ignore_file])

    if args.location:
        create_args.extend(["--location", args.location])
    if args.comment:
        create_args.extend(["--comment", args.comment])

    create_args.extend(["--author-name", author_name])

    if args.author_email:
        create_args.extend(["--author-email", args.author_email])
    if args.author_phone:
        create_args.extend(["--author-phone", args.author_phone])
    if args.author_role:
        create_args.extend(["--author-role", args.author_role])

    create_args.append(root_dir)

    res, mode = _invoke_ascmhl(create_args)
    print(f"[create] mode={mode} exit_code={res.exit_code}")
    if res.output.strip():
        print(res.output.rstrip())

    if res.exit_code != 0:
        print("Create failed; not proceeding to verify.", file=sys.stderr)
        return res.exit_code

    outputs = _find_outputs(root_dir)
    print("\n[outputs]")
    print(f"ascmhl_dir: {outputs['ascmhl_dir']}")
    for p in outputs["mhl_files"]:
        print(f"mhl:       {p}")
    for p in outputs["chain_files"]:
        print(f"xml:       {p}")

    # --- VERIFY (always) ---
    verify_args: list[str] = ["verify"]
    if args.verbose:
        verify_args.append("--verbose")
    verify_args.append(root_dir)

    vres, vmode = _invoke_ascmhl_debug(verify_args)
    print(f"\n[verify] mode={vmode} exit_code={vres.exit_code}")
    if vres.output.strip():
        print(vres.output.rstrip())

    return vres.exit_code


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()