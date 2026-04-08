import socket
import threading
import time
import uuid

from game_logic import BOARD_SIZE, HIT, MISS, all_ships_sunk, create_board, place_ships, process_shot
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

HOST = "127.0.0.1"
PORT = 5000
RESUME_TIMEOUT_SECONDS = 5 * 60

waiting_queue = []
games = {}


def send_message(sock, msg_type, **kwargs):
    if sock is None:
        return False
    try:
        sock.sendall((make_message(msg_type, **kwargs) + "\n").encode("utf-8"))
        return True
    except Exception:
        return False


def close_socket(sock):
    try:
        if sock is not None:
            sock.close()
    except Exception:
        pass


def other_player(player_num):
    return 2 if player_num == 1 else 1


def valid_coord(row, col):
    return isinstance(row, int) and isinstance(col, int) and 0 <= row < BOARD_SIZE and 0 <= col < BOARD_SIZE


def send_to_player(game, target_player, msg_type, **kwargs):
    send_message(game["players"][target_player]["sock"], msg_type, **kwargs)


def cleanup_game(game_uuid):
    game = games.pop(game_uuid, None)
    if game is None:
        return
    for player_num in (1, 2):
        sock = game["players"][player_num]["sock"]
        game["players"][player_num]["sock"] = None
        close_socket(sock)


def new_player_state(sock):
    return {
        "sock": sock,
        "board": create_board(),
        "ready": False,
        "new_game_requested": False,
        "disconnected_at": None,
    }


def reset_for_new_game(game):
    game["phase"] = "placement"
    game["turn"] = 1
    for p in (1, 2):
        game["players"][p]["board"] = create_board()
        game["players"][p]["ready"] = False
        game["players"][p]["new_game_requested"] = False


def start_game_pair(p1_sock, p2_sock):
    game_uuid = str(uuid.uuid4())
    game = {
        "id": game_uuid,
        "phase": "placement",
        "turn": 1,
        "players": {
            1: new_player_state(p1_sock),
            2: new_player_state(p2_sock),
        },
    }
    games[game_uuid] = game

    send_to_player(game, 1, MSG_PLAYER_ASSIGN, player_num=1, game_uuid=game_uuid)
    send_to_player(game, 2, MSG_PLAYER_ASSIGN, player_num=2, game_uuid=game_uuid)

    threading.Thread(target=handle_player, args=(game_uuid, 1, p1_sock)).start()
    threading.Thread(target=handle_player, args=(game_uuid, 2, p2_sock)).start()


def expire_resume_window(game_uuid, player_num, disconnected_at):
    time.sleep(RESUME_TIMEOUT_SECONDS)
    game = games.get(game_uuid)
    if game is None:
        return
    player = game["players"][player_num]
    if player["sock"] is not None or player["disconnected_at"] != disconnected_at:
        return
    winner = other_player(player_num)
    send_to_player(game, winner, MSG_GAME_OVER, winner=winner, reason="opponent_timeout")
    cleanup_game(game_uuid)


def mark_disconnected(game_uuid, player_num, sock):
    game = games.get(game_uuid)
    if game is None:
        close_socket(sock)
        return

    player = game["players"][player_num]
    if player["sock"] is not sock:
        close_socket(sock)
        return

    player["sock"] = None
    player["disconnected_at"] = time.time()
    disconnected_at = player["disconnected_at"]
    close_socket(sock)

    threading.Thread(target=expire_resume_window, args=(game_uuid, player_num, disconnected_at)).start()


def handle_place_ships(game, player_num, message):
    ships = message.get("ships")
    if not isinstance(ships, list):
        return

    board = create_board()
    try:
        place_ships(board, ships)
    except Exception:
        return

    if game["phase"] != "placement":
        return

    game["players"][player_num]["board"] = board
    game["players"][player_num]["ready"] = True

    if game["players"][1]["ready"] and game["players"][2]["ready"]:
        game["phase"] = "battle"
        game["turn"] = 1
        send_to_player(game, 1, MSG_GAME_START, your_turn=True, game_uuid=game["id"])
        send_to_player(game, 2, MSG_GAME_START, your_turn=False, game_uuid=game["id"])


