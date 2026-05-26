## TS‑TTS to MP4 Converter

Desktop GUI tool for converting `.tts` / transport‑stream recordings (and any other FFmpeg‑supported formats) into clean `.mp4` files, with **no quality loss by default**, live progress, and a modern, dark UI.

This repository currently consists of a single Python script, `convert.py`, which launches a Tkinter application wrapping `ffmpeg` / `ffprobe` on Windows.

---

<img width="1123" height="822" alt="Image" src="https://github.com/user-attachments/assets/9b78ee6a-8af7-4580-9aa7-9ed2c5cc2e77" />

### Features

- **Modern dark GUI**
  - Card‑style layout with clearly separated sections.
  - Input / output file pickers styled to match action buttons.
  - Large log console so you can see exactly what FFmpeg is doing.

- **Lossless or encoded conversion**
  - **Lossless stream copy (default)**  
    Copies all streams (`video`, `audio`, `subtitles`) directly into MP4 with `-c copy`, so there is **zero quality loss** and very fast conversion.
  - **Re‑encode to MP4 (H.264/AAC)**  
    Optional mode that converts to widely compatible H.264 video + AAC audio, with:
    - **CRF quality slider** (16–28, lower = better quality, larger file).
    - **Preset selector** (`ultrafast` → `veryslow`) to balance speed vs compression.

- **Media info panel (ffprobe)**
  - Shows resolution, codecs, duration, and file size (e.g. `1216x2160, H264 video + AAC audio · 19:09 · 303.4 MB`).
  - Updates automatically when you pick a new input file.

- **Live progress & logging**
  - Progress bar using FFmpeg `-progress` output (`out_time_ms`), with estimated percentage.
  - Streaming log window that shows FFmpeg output in real time for debugging.
  - **Cancel** button to terminate a running job cleanly.

- **“SweetAlert2‑style” success popup**
  - Custom modal dialog with a big green check mark when conversion finishes.
  - Shows the final output path.
  - Includes an **“Open folder”** button that opens the file location in Explorer.

---

### Requirements

- **OS**: Windows 10 or later (the script uses `os.startfile` and a Windows FFmpeg build).
- **Python**: 3.8+ (tested on modern 3.x).
- **FFmpeg + FFprobe (Windows build)**:
  - `ffmpeg.exe` and `ffprobe.exe` must be available on disk.
  - The script expects them in the same folder, with a configurable path.

---

### Setup

1. **Clone this repository**

   ```bash
   git clone https://github.com/needyamin/TS-TTS-to-MP4-Converter.git
   cd TS-TTS-to-MP4-Converter
   ```

2. **Install Python (if needed)**

   Download and install a recent Python 3 release from [`https://www.python.org/downloads/`](https://www.python.org/downloads/) and make sure `python` is on your PATH.

3. **Download FFmpeg for Windows**

   - Get a static Windows build of FFmpeg (which includes `ffprobe`) from e.g.:
     - [`https://ffmpeg.org`](https://ffmpeg.org) → Windows builds, or
     - A trusted build provider such as Gyan.dev / BtbN.
   - Extract it somewhere, for example:

     ```text
     C:\Users\<YOU>\Apps\ffmpeg\bin\ffmpeg.exe
     C:\Users\<YOU>\Apps\ffmpeg\bin\ffprobe.exe
     ```

4. **Point `convert.py` at your FFmpeg path**

   At the top of `convert.py` there is a constant:

   ```python
   FFMPEG_PATH = r"C:\Users\YAMiN\AppData\Local\Media Downloader\ffmpeg\ffmpeg.exe"
   ```

   Change this to match the full path of your own `ffmpeg.exe`.  
   Make sure that **`ffprobe.exe` is in the same folder** as `ffmpeg.exe` so the media‑info panel works.

---

### Running the converter

From the repository root (where `convert.py` lives):

```bash
python convert.py
```

This opens the main GUI window.

---

### Using the GUI

1. **Choose input file**
   - Click **“Browse…”** next to **Input file**.
   - Select a `.tts`, `.ts`, `.mp4`, or any other FFmpeg‑supported file.
   - The app will:
     - Auto‑fill **Output file** with the same name but `.mp4` extension.
     - Probe the file with `ffprobe` and show media info.

2. **Adjust output path (optional)**
   - Click **“Change…”** next to **Output file** if you want a different folder or filename.
   - If the file already exists, you’ll be asked whether to overwrite it.

3. **Pick conversion mode**
   - **Lossless stream copy (no quality loss)** – recommended when your player supports the codecs in the original file. Very fast.
   - **Re‑encode to MP4 (H.264/AAC)** – for maximum compatibility.
     - Adjust **Quality (CRF)** slider for more/less quality.
     - Choose a **Preset** for speed vs compression (e.g. `fast`, `medium`, `slow`).

4. **Start conversion**
   - Click **Start Conversion**.
   - The status line and progress bar update as FFmpeg runs.
   - The **Details** panel shows FFmpeg log output in real time.
   - You can click **Cancel** to stop an in‑progress job.

5. **Success dialog**
   - When done, a custom success window pops up:
     - Big check mark.
     - Output file path.
     - **Open folder** button to jump to the output location in Explorer.

---

### Notes on quality & performance

- **Lossless mode** uses FFmpeg with `-map 0 -c:v copy -c:a copy -c:s copy`, so no re‑encoding happens. The MP4 container is just remuxed, which is:
  - Extremely fast (usually close to disk speed).
  - Bit‑for‑bit identical for video and audio quality.
- **Encode mode** uses something like:
  - Video: `libx264` with your chosen **CRF** and **preset**.
  - Audio: `aac` at 192 kbps.
  - This trades CPU time and some quality loss for a more standard/compatible MP4.

---

### Troubleshooting

- **“ffmpeg.exe not found”**
  - Double‑check the `FFMPEG_PATH` in `convert.py` and make sure it points to a real `ffmpeg.exe` file.
  - Ensure you can run that exe manually (e.g. double‑click it or run from `cmd`).

- **Media info not shown**
  - The media info panel relies on `ffprobe.exe` from the same FFmpeg build.
  - Confirm that `ffprobe.exe` sits in the same folder as `ffmpeg.exe`.

- **Conversion fails immediately**
  - Check the **Details** log panel for FFmpeg error messages.
  - Verify that the input file actually exists and isn’t locked by another program.

---

### Roadmap / ideas

Some possible future enhancements for this tool:

- Queue / batch conversion of multiple files.
- Preset management (save your favorite CRF / preset combinations).
- Optional audio‑only extract (e.g. to `.mp3` / `.m4a`).
- Cross‑platform support (Linux/macOS) via path detection and `xdg-open` / `open`.

---

### License

This project is currently personal / experimental software.  
Add your preferred open‑source license here (e.g. MIT, Apache‑2.0) once you decide how you want others to use it.




