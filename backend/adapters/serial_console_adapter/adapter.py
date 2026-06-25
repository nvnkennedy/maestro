"""Serial console adapter — monitor a serial port and match boot-log patterns.

Requires ``pyserial`` (optional dependency). All reads run in a thread pool so
the event loop is never blocked.
"""

from __future__ import annotations

import asyncio
import re
import time

from backend.adapters.base_adapter import AdapterResult, BaseAdapter


def _read_serial_blocking(params: dict) -> AdapterResult:
    try:
        import serial
    except ImportError:
        return AdapterResult(
            success=False, error="pyserial is not installed (pip install pyserial)"
        )
    port = params.get("port", "COM1")
    baudrate = int(params.get("baudrate", 115200))
    duration = float(params.get("duration", 10))
    pattern = params.get("pattern")
    try:
        with serial.Serial(port, baudrate, timeout=1) as connection:
            deadline = time.monotonic() + duration
            captured: list[str] = []
            while time.monotonic() < deadline:
                line = connection.readline().decode("utf-8", errors="replace")
                if line:
                    captured.append(line.rstrip("\r\n"))
                    if pattern and re.search(pattern, line):
                        return AdapterResult(
                            success=True,
                            output="\n".join(captured),
                            data={"matched": True, "pattern": pattern},
                        )
            output = "\n".join(captured)
            if pattern:
                return AdapterResult(
                    success=False,
                    output=output,
                    error=f"Pattern '{pattern}' not seen within {duration}s",
                    data={"matched": False},
                )
            return AdapterResult(success=True, output=output)
    except serial.SerialException as exc:
        return AdapterResult(success=False, error=f"Serial error on {port}: {exc}")


def _write_serial_blocking(params: dict) -> AdapterResult:
    try:
        import serial
    except ImportError:
        return AdapterResult(
            success=False, error="pyserial is not installed (pip install pyserial)"
        )
    port = params.get("port", "COM1")
    data = params.get("data", "")
    if not data:
        return AdapterResult(success=False, error="Missing 'data' parameter")
    try:
        with serial.Serial(port, int(params.get("baudrate", 115200)), timeout=1) as conn:
            conn.write((data + params.get("line_ending", "\n")).encode())
            return AdapterResult(success=True, output=f"Sent {len(data)} chars to {port}")
    except serial.SerialException as exc:
        return AdapterResult(success=False, error=f"Serial error on {port}: {exc}")


class SerialConsoleAdapter(BaseAdapter):
    name = "serial"
    description = "Serial console monitoring, boot log parsing and text matching"

    def _register_actions(self) -> None:
        self.actions = {
            "monitor": self._monitor,
            "wait_for_pattern": self._monitor,  # alias; pass 'pattern'
            "send": self._send,
            "list_ports": self._list_ports,
        }

    async def _monitor(self, params: dict) -> AdapterResult:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _read_serial_blocking, params)

    async def _send(self, params: dict) -> AdapterResult:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _write_serial_blocking, params)

    @staticmethod
    def _list_ports_registry() -> list[dict]:
        """Fallback COM-port detection via the Windows registry (no pyserial)."""
        try:
            import winreg
        except ImportError:
            return []
        ports: list[dict] = []
        try:
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DEVICEMAP\SERIALCOMM"
            )
        except OSError:
            return []
        index = 0
        while True:
            try:
                name, value, _ = winreg.EnumValue(key, index)
            except OSError:
                break
            ports.append({"device": str(value), "description": str(name)})
            index += 1
        return ports

    async def _list_ports(self, params: dict) -> AdapterResult:
        ports: list[dict]
        try:
            from serial.tools import list_ports

            ports = [
                {"device": p.device, "description": p.description}
                for p in list_ports.comports()
            ]
        except ImportError:
            ports = self._list_ports_registry()
        return AdapterResult(
            success=True,
            output="\n".join(f"{p['device']}: {p['description']}" for p in ports)
            or "No serial ports found",
            data={"ports": ports, "devices": ports},
        )

    async def health_check(self) -> AdapterResult:
        try:
            import serial  # noqa: F401

            return AdapterResult(success=True, output="pyserial available")
        except ImportError:
            return AdapterResult(
                success=True,
                output="pyserial not installed — port detection works via the "
                "registry, but monitor/send actions need 'pip install pyserial'",
            )
