import board
import analogio
import digitalio
import fourwire
import adafruit_ili9341
import displayio
import time
import random

from adafruit_display_shapes.rect import Rect
from adafruit_display_shapes.circle import Circle
from adafruit_display_text import label
import terminalio

# Button A for restart (active-low with internal pull-up)
btn_a = digitalio.DigitalInOut(board.GPIO32)
btn_a.switch_to_input(pull=digitalio.Pull.UP)

# Fisher–Yates shuffle for in-place randomization
def shuffle_list(lst):
    for i in range(len(lst) - 1, 0, -1):
        j = random.randint(0, i)
        lst[i], lst[j] = lst[j], lst[i]

# Read direction from the analog joystick on GPIO34/35
pad_lr = analogio.AnalogIn(board.GPIO34)
pad_ud = analogio.AnalogIn(board.GPIO35)
def read_direction():
    dx = dy = 0
    lr, ud = pad_lr.value, pad_ud.value
    # Simple thresholding; tune for your hardware as needed
    if lr > 60000:                dx = -1
    elif 30000 < lr < 40000:      dx = 1
    if ud > 60000:                dy = -1
    elif 30000 < ud < 40000:      dy = 1
    return dx, dy

# Maze layout and rendering unit
CELL = 20

MAZE = [
    "XXXXXXXXXXXXX",
    "X...........X",
    "X.XXX.X.XXX.X",
    "X.X.......X.X",
    "X.X.XXX.X.X.X",
    "X...X...X...X",
    "XXX.X.X.X.XXX",
    "X.....X.....X",
    "X.XXX.X.XXX.X",
    "X...........X",
    "X...........X",
    "XXXXXXXXXXXXX"
]

# Ghost palette (RGB 0xRRGGBB)
GHOST_COLORS = [0xFF0000, 0x00FF00, 0xFF00FF]

# Initial ghost spawn positions (grid coordinates)
GHOST_STARTS = [(11, 1), (11, 10), (1, 10)]

def init_display():
    # Initialize the ILI9341 display over 4-wire SPI
    displayio.release_displays()
    bus = fourwire.FourWire(
        board.SPI(),
        command=board.LCD_DC,
        chip_select=board.LCD_CS,
        reset=None
    )
    disp = adafruit_ili9341.ILI9341(bus, width=320, height=240)
    disp.rotation = 180  # Rotate to match the device orientation (landscape)
    return disp

def init_game(disp):
    # Create a fresh scene graph for a new round
    root = displayio.Group()
    disp.root_group = root

    # Draw walls and place collectible dots
    dots = {}
    for y, row in enumerate(MAZE):
        for x, ch in enumerate(row):
            px, py = x * CELL, y * CELL
            if ch == "X":
                # Wall cell
                root.append(Rect(px, py, CELL, CELL, fill=0x0000FF))
            elif ch == ".":
                # Collectible dot
                dot = Circle(px + CELL // 2, py + CELL // 2, 3, fill=0xFFFF00)
                dots[(x, y)] = dot
                root.append(dot)

    # Spawn Pac-Man
    pac = {
        "pos": [1, 1],
        "shape": Circle(
            1 * CELL + CELL // 2,
            1 * CELL + CELL // 2,
            CELL // 2 - 2,
            fill=0xFFFF00
        )
    }
    root.append(pac["shape"])

    # Spawn ghosts
    ghosts = []
    for idx, (gx, gy) in enumerate(GHOST_STARTS):
        gshape = Circle(
            gx * CELL + CELL // 2,
            gy * CELL + CELL // 2,
            CELL // 2 - 2,
            fill=GHOST_COLORS[idx]
        )
        ghosts.append({"pos": [gx, gy], "shape": gshape})
        root.append(gshape)

    return root, dots, pac, ghosts

def show_message(disp, text):
    # Replace the scene with a message overlay (e.g., WIN/LOSE)
    grp = displayio.Group()
    lbl = label.Label(
        terminalio.FONT,
        text=text,
        color=0xFFFFFF,
        x=80,
        y=disp.height // 2 - 8
    )
    grp.append(lbl)
    disp.root_group = grp

def wait_for_button():
    # Wait for Button A press (value goes False when pressed)
    while btn_a.value:
        time.sleep(0.05)

# --- MAIN LOOP ---
display = init_display()

while True:
    root, dots, pac, ghosts = init_game(display)
    score = 0
    playing = True

    # Core gameplay loop
    while playing:
        dx, dy = read_direction()
        nx = pac["pos"][0] + dx
        ny = pac["pos"][1] + dy

        # Move Pac-Man if the next cell is not a wall
        if MAZE[ny][nx] != "X":
            pac["pos"] = [nx, ny]
            pac["shape"].x = nx * CELL + CELL // 2
            pac["shape"].y = ny * CELL + CELL // 2

            # Eat a dot if present
            if (nx, ny) in dots:
                root.remove(dots.pop((nx, ny)))
                score += 1

                # Win condition: all dots eaten
                if not dots:
                    show_message(display, "YOU WIN!")
                    playing = False
                    break

        # Move ghosts with a randomized valid direction each step
        for g in ghosts:
            dirs = [(1, 0), (-1, 0), (0, 1), (0, -1)]
            shuffle_list(dirs)
            for mx, my in dirs:
                gx, gy = g["pos"]
                if MAZE[gy + my][gx + mx] != "X":
                    g["pos"] = [gx + mx, gy + my]
                    g["shape"].x = (gx + mx) * CELL + CELL // 2
                    g["shape"].y = (gy + my) * CELL + CELL // 2
                    break

        # Collision detection: Pac-Man meets a ghost
        for g in ghosts:
            if pac["pos"] == g["pos"]:
                show_message(display, "GAME OVER")
                playing = False
                break

        # Step delay to control game speed
        time.sleep(0.15)

    # After the round ends, wait for Button A to restart
    wait_for_button()
    # Then continue the outer while True → start a new game round
