# **CMPT 371 A3 Socket Programming `Battleship`**

**Course:** CMPT 371 \- Data Communications & Networking  
**Instructor:** Mirza Zaeem Baig  
**Semester:** Spring 2026  

## **Group Members**
| Name | Email |
| :---- | :---- |
| Edmond Yoong | edmond_yoong@sfu.ca  |
| Shobhit Semwal | annu_semwal@sfu.ca |


## **1. Project Overview & Description**
This project is a multiplayer Battleship game built on a client-server setup using TCP sockets and Python's Socket API. A central server listens for incoming client connections and pairs the first two clients it gets into a shared game. From there it sits in the middle and handles all gameplay between the two players. Any extra clients that show up get queued and paired into their own games as they arrive.

We went with TCP over UDP because Battleship is turn-based and there's really no room for lost or reordered messages. If a FIRE or RESULT got dropped, the two players' boards would fall out of sync, and an out of order move could let someone skip a turn. TCP gives us reliable, in-order delivery for free at the transport layer, and the small latency hit doesn't really matter at the speed humans actually play.

## **2\. System Limitations & Edge Cases**
* Handling Multiple Clients Concurrently:
    * Solution: Utilizing Python's `threading` module, the server handles each incoming connection in its own thread. Two connected clients are paired from the queue into a shared game state. As the game is isolated from the queue, the server can continue to accept new clients and start new games without blocking.
    * Limitations: Thread creation is constrained by system resources. Excessive number of clients will exhaust the system resources.
* TCP Stream Buffering:
    * Solution: The protocol uses JSON messages delimited by the newline character (`\n`). Both the client and server expect each and every message to end with a newline character.
    * Limitation: It is assumed that one complete JSON message per `recv()` call. However, it is possible to read incomplete messages, which this implementation does not handle.
* Client Disconnections:
    * Solution: The server detects client disconnections, such as sudden network interruptions, and allows 5 minutes for the same client to reconnect before the remaining player is declared the winner.
    * Limitation: If the client process unexpectedly closes, they will not be able to reconnect to the existing game because the game's UUID is stored in-memory.
* Server Crashes:
    * Limitations: If the server crashes, all ongoing games will be lost and clients will need to reconnect and start new games. All game states are stored in-memory on the server, so they will be lost if the server process is terminated.
* High Latency & Network Conditions:
    * Solution: TCP handles packet loss and retransmission at the transport layer, so we don't need to deal with dropped messages in the app logic during normal play.
    * Limitation: The protocol doesn't have any app-level timeouts on FIRE/RESULT round trips. If the network stalls mid move, the client will just look frozen until TCP itself eventually gives up. We're also assuming both players are on a low latency network as we tested on localhost and SFU CSIL.

