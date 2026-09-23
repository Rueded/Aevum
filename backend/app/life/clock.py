from datetime import datetime, timedelta, timezone
from typing import Optional, Protocol, runtime_checkable

@runtime_checkable
class SimulationClock(Protocol):
    """Protocol for life simulation time providers."""
    def now(self) -> datetime:
        """Return the current simulation time as a timezone-aware UTC datetime."""
        ...

class RealTimeClock:
    """Production clock that returns actual system UTC time."""
    def now(self) -> datetime:
        return datetime.now(timezone.utc)

class DeterministicSimulationClock:
    """Deterministic, controllable clock for reproducible simulation and testing."""
    def __init__(self, initial_time: Optional[datetime] = None) -> None:
        if initial_time is None:
            self._current_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        else:
            if initial_time.tzinfo is None:
                self._current_time = initial_time.replace(tzinfo=timezone.utc)
            else:
                self._current_time = initial_time.astimezone(timezone.utc)

    def now(self) -> datetime:
        return self._current_time

    def advance(self, duration: timedelta) -> datetime:
        """Advance the simulation time by duration and return the new time."""
        self._current_time += duration
        return self._current_time

    def set_time(self, dt: datetime) -> datetime:
        """Set simulation time to a specific instant (ensured UTC aware)."""
        if dt.tzinfo is None:
            self._current_time = dt.replace(tzinfo=timezone.utc)
        else:
            self._current_time = dt.astimezone(timezone.utc)
        return self._current_time
