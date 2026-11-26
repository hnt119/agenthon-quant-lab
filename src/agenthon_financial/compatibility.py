"""Bind portability changes to one frozen receipt and one reviewed source inventory."""
from agenthon_quant.records import digest, strict_json
from agenthon_quant.resources import resource_root

ORIGINAL_RECEIPT = "89ae5b7c13d4dfd581182a714953b59c76c7f1c6779d9bb4706c9950da3f0317"
COMPATIBILITY = '7290cc5e1fc96a8d4fda6986af54d37910e631e86f30d5113fdbccdabdb3878c'


def qualify(recorded, current):
    raw = (resource_root() / "packaging/btc-compatibility.json").read_bytes()
    if digest(raw) != COMPATIBILITY:
        raise ValueError("Study compatibility record differs from the qualified version")
    manifest = strict_json(raw)
    if (manifest["original_receipt_sha256"] != ORIGINAL_RECEIPT
            or current != manifest["packaged_sources"]
            or recorded not in (manifest["original_sources"], current)):
        raise ValueError("Study implementation differs from the qualified version")
