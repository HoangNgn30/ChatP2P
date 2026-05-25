# 🔒 P2P Chat System

Hệ thống chat ngang hàng (Peer-to-Peer) cho phép nhiều người dùng trao đổi tin nhắn trực tiếp qua mạng với mã hóa End-to-End.

##  Tính năng

- **Chat P2P trực tiếp** – Tin nhắn đi trực tiếp giữa các peer, không qua server
- **Chat nhóm** – Tạo nhóm và gửi tin nhắn tới tất cả thành viên
- **Mã hóa E2E** – RSA-2048 + AES-256-CBC bảo vệ mọi tin nhắn
- **Peer Discovery** – Bootstrap server giúp peer tìm nhau
- **Online/Offline** – Hiển thị trạng thái realtime
- **Store-and-forward** – Lưu tin nhắn khi peer offline, gửi lại khi online
- **Lịch sử chat** – Lưu trữ trên MongoDB Atlas
- **GUI Desktop** – Giao diện PyQt6 dark theme đẹp mắt

## 🚀 Cài đặt

```bash
cd ChatP2Ppython
# 1. Tạo virtual environment  
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux/Mac

# 2. Cài dependencies
pip install -r requirements.txt

(Sử dụng nếu cần thiết)
#python -m pip install -r requirements.txt
#pip install PyQt6
#pip install colorlog

# 3. Cấu hình
copy .env.example .env
# Sửa MONGODB_URI trong .env
```

## 🏃 Chạy

```bash
cd ChatP2Ppython

# 2. Cài dependencies

pip install PyQt6
pip install colorlog


# Terminal 1: Bootstrap Server
python run_bootstrap.py

# Terminal n : Peer (mở GUI)
python run_peer.py
#Thay đổi Cổng peer cho các peer khác nhau (5001++)


## 🧪 Test

```bash
python -m pytest tests/ -v
```

## 📁 Cấu trúc

```
├── bootstrap_server/   # Bootstrap/Tracker Server
├── peer/               # Peer Node (Client + Server)
├── network/            # TCP Protocol layer
├── crypto/             # RSA + AES Encryption
├── database/           # MongoDB repositories
├── gui/                # PyQt6 GUI
├── utils/              # Config, Logger, Constants
├── tests/              # Unit tests
├── run_bootstrap.py    # Entry: chạy bootstrap server
└── run_peer.py         # Entry: chạy peer + GUI
```

## 🔧 Công nghệ

- **Python 3.10+** + asyncio
- **PyQt6** – Desktop GUI
- **MongoDB Atlas** – Cloud database
- **RSA + AES** – End-to-End Encryption
- **TCP Sockets** – Network communication

---

