from .config import DELTA_READONLY_ENABLED, DELTA_API_KEY, DELTA_API_SECRET

class DeltaReadOnlyAccount:
    async def positions(self):
        if not DELTA_READONLY_ENABLED:
            raise RuntimeError("Delta private account access is disabled by default.")
        if not DELTA_API_KEY or not DELTA_API_SECRET:
            raise RuntimeError("Missing Delta API credentials.")
        raise NotImplementedError(
            "Implement and test the exact current regional Delta API signing scheme and positions endpoint "
            "from official documentation before enabling private account access."
        )
