from __future__ import annotations

import threading

# Shared by legacy synchronous and queued local-model calls so a local model
# profile is never entered by two request paths at once.
LOCAL_MODEL_LOCK = threading.Lock()
