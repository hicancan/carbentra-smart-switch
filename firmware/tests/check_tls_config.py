"""Host-only config/compile-negative tests of the header used by network.c."""
import argparse
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
FIRMWARE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("tls_config", FIRMWARE / "tools/check_tls_config.py")
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)
CC = "cc"


class ConfigTests(unittest.TestCase):
    def test_maintained_configs(self):
        for name in ("sdkconfig", "sdkconfig.defaults"):
            policy.check(FIRMWARE / name)

    def test_regression_config_is_rejected(self):
        good = "CONFIG_MBEDTLS_HAVE_TIME=y\nCONFIG_MBEDTLS_HAVE_TIME_DATE=y\n"
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "sdkconfig"
            for bad in (good.replace("CONFIG_MBEDTLS_HAVE_TIME_DATE=y", "# CONFIG_MBEDTLS_HAVE_TIME_DATE is not set"),
                        good.replace("CONFIG_MBEDTLS_HAVE_TIME=y\n", ""),
                        good + "CONFIG_ESP_TLS_INSECURE=y\n",
                        good + "CONFIG_MBEDTLS_HAVE_TIME_DATE=n\n"):
                path.write_text(bad)
                with self.assertRaises(ValueError):
                    policy.check(path)

    def test_actual_compile_guard(self):
        sdk = "#define CONFIG_MBEDTLS_HAVE_TIME 1\n#define CONFIG_MBEDTLS_HAVE_TIME_DATE 1\n"
        library = "#define MBEDTLS_HAVE_TIME\n#define MBEDTLS_HAVE_TIME_DATE\n"
        cases = [(sdk, library, True),
                 (sdk.replace("#define CONFIG_MBEDTLS_HAVE_TIME_DATE 1", ""), library, False),
                 (sdk.replace("HAVE_TIME_DATE 1", "HAVE_TIME_DATE 0"), library, False),
                 (sdk.replace("#define CONFIG_MBEDTLS_HAVE_TIME 1", ""), library, False),
                 (sdk, library.replace("#define MBEDTLS_HAVE_TIME_DATE", ""), False),
                 (sdk, library.replace("#define MBEDTLS_HAVE_TIME\n", ""), False),
                 (sdk + "#define CONFIG_ESP_TLS_INSECURE 1\n", library, False)]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "mbedtls").mkdir()
            source = root / "guard.c"
            source.write_text('#include "tls_policy.h"\nint main(void) { return 0; }\n')
            for sdk_config, lib_config, accepted in cases:
                with self.subTest(sdk=sdk_config, library=lib_config):
                    (root / "sdkconfig.h").write_text(sdk_config)
                    (root / "mbedtls/build_info.h").write_text(lib_config)
                    if Path(CC).name.lower() in ("cl", "cl.exe"):
                        command = [CC, "/nologo", "/WX", "/c", str(source), f"/I{root}",
                                   f"/I{FIRMWARE / 'main'}", f"/Fo{root / 'guard.obj'}"]
                    else:
                        command = [CC, "-std=c11", "-Wall", "-Werror", "-c", str(source),
                                   "-I", str(root), "-I", str(FIRMWARE / "main"), "-o", str(root / "guard.o")]
                    result = subprocess.run(command, capture_output=True, text=True)
                    self.assertEqual(result.returncode == 0, accepted, result.stderr + result.stdout)
                    if not accepted:
                        self.assertIn("Switch TLS", result.stderr + result.stdout)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cc", default="cc")
    args, remaining = parser.parse_known_args()
    CC = args.cc
    unittest.main(argv=[__file__, *remaining])
