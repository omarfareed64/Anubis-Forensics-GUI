import unittest
from pathlib import Path

import os
import tempfile
import unittest

import config
from utils.paths import CASES_DIR, build_case_directory, ensure_case_structure

try:
    import main
except ModuleNotFoundError:
    main = None


class ConfigPathTests(unittest.TestCase):
    def test_default_data_and_log_paths_are_project_relative(self):
        cfg = config.Config()

        self.assertEqual(Path(cfg.app.data_dir), Path(config.PROJECT_ROOT) / "data")
        self.assertEqual(Path(cfg.app.temp_dir), Path(config.PROJECT_ROOT) / "temp")
        self.assertEqual(Path(cfg.logging.file_path), Path(config.PROJECT_ROOT) / "logs" / "app.log")

    @unittest.skipIf(main is None, "PyQt5 is not installed in this Python environment")
    def test_window_size_fits_screen(self):
        width, height = main.safe_window_geometry(1800, 1200, 1920, 991)
        self.assertLessEqual(width, 1920)
        self.assertLessEqual(height, 991)
        self.assertLessEqual(width, 1800)
        self.assertLessEqual(height, 1200)

    @unittest.skipIf(main is None, "PyQt5 is not installed in this Python environment")
    def test_window_size_fits_small_screen(self):
        width, height = main.safe_window_geometry(1800, 1200, 800, 600)

        self.assertEqual((width, height), (720, 520))
        self.assertLessEqual(width, 800)
        self.assertLessEqual(height, 600)

    def test_case_directory_defaults_to_project_cases_folder(self):
        case_dir = build_case_directory("22", "ezz")
        self.assertTrue(case_dir.startswith(CASES_DIR))
        self.assertTrue(case_dir.endswith("22_ezz"))

    def test_case_structure_init_creates_expected_subdirectories(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            case_dir = os.path.join(tmpdir, "99_case")
            ensure_case_structure(case_dir)

            for subdir in [
                "evidence",
                "memory_analysis",
                "web_artifacts",
                "registry_analysis",
                "srum_analysis",
                "usb_analysis",
                "reports",
            ]:
                self.assertTrue(os.path.isdir(os.path.join(case_dir, subdir)))


if __name__ == "__main__":
    unittest.main()
