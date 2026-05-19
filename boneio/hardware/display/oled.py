"""OLED Display driver using I2C."""

import asyncio
import contextlib
import logging
import subprocess
import threading
import time
from itertools import cycle
from typing import TYPE_CHECKING

import qrcode
from luma.core.error import DeviceNotFoundError
from luma.core.interface.serial import i2c
from luma.core.render import canvas
from luma.oled.device import sh1106
from PIL import Image, ImageDraw
from PIL.ImageDraw import ImageDraw as ImageDrawType

from boneio.const import LONG, SINGLE, UPTIME, WHITE
from boneio.core.events import EventBus, async_track_point_in_time, utcnow
from boneio.core.system import HostData
from boneio.core.utils.font_util import make_font
from boneio.core.utils.timeperiod import TimePeriod
from boneio.exceptions import I2CError
from boneio.models import InputState, OutputState

if TYPE_CHECKING:
    from boneio.hardware.i2c.bus import SMBus2I2C

_LOGGER = logging.getLogger(__name__)

# Try to use TTF fonts, fallback to default PIL fonts if not available
try:
    fonts = {
        "big": make_font("DejaVuSans.ttf", 12),
        "small": make_font("DejaVuSans.ttf", 9),
        "extraSmall": make_font("DejaVuSans.ttf", 7),
        "danube": make_font("danube__.ttf", 15, local=True),
    }
except OSError:
    # Fallback to default PIL fonts if TTF fonts are not available
    from PIL import ImageFont

    _LOGGER.warning("TTF fonts not found, using default PIL fonts")
    fonts = {
        "big": ImageFont.load_default(),
        "small": ImageFont.load_default(),
        "extraSmall": ImageFont.load_default(),
        "danube": ImageFont.load_default(),
    }

# Screen layout constants
START_ROW = 17
UPTIME_ROWS = list(range(22, 60, 10))
OUTPUT_ROWS = list(range(14, 60, 6))
INPUT_ROWS = list(range(12, 60, 6))
OUTPUT_COLS = range(0, 113, 56)
INPUT_COLS = range(0, 113, 30)


def shorten_name(name: str) -> str:
    """Shorten name for display."""
    if len(name) > 6:
        return f"{name[:4]}{name[-2:]}"
    return name


