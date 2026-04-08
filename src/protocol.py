import json

# All message types used between server and clients
MSG_PLAYER_ASSIGN = "PLAYER_ASSIGN"   # server tells client which player they are (P1 or P2)
MSG_PLACE_SHIPS   = "PLACE_SHIPS"     # client sends ship positions to server
MSG_GAME_START    = "GAME_START"      # server tells both clients the game has begun
MSG_FIRE          = "FIRE"            # client fires a shot at a coordinate
MSG_RESULT        = "RESULT"          # server tells clients if shot was hit or miss
MSG_OPPONENT_MOVE = "OPPONENT_MOVE"   # server tells client what move the opponent just made
MSG_GAME_OVER     = "GAME_OVER"       # server tells clients who won


# this function makes a JSON string from a message type and any extra data
# example make_message(MSG_FIRE, x=3, y=4) -> '{"type": "FIRE", "x": 3, "y": 4}'
def make_message(msg_type, **kwargs):
    type = {"type": msg_type}
    message = type | kwargs
    return json.dumps(message)


# parses a JSON string back into a dict
def parse_message(data):
    return json.loads(data)
