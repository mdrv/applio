"""
Minimal backup/restore for Applio prerequisites.
Supports offline use by backing up rvc/models/ directory.
"""

import os
import sys
import zipfile
from pathlib import Path
from typing import Optional
from tqdm import tqdm


def get_models_dir() -> Path:
    """Get the models directory path."""
    import os

    return Path(os.environ.get("APPLIO_DATA", ".")) / "rvc/models"


def create_backup(output_path: Optional[str] = None) -> str:
    """
    Create a backup of all prerequisites.

    Args:
        output_path: Optional path for backup file. Defaults to applio_backup.zip

    Returns:
        Path to created backup file

    Raises:
        FileNotFoundError: If models directory doesn't exist
    """
    models_dir = get_models_dir()

    if not models_dir.exists():
        raise FileNotFoundError(
            "Models directory not found. Run Applio first to download prerequisites."
        )

    if output_path is None:
        output_path = "applio_backup.zip"

    output_file = Path(output_path)

    # Get all files in models directory
    files_to_backup = []
    total_size = 0

    for root, dirs, files in os.walk(models_dir):
        for file in files:
            file_path = Path(root) / file
            rel_path = file_path.relative_to(models_dir.parent)
            files_to_backup.append((file_path, rel_path))
            total_size += file_path.stat().st_size

    if not files_to_backup:
        raise FileNotFoundError("No files found to backup in models directory")

    # Create backup
    desc = f"Backing up {len(files_to_backup)} files"

    with zipfile.ZipFile(output_file, "w", zipfile.ZIP_DEFLATED, compresslevel=3) as zf:
        with tqdm(total=total_size, unit="iB", unit_scale=True, desc=desc) as pbar:
            for file_path, rel_path in files_to_backup:
                file_size = file_path.stat().st_size
                zf.write(file_path, rel_path)
                pbar.update(file_size)

    final_size = output_file.stat().st_size
    ratio = (1 - final_size / total_size) * 100 if total_size > 0 else 0
    print(f"✓ Backup created: {output_file.resolve()}")
    print(f"  Original size: {total_size / 1024 / 1024:.1f} MiB")
    print(f"  Compressed size: {final_size / 1024 / 1024:.1f} MiB ({ratio:.1f}% saved)")
    return str(output_file.resolve())


def restore_from_backup(backup_path: str) -> None:
    """
    Restore prerequisites from a backup file.

    Args:
        backup_path: Path to backup zip file

    Raises:
        FileNotFoundError: If backup file doesn't exist
        zipfile.BadZipFile: If backup file is corrupted
    """
    backup_file = Path(backup_path)

    if not backup_file.exists():
        raise FileNotFoundError(f"Backup file not found: {backup_path}")

    models_dir = get_models_dir()

    # List contents first to get total size
    with zipfile.ZipFile(backup_file, "r") as zf:
        file_list = zf.namelist()
        compressed_size = sum(zf.getinfo(f).compress_size for f in file_list)
        uncompressed_size = sum(zf.getinfo(f).file_size for f in file_list)

    print(f"Backup file: {backup_file.resolve()}")
    print(f"  Compressed size: {compressed_size / 1024 / 1024:.1f} MiB")
    print(f"  Uncompressed size: {uncompressed_size / 1024 / 1024:.1f} MiB")

    desc = f"Restoring {len(file_list)} files"

    with zipfile.ZipFile(backup_file, "r") as zf:
        with tqdm(
            total=uncompressed_size, unit="iB", unit_scale=True, desc=desc
        ) as pbar:
            for file in file_list:
                file_size = zf.getinfo(file).file_size
                # Extract to temp dir first, then copy to final destination
                # This avoids zipfile.extract() following symlinks
                import tempfile
                import shutil

                with tempfile.TemporaryDirectory() as tmpdir:
                    # Extract to temp location
                    zf.extract(file, tmpdir)
                    src_path = Path(tmpdir) / file

                    # Build absolute destination path
                    # The zip contains paths like "models/embedders/file"
                    # We need to extract to APPLIO_DATA/rvc/models/embedders/file
                    data_dir = Path(os.environ.get("APPLIO_DATA", ".")).absolute()
                    rel_path = Path(file)  # e.g., "models/embedders/.gitkeep"
                    dst_path = data_dir / "rvc" / rel_path

                    # Ensure parent directory exists
                    dst_path.parent.mkdir(parents=True, exist_ok=True)

                    # Copy file
                    if src_path.exists():
                        # Remove destination if it exists (as symlink or file)
                        # to prevent write-through to read-only target
                        if dst_path.exists() or dst_path.is_symlink():
                            dst_path.unlink()
                        shutil.copy2(str(src_path), str(dst_path))
                        os.remove(src_path)

                pbar.update(file_size)

    print("✓ Restore complete")


def has_backup() -> bool:
    """Check if a backup file exists in current directory."""
    return Path("applio_backup.zip").exists()