class Oled:
    """OLED Display driver for SH1106 I2C display."""

    def __init__(
        self,
        host_data: HostData,
        grouped_outputs_by_expander: list[str],
        sleep_timeout: TimePeriod,
        screen_order: list[str],
        input_groups: list[str],
        event_bus: EventBus,
        i2c_bus: "SMBus2I2C | None" = None,
        device: "sh1106 | None" = None,
    ):
        """Initialize OLED display.

        Args:
            host_data: Host system data
            grouped_outputs_by_expander: List of grouped output names
            sleep_timeout: Sleep timeout period
            screen_order: Configured screen order (placeholders already replaced)
            input_groups: List of input group names
            event_bus: Event bus for handling events
            i2c_bus: I2C bus instance (optional, will create if not provided)
            device: Pre-initialized sh1106 device (optional, avoids duplicate I2C init)
        """
        self._host_data: HostData = host_data
        self._grouped_outputs_by_expander = grouped_outputs_by_expander
        self._event_bus = event_bus

        # Screen order is already configured by DisplayManager
        self._screen_order = screen_order
        self._input_groups = input_groups
        _LOGGER.debug("OLED initialized with screen order: %s", self._screen_order)

        self._current_screen = self._screen_order[0] if self._screen_order else UPTIME
        self._screen_cycle = cycle(self._screen_order) if self._screen_order else cycle([UPTIME])
        # Skip the first element so that next() shows the second screen on first click
        next(self._screen_cycle)
        self._sleep = False
        self._cancel_sleep_handle = None
        self._sleep_timeout = sleep_timeout

        # Shutdown confirmation state machine
        # States: None -> "wait_release" -> "confirm" -> "progress" -> shutdown
        # - Long press held 2s+ → show confirm screen, enter "wait_release"
        # - Release after first long → enter "confirm" (waiting for second long)
        # - Second long press → enter "progress" with filling progress bar
        # - Hold 3s → execute shutdown
        # - Single click or 30s timeout → cancel
        self._shutdown_state: str | None = None
        self._shutdown_cancel_handle = None
        # Timer to detect button release (no LONG event for 300ms = released)
        self._shutdown_release_timer: asyncio.TimerHandle | None = None
        # Last seen long press duration — used to detect new press cycle (duration resets)
        self._shutdown_last_long_duration: float = 0.0
        # Duration (seconds) the user must hold the button to confirm shutdown
        self._shutdown_hold_duration: float = 3.0
        # Timeout (seconds) to cancel shutdown confirmation if no action
        self._shutdown_confirm_timeout: float = 30.0
        # Minimum long press duration (seconds) before shutdown flow starts
        self._shutdown_long_press_threshold: float = 2.0

        # Initialize I2C display (reuse early device if provided)
        if device is not None:
            self._device = device
            _LOGGER.info("OLED display reusing early-initialized sh1106 device")
        else:
            # SH1106 init sends ~30 commands over i2c — on a contended bus
            # (other drivers booting in parallel: LM75, INA219, MCP23017)
            # the controller occasionally returns EREMOTEIO mid-sequence. The
            # hardware is actually fine (a tight single-threaded loop hits it
            # at 100% success rate post-boot), so a short retry with backoff
            # is enough to ride out the boot-time contention without crashing
            # the DisplayManager.
            # Total ramp here is ~14s (0.2 + 0.4 + 0.6 + ... + 2.0 = 11s plus
            # the time spent in the failed sh1106(serial) sequence itself).
            # Cold-boot i2c bus on the BBB+capes is genuinely unstable for
            # several seconds while parallel drivers (LM75, INA219, MCP23017)
            # finish their own probes — anything shorter loses the race.
            last_err: Exception | None = None
            for attempt in range(10):
                try:
                    serial = i2c(port=2, address=0x3C)
                    self._device = sh1106(serial)
                    if attempt > 0:
                        _LOGGER.info("OLED display initialized after %d retries", attempt)
                    else:
                        _LOGGER.info("OLED display initialized successfully")
                    break
                except (DeviceNotFoundError, OSError) as err:
                    last_err = err
                    _LOGGER.debug(
                        "OLED init attempt %d failed (%s), retrying...",
                        attempt + 1, err,
                    )
                    # Linear ramp 200ms → 2000ms (cap so we don't sleep forever).
                    time.sleep(min(0.2 * (attempt + 1), 2.0))
            else:
                raise I2CError(f"OLED display not found after 10 attempts: {last_err}") from last_err

        # Re-entrant lock guards every `canvas(self._device)` write — luma
        # opens its own SMBus handle that doesn't share the app's i2c bus lock,
        # so without this guard two draw paths (button handler + periodic
        # refresh) race on `/dev/i2c-2` and the kernel returns EREMOTEIO (121),
        # EAGAIN (11) or ETIMEDOUT (110) on a collision. Use RLock so a method
        # can call into another locked helper without self-deadlocking.
        self._draw_lock = threading.RLock()

        # Subscribe to OLED button events
        self._event_bus.add_event_listener(
            event_type="input",
            entity_id="oled_button",
            listener_id="oled_button_handler",
            target=self._handle_button_press,
        )

    # ------------------------------------------------------------------
    # i2c-safe draw helpers
    # ------------------------------------------------------------------

    @contextlib.contextmanager
    def _locked_canvas(self):
        """Acquire ``_draw_lock`` then ``canvas(self._device)``.

        Replaces every direct ``with canvas(self._device) as draw:`` so that
        only one writer touches the SH1106 over i2c at a time.
        Used as: ``with self._locked_canvas() as draw: …``.
        """
        with self._draw_lock:
            with canvas(self._device) as draw:
                yield draw

    def _safe_draw(self, draw_callable, *, label: str, retries: int = 6) -> bool:
        """Execute ``draw_callable(draw)`` inside a locked canvas, retry on
        transient i2c errors (EAGAIN/ETIMEDOUT/EREMOTEIO) up to ``retries``
        times with exponential backoff.

        Returns True on success, False if all attempts failed. Logs a warning
        on terminal failure so the OLED journal stays diagnosable. Used by
        the periodic refresh paths where dropping a frame is preferable to
        crashing the loop.

        Retry budget (retries=6 → 7 attempts, sleep ramp 10→640ms capped):
        total backoff ≈ 1.27s (10+20+40+80+160+320+640ms summed across the
        6 inter-attempt sleeps). The previous budget (retries=2 → ~30ms of
        sleep) was too short for the actual bus contention on this device:
        PCT2075 long temp reads at 0x48 stall the bus for 10-50ms, MCP23017
        scans add their own windows, so 3 tightly-spaced attempts often all
        landed inside the same stall and returned False. False from
        _safe_draw with the next clear_display() succeeding produces the
        "ekran ucięty w połowie" symptom — luma flushes pages 0-N then
        errors out, the partial frame stays on screen.
        """
        for attempt in range(retries + 1):
            try:
                with self._locked_canvas() as draw:
                    draw_callable(draw)
                return True
            except OSError as exc:
                if exc.errno in (11, 110, 121) and attempt < retries:
                    _LOGGER.debug(
                        "OLED %s: transient i2c errno %d, retry %d/%d",
                        label, exc.errno, attempt + 1, retries,
                    )
                    # Exponential 10→640ms (cap protects against pathological
                    # retries values; with default=6 the cap is never hit).
                    time.sleep(min(0.01 * (2 ** attempt), 0.64))
                    continue
                _LOGGER.warning(
                    "OLED %s failed after %d attempt(s): %s",
                    label, attempt + 1, exc,
                )
                return False
        return False

    async def _output_callback(self, event: OutputState) -> None:
        """Callback for output events."""
        if self._grouped_outputs_by_expander and self._current_screen in self._grouped_outputs_by_expander:
            self._update_display()

    async def _standard_callback(self, event: dict) -> None:
        """Callback for standard events."""
        self._update_display()

    async def _input_callback(self, event: InputState) -> None:
        """Callback for input events."""
        if self._input_groups and self._current_screen in self._input_groups:
            self._update_display()

    def _draw_output(self, data: dict, draw: ImageDrawType) -> None:
        """Draw outputs of GPIO/MCP relays."""
        cols = cycle(OUTPUT_COLS)
        draw.text(
            (1, 1),
            f"Relay {self._current_screen}",
            font=fonts["small"],
            fill=WHITE,
        )
        i = 0
        j = next(cols)
        for k in data.values():
            if len(OUTPUT_ROWS) == i:
                j = next(cols)
                i = 0
            draw.text(
                (j, OUTPUT_ROWS[i]),
                f"{shorten_name(k['name'])} {k['state']}",
                font=fonts["extraSmall"],
                fill=WHITE,
            )
            i += 1

    def _draw_input(self, data: dict, draw: ImageDrawType) -> None:
        """Draw inputs of boneIO Black."""
        cols = cycle(INPUT_COLS)
        draw.text(
            (1, 1),
            f"{self._current_screen}",
            font=fonts["small"],
            fill=WHITE,
        )
        i = 0
        j = next(cols)
        for k in data.values():
            if len(INPUT_ROWS) == i:
                j = next(cols)
                i = 0
            draw.text(
                (j, INPUT_ROWS[i]),
                f"{shorten_name(k['name'])} {k['state']}",
                font=fonts["extraSmall"],
                fill=WHITE,
            )
            i += 1

    def _draw_qr_code(self, url: str) -> None:
        """Draw QR code on the OLED display."""
        if not url:
            return

        # Create QR code with box_size 2 and scale down later
        qr = qrcode.QRCode(version=1, box_size=2, border=1)
        qr.add_data(url)
        qr.make(fit=True)

        # Create QR code image
        # For mode "1", colors must be int: 0=black, 1=white
        qr_image = qr.make_image(fill_color="white", back_color="black", mode="1")
        qr_image = qr_image.convert("1")  # type: ignore

        # Create a blank image with OLED dimensions
        display_image = Image.new("1", (128, 64), 0)  # Mode 1, size 128x64, black background
        draw = ImageDraw.Draw(display_image)

        # Add title text on the left side
        draw.text((2, 2), "Scan to", font=fonts["small"], fill=WHITE)
        draw.text((2, 12), "access", font=fonts["small"], fill=WHITE)
        draw.text((2, 22), "webui", font=fonts["small"], fill=WHITE)

        # Calculate position to align QR code to right and center vertically
        qr_size = qr_image.size if hasattr(qr_image, "size") else (32, 32)  # Default size  # type: ignore
        x = 128 - qr_size[0] - 2  # Align to right with 2 pixels padding
        y = (64 - qr_size[1]) // 2  # Center vertically

        # Paste QR code onto center of display image
        # Use bounding box format: (left, top, right, bottom)
        try:
            display_image.paste(qr_image, (x, y, x + qr_size[0], y + qr_size[1]))  # type: ignore
        except Exception as e:
            _LOGGER.error(f"Failed to paste QR code: {e}")
            return

        # Display the centered QR code
        self._device.display(display_image)

    async def _handle_button_press(self, event) -> None:
        """Handle button press event from input.

        Supports shutdown flow via long press:
        1. Long press held for 2s+ → show confirmation screen
        2. User releases button → state moves to "confirm"
        3. Second long press (held 3s) → progress bar fills, then shutdown
        4. Any single click or 30s timeout → cancel shutdown

        The detector emits periodic LONG events (every 200ms) with growing
        duration while the button is held. A new press cycle is detected
        when duration resets (new duration < last tracked duration).

        Args:
            event: InputEvent from EventBus with click_type and duration
        """
        click_type = getattr(event, "click_type", None)
        duration = getattr(event, "duration", None) or 0.0

        _LOGGER.debug(
            "OLED button event: click_type=%s, duration=%.2f, shutdown_state=%s",
            click_type,
            duration,
            self._shutdown_state,
        )

        # --- Shutdown state machine ---

        if self._shutdown_state == "wait_release":
            # Absorb periodic LONG events from the first long press.
            # Detector does NOT emit SINGLE after long press release.
            # Detect release via timer: each LONG resets a 300ms timer.
            # When no more LONG events arrive, timer fires → "confirm".
            if click_type == LONG:
                self._shutdown_last_long_duration = duration
                # Reset release-detection timer
                self._reset_release_timer()
                return
            elif click_type == SINGLE:
                # Shouldn't happen after long, but handle gracefully
                self._cancel_release_timer()
                self._shutdown_state = "confirm"
                self._shutdown_last_long_duration = 0.0
                return
            # Ignore other events
            return

        if self._shutdown_state == "confirm":
            if click_type == LONG:
                # Second long press — enter progress mode
                self._shutdown_state = "progress"
                self._cancel_shutdown_timeout()
                self._shutdown_last_long_duration = duration
                self._draw_shutdown_progress(duration)
                if duration >= self._shutdown_hold_duration:
                    await self._execute_shutdown()
                return
            elif click_type == SINGLE:
                # Single click cancels shutdown confirmation
                self._cancel_shutdown()
                return
            # Ignore other events during confirm
            return

        if self._shutdown_state == "progress":
            if click_type == LONG:
                if duration < self._shutdown_last_long_duration:
                    # Duration reset — user released and pressed again, cancel
                    self._cancel_shutdown()
                    return
                # Still holding — update progress bar
                self._shutdown_last_long_duration = duration
                self._draw_shutdown_progress(duration)
                if duration >= self._shutdown_hold_duration:
                    await self._execute_shutdown()
                return
            else:
                # Released (single) or other — cancel
                self._cancel_shutdown()
                return

        # --- Normal mode ---
        if self._sleep:
            self.wake_up()
            return

        if click_type == LONG and duration >= self._shutdown_long_press_threshold:
            # Long press held beyond threshold — show confirmation, enter wait_release
            self._shutdown_state = "wait_release"
            self._shutdown_last_long_duration = duration
            self._draw_shutdown_confirm()
            self._start_shutdown_timeout()
            self._reset_release_timer()
            return

        if click_type == SINGLE:
            self._next_screen()

    def _next_screen(self) -> None:
        """Switch to next screen.

        We explicitly clear the framebuffer between screens to defeat the
        "second click clears" symptom: under i2c bus contention luma's
        page-by-page write of the new canvas can land partially, leaving
        a column of the previous screen's pixels visible until the *next*
        successful flush overwrites them. A dedicated all-black write here
        + a retry loop on render_display() means each screen-switch starts
        from a guaranteed-clean buffer.

        If render_display() exhausts its retry budget (bus stuck inside
        a long stall window), schedule a deferred re-paint ~300ms later
        when the parallel i2c drivers (PCT2075, MCP23017) have released
        the bus. Without this, a click landing on a hot bus produces an
        "ucięty w połowie" screen that stays until the next click.
        """
        # Remove old listeners before switching screen (only if exists)
        with contextlib.suppress(KeyError):
            self._event_bus.remove_event_listener(listener_id=f"oled_{self._current_screen}")
        self._current_screen = next(self._screen_cycle)
        self.clear_display()        # 4-retry; logs warning if all fail
        if not self.render_display():
            self._schedule_recovery_paint(self._current_screen)

    def _schedule_recovery_paint(self, screen: str) -> None:
        """Schedule a one-shot deferred re-paint after a failed render.

        Used when ``_safe_draw`` exhausts its full retry budget on a
        contended bus — the OLED is left holding partial pixels from
        the half-flushed canvas. 300ms later most parallel-init i2c
        windows have closed (PCT2075 temp read ≤ ~50ms, MCP23017
        scan ≤ ~20ms), so a second attempt usually wins.

        If the user switched screens in the meantime (``_current_screen``
        no longer matches the captured value), or the screen went to
        sleep, the callback no-ops — we don't want to over-paint a
        screen the user already moved past.
        """
        loop = self._event_bus._loop

        def _recover() -> None:
            if self._current_screen != screen or self._sleep:
                return
            _LOGGER.debug("OLED scheduled recovery paint for %s", screen)
            self.clear_display()
            self.render_display()

        loop.call_later(0.3, _recover)

    # --- Shutdown helper methods ---

    def _draw_shutdown_confirm(self) -> None:
        """Draw shutdown confirmation screen on OLED.

        Shows a warning message asking the user to hold the button
        for 5 seconds to confirm system shutdown.
        """
        with self._locked_canvas() as draw:
            # Warning triangle
            draw.polygon([(64, 2), (54, 18), (74, 18)], outline=WHITE)
            draw.text((61, 5), "!", font=fonts["small"], fill=WHITE)
            # Message
            draw.text((10, 24), "Shutdown system?", font=fonts["small"], fill=WHITE)
            draw.text((4, 38), "Hold button 3s to confirm", font=fonts["extraSmall"], fill=WHITE)
            draw.text((8, 52), "Click to cancel (30s)", font=fonts["extraSmall"], fill=WHITE)

    def _draw_shutdown_progress(self, duration: float) -> None:
        """Draw shutdown progress bar on OLED.

        Shows a progress bar that fills proportionally to how long
        the user has been holding the button vs the required duration.

        Args:
            duration: How long the button has been held (seconds)
        """
        progress = min(duration / self._shutdown_hold_duration, 1.0)
        bar_x, bar_y = 10, 34
        bar_w, bar_h = 108, 14
        fill_w = int(bar_w * progress)

        with self._locked_canvas() as draw:
            draw.text((20, 4), "Shutting down...", font=fonts["small"], fill=WHITE)
            draw.text((28, 18), f"{int(progress * 100)}%", font=fonts["small"], fill=WHITE)
            # Progress bar outline
            draw.rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + bar_h], outline=WHITE)
            # Progress bar fill
            if fill_w > 0:
                draw.rectangle([bar_x + 1, bar_y + 1, bar_x + fill_w - 1, bar_y + bar_h - 1], fill=WHITE)
            draw.text((22, 54), "Release to cancel", font=fonts["extraSmall"], fill=WHITE)

    def _start_shutdown_timeout(self) -> None:
        """Start a 10-second timeout that cancels the shutdown confirmation.

        If the user doesn't interact within the timeout period,
        the shutdown flow is cancelled and the normal screen is restored.
        """
        self._cancel_shutdown_timeout()
        loop = self._event_bus._loop

        def _timeout_callback() -> None:
            """Cancel shutdown after timeout expires."""
            _LOGGER.info("Shutdown confirmation timed out, cancelling")
            self._shutdown_state = None
            self._shutdown_cancel_handle = None
            self.render_display()

        self._shutdown_cancel_handle = loop.call_later(self._shutdown_confirm_timeout, _timeout_callback)

    def _cancel_shutdown_timeout(self) -> None:
        """Cancel the pending shutdown timeout timer."""
        if self._shutdown_cancel_handle is not None:
            self._shutdown_cancel_handle.cancel()
            self._shutdown_cancel_handle = None

    def _reset_release_timer(self) -> None:
        """Reset the 300ms release-detection timer.

        Called on each periodic LONG event during wait_release state.
        If no more LONG events arrive within 300ms, the timer fires
        and transitions to 'confirm' state (button was released).
        """
        self._cancel_release_timer()
        loop = self._event_bus._loop

        def _on_release_detected() -> None:
            """No LONG event for 300ms — button was released."""
            self._shutdown_release_timer = None
            if self._shutdown_state == "wait_release":
                _LOGGER.debug("OLED button release detected (no LONG for 300ms)")
                self._shutdown_state = "confirm"
                self._shutdown_last_long_duration = 0.0
                # Timeout already running from first long press

        self._shutdown_release_timer = loop.call_later(0.3, _on_release_detected)

    def _cancel_release_timer(self) -> None:
        """Cancel the pending release-detection timer."""
        if self._shutdown_release_timer is not None:
            self._shutdown_release_timer.cancel()
            self._shutdown_release_timer = None

    def _cancel_shutdown(self) -> None:
        """Cancel the shutdown flow and return to normal display.

        Resets the shutdown state machine and restores the current screen.
        """
        _LOGGER.info("Shutdown cancelled by user")
        self._cancel_shutdown_timeout()
        self._cancel_release_timer()
        self._shutdown_state = None
        self._shutdown_last_long_duration = 0.0
        self.render_display()

    async def _execute_shutdown(self) -> None:
        """Execute system shutdown.

        Draws a final 'Goodbye' message on the OLED, then runs
        'sudo shutdown -h now' to power off the device.
        """
        _LOGGER.warning("System shutdown initiated from OLED button")
        self._shutdown_state = None
        self._shutdown_last_long_duration = 0.0
        self._cancel_shutdown_timeout()

        # Draw goodbye screen
        with self._locked_canvas() as draw:
            draw.text((20, 10), "Goodbye!", font=fonts["big"], fill=WHITE)
            draw.text((15, 35), "System shutting down...", font=fonts["extraSmall"], fill=WHITE)

        # Small delay so the user sees the message
        await asyncio.sleep(1)

        try:
            subprocess.run(
                ["sudo", "shutdown", "-h", "now"],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            _LOGGER.error("Failed to shutdown device: %s", e.stderr)
            # Show error on OLED and return to normal
            with self._locked_canvas() as draw:
                draw.text((10, 20), "Shutdown failed!", font=fonts["small"], fill=WHITE)
                draw.text((10, 40), str(e.stderr)[:20], font=fonts["extraSmall"], fill=WHITE)
            await asyncio.sleep(3)
            self.render_display()
        except Exception as e:
            _LOGGER.error("Error shutting down device: %s", e)
            self.render_display()

    def clear_display(self) -> bool:
        """Wipe the SH1106 framebuffer to black.

        Called during handoff from early_oled AND between screen switches in
        ``_next_screen()``. A failed clear is worse than no clear at all
        because the next paint partial-flushes over the previous content
        page-by-page — when the partial paint stalls, the user sees
        "half new screen, half old screen" (ekran ucięty w połowie).

        Retried 4× with the same exp backoff curve as ``_safe_draw`` so a
        single bus stall (PCT2075 long temp read, MCP23017 scan, etc.)
        doesn't leave dirty framebuffer behind. Returns True on success,
        False if all attempts exhausted (caller can decide whether to
        skip the paint entirely or defer it).
        """
        with self._draw_lock:
            for attempt in range(4):
                try:
                    self._device.clear()
                    return True
                except OSError as exc:
                    if exc.errno in (11, 110, 121) and attempt < 3:
                        _LOGGER.debug(
                            "OLED clear: transient i2c errno %d, retry %d/3",
                            exc.errno, attempt + 1,
                        )
                        time.sleep(min(0.01 * (2 ** attempt), 0.64))
                        continue
                    _LOGGER.warning(
                        "OLED clear failed after %d attempt(s) (%s) — "
                        "next paint may show ghost pixels",
                        attempt + 1, exc,
                    )
                    return False
            return False

    def render_display(self) -> None:
        """Render display - main method that decides what to display.

        Uses ``_safe_draw`` so a transient i2c stall during screen-switch
        retries instead of leaving the framebuffer half-written (which
        manifested as ghost pixels from the previous screen — the
        "second click clears" bug).
        """
        data = self._host_data.get(self._current_screen)
        if not data:
            self._next_screen()
            return

        if self._current_screen == "web":
            self._draw_qr_code(url=str(data))
        elif isinstance(data, dict):
            # Pick the right draw routine + listener subscription for the
            # current screen kind. The selector returns (draw_fn, register_fn)
            # so the actual canvas write happens inside `_safe_draw` (locked,
            # retryable) and the side-effecting listener registration happens
            # AFTER a successful flush — that ordering prevents stale
            # listeners from firing _update_display against a half-painted
            # frame.
            draw_fn, register_fn = self._render_plan(data)
            if self._safe_draw(draw_fn, label=f"render_display:{self._current_screen}"):
                register_fn()

        if not self._cancel_sleep_handle and self._sleep_timeout.total_seconds > 0:
            self.start_sleep_timer()

    def _render_plan(self, data: dict):
        """Return (draw_fn, register_fn) for the current screen.

        ``draw_fn(draw)`` runs inside the locked canvas. ``register_fn()``
        runs only after a successful canvas flush — registers event
        listeners that will trigger ``_update_display`` on future state
        changes. Separating the two keeps the i2c write tight (retryable
        as an atom) and never re-registers listeners on a failed paint.
        """
        screen = self._current_screen
        if self._grouped_outputs_by_expander and screen in self._grouped_outputs_by_expander:
            def _draw(draw):
                self._draw_output(data, draw)
            def _register():
                for id in data:
                    self._event_bus.add_event_listener(
                        event_type="output",
                        entity_id=id,
                        listener_id=f"oled_{screen}",
                        target=self._output_callback,
                    )
            return _draw, _register
        if screen == UPTIME:
            def _draw(draw):
                self._draw_uptime(draw)
            def _register():
                self._event_bus.add_event_listener(
                    event_type="host",
                    entity_id=f"{screen}_hoststats",
                    listener_id=f"oled_{screen}",
                    target=self._standard_callback,
                )
            return _draw, _register
        if self._input_groups and screen in self._input_groups:
            def _draw(draw):
                self._draw_input(data, draw)
            def _register():
                for id in data:
                    self._event_bus.add_event_listener(
                        event_type="input",
                        entity_id=id,
                        listener_id=f"oled_{screen}",
                        target=self._input_callback,
                    )
            return _draw, _register
        # Default fallback — system info screens (cpu / memory / disk / …)
        def _draw(draw):
            self._draw_standard(data, draw)
        def _register():
            self._event_bus.add_event_listener(
                event_type="host",
                entity_id=f"{screen}_hoststats",
                listener_id=f"oled_{screen}",
                target=self._standard_callback,
            )
        return _draw, _register

    def _update_display(self) -> None:
        """Update OLED display without re-registering listeners.

        Periodic / event-driven refresh — dropping a frame on transient i2c
        contention beats killing the loop. Uses ``_safe_draw`` so EAGAIN /
        ETIMEDOUT / EREMOTEIO get retried with backoff and only escalate to
        a warning if all retries fail.
        """
        if self._sleep:
            return

        data = self._host_data.get(self._current_screen)
        if not data:
            return

        if self._current_screen == "web":
            try:
                self._draw_qr_code(url=str(data))
            except Exception as e:  # noqa: BLE001
                _LOGGER.error("Failed to update OLED QR display: %s", e)
            return

        if not isinstance(data, dict):
            return

        def _do_draw(draw: ImageDrawType) -> None:
            if self._grouped_outputs_by_expander and self._current_screen in self._grouped_outputs_by_expander:
                self._draw_output(data, draw)
            elif self._current_screen == UPTIME:
                self._draw_uptime(draw)
            elif self._input_groups and self._current_screen in self._input_groups:
                self._draw_input(data, draw)
            else:
                self._draw_standard(data, draw)

        self._safe_draw(_do_draw, label="_update_display")

    def _draw_standard(self, data: dict, draw: ImageDrawType) -> None:
        """Draw standard information about host screen."""
        draw.text(
            (1, 1),
            self._current_screen.replace("_", " ").capitalize(),
            font=fonts["big"],
            fill=WHITE,
        )
        row_no = START_ROW
        for k in data:
            draw.text(
                (3, row_no),
                f"{k} {data[k]}",
                font=fonts["small"],
                fill=WHITE,
            )
            row_no += 15

    def _draw_uptime(self, draw: ImageDrawType) -> None:
        """Draw uptime screen with boneIO logo."""
        uptime_data = self._host_data.get(UPTIME)

        if not isinstance(uptime_data, dict):
            # Fallback for simple string data
            draw.text((1, 1), "Uptime", font=fonts["big"], fill=WHITE)
            draw.text((3, START_ROW), str(uptime_data), font=fonts["small"], fill=WHITE)
            return

        # Draw boneIO logo at the top (split into two parts)
        draw.text((3, 3), "bone", font=fonts["danube"], fill=WHITE)
        draw.text((53, 3), "iO", font=fonts["danube"], fill=WHITE)

        # Check if data follows the format with position info
        if all(isinstance(v, dict) and "data" in v for v in uptime_data.values()):
            for k in uptime_data:
                text = uptime_data[k]["data"]
                font_size_key = uptime_data[k]["fontSize"]
                font_to_use = fonts.get(font_size_key, fonts["small"])
                col = uptime_data[k]["col"]
                row = uptime_data[k]["row"]

                # Use UPTIME_ROWS for Y positioning
                y_position = UPTIME_ROWS[row] if row < len(UPTIME_ROWS) else 22 + row * 10

                # Display as "key: value" format
                draw.text(
                    (col, y_position),
                    f"{k}: {text}",
                    font=font_to_use,
                    fill=WHITE,
                )
        else:
            # Old format - simple key-value pairs
            row_no = START_ROW
            for key, value in uptime_data.items():
                draw.text(
                    (3, row_no),
                    f"{key}: {value}",
                    font=fonts["small"],
                    fill=WHITE,
                )
                row_no += 15

    def start_sleep_timer(self) -> None:
        """Start sleep timer."""
        if self._cancel_sleep_handle:
            self._cancel_sleep_handle()

        self._cancel_sleep_handle = async_track_point_in_time(
            loop=asyncio.get_running_loop(),
            job=self._sleep_callback,
            point_in_time=utcnow() + self._sleep_timeout.as_timedelta,
        )

    async def _sleep_callback(self, timestamp) -> None:
        """Sleep callback — fade the screen to black after inactivity.

        Used to use a raw locked_canvas write; that threw uncaught
        OSError(121) when fired right during boot-time i2c contention and
        left the asyncio task's exception unretrieved (loud journal noise).
        Routing through _safe_draw retries and demotes the failure to a
        warning — losing the sleep-blank is a cosmetic miss, not a crash.
        """
        self._sleep = True
        self._cancel_sleep_handle = None
        self._safe_draw(
            lambda draw: draw.rectangle(self._device.bounding_box, outline="black", fill="black"),
            label="_sleep_callback",
        )
        _LOGGER.debug("OLED display sleeping")

    def wake_up(self) -> None:
        """Wake up display and restart sleep timer."""
        self._sleep = False
        if self._cancel_sleep_handle:
            self._cancel_sleep_handle()
            self._cancel_sleep_handle = None
        # Use render_display() (not _update_display) so the sleep timer
        # is restarted.  Previously _update_display() was used, which
        # never schedules start_sleep_timer() — causing the screen to
        # stay on forever after a single-click wake-up.
        self.render_display()

    def shutdown(self) -> None:
        """Shutdown OLED display."""
        if self._cancel_sleep_handle:
            self._cancel_sleep_handle()
        # Clear display
        try:
            with self._locked_canvas() as draw:
                draw.rectangle([0, 0, 127, 63], outline=0, fill=0)
        except Exception as e:
            _LOGGER.error(f"Failed to shutdown OLED display: {e}")
