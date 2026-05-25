"""
System constants for P2P Chat.
"""

# ─── Protocol ──────────────────────────────────────────────
HEADER_SIZE = 4                      # bytes, message length prefix (big-endian)
MAX_MESSAGE_SIZE = 10 * 1024 * 1024  # 10 MB

# ─── Message Types: Peer ↔ Bootstrap ───────────────────────
MSG_REGISTER = "REGISTER"
MSG_REGISTER_ACK = "REGISTER_ACK"
MSG_LOGIN = "LOGIN"
MSG_LOGIN_ACK = "LOGIN_ACK"
MSG_HEARTBEAT = "HEARTBEAT"
MSG_HEARTBEAT_ACK = "HEARTBEAT_ACK"
MSG_PEER_UPDATE = "PEER_UPDATE"
MSG_GET_PEERS = "GET_PEERS"
MSG_PEERS_LIST = "PEERS_LIST"
MSG_DISCONNECT = "DISCONNECT"
MSG_STORE_OFFLINE = "STORE_OFFLINE"

# ─── Message Types: Peer ↔ Peer ───────────────────────────
MSG_CHAT_MESSAGE = "CHAT_MESSAGE"
MSG_CHAT_ACK = "CHAT_ACK"
MSG_GROUP_MESSAGE = "GROUP_MESSAGE"
MSG_GROUP_ACK = "GROUP_ACK"
MSG_KEY_EXCHANGE = "KEY_EXCHANGE"
MSG_KEY_EXCHANGE_ACK = "KEY_EXCHANGE_ACK"
MSG_TYPING = "TYPING"

# ─── Message Types: Group Management ──────────────────────
MSG_CREATE_GROUP = "CREATE_GROUP"
MSG_CREATE_GROUP_ACK = "CREATE_GROUP_ACK"
MSG_GROUP_INVITE = "GROUP_INVITE"
MSG_GET_GROUPS = "GET_GROUPS"
MSG_GROUPS_LIST = "GROUPS_LIST"
MSG_ADD_GROUP_MEMBER = "ADD_GROUP_MEMBER"
MSG_REMOVE_GROUP_MEMBER = "REMOVE_GROUP_MEMBER"
MSG_GROUP_MEMBER_ADDED = "GROUP_MEMBER_ADDED"
MSG_GROUP_MEMBER_REMOVED = "GROUP_MEMBER_REMOVED"

# ─── Peer Update Actions ──────────────────────────────────
ACTION_JOINED = "joined"
ACTION_LEFT = "left"

# ─── Status ────────────────────────────────────────────────
STATUS_ONLINE = "online"
STATUS_OFFLINE = "offline"
STATUS_SUCCESS = "success"
STATUS_ERROR = "error"

# ─── Heartbeat ─────────────────────────────────────────────
DEFAULT_HEARTBEAT_INTERVAL = 15  # seconds
DEFAULT_HEARTBEAT_TIMEOUT = 30   # seconds

# ─── Reliable Delivery ────────────────────────────────────
ACK_TIMEOUT = 5          # seconds to wait for ACK
MAX_RETRIES = 3          # max retry attempts
RETRY_BASE_DELAY = 2     # base delay in seconds (exponential backoff)

# ─── Encryption ───────────────────────────────────────────
RSA_KEY_SIZE = 2048      # bits
AES_KEY_SIZE = 32        # bytes (256-bit)
AES_IV_SIZE = 16         # bytes (128-bit)

# ─── Database ─────────────────────────────────────────────
DB_NAME = "p2p_chat"
COLLECTION_USERS = "users"
COLLECTION_OFFLINE_MESSAGES = "offline_messages"
COLLECTION_GROUPS = "groups"
COLLECTION_CHAT_HISTORY = "chat_history"

# ─── Offline Message TTL ──────────────────────────────────
OFFLINE_MSG_TTL_DAYS = 7
