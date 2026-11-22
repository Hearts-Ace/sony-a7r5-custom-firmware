# R5 modified-cable quick start

1. **Buy:** a **Waveshare RP2040 Zero**, a **Sony Multi breakout cable exposing four signals: RX, TX, RESET and GND**, and USB data cables for the board and camera. An ordinary four-wire USB cable alone is insufficient.
2. **Wire:** **GP28 → camera RX; GP29 → camera TX; GP27 → RESET; GND → GND**. A phone repair shop can solder the connections and check for shorts. Follow the [connector pinout](https://github.com/DavidBuchanan314/ILCE-7M4-RE/blob/main/images/multi_pinout.png), not wire colors. Do not connect signal pins to 5 V.
3. **Flash the board:** download [uart_boot.uf2](https://github.com/Hearts-Ace/sony-a7r5-custom-firmware/raw/refs/heads/main/tools/rp2040-bridge/uart_boot.uf2), our verified **RP2040 Zero / OPEN_DRAIN** build. Hold BOOT/BOOTSEL while plugging the board into your computer, then copy the file to **RPI-RP2**. It restarts automatically.
4. **Ask an AI coding assistant with local terminal access** to read [this repository](https://github.com/Hearts-Ace/sony-a7r5-custom-firmware). Give it this prompt:

   > Clone this repository and read its README and device-tool instructions. Follow the RP2040 modified-cable workflow for my R5: make and verify a complete original backup; prepare update trust; install firmware 4.65 from the memory card; then freshly read this camera's settings and check the six FL2/FL3 slots and color parameters. Preserve the original backup, verify current-device data before every write, and fully read back afterward. Never use another camera's settings image. Identify missing tools or inputs instead of inventing commands.

5. **Order:** full backup → modified-cable trust setup → 4.65 card update → modified-cable settings check/repair → restart and test photos.

The owner confirmed 4.65 passed their camera testing on 2026-11-21. Each new camera still needs its own backup and checks. The repository provides the six-slot tool, but not a complete one-click backup/trust/color-install workflow; obtain the separate bootloader package and camera firmware from the project owner. The UF2 above only runs the RP2040 bridge.
