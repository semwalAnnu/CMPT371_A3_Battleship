# This file contains the game logic for Battleship
#   0  = empty
#   1  = ship
#   2  = ship was hit
#  -1  = missed shot

EMPTY = 0
SHIP = 1
HIT = 2
MISS = -1

BOARD_SIZE = 10


# creates and returns a fully empty 10x10 board
def create_board():
    return [[EMPTY for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]


# places ships on the board given a list of (x, y) coordinates
def place_ships(board, ships):
    for x, y in ships:
        board[x][y] = SHIP


# process a shot at x, y on the board
# returns hit if a ship was there  and miss if it wasnt
def process_shot(board, x, y):
    if board[x][y] == SHIP:
        board[x][y] = HIT
        return "hit"
    else:
        board[x][y] = MISS
        return "miss"


# checks if all ships on the board have been hit
def all_ships_sunk(board):
    for row in board:
        if SHIP in row:
            return False
    return True
