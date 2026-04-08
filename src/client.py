import socket
import threading
import tkinter as tk

from gui import BattleshipGUI
from protocol import (
    MSG_CONNECT,
    MSG_FIRE,
    MSG_GAME_OVER,
    MSG_GAME_START,
    MSG_NEW_GAME,
    MSG_OPPONENT_MOVE,
    MSG_PLACE_SHIPS,
    MSG_PLAYER_ASSIGN,
    MSG_RESUME,
    MSG_RESULT,
    make_message,
    parse_message,
)


class BattleshipClient:
    def __init__(self, root):
        self.root = root
        self.gui = BattleshipGUI(root)
        setattr(self.gui, "on_connect", self.on_connect)
        setattr(self.gui, "on_ships_placed", self.on_ships_placed)
        setattr(self.gui, "on_fire", self.on_fire)
        setattr(self.gui, "on_new_game", self.on_new_game_request)

        self.sock = None
        self.running = False
        self.closing = False

        self.server_ip = None
        self.server_port = None
        self.player_num = None
        self.game_uuid = None
        self.can_resume = False

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def open_connection(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.server_ip, self.server_port))
        self.running = True
        threading.Thread(target=self.listen_loop, args=(self.sock,)).start()

    def close_connection(self):
        try:
            if self.sock is not None:
                self.sock.close()
        except OSError:
            pass
        self.sock = None

    def send(self, msg_type, **kwargs):
        if self.sock is None:
            return
        try:
            self.sock.sendall((make_message(msg_type, **kwargs) + "\n").encode("utf-8"))
        except OSError:
            self.root.after(0, self.on_disconnect)

    def on_connect(self, ip, port):
        if self.running:
            self.gui.set_status("Already connected", color="#F39C12")
            return

        self.server_ip = ip.strip()
        try:
            self.server_port = int(port)
        except (TypeError, ValueError):
            self.gui.set_status("Port must be a number", color="#E74C3C")
            return

        try:
            self.open_connection()
            if self.can_resume and self.game_uuid and self.player_num:
                self.send(MSG_RESUME, game_uuid=self.game_uuid, player_num=self.player_num)
                self.gui.set_status("Trying to resume...", color="#F39C12")
            else:
                self.send(MSG_CONNECT)
                self.gui.set_status("Connected. Waiting for opponent...", color="#00B894")
        except OSError as exc:
            self.running = False
            self.close_connection()
            self.gui.set_status(f"Connection failed: {exc}", color="#E74C3C")

    def listen_loop(self, sock):
        try:
            while self.running and self.sock is sock:
                data = sock.recv(4096)
                if not data:
                    break
                try:
                    message = parse_message(data.decode("utf-8").strip())
                except Exception:
                    continue
                self.root.after(0, lambda msg=message: self.handle_message(msg))
        finally:
            self.root.after(0, self.on_disconnect)

    def on_disconnect(self):
        if self.closing:
            return
        if not self.running and self.sock is None:
            return

        self.running = False
        self.close_connection()

        self.can_resume = bool(self.game_uuid and self.player_num)
        if self.can_resume:
            self.gui.set_status("Disconnected. Click CONNECT to resume.", color="#F39C12")
        else:
            self.gui.set_status("Disconnected from server", color="#E74C3C")

    def handle_message(self, message):
        msg_type = message.get("type")

        if msg_type == MSG_PLAYER_ASSIGN:
            self.player_num = int(message.get("player_num"))
            self.game_uuid = message.get("game_uuid")
            self.can_resume = False
            self.gui.set_connected(self.player_num)
            self.gui.reset_for_new_game()
            self.gui.set_status("Connected. Place your ships.", color="#00B894")
            return

        if msg_type == MSG_RESUME:
            if not message.get("ok"):
                self.running = False
                self.close_connection()
                self.gui.set_status(f"Resume failed: {message.get('reason', 'unknown')}", color="#E74C3C")
                return

            self.player_num = int(message.get("player_num", self.player_num))
            self.game_uuid = message.get("game_uuid", self.game_uuid)
            self.can_resume = False
            self.gui.set_connected(self.player_num)

            phase = message.get("phase")
            if phase == "placement":
                self.gui.start_placement()
            elif phase == "battle":
                self.gui.start_game(bool(message.get("your_turn")))
            self.gui.set_status("Resumed game", color="#00B894")
            return

        if msg_type == MSG_GAME_START:
            self.gui.start_game(bool(message.get("your_turn")))
            return

        if msg_type == MSG_RESULT:
            self.gui.update_enemy_board(message.get("row"), message.get("col"), message.get("result"))
            return

        if msg_type == MSG_OPPONENT_MOVE:
            self.gui.update_my_board(message.get("row"), message.get("col"), message.get("result"))
            self.gui.set_turn(True)
            return

        if msg_type == MSG_GAME_OVER:
            winner = int(message.get("winner"))
            self.gui.show_game_over(winner == self.player_num)
            return

        if msg_type == MSG_NEW_GAME:
            self.gui.reset_for_new_game()
            self.gui.set_status("New game started. Place your ships.", color="#00B894")

    def on_ships_placed(self, ships):
        self.send(MSG_PLACE_SHIPS, ships=ships)
        self.gui.set_status("Ships sent. Waiting for opponent...", color="#F39C12")

    def on_fire(self, row, col):
        self.gui.set_turn(False)
        self.send(MSG_FIRE, row=row, col=col)

    def on_new_game_request(self):
        self.send(MSG_NEW_GAME)
        self.gui.set_status("New game requested...", color="#F39C12")

    def on_close(self):
        self.closing = True
        self.running = False
        self.close_connection()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    BattleshipClient(root)
    root.mainloop()
