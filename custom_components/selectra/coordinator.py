"""Data update coordinator for the Selectra integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.components.persistent_notification import (
    async_create as pn_async_create,
    async_dismiss as pn_async_dismiss,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import (
    SelectraApiClient,
    SelectraApiError,
    SelectraAuthError,
    SelectraRateLimitError,
    SelectraRequalificationError,
)
from .const import (
    CONF_CATEGORY,
    CONF_MODE,
    CONF_QUALIFICATION_INPUTS,
    CONF_SELECTED_PERIODS,
    CONF_STRATEGY,
    CONF_STRATEGY_VALUE,
    CONF_TOKEN,
    DEFAULT_POLL_INTERVAL_SECONDS,
    DOMAIN,
    MIN_POLL_INTERVAL_SECONDS,
    MODE_CLASSIC,
    MODE_FLAT,
    STRATEGY_CHEAPEST_PERCENT,
)

_LOGGER = logging.getLogger(__name__)

NOTIFICATION_ID = f"{DOMAIN}_requalification"
AUTH_NOTIFICATION_ID = f"{DOMAIN}_auth_error"


@dataclass
class SelectraData:
    """Processed data from the Selectra API."""

    prices: list[dict[str, Any]] = field(default_factory=list)
    currency: str | None = None
    next_update: datetime | None = None
    binary_state: bool | None = None
    current_period: dict[str, Any] | None = None
    next_change: datetime | None = None
    active_periods: list[dict[str, Any]] = field(default_factory=list)
    requalification: bool = False


class SelectraCoordinator(DataUpdateCoordinator[SelectraData]):
    """Coordinator to fetch and process Selectra price data."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self._entry = entry
        self._client = SelectraApiClient(
            entry.data[CONF_TOKEN], async_get_clientsession(hass)
        )
        self._details: dict[str, Any] = {}
        self._consecutive_failures = 0
        self._next_change_unsub: CALLBACK_TYPE | None = None

        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_POLL_INTERVAL_SECONDS),
        )

    @property
    def mode(self) -> str:
        return self._entry.data.get(CONF_MODE, MODE_CLASSIC)

    @property
    def category(self) -> str | None:
        return self._entry.data.get(CONF_CATEGORY)

    @property
    def details(self) -> dict[str, Any]:
        return self._details

    async def async_setup(self) -> None:
        """Fetch initial details data."""
        inputs = self._entry.data[CONF_QUALIFICATION_INPUTS]
        try:
            self._details = await self._client.get_details(inputs)
        except SelectraApiError as err:
            _LOGGER.warning("Failed to fetch initial details: %s", err)
            self._details = {}

    async def _async_update_data(self) -> SelectraData:
        """Fetch price data and compute binary sensor state."""
        inputs = self._entry.data[CONF_QUALIFICATION_INPUTS]
        data = SelectraData()

        try:
            price_data = await self._client.get_prices(inputs)
            self._consecutive_failures = 0
        except SelectraRequalificationError as err:
            _LOGGER.warning("Requalification required: %s", err.reason)
            pn_async_create(
                self.hass,
                f"{err.reason}",
                title="Selectra: Reconfiguration Required",
                notification_id=NOTIFICATION_ID,
            )
            self._cancel_next_change_timer()
            data.requalification = True
            self.update_interval = timedelta(hours=1)
            return data
        except SelectraAuthError as err:
            _LOGGER.error("Authentication error: %s", err)
            pn_async_create(
                self.hass,
                "Your Selectra API token is invalid. Please update it in the integration settings.",
                title="Selectra: Authentication Error",
                notification_id=AUTH_NOTIFICATION_ID,
            )
            self._cancel_next_change_timer()
            data.requalification = True
            self.update_interval = None
            return data
        except SelectraRateLimitError as err:
            _LOGGER.warning("Rate limited by Selectra API, next retry in 24h")
            self.update_interval = timedelta(hours=24)
            raise UpdateFailed("Rate limited by Selectra API") from err
        except SelectraApiError as err:
            self._consecutive_failures += 1
            # Backoff exponentiel : double l'intervalle a chaque echec, max 24h
            backoff_seconds = min(
                DEFAULT_POLL_INTERVAL_SECONDS * (2 ** self._consecutive_failures),
                86400,
            )
            self.update_interval = timedelta(seconds=backoff_seconds)
            if self._consecutive_failures >= 3:
                _LOGGER.warning(
                    "Selectra API unreachable for %d consecutive attempts: %s",
                    self._consecutive_failures,
                    err,
                )
            raise UpdateFailed(f"Error fetching Selectra data: {err}") from err

        # Dismiss any previous requalification notification on success
        pn_async_dismiss(self.hass, NOTIFICATION_ID)
        pn_async_dismiss(self.hass, AUTH_NOTIFICATION_ID)

        try:
            # Parse price periods
            raw_prices = price_data.get("prices", [])
            data.currency = price_data.get("currency")
            data.prices = _parse_price_periods(raw_prices)

            # Remplacer les noms bruts par les noms lisibles des features
            features = self._details.get("features", [])
            key_to_name = {
                f["key"]: f["name"]
                for f in features
                if "key" in f and "name" in f
            }
            for p in data.prices:
                p["name"] = key_to_name.get(p["name"], p["name"])

            # Parse next_update and adjust poll interval
            next_update_str = price_data.get("next_update")
            if next_update_str:
                try:
                    data.next_update = datetime.fromisoformat(next_update_str)
                except (ValueError, TypeError):
                    data.next_update = None

            self._update_poll_interval(data.next_update)

            # Compute binary sensor state
            now = dt_util.now()
            data.current_period = _find_current_period(data.prices, now)

            if self.mode == MODE_FLAT:
                data.binary_state = True
                data.active_periods = list(data.prices)
            elif self.mode == MODE_CLASSIC:
                selected = self._entry.data.get(CONF_SELECTED_PERIODS, [])
                # selected peut contenir des cles (ancien format) ou des noms lisibles
                resolved = [key_to_name.get(s, s) for s in selected]
                data.active_periods = _compute_classic_active(data.prices, resolved)
                if data.current_period:
                    data.binary_state = data.current_period["name"] in resolved
                else:
                    data.binary_state = False
            else:
                strategy = self._entry.data.get(CONF_STRATEGY, STRATEGY_CHEAPEST_PERCENT)
                value = self._entry.data.get(CONF_STRATEGY_VALUE, 30)
                local_tz = dt_util.get_default_time_zone()

                today_periods = _get_day_periods(data.prices, now, local_tz)

                if not today_periods:
                    _LOGGER.warning(
                        "No price data available for today. Binary sensor set to unknown"
                    )
                    data.binary_state = None
                    data.active_periods = []
                elif strategy == STRATEGY_CHEAPEST_PERCENT:
                    data.active_periods = _compute_cheapest_percent(today_periods, value)
                    data.binary_state = _is_in_active_periods(now, data.active_periods)
                else:
                    data.active_periods = _compute_cheapest_consecutive(
                        today_periods, value
                    )
                    data.binary_state = _is_in_active_periods(now, data.active_periods)

            # Mark active flag on prices list
            # Normalize to UTC to avoid isoformat mismatch between timezones
            # (e.g. "2026-02-26T03:00:00+01:00" vs "2026-02-26T02:00:00+00:00")
            active_starts = {
                p.get("_original_start", p["start"]).astimezone(dt_util.UTC)
                for p in data.active_periods
                if isinstance(p.get("_original_start", p["start"]), datetime)
            }
            for p in data.prices:
                if isinstance(p["start"], datetime):
                    p["is_active"] = p["start"].astimezone(dt_util.UTC) in active_starts
                else:
                    p["is_active"] = False

            # Calculate next state change
            data.next_change = _find_next_change(
                data.prices, now, data.binary_state
            )

            # Programmer un timer local sur la prochaine frontiere de periode
            next_boundary = _find_next_period_boundary(data.prices, now)
            self._schedule_next_change_timer(next_boundary)

        except Exception as err:
            raise UpdateFailed(f"Error processing Selectra data: {err}") from err

        return data

    def _update_poll_interval(self, next_update: datetime | None) -> None:
        """Dynamically adjust the polling interval based on next_update."""
        now = dt_util.now()
        if next_update and next_update > now:
            seconds = (next_update - now).total_seconds()
            interval = max(seconds, MIN_POLL_INTERVAL_SECONDS)
        else:
            interval = DEFAULT_POLL_INTERVAL_SECONDS

        self.update_interval = timedelta(seconds=interval)

    async def async_shutdown(self) -> None:
        """Cleanup a l'unload de l'entree."""
        self._cancel_next_change_timer()
        await super().async_shutdown()

    def _cancel_next_change_timer(self) -> None:
        """Annule le timer de transition local."""
        if self._next_change_unsub is not None:
            self._next_change_unsub()
            self._next_change_unsub = None

    def _schedule_next_change_timer(self, next_change: datetime | None) -> None:
        """Programme un timer local au moment de la prochaine transition."""
        self._cancel_next_change_timer()
        if next_change is None:
            return
        _LOGGER.debug("Scheduling next change timer at %s", next_change)
        self._next_change_unsub = async_track_point_in_time(
            self.hass, self._handle_next_change, next_change
        )

    async def _handle_next_change(self, _now: datetime) -> None:
        """Callback du timer : recalcule l'etat sans appel API."""
        _LOGGER.debug("Timer fired, recalculating local state")
        self._next_change_unsub = None
        try:
            self._recalculate_local_state()
        except Exception:
            _LOGGER.exception("Error in local state recalculation")

    def _recalculate_local_state(self) -> None:
        """Recalcule l'etat a partir des prix en memoire, sans appel API."""
        if self.data is None or not self.data.prices:
            return

        now = dt_util.now()
        data = self.data

        data.current_period = _find_current_period(data.prices, now)

        if self.mode == MODE_FLAT:
            data.binary_state = True
        elif self.mode == MODE_CLASSIC:
            selected = self._entry.data.get(CONF_SELECTED_PERIODS, [])
            key_to_name = {
                f["key"]: f["name"]
                for f in self._details.get("features", [])
                if "key" in f and "name" in f
            }
            resolved = [key_to_name.get(s, s) for s in selected]
            if data.current_period:
                data.binary_state = data.current_period["name"] in resolved
            else:
                data.binary_state = False
        else:
            # Mode dynamique : recalculer active_periods pour le jour courant
            strategy = self._entry.data.get(CONF_STRATEGY, STRATEGY_CHEAPEST_PERCENT)
            value = self._entry.data.get(CONF_STRATEGY_VALUE, 30)
            local_tz = dt_util.get_default_time_zone()
            today_periods = _get_day_periods(data.prices, now, local_tz)

            if not today_periods:
                data.binary_state = None
                data.active_periods = []
            elif strategy == STRATEGY_CHEAPEST_PERCENT:
                data.active_periods = _compute_cheapest_percent(today_periods, value)
                data.binary_state = _is_in_active_periods(now, data.active_periods)
            else:
                data.active_periods = _compute_cheapest_consecutive(today_periods, value)
                data.binary_state = _is_in_active_periods(now, data.active_periods)

            # Mettre a jour les flags is_active sur les prix
            active_starts = {
                p.get("_original_start", p["start"]).astimezone(dt_util.UTC)
                for p in data.active_periods
                if isinstance(p.get("_original_start", p["start"]), datetime)
            }
            for p in data.prices:
                if isinstance(p["start"], datetime):
                    p["is_active"] = p["start"].astimezone(dt_util.UTC) in active_starts
                else:
                    p["is_active"] = False

        data.next_change = _find_next_change(data.prices, now, data.binary_state)

        self.async_update_listeners()

        next_boundary = _find_next_period_boundary(data.prices, now)
        _LOGGER.debug(
            "Recalculated: period=%s, binary_state=%s, next_boundary=%s",
            data.current_period.get("name") if data.current_period else None,
            data.binary_state,
            next_boundary,
        )
        self._schedule_next_change_timer(next_boundary)


