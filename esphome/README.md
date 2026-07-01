# Waveshare ESP32-S3-AUDIO-Board — ESPHome

ESPHome configuration that adopts the
[Waveshare ESP32-S3-AUDIO-Board](https://www.waveshare.com/esp32-s3-audio-board.htm)
as a **Home Assistant Voice Assistant satellite** with on-device wake-word
detection, media playback, TTS announcements, three capacitive keys and the
7-LED surround RGB ring.

## Files

| File | Purpose |
|------|---------|
| `waveshare-esp32-s3-audio.yaml` | The device configuration. |
| `secrets.yaml` | Wi-Fi / API / OTA credentials (you create this). |

## Pin mapping

| Function | GPIO / Address | Notes |
|----------|----------------|-------|
| I2S MCLK | GPIO12 | |
| I2S BCLK | GPIO13 | shared DAC + ADC |
| I2S LRCLK/WS | GPIO14 | shared DAC + ADC |
| I2S DIN (mic) | GPIO15 | ES7210 → ESP |
| I2S DOUT (speaker) | GPIO16 | ESP → ES8311 |
| I2C SDA | GPIO11 | |
| I2C SCL | GPIO10 | |
| ES8311 DAC | I2C `0x18` | speaker codec |
| ES7210 ADC | I2C `0x40` | dual-mic array |
| TCA9555 expander | I2C `0x20` | keys + amp enable |
| PCF85063 RTC | I2C `0x51` | |
| WS2812 RGB ring | GPIO38 | 7 LEDs |
| Amp enable | TCA9555 EXIO08 | |
| Key: Vol− / Play-Pause / Vol+ | TCA9555 EXIO09 / EXIO10 / EXIO11 | |
| BOOT button | GPIO0 | triple-click toggles VA |
| Battery ADC | GPIO8 | verify divider ratio |
| microSD | CLK 40 / CMD 42 / D0 41 | not configured here |

## Why the ES8311 is the I2S master

The ES8311 (DAC) and ES7210 (ADC) sit on **one shared I2S bus** — they use the
same BCLK and LRCLK lines. Only one device can drive those clocks. If the
ESP32's speaker peripheral drove them, the clocks would stop whenever no audio
was playing, and the microphone (and wake word) would go deaf.

So the ES8311 is put into **master mode** (`force_master: true`); it generates
BCLK/LRCLK continuously, both ESP32 I2S peripherals run as `secondary`, and the
shared pins are declared with `allow_other_uses: true`.

Mainline ESPHome's `es8311` component can't be forced into master mode, so the
config pulls a patched fork via `external_components`:

```yaml
external_components:
  - source:
      type: git
      url: https://github.com/sw3Dan/waveshare-s2-audio_esphome_voice
      ref: main
    components: [es8311]
```

Everything else (`es7210`, `pca9554`, `i2s_audio`, `micro_wake_word`,
`voice_assistant`, `mixer`/`resampler` speakers) is stock ESPHome.

## Setup

1. Create `esphome/secrets.yaml`:

   ```yaml
   wifi_ssid: "YourNetwork"
   wifi_password: "YourPassword"
   # Generate a key: `openssl rand -base64 32`
   api_encryption_key: "base64-32-byte-key"
   ota_password: "some-ota-password"
   ```

2. Flash (first time over USB-C, then OTA):

   ```bash
   cd esphome
   esphome run waveshare-esp32-s3-audio.yaml
   ```

3. Adopt the device in Home Assistant → **Settings ▸ Devices & Services**, then
   assign it to a Voice Assistant pipeline
   (**Settings ▸ Voice assistants**).

Say **"Okay Nabu"** to trigger the assistant. The LED ring shows blue while
listening, amber while thinking, green while speaking, and red on error.

## Notes & options

- **microSD / camera / LCD headers** are not configured here — they aren't
  needed for a voice satellite. Add the `sd_mmc_card`, `esp32_camera`, or a
  `display` component if you want them.
- **Amp hiss:** the amplifier is held enabled (`restore_mode: ALWAYS_ON`). If
  idle hiss is a problem, gate `amp_enable` on speaker start/stop instead.
- **Wake word:** swap `okay_nabu` for `hey_jarvis`/`hey_mycroft` under
  `micro_wake_word:`, or set `use_wake_word: true` on `voice_assistant` and
  remove `micro_wake_word` to use HA-side (streaming) wake word.