def handle_fire(game, player_num, message):
    row = message.get("row")
    col = message.get("col")
    if not valid_coord(row, col):
        return

    if game["phase"] != "battle" or game["turn"] != player_num:
        return

    opponent = other_player(player_num)
    board = game["players"][opponent]["board"]
    if board[row][col] in (HIT, MISS):
        return

    result = process_shot(board, row, col)
    won = all_ships_sunk(board)

    if won:
        game["phase"] = "finished"
    else:
        game["turn"] = opponent

    send_to_player(game, player_num, MSG_RESULT, row=row, col=col, result=result)
    send_to_player(game, opponent, MSG_OPPONENT_MOVE, row=row, col=col, result=result)

    if won:
        send_to_player(game, 1, MSG_GAME_OVER, winner=player_num)
        send_to_player(game, 2, MSG_GAME_OVER, winner=player_num)


def handle_new_game(game, player_num):
    if game["phase"] != "finished":
        return

    game["players"][player_num]["new_game_requested"] = True
    if not (game["players"][1]["new_game_requested"] and game["players"][2]["new_game_requested"]):
        return

    reset_for_new_game(game)
    send_to_player(game, 1, MSG_NEW_GAME, game_uuid=game["id"])
    send_to_player(game, 2, MSG_NEW_GAME, game_uuid=game["id"])


def process_player_message(game_uuid, player_num, message):
    game = games.get(game_uuid)
    if game is None:
        return

    msg_type = message.get("type")
    if msg_type == MSG_PLACE_SHIPS:
        handle_place_ships(game, player_num, message)
    elif msg_type == MSG_FIRE:
        handle_fire(game, player_num, message)
    elif msg_type == MSG_NEW_GAME:
        handle_new_game(game, player_num)


def handle_player(game_uuid, player_num, sock):
    try:
        while True:
            data = sock.recv(4096)
            if not data:
                break
            try:
                message = parse_message(data.decode("utf-8").strip())
            except Exception:
                continue
            process_player_message(game_uuid, player_num, message)
    finally:
        mark_disconnected(game_uuid, player_num, sock)


def handle_resume(sock, message):
    game_uuid = message.get("game_uuid")
    player_num = message.get("player_num")

    try:
        player_num = int(player_num)
    except Exception:
        send_message(sock, MSG_RESUME, ok=False, reason="invalid_player")
        close_socket(sock)
        return

    game = games.get(game_uuid)
    if game is None:
        send_message(sock, MSG_RESUME, ok=False, reason="unknown_game")
        close_socket(sock)
        return

    if player_num not in (1, 2):
        send_message(sock, MSG_RESUME, ok=False, reason="invalid_player")
        close_socket(sock)
        return

    player = game["players"][player_num]
    if player["sock"] is not None or player["disconnected_at"] is None:
        send_message(sock, MSG_RESUME, ok=False, reason="not_disconnected")
        close_socket(sock)
        return

    if time.time() - player["disconnected_at"] > RESUME_TIMEOUT_SECONDS:
        send_message(sock, MSG_RESUME, ok=False, reason="expired")
        close_socket(sock)
        return

    player["sock"] = sock
    player["disconnected_at"] = None
    phase = game["phase"]
    your_turn = phase == "battle" and game["turn"] == player_num

    send_message(sock, MSG_RESUME, ok=True, game_uuid=game_uuid, player_num=player_num, phase=phase, your_turn=your_turn)
    threading.Thread(target=handle_player, args=(game_uuid, player_num, sock)).start()


def handle_connect(sock):
    waiting_queue.append(sock)
    if len(waiting_queue) < 2:
        return
    start_game_pair(waiting_queue.pop(0), waiting_queue.pop(0))


def handle_incoming_connection(sock, addr):
    try:
        data = sock.recv(4096)
        if not data:
            close_socket(sock)
            return
        message = parse_message(data.decode("utf-8").strip())
    except Exception:
        close_socket(sock)
        return

    msg_type = message.get("type")
    if msg_type == MSG_CONNECT:
        handle_connect(sock)
    elif msg_type == MSG_RESUME:
        handle_resume(sock, message)
    else:
        print(f"Invalid handshake from {addr}: {msg_type}")
        close_socket(sock)


def handle_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((HOST, PORT))
    server_socket.listen()

    try:
        while True:
            client_socket, addr = server_socket.accept()
            threading.Thread(target=handle_incoming_connection, args=(client_socket, addr)).start()
    except KeyboardInterrupt:
        pass
    finally:
        server_socket.close()


if __name__ == "__main__":
    handle_server()
