import sys
import os
import traceback

sys.path.insert(0, os.path.dirname(__file__))

LOG_FILE = os.path.join(os.path.dirname(__file__), "..", "server.log")

with open(LOG_FILE, "w") as log:
    try:
        log.write("Starting Flask server...\n")
        log.flush()
        from app import app
        log.write("Flask app imported successfully.\n")
        log.write("Registered routes:\n")
        for rule in app.url_map.iter_rules():
            log.write(f"  {rule.rule} -> {rule.endpoint}\n")
        log.flush()
        log.write("\nStarting server on http://127.0.0.1:5000\n")
        log.flush()
        app.run(host="127.0.0.1", port=5000, debug=False)
    except Exception as e:
        log.write(f"ERROR: {type(e).__name__}: {e}\n")
        log.write(traceback.format_exc())
        log.flush()