def _parse_price_periods(raw_prices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Parse raw price period dicts, converting datetimes."""
    periods = []
    for p in raw_prices:
        try:
            start = datetime.fromisoformat(p["start"])
            end = datetime.fromisoformat(p["end"])
        except (ValueError, KeyError, TypeError):
            continue
        periods.append(
            {
                "name": p.get("name", ""),
                "price": p.get("price", 0.0),
                "start": start,
                "end": end,
            }
        )
    periods.sort(key=lambda x: x["start"])
    return periods


def _find_current_period(
    periods: list[dict[str, Any]], now: datetime
) -> dict[str, Any] | None:
    """Find the price period that contains the current time."""
    for p in periods:
        if p["start"] <= now < p["end"]:
            return p
    return None


def _compute_classic_active(
    periods: list[dict[str, Any]], selected_names: list[str]
) -> list[dict[str, Any]]:
    """Mark periods whose name is in the selected list as active."""
    return [p for p in periods if p["name"] in selected_names]


def _get_day_periods(
    periods: list[dict[str, Any]], now: datetime, local_tz: Any
) -> list[dict[str, Any]]:
    """Get all price periods within the current day (midnight to midnight local)."""
    local_now = now.astimezone(local_tz)
    day_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)

    day_periods = []
    for p in periods:
        p_start = p["start"].astimezone(local_tz) if p["start"].tzinfo else p["start"]
        p_end = p["end"].astimezone(local_tz) if p["end"].tzinfo else p["end"]

        # Include periods that overlap with the day window
        if p_start < day_end and p_end > day_start:
            # Clamp to day boundaries
            clamped_start = max(p_start, day_start)
            clamped_end = min(p_end, day_end)
            day_periods.append(
                {
                    **p,
                    "_original_start": p["start"],
                    "start": clamped_start,
                    "end": clamped_end,
                }
            )

    return day_periods


def _compute_cheapest_percent(
    periods: list[dict[str, Any]], percent: int
) -> list[dict[str, Any]]:
    """Find periods that fill the cheapest X% of the day."""
    target_seconds = 24 * 3600 * percent / 100.0

    sorted_periods = sorted(periods, key=lambda p: p["price"])

    active = []
    cumulative = 0.0
    for p in sorted_periods:
        duration = (p["end"] - p["start"]).total_seconds()
        if cumulative + duration <= target_seconds:
            active.append(p)
            cumulative += duration
        else:
            # Include partial coverage if needed
            remaining = target_seconds - cumulative
            if remaining > 0:
                active.append(p)
            break

    return active


def _compute_cheapest_consecutive(
    periods: list[dict[str, Any]], hours: int
) -> list[dict[str, Any]]:
    """Find the consecutive window of X hours with the lowest weighted average price."""
    window_seconds = hours * 3600.0
    sorted_periods = sorted(periods, key=lambda p: p["start"])

    if not sorted_periods:
        return []

    best_cost = float("inf")
    best_start: datetime | None = None
    best_end: datetime | None = None

    # Generate candidate window start times: start of each period and
    # any point where a window ending at a period boundary would start.
    candidate_starts: set[datetime] = set()
    for p in sorted_periods:
        candidate_starts.add(p["start"])
        # Also consider window starting such that it ends at this period's end
        candidate_start = p["end"] - timedelta(seconds=window_seconds)
        if candidate_start >= sorted_periods[0]["start"]:
            candidate_starts.add(candidate_start)

    for w_start in sorted(candidate_starts):
        w_end = w_start + timedelta(seconds=window_seconds)

        # Compute weighted cost for this window
        total_cost = 0.0
        total_duration = 0.0

        for p in sorted_periods:
            # Overlap between window and period
            overlap_start = max(w_start, p["start"])
            overlap_end = min(w_end, p["end"])
            if overlap_start < overlap_end:
                duration = (overlap_end - overlap_start).total_seconds()
                total_cost += p["price"] * duration
                total_duration += duration

        # Skip windows not fully covered by data — a 4h window with
        # only 1h of overlap would win on raw cost despite being partial
        if total_duration < window_seconds * 0.99:
            continue

        if total_duration > 0 and total_cost < best_cost:
            best_cost = total_cost
            best_start = w_start
            best_end = w_end

    if best_start is None or best_end is None:
        return []

    # Collect periods that fall within the best window
    active = []
    for p in sorted_periods:
        overlap_start = max(best_start, p["start"])
        overlap_end = min(best_end, p["end"])
        if overlap_start < overlap_end:
            active.append(p)

    return active


def _is_in_active_periods(
    now: datetime, active_periods: list[dict[str, Any]]
) -> bool:
    """Check if now falls within any active period."""
    for p in active_periods:
        if p["start"] <= now < p["end"]:
            return True
    return False


def _find_next_change(
    prices: list[dict[str, Any]], now: datetime, current_state: bool | None
) -> datetime | None:
    """Find when the binary state will next change."""
    if current_state is None:
        return None

    future_periods = [p for p in prices if p["end"] > now]
    future_periods.sort(key=lambda p: p["start"])

    for p in future_periods:
        if p["start"] <= now < p["end"]:
            # We're inside this period
            is_active = p.get("is_active", False)
            if is_active == current_state:
                # State matches — the change happens at the end of this period
                # But only if the next period has a different state
                continue
            else:
                return p["start"]
        elif p["start"] > now:
            is_active = p.get("is_active", False)
            if is_active != current_state:
                return p["start"]

    return None


def _find_next_period_boundary(
    prices: list[dict[str, Any]], now: datetime
) -> datetime | None:
    """Retourne la fin de la periode courante (prochaine frontiere)."""
    for p in prices:
        if p["start"] <= now < p["end"]:
            return p["end"]
    # Pas dans une periode : retourner le debut de la prochaine
    future = [p for p in prices if p["start"] > now]
    if future:
        future.sort(key=lambda p: p["start"])
        return future[0]["start"]
    return None
