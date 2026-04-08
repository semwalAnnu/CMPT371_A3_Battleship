import tkinter as tk
import math

from game_logic import BOARD_SIZE, EMPTY, SHIP, HIT, MISS

# ---- Color palette: deep navy / military tactical HUD ----
BG         = "#000000"     # near-black navy background
PANEL      = "#0B1A2E"     # raised panel surfaces
GRID_BG    = "#071422"     # grid background
HEADER_BG  = "#040C18"     # top bar bg

CELL_EMPTY = "#0D2035"     # empty water cell
CELL_SHIP  = "#1A5276"     # placed ship (dark teal)
CELL_HIT   = "#C0392B"     # confirmed hit
CELL_MISS  = "#2C3E50"     # confirmed miss
CELL_HOVER = "#1A3A5C"     # hover highlight on enemy grid
CELL_BAD   = "#7B241C"     # invalid placement preview

ACCENT     = "#00B4D8"     # electric cyan - main accent
ACCENT_DIM = "#004E62"     # dimmed cyan for subtle elements
DANGER     = "#E74C3C"     # red for errors / defeat
SUCCESS    = "#00B894"     # teal-green for success / victory
WARNING    = "#F39C12"     # amber for waiting states

TEXT       = "#B8E3F5"     # primary text (light blue-white)
TEXT_BRIGHT = "#E8F8FF"    # bright white-blue for emphasis
TEXT_DIM   = "#3D5A70"     # muted text
BORDER     = "#112233"     # subtle borders between cells

# ---- Layout constants ----
CELL_SIZE = 38    # grid cell size in pixels
GRID_OFF  = 28    # offset for row/col labels
WIN_W     = 1000  # default window width
WIN_H     = 600   # default window height

# ---- Font definitions ----
F_BTN    = ("Courier", 13, "bold")
F_HUGE   = ("Courier", 48, "bold")

# standard Battleship fleet in placement order
SHIPS = [
    ("Carrier",    5),
    ("Battleship", 4),
    ("Cruiser",    3),
    ("Submarine",  3),
    ("Destroyer",  2),
]


