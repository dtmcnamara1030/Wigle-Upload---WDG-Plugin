# Watch Dogs Go — WiGLE Sync Plugin

An in-game plugin for the [Watch Dogs Go](https://github.com/LOCOSP/esp32-watch-dogs) game running on the ClockworkPi uConsole. This plugin allows players to upload their wardriving CSV logs directly to WiGLE.net from their device using an interactive retro-themed Pyxel UI overlay.

## Features
- **Interactive UI Overlay**: Full-screen Pyxel menu offering options to Upload All, Upload Latest, Test Credentials, and check pending logs.
- **Auto-Discovery**: Scans all `loot/*/wardriving.csv` logs automatically.
- **Duplicate Prevention**: Keeps track of uploaded drives using a local state file so you never upload the same log twice.
- **Asynchronous Sync**: Uploads are performed in background threads so the game screen never stutters or freezes.
- **Dynamic File Naming**: Uploads files as `WDG_<SessionDate>_Wigle.csv` making them easy to identify on your WiGLE dashboard.

---

## Installation

### 1. Copy the Plugin
Download **`wigle_upload.py`** and place it in the `plugins/` directory of your `WatchDogsGo` game folder:
```text
WatchDogsGo/
└── plugins/
    └── wigle_upload.py
```

### 2. Install Python Dependencies
The plugin requires the Python `requests` library. Install it inside your game's virtual environment:
```bash
cd WatchDogsGo
./.venv/bin/pip install requests
```

### 3. Add Your Credentials
Open (or create) the `secrets.conf` file in the root of your `WatchDogsGo` folder:
```bash
nano secrets.conf
```
Add your WiGLE developer API credentials (which you can generate on the Account page at [wigle.net](https://wigle.net)):
```ini
WDG_WIGLE_NAME=AIDxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
WDG_WIGLE_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```
*Note: Make sure to use your **API Name** (starts with `AID...`) and not your standard website login username.*

---

## Usage
1. Run the game.
2. Go to the **PLUGINS** tab in the main menu.
3. Press the **`i`** key to open the **WiGLE Sync** overlay.
4. Use the **Up/Down Arrow Keys** to navigate.
5. Highlight **`Upload All`** (or **`Upload Latest`**) and press **`ENTER`** to sync!
