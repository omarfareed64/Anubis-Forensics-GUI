"""Central place for locating bundled tools and project directories.

Every module used to build paths relative to the current working directory or
to a hard-coded folder name ("Anubis-Forensics-GUI"). That broke as soon as the
application was launched from another directory or the repository was renamed.
All paths are now derived from the location of this file.
"""
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

ASSETS_DIR = os.path.join(PROJECT_ROOT, "assets")
CASES_DIR = os.path.join(PROJECT_ROOT, "cases")
PSTOOLS_DIR = os.path.join(PROJECT_ROOT, "PSTools")
SAMPLE_MEMORY_ANALYSIS_DIR = os.path.join(PROJECT_ROOT, "memory_analysis")

PSEXEC_EXE = os.path.join(PSTOOLS_DIR, "PsExec.exe")
FILEBROWSER_EXE = os.path.join(PROJECT_ROOT, "filebrowser.exe")
WINPMEM_EXE = os.path.join(PROJECT_ROOT, "winpmem_mini_x64_rc2.exe")
PROCDUMP_EXE = os.path.join(PROJECT_ROOT, "procdump.exe")
RAWCOPY_EXE = os.path.join(PROJECT_ROOT, "RawCopy.exe")
RLA_EXE = os.path.join(PROJECT_ROOT, "rla.exe")

# Sub-folders created inside a case directory.
CASE_EVIDENCE_SUBDIR = "evidence"
CASE_MEMORY_SUBDIR = "memory_analysis"
CASE_WEB_SUBDIR = "web_artifacts"
CASE_REGISTRY_SUBDIR = "registry_analysis"
CASE_SRUM_SUBDIR = "srum_analysis"
CASE_USB_SUBDIR = "usb_analysis"
CASE_REPORT_SUBDIR = "reports"


def sanitize_case_name(value: str) -> str:
    """Normalize case names to a safe folder name."""
    text = (value or "").strip()
    return "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in text)


def build_case_directory(case_number: str, case_name: str, parent_dir: str | None = None) -> str:
    """Build the canonical path for a case under the project cases folder."""
    base_dir = os.path.abspath(parent_dir or CASES_DIR)
    folder_name = "_".join(part for part in (sanitize_case_name(case_number), sanitize_case_name(case_name)) if part)
    if not folder_name:
        folder_name = "case"
    return os.path.join(base_dir, folder_name)


def ensure_case_structure(case_path: str) -> list[str]:
    """Create the canonical forensic subdirectories for a case and return them."""
    os.makedirs(case_path, exist_ok=True)
    created = []
    for subdir in (
        CASE_EVIDENCE_SUBDIR,
        CASE_MEMORY_SUBDIR,
        CASE_WEB_SUBDIR,
        CASE_REGISTRY_SUBDIR,
        CASE_SRUM_SUBDIR,
        CASE_USB_SUBDIR,
        CASE_REPORT_SUBDIR,
    ):
        full_path = os.path.join(case_path, subdir)
        os.makedirs(full_path, exist_ok=True)
        created.append(full_path)
    return created


def asset(name: str) -> str:
    """Return the absolute path of a file inside assets/4x."""
    return os.path.join(ASSETS_DIR, "4x", name)


def case_subdir(case_path: str, subdir: str, create: bool = True) -> str:
    """Return (and optionally create) a sub-folder of a case."""
    path = os.path.join(case_path, subdir)
    if create:
        os.makedirs(path, exist_ok=True)
    return path


def memory_analysis_dir(case_path: str | None) -> str | None:
    """Pick the memory analysis folder to display.

    Prefers the case's own folder, otherwise falls back to the bundled sample
    data so the memory tab still demonstrates something without a case.
    """
    if case_path:
        candidate = os.path.join(case_path, CASE_MEMORY_SUBDIR)
        if os.path.isdir(candidate) and os.listdir(candidate):
            return candidate
    if os.path.isdir(SAMPLE_MEMORY_ANALYSIS_DIR):
        return SAMPLE_MEMORY_ANALYSIS_DIR
    return None


def venv_script(name: str) -> str:
    """Return the path of a console script installed next to the interpreter.

    Falls back to the bare name so that a globally installed tool on PATH still
    works.
    """
    scripts_dir = os.path.dirname(sys.executable)
    for candidate in (os.path.join(scripts_dir, name + ".exe"), os.path.join(scripts_dir, name)):
        if os.path.isfile(candidate):
            return candidate
    return name


NO_WINDOW = 0x08000000 if os.name == "nt" else 0
