import curses
import time
from curses import textpad
from typing import Optional

# Layout
BORDER = 1  # rows/columns taken by the outer box on each side
HUD_HEIGHT = 3  # rows used by the HUD box (top edge, text row, bottom edge)
ROAD_HALF_WIDTH = 4  # distance from the road center to each border
MARKING_GAP = 4  # rows between lane markings

# Characters
MARKING_CHAR = "|"
PLAYER_CHAR = "A"

# Colors
ROAD_COLOR_PAIR = 1

# Timing
FRAME_DELAY = 0.033  # seconds between frames (~30 FPS)

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


def main(stdscr: curses.window):
    """Run the game loop: read input, update state, draw, repeat."""
    setup_curses(stdscr)

    height, width = stdscr.getmaxyx()
    center, road_top, road_bottom = compute_layout(height, width)

    car_lane = LEFT_LANE
    is_game_running = True

    while is_game_running:
        command = read_command(stdscr)

        if command == CMD_QUIT:
            is_game_running = False
        else:
            car_lane = move_car(car_lane, command)

        draw_frame(stdscr, width, center, road_top, road_bottom, car_lane)
        time.sleep(FRAME_DELAY)


def setup_curses(stdscr: curses.window):
    """Configure options that curses.wrapper does not already set."""
    # wrapper() has already enabled cbreak mode, the keypad and basic colors.
    curses.curs_set(0)
    curses.use_default_colors()
    curses.init_pair(ROAD_COLOR_PAIR, curses.COLOR_YELLOW, -1)
    stdscr.nodelay(True)  # getch() returns immediately instead of waiting


def compute_layout(height: int, width: int) -> tuple[int, int, int]:
    """Return the road's center column, first row and last row."""
    center = width // 2
    road_top = BORDER + HUD_HEIGHT  # first row below the HUD
    road_bottom = height - BORDER - 1  # last usable row above the outer box
    return center, road_top, road_bottom


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


def lane_to_column(lane: int, center: int) -> int:
    """Convert a lane number into a screen column."""
    offset = ROAD_HALF_WIDTH // 2
    if lane == LEFT_LANE:
        return center - offset
    return center + offset


def format_time(total_seconds: int) -> str:
    """Convert a number of seconds into an HH:MM:SS string."""
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def draw_frame(
    stdscr: curses.window,
    width: int,
    center: int,
    road_top: int,
    road_bottom: int,
    car_lane: int,
):
    """Redraw the whole screen from the current game state."""
    stdscr.erase()
    stdscr.box()
    draw_hud(stdscr, width)
    draw_road_borders(stdscr, road_top, road_bottom, center)
    draw_lane_markings(stdscr, road_top, road_bottom, center)
    draw_car(stdscr, road_bottom, lane_to_column(car_lane, center))
    stdscr.refresh()


def draw_hud(
    stdscr: curses.window,
    width: int,
    score: int = 0,
    elapsed_seconds: int = 0,
    speed: int = 0,
):
    """Draw the boxed status bar showing score, time and speed."""
    top = BORDER
    bottom = BORDER + HUD_HEIGHT - 1
    left = BORDER
    right = width - 1 - BORDER
    textpad.rectangle(stdscr, top, left, bottom, right)

    inner_width = width - 2 * BORDER
    text_row = top + 1
    score_text = f"Score: {score}"
    time_text = f"Time: {format_time(elapsed_seconds)}"
    speed_text = f"Speed: {speed:02d}"

    stdscr.addstr(text_row, left + 2, score_text)
    stdscr.addstr(text_row, left + (inner_width - len(time_text)) // 2, time_text)
    stdscr.addstr(text_row, left + inner_width - 2 - len(speed_text), speed_text)


def draw_road_borders(stdscr: curses.window, top: int, bottom: int, center: int):
    """Draw the left and right edges of the road."""
    length = bottom - top + 1
    for column in (center - ROAD_HALF_WIDTH, center + ROAD_HALF_WIDTH):
        stdscr.vline(
            top,
            column,
            curses.ACS_VLINE,
            length,
            curses.color_pair(ROAD_COLOR_PAIR),
        )


def draw_lane_markings(stdscr: curses.window, top: int, bottom: int, center: int):
    """Draw the dashed line down the middle of the road."""
    for row in range(top, bottom + 1, MARKING_GAP):
        stdscr.addstr(row, center, MARKING_CHAR)


def draw_car(stdscr: curses.window, row: int, column: int):
    """Draw the player car at the given position."""
    stdscr.addstr(row, column, PLAYER_CHAR)


if __name__ == "__main__":
    curses.wrapper(main)
