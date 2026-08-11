from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INIT = ROOT / "scripts" / "init_vault.py"
VALIDATE = ROOT / "scripts" / "validate_vault.py"


class PersonalOSCliTests(unittest.TestCase):
    def test_public_template_validates(self) -> None:
        result = subprocess.run(
            [sys.executable, str(VALIDATE), "--vault", str(ROOT / "vault-template"), "--template-mode"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("RESULT PASS", result.stdout)

    def test_initializer_generates_period_pages_and_valid_vault(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "personal-os"
            result = subprocess.run(
                [sys.executable, str(INIT), str(target), "--date", "2030-05-20"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue((target / "02 战略" / "2030 年度主题.md").is_file())
            self.assertTrue((target / "03 季度" / "2030-Q2.md").is_file())
            self.assertTrue((target / "01 基础" / "工作观与人生观.md").is_file())
            self.assertTrue((target / "02 战略" / "奥德赛计划.md").is_file())
            self.assertTrue((target / "90 模板" / "奥德赛原型访谈.md").is_file())
            self.assertTrue((target / "90 模板" / "奥德赛原型实验.md").is_file())
            self.assertTrue((target / "99 系统" / "scripts" / "validate_vault.py").is_file())
            self.assertNotIn("__INIT_", (target / "00 首页.md").read_text(encoding="utf-8"))

            odyssey = (target / "02 战略" / "奥德赛计划.md").read_text(encoding="utf-8")
            self.assertIn("## 计划 1：当前轨迹", odyssey)
            self.assertIn("## 计划 2：当前路径不再可行", odyssey)
            self.assertIn("## 计划 3：暂时放下金钱与社会期待", odyssey)

    def test_life_design_contract_rejects_missing_odyssey_section(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "personal-os"
            result = subprocess.run(
                [sys.executable, str(INIT), str(target), "--date", "2030-05-20"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            path = target / "02 战略" / "奥德赛计划.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace("## 原型队列", "## 待办"),
                encoding="utf-8",
            )
            validation = subprocess.run(
                [sys.executable, str(target / "99 系统" / "scripts" / "validate_vault.py"), "--vault", str(target)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(validation.returncode, 1)
            self.assertIn("LIFE_DESIGN_SECTION_MISSING", validation.stdout)

    def test_initializer_refuses_nonempty_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "existing"
            target.mkdir()
            (target / "keep.txt").write_text("do not overwrite", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(INIT), str(target)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 2)
            self.assertEqual((target / "keep.txt").read_text(encoding="utf-8"), "do not overwrite")


if __name__ == "__main__":
    unittest.main()
