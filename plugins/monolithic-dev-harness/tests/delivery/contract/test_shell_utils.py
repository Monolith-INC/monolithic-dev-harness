import unittest

from scripts.policy.shell_utils import extract_shell_write_targets


class TestShellUtils(unittest.TestCase):
    def test_redirect_targets(self):
        self.assertEqual(
            extract_shell_write_targets("echo code > lib/feature.dart"),
            ["lib/feature.dart"],
        )
        self.assertEqual(
            extract_shell_write_targets("printf 'x' >> docs/notes.md"),
            ["docs/notes.md"],
        )

    def test_ignores_dev_null(self):
        self.assertEqual(
            extract_shell_write_targets("npm test 2> /dev/null"),
            [],
        )

    def test_tee_target(self):
        self.assertEqual(
            extract_shell_write_targets("echo hello | tee output.txt"),
            ["output.txt"],
        )

    def test_cp_destination(self):
        self.assertEqual(
            extract_shell_write_targets("cp /tmp/payload.dart lib/payload.dart"),
            ["lib/payload.dart"],
        )

    def test_sed_inplace(self):
        self.assertEqual(
            extract_shell_write_targets("sed -i 's/a/b/' lib/main.dart"),
            ["lib/main.dart"],
        )


if __name__ == "__main__":
    unittest.main()
