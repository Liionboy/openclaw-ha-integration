"""Configuration editor — read, write, backup, check configuration.yaml and other YAML files."""

import asyncio
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path

_LOGGER = logging.getLogger(__name__)


class ConfigEditor:
    """Safe editor for Home Assistant YAML configuration files."""

    def __init__(self, config_dir: str) -> None:
        """Initialize with the HA config directory."""
        self._config_dir = Path(config_dir)

    def _resolve(self, filename: str) -> Path:
        """Resolve a filename to the config directory (prevent path traversal)."""
        target = (self._config_dir / filename).resolve()
        if not str(target).startswith(str(self._config_dir.resolve())):
            raise ValueError(f"Path traversal detected: {filename}")
        return target

    # ── Read ─────────────────────────────────────────────────────

    async def read_file(self, filename: str = "configuration.yaml") -> str:
        """Read a YAML file from the config directory."""
        path = self._resolve(filename)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {filename}")
        return await asyncio.to_thread(path.read_text, encoding="utf-8")

    async def list_files(self, pattern: str = "*.yaml") -> list[str]:
        """List YAML files in the config directory."""
        def _list():
            return sorted(
                f.name
                for f in self._config_dir.iterdir()
                if f.is_file() and f.match(pattern)
            )
        return await asyncio.to_thread(_list)

    # ── Write ────────────────────────────────────────────────────

    async def write_file(
        self,
        filename: str,
        content: str,
        backup: bool = True,
    ) -> bool:
        """Write content to a YAML file. Optionally create a backup first."""
        path = self._resolve(filename)
        if backup and path.exists():
            await self.backup_file(filename)
        await asyncio.to_thread(path.write_text, content, encoding="utf-8")
        _LOGGER.info("Wrote %s (%d bytes)", filename, len(content))
        return True

    async def patch_file(
        self,
        filename: str,
        section: str,
        content: str,
    ) -> bool:
        """Replace or add a top-level YAML section in a file.
        
        Example: patch_file("configuration.yaml", "automation", "  - alias: Test\\n    trigger: ...")
        """
        original = await self.read_file(filename)
        lines = original.splitlines()

        # Find section start
        section_start = None
        section_end = None
        for i, line in enumerate(lines):
            if line.startswith(f"{section}:") and (line[len(section)] == ":" or line[len(section)+1:].startswith(" ")):
                section_start = i
                continue
            if section_start is not None and i > section_start:
                # Check if this line starts a new top-level section (no indent)
                if line and not line[0].isspace() and ":" in line:
                    section_end = i
                    break

        new_lines = []
        if section_start is not None:
            # Replace existing section
            new_lines = lines[:section_start]
            new_lines.append(f"{section}:")
            # Add indented content
            for cl in content.splitlines():
                if cl.strip():
                    new_lines.append(f"  {cl.strip()}" if not cl.startswith("  ") else cl)
            if section_end is not None:
                new_lines.extend(lines[section_end:])
        else:
            # Add new section at the end
            new_lines = lines
            new_lines.append("")
            new_lines.append(f"{section}:")
            for cl in content.splitlines():
                if cl.strip():
                    new_lines.append(f"  {cl.strip()}" if not cl.startswith("  ") else cl)

        result = "\n".join(new_lines)
        return await self.write_file(filename, result)

    # ── Backup ───────────────────────────────────────────────────

    async def backup_file(self, filename: str) -> str:
        """Create a timestamped backup of a file. Returns backup path."""
        path = self._resolve(filename)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {filename}")

        backup_dir = self._config_dir / "backups"
        await asyncio.to_thread(backup_dir.mkdir, exist_ok=True)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{filename}.{ts}.bak"
        backup_path = backup_dir / backup_name

        await asyncio.to_thread(shutil.copy2, path, backup_path)
        _LOGGER.info("Backup created: %s", backup_path)
        return str(backup_path)

    async def backup_all(self) -> str:
        """Create a full config directory backup. Returns archive path."""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_base = self._config_dir / "backups" / f"full_config_{ts}"

        def _create_archive():
            backup_dir = self._config_dir / "backups"
            backup_dir.mkdir(exist_ok=True)
            return shutil.make_archive(str(archive_base), "gztar", str(self._config_dir))

        archive_path = await asyncio.to_thread(_create_archive)
        _LOGGER.info("Full backup created: %s", archive_path)
        return archive_path

    # ── Validate ─────────────────────────────────────────────────

    async def check_config(self) -> dict:
        """Run HA config check using the shell command.
        
        Returns dict with keys: valid (bool), output (str).
        """
        proc = await asyncio.create_subprocess_exec(
            "python3", "-c",
            "import homeassistant.core; print('ok')",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        # Also try the HA CLI check if available
        proc2 = await asyncio.create_subprocess_exec(
            "hass", "--script", "check_config", "-c", str(self._config_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout2, stderr2 = await proc2.communicate()

        output = (stdout2 or stdout or b"").decode()
        errors = (stderr2 or stderr or b"").decode()

        return {
            "valid": proc.returncode == 0 and proc2.returncode == 0,
            "output": output,
            "errors": errors,
        }

    # ── List backups ─────────────────────────────────────────────

    async def list_backups(self) -> list[dict]:
        """List available backups."""
        backup_dir = self._config_dir / "backups"
        if not backup_dir.exists():
            return []

        def _list():
            result = []
            for f in sorted(backup_dir.iterdir(), reverse=True):
                if f.is_file():
                    stat = f.stat()
                    result.append({
                        "name": f.name,
                        "size": stat.st_size,
                        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    })
            return result

        return await asyncio.to_thread(_list)
