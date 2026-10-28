"""Offline bootstrap tests; never install system software or download a model."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import bootstrap as b


class DetectTests(unittest.TestCase):
    def test_linux_distro_selection(self):
        available = lambda name: f"/usr/bin/{name}" if name in {"dnf", "apt-get", "pacman", "zypper", "apk"} else None
        cases = [
            ("ID=fedora\n", "dnf"),
            ("ID=ubuntu\nID_LIKE=debian\n", "apt-get"),
            ("ID=arch\n", "pacman"),
            ("ID=opensuse-tumbleweed\nID_LIKE=suse opensuse\n", "zypper"),
            ("ID=alpine\n", "apk"),
        ]
        for content, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(b.detect_host("Linux", available, content).manager, expected)

    def test_windows_and_macos(self):
        self.assertEqual(b.detect_host("Windows", lambda x: "x" if x == "winget" else None).manager, "winget")
        self.assertEqual(b.detect_host("Darwin", lambda x: "x" if x == "brew" else None).system, "macos")

    def test_linux_package_names(self):
        self.assertEqual(b.package_names(b.Host("linux", "dnf"), {"tk", "font"}),
                         ["dejavu-sans-fonts", "python3-tkinter"])
        self.assertEqual(b.package_names(b.Host("linux", "apt-get"), {"venv", "font", "tk"}),
                         ["fonts-dejavu-core", "python3-tk", "python3-venv"])
        self.assertEqual(b.package_names(b.Host("linux", "pacman"), {"font", "tk"}),
                         ["tk", "ttf-dejavu"])
        self.assertEqual(b.package_names(b.Host("macos", "brew"), {"tk"}, (3, 13)),
                         ["python-tk@3.13"])
        self.assertEqual(b.package_names(b.Host("windows", "winget"), {"tk"}), [])

    def test_ollama_install_avoids_remote_script(self):
        self.assertEqual(b.ollama_install_command(b.Host("windows", "winget"))[:4],
                         ["winget", "install", "--id", "Ollama.Ollama"])
        self.assertEqual(b.ollama_install_command(b.Host("macos", "brew")),
                         ["brew", "install", "ollama"])
        self.assertIsNone(b.ollama_install_command(b.Host("linux", "apt-get", "ubuntu")))

    def test_feature_selection(self):
        self.assertEqual(b.features_for_args([]), (True, True))
        self.assertEqual(b.features_for_args(["--original", "test.pdf", "--compress-only"]),
                         (False, False))
        self.assertEqual(b.features_for_args(["--help"]), (False, False))
        self.assertEqual(b.features_for_args(["--original", "a.pdf", "--compressed", "b.pdf"]),
                         (False, True))

    def test_no_install_in_doctor(self):
        with patch.object(b, "detect_host", return_value=b.Host("linux", "apt-get")), \
             patch.object(b, "doctor") as diag, \
             patch.object(b, "install_python_deps") as pip:
            self.assertEqual(b.main(["--doctor"]), 0)
            diag.assert_called_once()
            pip.assert_not_called()

    def test_compress_only_does_not_install_ollama_or_tk(self):
        with patch.object(b, "detect_host", return_value=b.Host("linux", "dnf")), \
             patch.object(b, "install_python_deps"), \
             patch.object(b, "ensure_ollama") as model, \
             patch.object(b, "install_system_features") as packages, \
             patch.object(b.subprocess, "call", return_value=0) as call:
            self.assertEqual(b.main(["--original", "a.pdf", "--compress-only",
                                     "--compress", "lossless"]), 0)
            model.assert_not_called()
            self.assertEqual(packages.call_args.args[1], set())
            self.assertIn("htr_compare.py", call.call_args.args[0][1])

    def test_model_requires_confirmation_without_terminal(self):
        with patch.object(b.sys.stdin, "isatty", return_value=False):
            self.assertFalse(b.confirm("test", ["ollama", "pull", b.MODEL], False))

    def test_root_does_not_modify_system_when_opted_out(self):
        with patch.object(b, "run_install") as runner:
            b.install_system_features(b.Host("linux", "dnf"), {"tk"}, False, True)
            runner.assert_not_called()


if __name__ == "__main__":
    unittest.main()