## **3\. Video Demo**
A quick demonstration video has been created specifically for CMPT 371 Assignment 3. It shows how the two clients connect to the server and plays the game. The video can be found on [SFU OneDrive here](https://1sfu-my.sharepoint.com/:v:/g/personal/ezy_sfu_ca/IQBB5vtmb5aZR5f1tTKHNN5RAcLD0RQhHTFzTfCg7R5wC8w?nav=eyJyZWZlcnJhbEluZm8iOnsicmVmZXJyYWxBcHAiOiJPbmVEcml2ZUZvckJ1c2luZXNzIiwicmVmZXJyYWxBcHBQbGF0Zm9ybSI6IldlYiIsInJlZmVycmFsTW9kZSI6InZpZXciLCJyZWZlcnJhbFZpZXciOiJNeUZpbGVzTGlua0NvcHkifX0&e=qpFaZg).

## **4\. Prerequisites (Fresh Environment)**

To successfully run this project, you will need:

* Python 3.12.0 or higher
* Install the required package using `pip install -r requirements.txt`
* Terminal (or equivalent)

**Note**: If port 5001 is in use, this project will not run successfully. Functionality was successfully on SFU's CSIL. Likewise, the above video link recorded the project running on a CSIL Windows machine.

## **5\. Step-by-Step Run Guide**

### **Step 1: Clone the Repository**
Start a Terminal/Command Prompt session. Clone the repository to your local machine using the following command. Then switch to the project directory.
```
git clone https://github.com/semwalAnnu/CMPT371_A3_Battleship.git Battleship
cd Battleship
```

Alternatively, you can [download the repository as a ZIP file](https://github.com/semwalAnnu/CMPT371_A3_Battleship/archive/refs/heads/main.zip) and extract it to your desired location. Then, navigate to the project directory in your Terminal/Command Prompt session.

### **Step 2: Create a virtual environment and install the required Python libraries**
Using the same Terminal/Command Prompt session, run the following command to create a virtual environment and activate it:
```
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```
Then, run the following command to install the required libraries:
```
pip install -r requirements.txt
```

### **Step 3: Start the Server**
Using the same Terminal/Command Prompt session, run the following below. The server binds to 127.0.0.1 on port 5001 by default.
```
python src/server.py
```

### **Step 4: Connect Player 1**
Start another Terminal/Command Prompt session without terminating the server Terminal/Command Prompt session and navigate to the root directory of the project. Run the following below. A GUI will appear with the default IP address of 127.0.0.1 and default port of 5001 shown.
```
python src/client.py
```

### **Step 5: Connect Player 2**
Start another Terminal/Command Prompt session without terminating the server Terminal/Command Prompt session and navigate to the root directory of the project. Run the following below. A GUI will appear with the default IP address of 127.0.0.1 and default port of 5001 shown.
```
python src/client.py
```

### **Step 6: Gameplay**

This project includes a GUI for gameplay. It is best to follow the on screen instructions.

1. Start the client, click on "Engage", confirm the server IP address and port, and click "Connect". 
2. Wait until there are two players (including yourself) to pair and start a game.
3. Both players to click on the grid to place their Carrier, Battleship, Cruiser, Submarine, and Destroyer ships. For the player who finishes first, they will need to wait for the other player.
4. Left grid shows their own placement of ships and the spots the enemy previously attacked. Players click on the right grid to attack. Turn order is enforced by the server: a miss passes the turn, while a hit allows the same player to fire again.
5. When one player has had all of their ship spots hit, they will be declared defeated and the other player will be declared the winner.
6. They will be offered a choice to play again with a new game. If both players click for a new game, they will be taken back to place their ships (Step 3). Otherwise, they will be offered the alternative option to close the game.

## **6\. Technical Protocol Details (JSON over TCP)**
A simple protocol was designed, inspired on the sample repository. This can be found in protocol.py.

* Message Format: 
    * `'{"type": "FIRE", "anyvariable": 0, "unlimitedvariables": "anyvalue"}\n'`  
        A JSON string is created from a message type and any extra data associated with it.
* Handshake Phase: 
    * A newly started client will send `{"type": "CONNECT"}`  
        * Server will respond with `{"type": "PLAYER_ASSIGN", "player_num": #, "game_uuid": uuid}`  
    Where `#` = 1 or 2 and `uuid` = a randomly generated UUID for the new game.
    * If a client unexpectedly disconnects but does not terminate their client, it may attempt to reconnect to the server. If successful within 5 minutes, the game can resume.  
    Upon reconnection, client will send `{"type": "RESUME", "game_uuid": uuid, "player_num": #}`  
    Where `#` = 1 or 2 and `uuid` = a randomly generated UUID for the existing game.  
        * If success, the server will respond with `{"type": "RESUME", "ok": true, "game_uuid": uuid, "player_num": #, "phase": phase, "your_turn": boolean}`  
        Where `uuid` = the UUID of the existing game, `#` = 1 or 2, `phase` = "placement" or "battle", and `boolean` = true if it is the player's turn and false otherwise.
        * If failure, the server will respond with `{"type": "RESUME", "ok": false, "reason": reason}`  
        Where `reason` = the reason why the game cannot be resumed, such as `invalid_player`, `unknown_game`, `not_disconnected`, or `expired`.

* Gameplay Phase:
    * During the placement phase, clients will send `{"type": "PLACE_SHIPS", "ships" : [[#, #], [#, #], ...]}`  
    Where `#` = the row or column of the ship. The server stores placement data and waits; there is no immediate message sent in response until both players are ready.  
    * After both clients have placed their ships, the game begins. To begin the game, the server will send `{"type": "GAME_START", "your_turn": boolean}` to both clients to inform them that the game has started and which player goes first.
    * During the battle phase, clients will send `{"type": "FIRE", "row": #, "col": #}`  
    Where `#` = the row and column of the cell to attack.  
    * The server will respond with a `RESULT` message.
        * If the player hit their opponent's ship (and the game is not over), the server will respond with: `{"type": "RESULT", "row": #, "col": #, "result": "hit", "your_turn": true}`
        Where `#` = the row and column of the cell to attack.
        * If the player fails to hit their opponent's ship, the server will respond with: `{"type": "RESULT", "row": #, "col": #, "result": "miss", "your_turn": false}`
        Where `#` = the row and column of the cell to attack.  
    * The server also notifies the opponent of the move with an `OPPONENT_MOVE` message:
        * If their ship was hit: `{"type": "OPPONENT_MOVE", "row": #, "col": #, "result": "hit"}` 
        Where `#` = the row and column of the cell to attack.  
        * If their ship was missed: `{"type": "OPPONENT_MOVE", "row": #, "col": #, "result": "miss"}` 
        Where `#` = the row and column of the cell to attack.  
    * When the game is over, the server will send to both clients `{"type": "GAME_OVER", "winner": #}`  
    Where `#` = 1 or 2 to indicate the winning player.
    * For a rematch, each client may send `{"type": "NEW_GAME"}` after `GAME_OVER`. The server starts a new round only after both players request it, and then sends `{"type": "NEW_GAME", "game_uuid": uuid}` to both clients.

* Connection Termination:
    * Normal termination: After `GAME_OVER`, if either player decides not to do a rematch, the client closes its socket and exits. The server picks up on the closed socket the next time it calls `recv()` (which returns empty) and then cleans up that player's slot in the game.
    * Mid-game disconnect: If a client closes unexpectedly during placement or battle, the server marks that player as disconnected and kicks off a 5 minute resume window (see Section 2). If the original client manages to reconnect within that window using a `RESUME` message, the game picks up from where it left off. Otherwise the remaining player gets a `GAME_OVER` with `reason: "opponent_timeout"` and the game gets removed from server memory.
    * Server shutdown: The server catches `KeyboardInterrupt` (Ctrl+C) and closes its listening socket so no new connections come in. Active client sockets don't get explicitly notified though, they'll just see their next `recv()` fail and treat it as a disconnect. This is a known limitation, a graceful shutdown broadcast is something we'd add in a future revision.

## **7\. Academic Integrity & References**

* **Code Origin:**
    * A portion of the code and this README layout was adopted from the provided sample [repository](https://github.com/mariam-bebawy/CMPT371_A3_Socket_Programming/) along with the provided demo videos for this assignment. The core protocol, socket programming, and game design were written by the group. Although the README shares a similar structure to the sample repository, the content is original and written by the group, specifically for this project.

* **GenAI Usage:**
    * Claude Code assisted with creation of the GUI suitable for the Battleship game.

* **References:**  
    * [CMPT371 Assignment 3 - TA guided tutorial videos](https://www.youtube.com/playlist?list=PL-8C2cUhmkO1yWLTCiqf4mFXId73phvdx&si=FIq3OxypbBeWHhYm)
    * [CMPT371 Assignment 3 - Sample repository](https://github.com/mariam-bebawy/CMPT371_A3_Socket_Programming/)
    * [Python Socket Programming HOWTO](https://docs.python.org/3/howto/sockets.html)