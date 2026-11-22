# RP2040 Zero camera boot bridge

[Download uart_boot.uf2](https://github.com/Hearts-Ace/sony-a7r5-custom-firmware/raw/refs/heads/main/tools/rp2040-bridge/uart_boot.uf2) · [Beginner guide](../../docs/MODIFIED_CABLE_QUICKSTART.en.md) · [SHA256](SHA256SUMS)

Board: **Waveshare RP2040 Zero**. Build: **OPEN_DRAIN**, without UART_TX; uart_boot 1, 48000 baud. This is the 153,088-byte build used by this project, not camera firmware or MicroPython.

Hold BOOT/BOOTSEL while connecting the board to a computer. Copy uart_boot.uf2 to the **RPI-RP2** drive; the board restarts automatically.

| RP2040 pin | Camera Multi signal |
|---|---|
| GP28 | RX |
| GP29 | TX |
| GP27 | RESET |
| GND | GND |

Use a Sony Multi breakout that exposes these signals. The four wires of an ordinary USB cable are not these four signals. Confirm connector orientation with the [upstream pinout](https://github.com/DavidBuchanan314/ILCE-7M4-RE/blob/main/images/multi_pinout.png); do not identify wires by color or feed 5 V into signal pins.

Built on 2026-10-13 from [DavidBuchanan314/ILCE-7M4-RE](https://github.com/DavidBuchanan314/ILCE-7M4-RE/tree/2328d18/tools/uart_boot), using Arduino-Pico 6.3.0 and board rp2040:rp2040:waveshare_rp2040_zero, with -DOPEN_DRAIN. Source files: uart_boot.ino and serialboot.pio. The UF2 family, block structure, GPIO immediates and open-drain-only PIO were checked in the original build record; size/hash and all 299 UF2 blocks were checked again before this upload.

This third-party build is attributed to its upstream authors; the repository's MIT license does not relicense it. The camera-side RAM payload and bootloader script package are separate and are not included.
