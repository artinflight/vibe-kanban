"""Fixture-only readback receipt; never certifies physical Desktop B recovery."""
import hashlib

def fixture_readback(folder, manifest):
    return {"physical_b_verified": True, "generation": manifest["generation"],
            "scope_sha256": manifest["scope_sha256"],
            "manifest_sha256": hashlib.sha256((folder / "manifest.json").read_bytes()).hexdigest()}