class BattleshipGUI:
    """
    Manages all screens for the Battleship game:
      start -> connect -> waiting -> placement -> battle -> (game over overlay)

    client.py wires up callbacks:
      gui.on_connect(ip, port)
      gui.on_ships_placed(ship_list)
      gui.on_fire(row, col)

    client.py calls to drive UI:
      set_connected(player_num), start_placement(), start_game(my_turn),
      update_my_board(), update_enemy_board(), set_turn(), show_game_over()
    """

    def __init__(self, root):
        self.root = root
        self.root.title("BATTLESHIP")
        self.root.configure(bg=BG)
        self.root.resizable(True, True)
        self.root.geometry(f"{WIN_W}x{WIN_H}")
        self.root.minsize(WIN_W, WIN_H)

        # ---- game state ----
        self.my_board     = [[EMPTY] * BOARD_SIZE for _ in range(BOARD_SIZE)]
        self.enemy_board  = [[EMPTY] * BOARD_SIZE for _ in range(BOARD_SIZE)]
        self.is_my_turn   = False
        self.game_active  = False
        self.placing      = True
        self.ship_idx     = 0
        self.orientation  = "H"
        self.preview      = []
        self.placed_ships = []
        self.hit_count    = 0
        self.miss_count   = 0

        # ---- animation state ----
        self.radar_angle  = 0
        self._anim_id     = None
        self._dot_id      = None
        self._pulse_id    = None    # for pulsing turn indicator
        self._dot_count   = 0
        self._radar_cx    = WIN_W // 2    # current radar center (updates on resize)
        self._radar_cy    = WIN_H // 2 - 30

        # ---- callbacks set by client.py ----
        self.on_connect      = None
        self.on_ships_placed = None
        self.on_fire         = None

        self._current = None
        self._screens = {}
        self._build_all()
        self._show("start")

    def _build_all(self):
        self._build_start()
        self._build_connect()
        self._build_waiting()
        self._build_placement()
        self._build_battle()

    # switches visible screen and manages animations
    def _show(self, name):
        if self._current:
            self._current.pack_forget()
        self._screens[name].pack(fill="both", expand=True)
        self._current = self._screens[name]
        self._cancel_animations()

        if name == "start":
            self.radar_angle = 0
            self._animate_radar()
            self.root.after(200, self._typewriter_title)
        elif name == "waiting":
            self._animate_dots()
        elif name == "battle":
            self._pulse_turn()

    def _cancel_animations(self):
        for aid in (self._anim_id, self._dot_id, self._pulse_id):
            if aid:
                self.root.after_cancel(aid)
        self._anim_id = self._dot_id = self._pulse_id = None

    # ==========================================================
    # START SCREEN  — animated radar + typewriter title
    # ==========================================================

    def _build_start(self):
        frame = tk.Frame(self.root, bg=BG)
        self._screens["start"] = frame

        # canvas fills the entire window
        self.rc = tk.Canvas(frame, bg=BG, highlightthickness=0)
        self.rc.pack(fill="both", expand=True)

        cx, cy = self._radar_cx, self._radar_cy

        # ---- static radar elements (all drawn relative to center) ----
        for radius in [90, 160, 230, 300]:
            self.rc.create_oval(cx - radius, cy - radius, cx + radius, cy + radius,
                                outline=ACCENT_DIM, width=1)

        # crosshair lines
        self.rc.create_line(cx - 310, cy, cx + 310, cy, fill=ACCENT_DIM, width=1)
        self.rc.create_line(cx, cy - 310, cx, cy + 310, fill=ACCENT_DIM, width=1)

        # tick marks on rings
        for radius in [90, 160, 230, 300]:
            for angle in range(0, 360, 45):
                rad = math.radians(angle)
                x1 = cx + (radius - 5) * math.cos(rad)
                y1 = cy - (radius - 5) * math.sin(rad)
                x2 = cx + (radius + 5) * math.cos(rad)
                y2 = cy - (radius + 5) * math.sin(rad)
                self.rc.create_line(x1, y1, x2, y2, fill=ACCENT_DIM, width=1)

        # center dot
        self.rc.create_oval(cx - 3, cy - 3, cx + 3, cy + 3, fill=ACCENT, outline="")

        # ---- animated sweep wedge + leading edge ----
        self.sweep_wedge = self.rc.create_arc(
            cx - 300, cy - 300, cx + 300, cy + 300,
            start=0, extent=40,
            fill=ACCENT_DIM, outline=""
        )
        self.sweep_line = self.rc.create_line(cx, cy, cx + 300, cy, fill=ACCENT, width=2)

        # ---- title (typewriter) and subtitle ----
        self.rc_title = self.rc.create_text(
            cx, cy - 40, text="", font=F_HUGE, fill=TEXT_BRIGHT
        )
        self.rc_sub = self.rc.create_text(
            cx, cy + 20, text="", font=("Courier", 12), fill=TEXT_DIM
        )

        # ---- ENGAGE button ----
        bx, by, bw, bh = cx, cy + 80, 180, 46
        self._sb_bg = self.rc.create_rectangle(
            bx - bw // 2, by - bh // 2, bx + bw // 2, by + bh // 2,
            fill=PANEL, outline=ACCENT, width=2
        )
        self._sb_txt = self.rc.create_text(bx, by, text="ENGAGE", font=F_BTN, fill=ACCENT)

        for tag in (self._sb_bg, self._sb_txt):
            self.rc.tag_bind(tag, "<Enter>",    lambda e: self._start_btn_hover(True))
            self.rc.tag_bind(tag, "<Leave>",    lambda e: self._start_btn_hover(False))
            self.rc.tag_bind(tag, "<Button-1>", lambda e: self._show("connect"))

        # footer text
        self.rc_footer = self.rc.create_text(
            cx, cy + 250,
            text="CMPT 371  ——  NETWORK PROGRAMMING  ——  2-PLAYER NAVAL WARFARE",
            font=("Courier", 9), fill=TEXT_DIM
        )

        # ---- bind resize to reposition all canvas items ----
        self.rc.bind("<Configure>", self._on_start_resize)

    # moves ALL canvas items so radar stays centered when window resizes
    def _on_start_resize(self, event):
        new_cx = event.width // 2
        new_cy = event.height // 2 - 30
        dx = new_cx - self._radar_cx
        dy = new_cy - self._radar_cy
        if dx != 0 or dy != 0:
            self.rc.move("all", dx, dy)
            self._radar_cx = new_cx
            self._radar_cy = new_cy

    def _start_btn_hover(self, on):
        if on:
            self.rc.itemconfig(self._sb_bg,  fill=ACCENT_DIM)
            self.rc.itemconfig(self._sb_txt, fill=TEXT_BRIGHT)
        else:
            self.rc.itemconfig(self._sb_bg,  fill=PANEL)
            self.rc.itemconfig(self._sb_txt, fill=ACCENT)

    # radar sweep animation loop (~40fps)
    def _animate_radar(self):
        cx, cy, r = self._radar_cx, self._radar_cy, 300
        self.radar_angle = (self.radar_angle + 2) % 360

        # update the arc wedge rotation
        self.rc.itemconfig(self.sweep_wedge, start=self.radar_angle)

        # update leading edge line endpoint
        rad = math.radians(self.radar_angle)
        ex = cx + r * math.cos(rad)
        ey = cy - r * math.sin(rad)
        self.rc.coords(self.sweep_line, cx, cy, ex, ey)

        self._anim_id = self.root.after(25, self._animate_radar)

    # typewriter effect for the title text
    def _typewriter_title(self, i=0):
        full = "BATTLESHIP"
        self.rc.itemconfig(self.rc_title, text=full[:i])
        if i < len(full):
            self.root.after(85, lambda: self._typewriter_title(i + 1))
        else:
            self.root.after(400, lambda: self.rc.itemconfig(
                self.rc_sub, text="NAVAL WARFARE SIMULATION  ——  TWO PLAYERS"
            ))

    # ==========================================================
    # CONNECT SCREEN  — IP / port entry form (centered)
    # ==========================================================

    def _build_connect(self):
        frame = tk.Frame(self.root, bg=BG)
        self._screens["connect"] = frame

        # centered wrapper so content stays in the middle on resize
        wrapper = tk.Frame(frame, bg=BG)
        wrapper.place(relx=0.5, rely=0.45, anchor="center")

        tk.Label(wrapper, text="CONNECT TO SERVER",
                 font=("Courier", 22, "bold"), fg=ACCENT, bg=BG).pack(pady=(0, 6))

        tk.Label(wrapper, text="Enter the server's IP address and port",
                 font=("Courier", 11), fg=TEXT_DIM, bg=BG).pack(pady=(0, 40))

        # form card
        card = tk.Frame(wrapper, bg=PANEL, padx=50, pady=32)
        card.pack()

        # IP field
        self.ip_var = tk.StringVar(value="127.0.0.1")
        self._make_field(card, "HOST IP ADDRESS", self.ip_var, width=22)

        # Port field
        self.port_var = tk.StringVar(value="5000")
        self._make_field(card, "PORT", self.port_var, width=22, top_pad=18)

        # CONNECT button
        btn = tk.Label(card, text="CONNECT", font=F_BTN,
                       fg=BG, bg=ACCENT, padx=28, pady=10, cursor="hand2")
        btn.pack(pady=(24, 0))
        btn.bind("<Enter>",    lambda e: btn.config(bg=TEXT_BRIGHT))
        btn.bind("<Leave>",    lambda e: btn.config(bg=ACCENT))
        btn.bind("<Button-1>", lambda e: self._do_connect())

        # status / error text
        self.conn_msg = tk.Label(wrapper, text="", font=("Courier", 10), fg=DANGER, bg=BG)
        self.conn_msg.pack(pady=(14, 0))

        # back link
        back = tk.Label(wrapper, text="< BACK", font=("Courier", 10),
                        fg=TEXT_DIM, bg=BG, cursor="hand2")
        back.pack(pady=(10, 0))
        back.bind("<Button-1>", lambda e: self._show("start"))
        back.bind("<Enter>",    lambda e: back.config(fg=ACCENT))
        back.bind("<Leave>",    lambda e: back.config(fg=TEXT_DIM))

    # styled text entry with label and bottom glow-border
    def _make_field(self, parent, label_text, var, width=20, top_pad=0):
        wrapper = tk.Frame(parent, bg=PANEL)
        wrapper.pack(fill="x", pady=(top_pad, 0))

        tk.Label(wrapper, text=label_text, font=("Courier", 9, "bold"),
                 fg=TEXT_DIM, bg=PANEL).pack(anchor="w", pady=(0, 3))

        entry = tk.Entry(wrapper, textvariable=var, font=("Courier", 13),
                         fg=TEXT_BRIGHT, bg="#0D1E33", insertbackground=ACCENT,
                         relief="flat", width=width, bd=0)
        entry.pack(fill="x", ipady=7)

        # thin border under the field that lights up on focus
        border = tk.Frame(wrapper, height=2, bg=ACCENT_DIM)
        border.pack(fill="x")
        entry.bind("<FocusIn>",  lambda e: border.config(bg=ACCENT))
        entry.bind("<FocusOut>", lambda e: border.config(bg=ACCENT_DIM))

    def _do_connect(self):
        ip = self.ip_var.get().strip()
        port_str = self.port_var.get().strip()
        if not ip:
            self.conn_msg.config(text="IP address is required", fg=DANGER)
            return
        try:
            port = int(port_str)
        except ValueError:
            self.conn_msg.config(text="Port must be a number", fg=DANGER)
            return
        self.conn_msg.config(text="Connecting...", fg=WARNING)
        if self.on_connect:
            self.on_connect(ip, port)

    # ==========================================================
    # WAITING SCREEN  — animated dots (centered)
    # ==========================================================

    def _build_waiting(self):
        frame = tk.Frame(self.root, bg=BG)
        self._screens["waiting"] = frame

        # centered container
        inner = tk.Frame(frame, bg=BG)
        inner.place(relx=0.5, rely=0.45, anchor="center")

        self.wait_badge = tk.Label(inner, text="", font=("Courier", 12),
                                   fg=SUCCESS, bg=BG)
        self.wait_badge.pack(pady=(0, 28))

        tk.Label(inner, text="WAITING FOR OPPONENT",
                 font=("Courier", 24, "bold"), fg=TEXT_BRIGHT, bg=BG).pack()

        self.wait_dots = tk.Label(inner, text="...", font=("Courier", 22, "bold"),
                                  fg=ACCENT, bg=BG)
        self.wait_dots.pack()

        tk.Label(inner, text="Both players must be connected before the game can start",
                 font=("Courier", 10), fg=TEXT_DIM, bg=BG).pack(pady=(20, 0))

    def _animate_dots(self):
        self._dot_count = (self._dot_count + 1) % 4
        self.wait_dots.config(text="." * self._dot_count + " " * (3 - self._dot_count))
        self._dot_id = self.root.after(450, self._animate_dots)

    # ==========================================================
    # PLACEMENT SCREEN  — fleet panel + grid (centered in middle)
    # ==========================================================

    def _build_placement(self):
        frame = tk.Frame(self.root, bg=BG)
        self._screens["placement"] = frame

        # ---- top bar ----
        top = tk.Frame(frame, bg=HEADER_BG, height=46)
        top.pack(fill="x")
        top.pack_propagate(False)

        tk.Label(top, text="BATTLESHIP", font=("Courier", 13, "bold"),
                 fg=TEXT, bg=HEADER_BG).pack(side="left", padx=16, pady=10)

        self.place_phase = tk.Label(top, text="SHIP PLACEMENT",
                                    font=("Courier", 11), fg=ACCENT, bg=HEADER_BG)
        self.place_phase.pack(side="right", padx=16)

        # ---- bottom bar (pack before middle so it stays at bottom) ----
        bot = tk.Frame(frame, bg=PANEL, height=48)
        bot.pack(fill="x", side="bottom")
        bot.pack_propagate(False)

        bar = tk.Frame(bot, bg=PANEL)
        bar.pack(padx=18, pady=10)

        self.placing_lbl = tk.Label(bar, text="Placing: Carrier (5)",
                                    font=("Courier", 12, "bold"), fg=TEXT_BRIGHT, bg=PANEL)
        self.placing_lbl.pack(side="left", padx=(0, 30))

        self.orient_lbl = tk.Label(bar, text="[R] Rotate  ·  HORIZONTAL",
                                   font=("Courier", 10), fg=ACCENT, bg=PANEL, cursor="hand2")
        self.orient_lbl.pack(side="left")
        self.orient_lbl.bind("<Button-1>", lambda e: self._toggle_orient())

        # ---- middle area: fills remaining space, content centered inside ----
        mid = tk.Frame(frame, bg=BG)
        mid.pack(fill="both", expand=True)

        # inner container that holds fleet panel + board, centered via place
        content = tk.Frame(mid, bg=BG)
        content.place(relx=0.5, rely=0.5, anchor="center")

        # fleet panel (left)
        fleet_panel = tk.Frame(content, bg=PANEL, width=175, padx=12, pady=14)
        fleet_panel.pack(side="left", fill="y", padx=(0, 18))
        fleet_panel.pack_propagate(False)

        tk.Label(fleet_panel, text="FLEET", font=("Courier", 11, "bold"),
                 fg=ACCENT, bg=PANEL).pack(anchor="w", pady=(0, 10))

        self.fleet_rows = []
        for name, length in SHIPS:
            row = tk.Frame(fleet_panel, bg=PANEL)
            row.pack(fill="x", pady=4)
            squares = tk.Label(row, text=" ".join(["■"] * length),
                               font=("Courier", 8), fg=ACCENT_DIM, bg=PANEL)
            squares.pack(anchor="w")
            name_lbl = tk.Label(row, text=name, font=("Courier", 10),
                                fg=TEXT_DIM, bg=PANEL)
            name_lbl.pack(anchor="w")
            self.fleet_rows.append((squares, name_lbl))

        # board (right of fleet)
        board_wrap = tk.Frame(content, bg=BG)
        board_wrap.pack(side="left")

        tk.Label(board_wrap, text="YOUR GRID", font=("Courier", 10, "bold"),
                 fg=TEXT_DIM, bg=BG).pack(pady=(0, 6))

        gp = self._make_grid(board_wrap)
        gp["frame"].pack()
        self.place_canvas = gp["canvas"]
        self.place_cells  = gp["cells"]

        # keyboard + mouse bindings
        self.root.bind("r", lambda e: self._toggle_orient())
        self.root.bind("R", lambda e: self._toggle_orient())
        self.place_canvas.bind("<Motion>",   self._on_place_hover)
        self.place_canvas.bind("<Leave>",    self._on_place_leave)
        self.place_canvas.bind("<Button-1>", self._on_place_click)

        self._highlight_fleet_row(0)

    # ==========================================================
    # BATTLE SCREEN  — two boards + HUD (centered in middle)
    # ==========================================================

    def _build_battle(self):
        frame = tk.Frame(self.root, bg=BG)
        self._screens["battle"] = frame

        # ---- top bar ----
        top = tk.Frame(frame, bg=HEADER_BG, height=46)
        top.pack(fill="x")
        top.pack_propagate(False)

        tk.Label(top, text="BATTLESHIP", font=("Courier", 13, "bold"),
                 fg=TEXT, bg=HEADER_BG).pack(side="left", padx=16, pady=10)

        self.battle_player_lbl = tk.Label(top, text="", font=("Courier", 11),
                                          fg=TEXT_DIM, bg=HEADER_BG)
        self.battle_player_lbl.pack(side="right", padx=16)

        # ---- bottom status bar (pack before middle) ----
        bot = tk.Frame(frame, bg=PANEL, height=34)
        bot.pack(fill="x", side="bottom")
        bot.pack_propagate(False)

        self.status_lbl = tk.Label(bot, text="", font=("Courier", 10),
                                   fg=TEXT_DIM, bg=PANEL)
        self.status_lbl.pack(pady=7)

        # ---- middle: expands to fill, content centered inside ----
        mid = tk.Frame(frame, bg=BG)
        mid.pack(fill="both", expand=True)

        # boards + HUD container, centered via place
        content = tk.Frame(mid, bg=BG)
        content.place(relx=0.5, rely=0.5, anchor="center")

        # MY BOARD (left)
        left = tk.Frame(content, bg=BG)
        left.pack(side="left")

        tk.Label(left, text="YOUR WATERS", font=("Courier", 9, "bold"),
                 fg=TEXT_DIM, bg=BG).pack(pady=(0, 4))

        gp_my = self._make_grid(left)
        gp_my["frame"].pack()
        self.my_canvas = gp_my["canvas"]
        self.my_cells  = gp_my["cells"]

        # HUD (center between boards)
        hud = tk.Frame(content, bg=PANEL, width=130)
        hud.pack(side="left", fill="y", padx=14)
        hud.pack_propagate(False)

        tk.Frame(hud, height=14, bg=PANEL).pack()

        tk.Label(hud, text="STATUS", font=("Courier", 8, "bold"),
                 fg=TEXT_DIM, bg=PANEL).pack(pady=(6, 2))

        self.turn_lbl = tk.Label(hud, text="", font=("Courier", 12, "bold"),
                                 fg=ACCENT, bg=PANEL, wraplength=110, justify="center")
        self.turn_lbl.pack()

        tk.Frame(hud, height=1, bg=BORDER).pack(fill="x", padx=8, pady=10)

        tk.Label(hud, text="HITS", font=("Courier", 8, "bold"),
                 fg=TEXT_DIM, bg=PANEL).pack()
        self.hits_lbl = tk.Label(hud, text="0", font=("Courier", 22, "bold"),
                                 fg=CELL_HIT, bg=PANEL)
        self.hits_lbl.pack()

        tk.Label(hud, text="MISSES", font=("Courier", 8, "bold"),
                 fg=TEXT_DIM, bg=PANEL).pack(pady=(8, 0))
        self.misses_lbl = tk.Label(hud, text="0", font=("Courier", 22, "bold"),
                                   fg=CELL_MISS, bg=PANEL)
        self.misses_lbl.pack()

        tk.Frame(hud, height=1, bg=BORDER).pack(fill="x", padx=8, pady=10)

        self.feedback_lbl = tk.Label(hud, text="", font=("Courier", 10, "bold"),
                                     fg=TEXT, bg=PANEL, wraplength=110, justify="center")
        self.feedback_lbl.pack()

        # ENEMY BOARD (right)
        right = tk.Frame(content, bg=BG)
        right.pack(side="left")

        tk.Label(right, text="ENEMY WATERS", font=("Courier", 9, "bold"),
                 fg=TEXT_DIM, bg=BG).pack(pady=(0, 4))

        gp_enemy = self._make_grid(right)
        gp_enemy["frame"].pack()
        self.enemy_canvas = gp_enemy["canvas"]
        self.enemy_cells  = gp_enemy["cells"]

        # wire up enemy board interactions
        self.enemy_canvas.bind("<Motion>",   self._on_enemy_hover)
        self.enemy_canvas.bind("<Leave>",    self._on_enemy_leave)
        self.enemy_canvas.bind("<Button-1>", self._on_enemy_click)

    # ==========================================================
    # GRID BUILDER  — creates a 10x10 board canvas with labels
    # ==========================================================

    def _make_grid(self, parent):
        cw = GRID_OFF + CELL_SIZE * BOARD_SIZE
        ch = GRID_OFF + CELL_SIZE * BOARD_SIZE
        frame = tk.Frame(parent, bg=PANEL, padx=6, pady=6)
        canvas = tk.Canvas(frame, width=cw, height=ch, bg=GRID_BG, highlightthickness=0)
        canvas.pack()

        # column labels A-J
        for c in range(BOARD_SIZE):
            x = GRID_OFF + c * CELL_SIZE + CELL_SIZE // 2
            canvas.create_text(x, 12, text=chr(65 + c), fill=TEXT_DIM,
                               font=("Courier", 9, "bold"))
        # row labels 1-10
        for r in range(BOARD_SIZE):
            y = GRID_OFF + r * CELL_SIZE + CELL_SIZE // 2
            canvas.create_text(12, y, text=str(r + 1), fill=TEXT_DIM,
                               font=("Courier", 9))
        # grid cells
        cells = {}
        for r in range(BOARD_SIZE):
            for c in range(BOARD_SIZE):
                x1 = GRID_OFF + c * CELL_SIZE
                y1 = GRID_OFF + r * CELL_SIZE
                rect = canvas.create_rectangle(
                    x1, y1, x1 + CELL_SIZE - 2, y1 + CELL_SIZE - 2,
                    fill=CELL_EMPTY, outline=BORDER, width=1
                )
                cells[(r, c)] = rect

        return {"frame": frame, "canvas": canvas, "cells": cells}

    # converts pixel position on a grid canvas to (row, col)
    def _pix_to_grid(self, x, y):
        col = (x - GRID_OFF) // CELL_SIZE
        row = (y - GRID_OFF) // CELL_SIZE
        if 0 <= row < BOARD_SIZE and 0 <= col < BOARD_SIZE:
            return row, col
        return None, None

    # ==========================================================
    # SHIP PLACEMENT HANDLERS
    # ==========================================================

    def _toggle_orient(self):
        if not self.placing:
            return
        self.orientation = "V" if self.orientation == "H" else "H"
        label = "HORIZONTAL" if self.orientation == "H" else "VERTICAL"
        self.orient_lbl.config(text=f"[R] Rotate  ·  {label}")

    # returns list of (row, col) cells the ship would occupy, None if out of bounds
    def _ship_cells(self, row, col, length):
        cells = []
        for i in range(length):
            r = row + (i if self.orientation == "V" else 0)
            c = col + (i if self.orientation == "H" else 0)
            if r >= BOARD_SIZE or c >= BOARD_SIZE:
                return None
            cells.append((r, c))
        return cells

    def _can_place(self, cells):
        if cells is None:
            return False
        return all(self.my_board[r][c] == EMPTY for r, c in cells)

    # clears the ship preview overlay back to real board state
    def _clear_preview(self):
        for r, c in self.preview:
            self.place_canvas.itemconfig(
                self.place_cells[(r, c)],
                fill=self._cell_color(self.my_board[r][c], show_ships=True)
            )
        self.preview = []

    def _on_place_hover(self, event):
        if not self.placing or self.ship_idx >= len(SHIPS):
            return
        self._clear_preview()
        row, col = self._pix_to_grid(event.x, event.y)
        if row is None:
            return
        _, length = SHIPS[self.ship_idx]
        cells = self._ship_cells(row, col, length)
        if cells:
            color = CELL_SHIP if self._can_place(cells) else CELL_BAD
            for r, c in cells:
                if 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE:
                    self.place_canvas.itemconfig(self.place_cells[(r, c)], fill=color)
                    self.preview.append((r, c))

    def _on_place_leave(self, event):
        self._clear_preview()

    def _on_place_click(self, event):
        if not self.placing or self.ship_idx >= len(SHIPS):
            return
        row, col = self._pix_to_grid(event.x, event.y)
        if row is None:
            return
        _, length = SHIPS[self.ship_idx]
        cells = self._ship_cells(row, col, length)
        if not self._can_place(cells):
            return

        # commit ship to board
        for r, c in cells:
            self.my_board[r][c] = SHIP
        self.placed_ships.extend(cells)
        self.preview = []
        self._redraw(self.place_canvas, self.place_cells, self.my_board, show_ships=True)

        # mark placed in fleet list
        sq_lbl, nm_lbl = self.fleet_rows[self.ship_idx]
        sq_lbl.config(fg=CELL_SHIP)
        nm_lbl.config(fg=SUCCESS)

        self.ship_idx += 1
        if self.ship_idx >= len(SHIPS):
            self.placing = False
            self.placing_lbl.config(text="All ships placed!")
            self.orient_lbl.config(text="Waiting for game to start...")
            if self.on_ships_placed:
                self.on_ships_placed(self.placed_ships)
            self._show("waiting")
        else:
            next_name, next_len = SHIPS[self.ship_idx]
            self.placing_lbl.config(text=f"Placing: {next_name} ({next_len})")
            self._highlight_fleet_row(self.ship_idx)

    def _highlight_fleet_row(self, idx):
        if idx < len(self.fleet_rows):
            _, nm_lbl = self.fleet_rows[idx]
            nm_lbl.config(fg=TEXT_BRIGHT)

    # ==========================================================
    # BATTLE HANDLERS
    # ==========================================================

    def _on_enemy_hover(self, event):
        if not self.game_active or not self.is_my_turn:
            return
        for r in range(BOARD_SIZE):
            for c in range(BOARD_SIZE):
                if self.enemy_board[r][c] == EMPTY:
                    self.enemy_canvas.itemconfig(self.enemy_cells[(r, c)], fill=CELL_EMPTY)
        row, col = self._pix_to_grid(event.x, event.y)
        if row is not None and self.enemy_board[row][col] == EMPTY:
            self.enemy_canvas.itemconfig(self.enemy_cells[(row, col)], fill=CELL_HOVER)

    def _on_enemy_leave(self, event):
        if not self.game_active:
            return
        for r in range(BOARD_SIZE):
            for c in range(BOARD_SIZE):
                if self.enemy_board[r][c] == EMPTY:
                    self.enemy_canvas.itemconfig(self.enemy_cells[(r, c)], fill=CELL_EMPTY)

    def _on_enemy_click(self, event):
        if not self.game_active or not self.is_my_turn:
            return
        row, col = self._pix_to_grid(event.x, event.y)
        if row is None or self.enemy_board[row][col] != EMPTY:
            return
        if self.on_fire:
            self.on_fire(row, col)

    # ==========================================================
    # DRAW HELPERS + ANIMATIONS
    # ==========================================================

    def _cell_color(self, val, show_ships):
        if val == HIT:
            return CELL_HIT
        elif val == MISS:
            return CELL_MISS
        elif val == SHIP and show_ships:
            return CELL_SHIP
        return CELL_EMPTY

    # redraws every cell on a board canvas
    def _redraw(self, canvas, cells, board, show_ships):
        for r in range(BOARD_SIZE):
            for c in range(BOARD_SIZE):
                canvas.itemconfig(cells[(r, c)],
                                  fill=self._cell_color(board[r][c], show_ships))
        self._draw_markers(canvas, board)

    # draws X on hits and dots on misses
    def _draw_markers(self, canvas, board):
        canvas.delete("marker")
        for r in range(BOARD_SIZE):
            for c in range(BOARD_SIZE):
                if board[r][c] in (HIT, MISS):
                    x1 = GRID_OFF + c * CELL_SIZE
                    y1 = GRID_OFF + r * CELL_SIZE
                    cx = x1 + CELL_SIZE // 2 - 1
                    cy = y1 + CELL_SIZE // 2 - 1
                    if board[r][c] == HIT:
                        s = 7
                        canvas.create_line(cx-s, cy-s, cx+s, cy+s,
                                           fill="white", width=2, tags="marker")
                        canvas.create_line(cx+s, cy-s, cx-s, cy+s,
                                           fill="white", width=2, tags="marker")
                    else:
                        canvas.create_oval(cx-3, cy-3, cx+3, cy+3,
                                           fill="white", outline="", tags="marker")

    # flashes a cell white then settles to its final color (hit/miss feedback)
    def _flash(self, canvas, cell, flash_color, final_color, steps=6):
        if steps > 0:
            c = flash_color if steps % 2 == 0 else final_color
            canvas.itemconfig(cell, fill=c)
            self.root.after(65, lambda: self._flash(canvas, cell, flash_color, final_color, steps - 1))
        else:
            canvas.itemconfig(cell, fill=final_color)

    # pulses the turn indicator between bright and dim during battle
    def _pulse_turn(self):
        if not self.game_active:
            return
        if self.is_my_turn:
            # pulse between bright cyan and dim cyan
            current = self.turn_lbl.cget("fg")
            nxt = ACCENT if current == TEXT_BRIGHT else TEXT_BRIGHT
            self.turn_lbl.config(fg=nxt)
        self._pulse_id = self.root.after(600, self._pulse_turn)

    # ==========================================================
    # PUBLIC API  — called by client.py
    # ==========================================================

    # socket connected, show player number
    def set_connected(self, player_num):
        self.wait_badge.config(text=f"[ PLAYER {player_num} — CONNECTED ]")
        self.battle_player_lbl.config(text=f"PLAYER {player_num}")
        self.conn_msg.config(text="Connected!", fg=SUCCESS)

    # server says start placing ships
    def start_placement(self):
        self._show("placement")

    # both players placed, start the game
    def start_game(self, my_turn):
        self.game_active = True
        self.is_my_turn  = my_turn
        self._redraw(self.my_canvas, self.my_cells, self.my_board, show_ships=True)
        self._show("battle")
        self._update_turn()

    # opponent fired at your board
    def update_my_board(self, row, col, result):
        self.my_board[row][col] = HIT if result == "hit" else MISS
        final = CELL_HIT if result == "hit" else CELL_MISS
        self._flash(self.my_canvas, self.my_cells[(row, col)], "#FFFFFF", final)
        self.root.after(450, lambda: self._redraw(
            self.my_canvas, self.my_cells, self.my_board, show_ships=True
        ))

    # result of your shot
    def update_enemy_board(self, row, col, result):
        if result == "hit":
            self.enemy_board[row][col] = HIT
            final = CELL_HIT
            self.hit_count += 1
            self.hits_lbl.config(text=str(self.hit_count))
            self.feedback_lbl.config(text="HIT!", fg=CELL_HIT)
            self.status_lbl.config(text=f"  Direct hit at {chr(65+col)}{row+1}!", fg=CELL_HIT)
        else:
            self.enemy_board[row][col] = MISS
            final = CELL_MISS
            self.miss_count += 1
            self.misses_lbl.config(text=str(self.miss_count))
            self.feedback_lbl.config(text="Miss.", fg=TEXT_DIM)
            self.status_lbl.config(text=f"  Missed at {chr(65+col)}{row+1}.", fg=TEXT_DIM)

        self._flash(self.enemy_canvas, self.enemy_cells[(row, col)], "#FFFFFF", final)
        self.root.after(450, lambda: self._redraw(
            self.enemy_canvas, self.enemy_cells, self.enemy_board, show_ships=False
        ))

    # turn switched
    def set_turn(self, my_turn):
        self.is_my_turn = my_turn
        self._update_turn()

    def _update_turn(self):
        if self.is_my_turn:
            self.turn_lbl.config(text="YOUR\nTURN", fg=ACCENT)
            self.status_lbl.config(text="  Select a target on the enemy grid", fg=TEXT_DIM)
        else:
            self.turn_lbl.config(text="ENEMY\nTURN", fg=TEXT_DIM)
            self.status_lbl.config(text="  Waiting for opponent to fire...", fg=TEXT_DIM)

    # game over overlay with stats
    def show_game_over(self, won):
        self.game_active = False
        self.is_my_turn  = False
        self._cancel_animations()

        overlay = tk.Frame(self.root, bg=BG)
        overlay.place(relx=0, rely=0, relwidth=1, relheight=1)

        card = tk.Frame(overlay, bg=PANEL, padx=60, pady=44)
        card.place(relx=0.5, rely=0.5, anchor="center")

        if won:
            title, color, sub = "VICTORY", SUCCESS, "All enemy ships have been sunk."
        else:
            title, color, sub = "DEFEAT", DANGER, "Your entire fleet has been destroyed."

        tk.Label(card, text=title, font=("Courier", 48, "bold"),
                 fg=color, bg=PANEL).pack(pady=(0, 8))

        tk.Frame(card, height=2, bg=color).pack(fill="x", pady=4)

        tk.Label(card, text=sub, font=("Courier", 13),
                 fg=TEXT_DIM, bg=PANEL).pack(pady=(10, 4))

        total = self.hit_count + self.miss_count
        acc = int(self.hit_count / max(1, total) * 100)
        tk.Label(card, text=f"Shots: {total}   Hits: {self.hit_count}   Accuracy: {acc}%",
                 font=("Courier", 10), fg=TEXT_DIM, bg=PANEL).pack(pady=(0, 22))

        close = tk.Label(card, text="CLOSE", font=("Courier", 12, "bold"),
                         fg=BG, bg=color, padx=24, pady=10, cursor="hand2")
        close.pack()
        close.bind("<Button-1>", lambda e: self.root.destroy())

    # update status text (used by client.py for connection errors etc)
    def set_status(self, text, color=WARNING):
        self.conn_msg.config(text=text, fg=color)


# standalone test — run gui.py directly to see the start screen
if __name__ == "__main__":
    root = tk.Tk()
    gui = BattleshipGUI(root)
    root.mainloop()
