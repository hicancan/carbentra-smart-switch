"""Negative controls for the separately compiled host mbedTLS verifier.

Requires cryptography in the host test environment. Generates ephemeral synthetic
certificates for broker.test.invalid; no real credentials or network connection.
The --verifier argument is mandatory: an absent C binary cannot silently skip.
"""
import argparse
import datetime as dt
from pathlib import Path
import subprocess
import tempfile
import unittest

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

VERIFIER = None


class CertificatePolicyTests(unittest.TestCase):
    def test_dates_ca_and_hostname(self):
        now = dt.datetime.now(dt.timezone.utc)
        day = dt.timedelta(days=1)
        key = ec.generate_private_key(ec.SECP256R1())
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Synthetic Switch test CA")])

        def root_for(signing_key):
            return (x509.CertificateBuilder().subject_name(name).issuer_name(name)
                    .public_key(signing_key.public_key()).serial_number(x509.random_serial_number())
                    .not_valid_before(now - day).not_valid_after(now + 30 * day)
                    .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
                    .sign(signing_key, hashes.SHA256()))

        def leaf(start, end):
            return (x509.CertificateBuilder()
                    .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "broker.test.invalid")]))
                    .issuer_name(name).public_key(ec.generate_private_key(ec.SECP256R1()).public_key())
                    .serial_number(x509.random_serial_number()).not_valid_before(start).not_valid_after(end)
                    .add_extension(x509.SubjectAlternativeName([x509.DNSName("broker.test.invalid")]), critical=False)
                    .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
                    .sign(key, hashes.SHA256()))

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "ca.pem"
            target = Path(temp) / "leaf.pem"
            root.write_bytes(root_for(key).public_bytes(serialization.Encoding.PEM))

            def check(cert, expected_flag, hostname="broker.test.invalid"):
                target.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
                result = subprocess.run([str(VERIFIER), str(root), str(target), hostname],
                                        capture_output=True, text=True, check=False)
                self.assertEqual(result.returncode, 1 if expected_flag else 0, result.stderr)
                flags = int(result.stdout.strip().removeprefix("flags="))
                if expected_flag:
                    self.assertNotEqual(flags & expected_flag, 0, result.stdout)
                else:
                    self.assertEqual(flags, 0)

            cases = [("valid", now - day, now + day, 0),
                     ("expired", now - 2 * day, now - day, 0x01),
                     ("not_yet_valid", now + day, now + 2 * day, 0x200)]
            for label, start, end, flag in cases:
                with self.subTest(case=label):
                    check(leaf(start, end), flag)
            with self.subTest(case="wrong_hostname"):
                check(leaf(now - day, now + day), 0x04, "wrong.test.invalid")
            with self.subTest(case="wrong_ca"):
                root.write_bytes(root_for(ec.generate_private_key(ec.SECP256R1())).public_bytes(serialization.Encoding.PEM))
                check(leaf(now - day, now + day), 0x08)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verifier", required=True, type=Path)
    args, remaining = parser.parse_known_args()
    VERIFIER = args.verifier.resolve(strict=True)
    unittest.main(argv=[__file__, *remaining])
