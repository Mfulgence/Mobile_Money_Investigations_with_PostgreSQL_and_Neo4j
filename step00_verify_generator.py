"""Section 9.2 - verify mobile_money_generator.py is the unchanged supplied file."""
import hashlib
from pathlib import Path

EXPECTED = "2ea0e59d2b7b987d84a3d151bd9d1ad7b3052bfbc25abf1466c8e94467e9455a"
path = Path(__file__).with_name("mobile_money_generator.py")
data = path.read_bytes()
# Git on Windows may convert line endings on checkout; hash the LF form so both compare equal.
actual = hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()
print(f"SHA-256 of {path.name}: {actual}")
print("UNCHANGED - matches the supplied generator" if actual == EXPECTED else "CHANGED - restore the supplied file!")
