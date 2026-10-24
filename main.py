import curses

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


def main(stdscr: curses.window):
    """Draw the static road screen and wait for a keypress."""
    setup_curses()
    stdscr.erase()
    stdscr.box()

    height, width = stdscr.getmaxyx()
    center = width // 2
    road_top = BORDER + HUD_HEIGHT  # first row below the HUD
    road_bottom = height - BORDER - 1  # last usable row above the outer box

    draw_hud(stdscr, width)
    draw_road_borders(stdscr, road_top, road_bottom, center)
    draw_lane_markings(stdscr, road_top, road_bottom, center)
    draw_car(stdscr, road_bottom, center)

    stdscr.refresh()
    stdscr.getch()


def setup_curses():
    """Hide the cursor and define the color pairs used by the game."""
    curses.curs_set(0)
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(ROAD_COLOR_PAIR, curses.COLOR_YELLOW, -1)


def format_time(total_seconds: int) -> str:
    """Convert a number of seconds into an HH:MM:SS string."""
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def draw_hud(
    stdscr: curses.window,
    width: int,
    score: int = 0,
    elapsed_seconds: int = 0,
    speed: int = 0,
):
    """Draw the boxed status bar showing score, time and speed."""
    hud = stdscr.derwin(HUD_HEIGHT, width - 2 * BORDER, BORDER, BORDER)
    hud.box()
    hud_width = hud.getmaxyx()[1]
    text_row = 1

    score_text = f"Score: {score}"
    time_text = f"Time: {format_time(elapsed_seconds)}"
    speed_text = f"Speed: {speed:02d}"

    hud.addstr(text_row, 2, score_text)
    hud.addstr(text_row, (hud_width - len(time_text)) // 2, time_text)
    hud.addstr(text_row, hud_width - 2 - len(speed_text), speed_text)


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


def draw_car(stdscr: curses.window, bottom: int, center: int):
    """Draw the player car in the middle of the left lane."""
    column = center - ROAD_HALF_WIDTH // 2
    stdscr.addstr(bottom, column, PLAYER_CHAR)


if __name__ == "__main__":
    curses.wrapper(main)
