"""Print a VAPID key pair for browser push (D26).

    .venv/Scripts/python scripts/generate_vapid_keys.py

Put the two lines in the API and worker environment. Keep the private key secret; changing
the pair means every browser has to turn notifications on again.
"""

import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def main() -> None:
    key = ec.generate_private_key(ec.SECP256R1())
    private = key.private_numbers().private_value.to_bytes(32, "big")
    public = key.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    print(f"WEBPUSH_PUBLIC_KEY={_b64(public)}")
    print(f"WEBPUSH_PRIVATE_KEY={_b64(private)}")


if __name__ == "__main__":
    main()
