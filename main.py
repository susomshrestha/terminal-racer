import curses
import math
import time
from curses import textpad
from dataclasses import dataclass, field
from typing import Optional

# Layout
BORDER = 1  # rows/columns taken by the outer box on each side
HUD_HEIGHT = 3  # rows used by the HUD box (top edge, text row, bottom edge)
ROAD_HALF_WIDTH = 4  # distance from the road center to each border
MARKING_GAP = 4  # rows in one repeat of the road pattern

# Characters
PLAYER_CHAR = "A"
ENEMY_CHAR = "V"

# Row-template placeholders: stand-ins that the draw step translates
# into what actually appears on screen (and in which color).
EMPTY_CHAR = "."
BORDER_CHAR = "#"
DIVIDER_CHAR = "|"

# What an unknown placeholder looks like: a blank with no color.
DEFAULT_CELL = (" ", 0)

# Colors
ROAD_COLOR_PAIR = 1

# Timing
TARGET_FPS = 30  # frames per second the loop aims for
FRAME_TIME = 1 / TARGET_FPS  # seconds each frame should take
MAX_FRAME_DELTA = 0.1  # seconds; caps elapsed time so a stall can't teleport objects

# Speed progression
INITIAL_SPEED = 6.0  # rows per second at the start
MAX_SPEED = 18.0  # rows per second, the cap
SPEED_INTERVAL = 5.0  # seconds between speed increases
SPEED_INCREASE_AMOUNT = 1.0  # rows per second added at each increase

# Enemies
ENEMY_START_ROW = -1.0  # road row where new enemies appear (one row above the road)

# Lanes
LEFT_LANE = 0
RIGHT_LANE = 1

# Commands (what the player wants to do, independent of which key they pressed)
CMD_LEFT = "left"
CMD_RIGHT = "right"
CMD_QUIT = "quit"

KEY_COMMANDS = {
    curses.KEY_LEFT: CMD_LEFT,
    ord("a"): CMD_LEFT,
    ord("A"): CMD_LEFT,
    curses.KEY_RIGHT: CMD_RIGHT,
    ord("d"): CMD_RIGHT,
    ord("D"): CMD_RIGHT,
    ord("q"): CMD_QUIT,
    ord("Q"): CMD_QUIT,
}


def build_row_template(middle: str) -> str:
    """Build one road row: a border, a gap, the middle character, a gap, a border."""
    gap = EMPTY_CHAR * (ROAD_HALF_WIDTH - 1)
    return BORDER_CHAR + gap + middle + gap + BORDER_CHAR


ROW_TEMPLATES = [build_row_template(DIVIDER_CHAR)] + [
    build_row_template(EMPTY_CHAR) for _ in range(MARKING_GAP - 1)
]


@dataclass(frozen=True)
class Layout:
    width: int
    center: int
    road_top: int
    road_bottom: int

    @property
    def road_height(self) -> int:
        """Number of road rows. Road rows are numbered 0 to road_height - 1."""
        return self.road_bottom - self.road_top + 1

    @property
    def player_row(self) -> int:
        """The player's row in road rows: the last row of the road."""
        return self.road_height - 1


@dataclass
class Enemy:
    """One enemy car."""

    lane: int  # LEFT_LANE or RIGHT_LANE
    row: float  # road row: 0.0 is the first road row, and it grows downward
    extra_speed: float = (
        0.0  # rows per second on top of the road speed (used from M4-4)
    )


@dataclass
class GameState:
    """Everything that changes while the game runs."""

    car_lane: int = LEFT_LANE
    offset: int = 0  # whole rows the road has scrolled
    speed: float = INITIAL_SPEED  # rows per second
    fractional_movement: float = (
        0.0  # leftover part of a row, carried to the next frame
    )
    elapsed_seconds: int = 0  # whole seconds since the game started
    start_time: float = 0.0
    previous_update_time: float = 0.0
    next_speed_increase: float = 0.0
    # Each GameState needs its own list, so the default comes from a factory.
    enemies: list[Enemy] = field(default_factory=list)


