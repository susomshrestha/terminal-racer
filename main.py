import curses

def main(stdscr):
  stdscr.clear()

  curses.curs_set(0)

  stdscr.addstr(5, 10, 'Hello dummy', curses.A_BOLD)
  stdscr.refresh()

  stdscr.getch()



curses.wrapper(main)