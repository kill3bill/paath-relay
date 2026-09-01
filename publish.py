#!/usr/bin/env python3
"""Build the PAATH relay bundle from a freshly issued certificate.

Wire format (design doc section 4): one ASCII line `base64(manifest).base64(sigDER)`,
manifest = line-based key=value, leaf private key PKCS#8 DER AES-256-GCM encrypted.

Env: SIGNING_KEY_PEM (ECDSA P-256 private PEM), BUNDLE_AES_KEY (64 hex chars).
Args: <fullchain.pem> <privkey.pem> <out.txt>
"""
import base64
import os
import sys

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def b64(b: bytes) -> str:
    return base64.b64encode(b).decode()


def main() -> None:
    fullchain_path, key_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
    with open(fullchain_path, "rb") as f:
        fullchain = f.read()
    with open(key_path, "rb") as f:
        key_pem = f.read()

    leaf = x509.load_pem_x509_certificate(fullchain)
    not_after = int(leaf.not_valid_after_utc.timestamp())
    serial = format(leaf.serial_number, "x")
    san = leaf.extensions.get_extension_for_class(
        x509.SubjectAlternativeName
    ).value.get_values_for_type(x509.DNSName)
    domain = san[0]

    # Normalize the leaf private key to PKCS#8 DER (lego may emit SEC1).
    priv = serialization.load_pem_private_key(key_pem, password=None)
    pkcs8 = priv.private_bytes(
        serialization.Encoding.DER,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )

    aes_key = bytes.fromhex(os.environ["BUNDLE_AES_KEY"].strip())
    if len(aes_key) != 32:
        sys.exit("BUNDLE_AES_KEY must be 32 bytes (64 hex chars)")
    nonce = os.urandom(12)
    cipher = AESGCM(aes_key).encrypt(nonce, pkcs8, None)  # ciphertext || 16-byte tag

    manifest = (
        "v=1\n"
        f"domain={domain}\n"
        f"notAfter={not_after}\n"
        f"serial={serial}\n"
        f"chainPem={b64(fullchain)}\n"
        f"keyCipher={b64(cipher)}\n"
        f"keyNonce={b64(nonce)}\n"
    ).encode()

    signer = serialization.load_pem_private_key(
        os.environ["SIGNING_KEY_PEM"].encode(), password=None
    )
    if not isinstance(signer, ec.EllipticCurvePrivateKey):
        sys.exit("SIGNING_KEY_PEM must be an EC (P-256) private key")
    sig = signer.sign(manifest, ec.ECDSA(hashes.SHA256()))  # DER

    with open(out_path, "w") as f:
        f.write(b64(manifest) + "." + b64(sig) + "\n")
    print(f"wrote {out_path}: domain={domain} notAfter={not_after} serial={serial}")


if __name__ == "__main__":
    main()