def main(stdscr: curses.window) -> tuple[list[float], list[float]]:
    """Run the game loop with elapsed-time movement and deadline scheduling.

    Returns:
        A tuple containing frame-start intervals and frame work durations,
        both measured in seconds.
        TEMPORARY enemies and layout
    """
    setup_curses(stdscr)

    height, width = stdscr.getmaxyx()
    layout = compute_layout(height, width)
    cell_styles = build_road_dict()

    start_time = time.perf_counter()
    state = GameState(
        start_time=start_time,
        previous_update_time=start_time,
        next_speed_increase=start_time + SPEED_INTERVAL,
    )

    # TEMPORARY (M4-3): two hand-placed enemy to test drawing.
    # Replaced by random spawning in M4-6.
    state.enemies.append(create_enemy(RIGHT_LANE, row=5.0))
    state.enemies.append(create_enemy(LEFT_LANE, row=10.0))

    frame_times: list[float] = []
    work_times: list[float] = []

    next_frame_deadline = start_time + FRAME_TIME
    previous_frame_start = None

    while True:
        frame_start = time.perf_counter()

        command = read_command(stdscr)
        if command == CMD_QUIT:
            break

        update_game(state, command, frame_start, layout)
        draw_frame(stdscr, layout, cell_styles, state)

        work_time = time.perf_counter() - frame_start

        # Wait until the scheduled deadline, if time remains.
        remaining_time = next_frame_deadline - time.perf_counter()
        if remaining_time > 0:
            time.sleep(remaining_time)

        frame_end = time.perf_counter()

        # Record actual intervals between frame starts.
        if previous_frame_start is not None:
            frame_times.append(frame_start - previous_frame_start)
        previous_frame_start = frame_start

        work_times.append(work_time)

        # Advance the absolute deadline.
        next_frame_deadline += FRAME_TIME

        # Skip obsolete deadlines after an overrun.
        if frame_end >= next_frame_deadline:
            missed_periods = int((frame_end - next_frame_deadline) // FRAME_TIME) + 1
            next_frame_deadline += missed_periods * FRAME_TIME

    return frame_times, work_times, state.enemies, layout


def setup_curses(stdscr: curses.window):
    """Configure options that curses.wrapper does not already set."""
    # wrapper() has already enabled cbreak mode, the keypad and basic colors.
    curses.curs_set(0)
    curses.use_default_colors()
    curses.init_pair(ROAD_COLOR_PAIR, curses.COLOR_YELLOW, -1)
    stdscr.nodelay(True)  # getch() returns immediately instead of waiting


def compute_layout(height: int, width: int) -> Layout:
    """Work out where the road sits on a terminal of the given size."""
    return Layout(
        width=width,
        center=width // 2,
        road_top=BORDER + HUD_HEIGHT,  # first row below the HUD
        road_bottom=height - BORDER - 1,  # last usable row above the outer box
    )


def build_road_dict() -> dict:
    """Map each template placeholder to (character to draw, attributes)."""
    return {
        BORDER_CHAR: (curses.ACS_VLINE, curses.color_pair(ROAD_COLOR_PAIR)),
        DIVIDER_CHAR: (DIVIDER_CHAR, 0),  # drawn as itself, default color
        EMPTY_CHAR: (" ", 0),
    }


# ---------- Input and game state (no drawing here) ----------


def read_command(stdscr: curses.window) -> Optional[str]:
    """Return the command for the pressed key, or None if there isn't one."""
    key = stdscr.getch()  # -1 when no key is pressed
    return KEY_COMMANDS.get(key)


def move_car(lane: int, command: Optional[str]) -> int:
    """Return the car's new lane, never leaving the road."""
    if command == CMD_LEFT:
        return max(LEFT_LANE, lane - 1)
    if command == CMD_RIGHT:
        return min(RIGHT_LANE, lane + 1)
    return lane


def create_enemy(lane: int, row: float = ENEMY_START_ROW) -> Enemy:
    """Return a new enemy in the given lane, by default just above the road."""
    return Enemy(lane=lane, row=row)


def update_enemies(
    enemies: list[Enemy], road_speed: float, elapsed_time: float
) -> None:
    """Move every enemy down the road, changing the enemies in place."""
    for enemy in enemies:
        enemy.row += (road_speed + enemy.extra_speed) * elapsed_time


def remove_enemies(enemies: list[Enemy], road_height: int) -> list[Enemy]:
    """Return only the enemies that have not left the bottom of the road.

    Road rows run from 0 to road_height - 1, so an enemy is gone once row >= road_height.
    """
    return [enemy for enemy in enemies if enemy.row < road_height]


def update_game(
    state: GameState, command: Optional[str], now: float, layout: Layout
) -> None:
    """Advance the game by one frame, changing `state` in place.

    In order: record the elapsed time, raise the speed if an increase is due,
    move the car, then scroll the road by speed * elapsed time. Any leftover
    fraction of a row is carried over to the next frame.
    """
    elapsed_time = min(now - state.previous_update_time, MAX_FRAME_DELTA)
    state.previous_update_time = now
    state.elapsed_seconds = int(now - state.start_time)

    while now >= state.next_speed_increase and state.speed < MAX_SPEED:
        state.speed = min(state.speed + SPEED_INCREASE_AMOUNT, MAX_SPEED)
        state.next_speed_increase += SPEED_INTERVAL

    state.car_lane = move_car(state.car_lane, command)

    state.fractional_movement += state.speed * elapsed_time
    whole_rows = int(state.fractional_movement)
    state.offset += whole_rows
    state.fractional_movement -= whole_rows

    update_enemies(state.enemies, state.speed, elapsed_time)
    state.enemies = remove_enemies(state.enemies, layout.road_height)


def speed_to_level(speed: float) -> int:
    """Convert speed in rows per second into the level shown in the HUD.

    Level 1 is the starting speed, and each extra row per second is one more level.
    """
    return int(speed - INITIAL_SPEED) + 1


def get_row_template(screen_row: int, road_top: int, offset: int) -> str:
    """Return the template that a screen row should display at this offset."""
    row_in_road = screen_row - road_top
    shifted_row = row_in_road - offset
    index = shifted_row % len(ROW_TEMPLATES)
    return ROW_TEMPLATES[index]


def lane_to_column(lane: int, center: int) -> int:
    """Convert a lane number into a screen column."""
    lane_shift = ROAD_HALF_WIDTH // 2
    if lane == LEFT_LANE:
        return center - lane_shift
    return center + lane_shift


def road_row_to_screen_row(road_row: float, layout: Layout) -> Optional[int]:
    """Convert a road row to a screen row, or None if it is not on the road.

    Uses floor, not int(): int() rounds toward zero, which would turn -0.5
    into row 0 and draw an enemy that is still above the road.
    """
    screen_row = math.floor(road_row) + layout.road_top
    if layout.road_top <= screen_row <= layout.road_bottom:
        return screen_row
    return None


def format_time(total_seconds: int) -> str:
    """Convert a number of seconds into an HH:MM:SS string."""
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


# ---------- Drawing (reads state, never changes it) ----------


def draw_frame(
    stdscr: curses.window,
    layout: Layout,
    cell_styles: dict,
    state: GameState,
) -> None:
    """Redraw the whole screen from the current state."""
    stdscr.erase()
    stdscr.box()

    draw_hud(
        stdscr,
        layout.width,
        elapsed_seconds=state.elapsed_seconds,
        speed_level=speed_to_level(state.speed),
    )
    draw_road(stdscr, layout, state.offset, cell_styles)
    draw_enemies(stdscr, state.enemies, layout)
    draw_car(stdscr, layout, state.car_lane)

    stdscr.refresh()


def draw_cell(
    stdscr: curses.window,
    row: int,
    column: int,
    placeholder: str,
    cell_styles: dict,
):
    """Draw one template cell using the character and attributes from the dictionary."""
    char, attributes = cell_styles.get(placeholder, DEFAULT_CELL)
    stdscr.addch(row, column, char, attributes)


def draw_template_row(
    stdscr: curses.window,
    row: int,
    start_column: int,
    template: str,
    cell_styles: dict,
):
    """Draw every cell of one template, left to right, starting at start_column."""
    for position, placeholder in enumerate(template):
        draw_cell(stdscr, row, start_column + position, placeholder, cell_styles)


def draw_road(
    stdscr: curses.window,
    layout: Layout,
    offset: int,
    cell_styles: dict,
):
    """Draw every road row using the template that the scroll offset selects."""
    left_column = layout.center - ROAD_HALF_WIDTH
    for row in range(layout.road_top, layout.road_bottom + 1):
        template = get_row_template(row, layout.road_top, offset)
        draw_template_row(stdscr, row, left_column, template, cell_styles)


def draw_enemies(stdscr: curses.window, enemies: list[Enemy], layout: Layout):
    """Draw every enemy that is currently on the road."""
    for enemy in enemies:
        screen_row = road_row_to_screen_row(enemy.row, layout)
        if screen_row is None:
            continue  # above or below the road: nothing to draw
        column = lane_to_column(enemy.lane, layout.center)
        stdscr.addstr(screen_row, column, ENEMY_CHAR)


def draw_hud(
    stdscr: curses.window,
    width: int,
    score: int = 0,
    elapsed_seconds: int = 0,
    speed_level: int = 1,
):
    """Draw the boxed status bar showing score, time and speed level."""
    top = BORDER
    bottom = BORDER + HUD_HEIGHT - 1
    left = BORDER
    right = width - 1 - BORDER
    textpad.rectangle(stdscr, top, left, bottom, right)

    inner_width = width - 2 * BORDER
    text_row = top + 1
    score_text = f"Score: {score}"
    time_text = f"Time: {format_time(elapsed_seconds)}"
    speed_text = f"Speed: {speed_level:02d}"

    stdscr.addstr(text_row, left + 2, score_text)
    stdscr.addstr(text_row, left + (inner_width - len(time_text)) // 2, time_text)
    stdscr.addstr(text_row, left + inner_width - 2 - len(speed_text), speed_text)


def draw_car(stdscr: curses.window, layout: Layout, lane: int) -> None:
    """Draw the player car in its lane, on the player's road row."""
    screen_row = road_row_to_screen_row(layout.player_row, layout)
    if screen_row is None:
        return
    stdscr.addstr(screen_row, lane_to_column(lane, layout.center), PLAYER_CHAR)


# ---------- Profiling ----------


def print_performance_summary(
    frame_times: list[float],
    work_times: list[float],
):
    """Print frame-interval and work-duration statistics."""
    total_frames = len(work_times)
    total_intervals = len(frame_times)

    if total_frames == 0:
        print("No frames were recorded.")
        return

    avg_work_time = sum(work_times) / total_frames
    slowest_work = max(work_times)

    print("\n" + "=" * 40)
    print("         PERFORMANCE SUMMARY          ")
    print("=" * 40)
    print(f"Target Frame Rate     : {TARGET_FPS} FPS")
    print(f"Total Frames Profiled : {total_frames}")
    print(f"Frame Intervals       : {total_intervals}")
    print(f"Average Work Time     : {avg_work_time * 1000:.2f} ms")
    print(f"Slowest Work Time     : {slowest_work * 1000:.2f} ms")

    if total_intervals:
        avg_frame_time = sum(frame_times) / total_intervals
        slowest_frame = max(frame_times)
        implied_fps = 1.0 / avg_frame_time

        print(f"Average Frame Interval: {avg_frame_time * 1000:.2f} ms")
        print(f"Slowest Frame Interval: {slowest_frame * 1000:.2f} ms")
        print(f"Implied Frame Rate    : {implied_fps:.2f} FPS")
    else:
        print("No frame intervals available.")

    print("=" * 40)


if __name__ == "__main__":
    frame_times, work_times, enemies, layout = curses.wrapper(main)
    print("=" * 40)
    print(layout)
    print(enemies)
    print("=" * 40)
    print_performance_summary(frame_times, work_times)
