"""Upload files ke VPS via tar piped through SSH — 1 koneksi, semua file sekaligus."""
import io
import os
import subprocess
import tarfile

SSH_OPTS = [
    "ssh",
    "-i", os.path.expanduser("~/.ssh/id_ed25519_mael"),
    "-p", "443",
    "-o", "ConnectTimeout=30",
    "-o", "StrictHostKeyChecking=no",
    "root@31.97.188.69",
]

BASE        = os.path.dirname(os.path.abspath(__file__))
REMOTE_BASE = "/root/btc-scalping-execution"

FILES = [
    "backend/paper_executor_pullback.py",
    "backend/tests/test_paper_pullback.py",
    "Dockerfile.signal",
    "docker-compose.yml",
]


if __name__ == "__main__":
    # Build tar archive in memory
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        for rel in FILES:
            local = os.path.join(BASE, rel)
            tar.add(local, arcname=rel)
    tar_bytes = buf.getvalue()

    print(f"Uploading {len(FILES)} files ({len(tar_bytes):,} bytes) via tar|ssh...")

    # Pipe tar to VPS: ssh ... 'tar -xf - -C /root/btc-scalping-execution'
    proc = subprocess.run(
        SSH_OPTS + [f"tar -xf - -C {REMOTE_BASE}"],
        input=tar_bytes,
        capture_output=True,
    )

    if proc.returncode == 0:
        for f in FILES:
            print(f"  OK  {f}")
        print("Upload complete.")
    else:
        print("FAIL:", proc.stderr.decode())

