import json
import os
import tempfile

import monitor.watchdog as watchdog


def test_watchdog_rejects_missing_server_launch_script():
    original = watchdog.SERVER_LAUNCH
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    try:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"command": "python C:/missing/server.py --port 8765"}, handle)
        watchdog.SERVER_LAUNCH = path

        command = watchdog._backend_start_command()

        expected = os.path.normcase(os.path.join(
            watchdog.BRAIN_DIR, "server", "server.py"))
        assert expected in os.path.normcase(command)
    finally:
        watchdog.SERVER_LAUNCH = original
        os.unlink(path)