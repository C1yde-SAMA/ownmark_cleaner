# OwnMark Cleaner

OwnMark Cleaner is a local web-based video cleanup tool for repairing selected watermark areas in videos you own or are authorized to edit.

It lets you load the first frame of a video, draw one or more regions, split each selected area into smaller tiles, apply local inpainting, Gaussian blur, rounded edges, feathered blending, and export the final MP4 video.

> This project is intended only for videos you own, created yourself, watermarked yourself, or have explicit permission to edit. Do not use this tool to bypass third-party platform watermarks, copyright notices, ownership marks, or usage restrictions.

---

## Features

- Runs locally on your machine
- Simple web UI
- Draw watermark regions directly on the first video frame
- Supports multiple selected regions
- Splits large regions into smaller tiles to reduce obvious patch artifacts
- Three processing presets: Fine, Normal, Strong
- Adjustable Gaussian blur size and strength
- Rounded region edges with feathered transitions
- Progress bar during processing
- Keeps the original audio track
- Exports MP4 videos

---

## Best Use Cases

This tool works best for:

- Your own generated videos
- Your own added watermark, logo, text, or corner mark
- Small static watermark areas
- Fixed-position watermark regions
- Simple background areas

This tool is not ideal for:

- Moving watermarks
- Very large watermarks covering the main subject
- Watermarks over faces, hands, text, or complex textures
- Videos you do not own or are not authorized to edit
- Third-party platform copyright watermarks

---

## Requirements

You need:

- Python 3.9+
- FFmpeg
- Flask
- OpenCV
- NumPy

Check Python:

```bash
python --version
```

Check FFmpeg:

```bash
ffmpeg -version
```

Install FFmpeg on macOS:

```bash
brew install ffmpeg
```

On Windows, install FFmpeg and add the `bin` folder to your system PATH.

---

## Installation

Go to the project folder:

```bash
cd ownmark-cleaner
```

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it:

### macOS / Linux

```bash
source .venv/bin/activate
```

### Windows PowerShell

```powershell
.venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install flask opencv-python numpy tqdm
python -m pip install -e .
```

---

## Start the Web App

Run this from the project root:

```bash
PYTHONPATH=src python webapp.py
```

On Windows PowerShell:

```powershell
$env:PYTHONPATH="src"
python webapp.py
```

Then open:

```text
http://127.0.0.1:7860
```

---

## Where to Put Your Video

You have two options.

### Option 1: Put the video in the project root

Example:

```text
ownmark-cleaner/
├── input.mp4
├── webapp.py
├── templates/
├── src/
└── README.md
```

In the web UI, enter:

```text
input.mp4
```

Then click:

```text
Load First Frame
```

### Option 2: Upload from the Web UI

Click:

```text
Choose File → Upload and Load
```

Uploaded videos are stored in:

```text
web_uploads. Start the web app.
2. Load a video or upload one.
3. Click **Load First Frame**.
4. Draw one or more regions over the watermark area.
5. Choose processing settings.
6. Click **Start Processing**.
7. Wait for the progress bar to finish.
8. Download the processed video.

Output videos are saved in:

```text
web_outputs/
```

Preview images are saved in:

```text
web_previews/
```

---

## Settings

### Tiles Per Selected Region

This controls how many smaller pieces each selected region is split into.

Options:

```text
1 / 4 / 9 / 16 / 25 / 36
```

Recommended:

| Situation | Suggested value |
|---|---|
| Very small watermark | 4 |
| Normal watermark | 9 |
| Large patch looks too obvious | 16 or 25 |
| Large region with visible mosaic artifacts | 25 or 36 |

More tiles usually look more natural, but processing becomes slower.

---

### Processing Mode

Options:

```text
Fine / Normal / Strong
```

| Mode | Best for |
|---|---|
| Fine | More natural result, less blur |
| Normal | Balanced cleanup and natural look |
| Strong | More aggressive removal when watermark is still visible |

Strong mode automatically:

- Expands the processing area
- Runs repair twice
- Uses stronger blur
- Covers watermark remnants more aggressively
- May look blurrier

---

### Gaussian Blur Size

Controls the blur radius.

Options:

```text
0 / 7 / 15 / 31 / 51 / 71
```

| Value | Effect |
|---|---|
| 0 | No blur |
| 7 | Light blur |
| 15 | Medium blur |
| 31 | Noticeable blur |
| 51 | Strong blur |
| 71 | Very strong blur |

Increase this if the watermark remains visible.  
Decrease it if the edited area looks too blurry.

---

### Gaussian Blur Strength

Controls how much of the blurred result is blended into the selected area.

Options:

```text
0 / 0.25 / 0.50 / 0.75 / 0.95 / 1.00
```

| Value | Effect |
|---|---|
| 0 | No blur |
| 0.25 | Light blend |
| 0.50 | Medium blend |
| 0.75 | Strong blend |
| 0.95 | Very strong blend |
| 1.00 | Full blur result |

---

## Recommended Presets

### Natural Result

```text
16 tiles + Fine + Blur Size 15 + Blur Strength 0.50
```

Use this when the area should stay as natural as possible.

---

### Balanced Result

```text
16 tiles + Normal + Blur Size 31 + Blur Strength 0.75
```

Good for most cases.

---

### Strong Cleanup

```text
25 tiles + Strong
```

Use this when the watermark is still visible.

---

### Reduce Mosaic Look

```text
25 tiles + Fine + Blur Size 15 + Blur Strength 0.50
```

Use this when the selected area looks like one obvious patch.

---

## Tips

### Keep the selected area small

Only cover the watermark area.  
A larger selection is more likely to look blurry or artificial.

### Split long watermarks into multiple selections

For a long watermark, drawing several smaller regions often looks better than drawing one huge rectangle.

### Test on a short video first

Before processing a long video, test your settings on a short clip.

### If the result is too blurry

Try:

```text
Fine mode
Lower blur size
Lower blur strength
More tiles
```

Example:

```text
25 tiles + Fine + Blur Size 15 + Blur Strength 0.50
```

### If the watermark is still visible

Try:

```text
Normal or Strong mode
Higher blur size
Higher blur strength
Slightly larger selection
```

Example:

```text
25 tiles + Strong
```

---

## Troubleshooting

### ModuleNotFoundError: No module named 'ownmark_cleaner'

Run:

```bash
python -m pip install -e .
```

Or start with:

```bash
PYTHONPATH=src python webapp.py
```

On Windows:

```powershell
$env:PYTHONPATH="src"
python webapp.py
```

---

### ffmpeg not found

FFmpeg is not installed or not added to PATH.

Check:

```bash
ffmpeg -version
```

Install FFmpeg and make sure the command works in your terminal.

---

### The web app does not open

Make sure your terminal shows:

```text
Running on http://127.0.0.1:7860
```

Then open:

```text
http://127.0.0.1:7860
```

If the port is already in use, stop the old process:

```bash
control + c
```

Then restart:

```bash
PYTHONPATH=src python webapp.py
```

---

### I changed the code but the UI did not update

Restart the server:

```bash
control + c
PYTHONPATH=src python webapp.py
```

Then hard refresh the browser:

```text
macOS: Command + Shift + R
Windows: Ctrl + F5
```

---

### Progress bar does not move

Possible reasons:

- The video is very short and finishes quickly
- The backend task failed
- The page is using an old cached version
- FFmpeg is missing or stuck

Check the terminal output for errors.

---

### Output video has no sound

The app tries to copy the original audio by default.  
If audio copy fails, change this in the code:

```python
audio="copy"
```

to:

```python
audio="aac"
```

---

## Project Structure

```text
ownmark-cleaner/
├── README.md
├── webapp.py
├── templates/
│   └── index.html
├── src/
│   └── ownmark_cleaner/
│       ├── __init__.py
│       ├── video_io.py
│       ├── detection.py
│       └── inpaint.py
├── web_uploads/
├── web_outputs/
├── web_previews/
├── requirements.tcommit -m "Initial commit: OwnMark Cleaner web UI"
```

Add your remote repository:

```bash
git branch -M main
git remote add origin <your-repo-url>
git push -u origin main
```

---

## Legal Notice

Use this project only for:

- Videos you own
- Videos you created
- Videos you watermarked yourself
- Videos you are explicitly authorized to edit

Do not use it to:

- Remove third-party platform watermarks
- Remove copyright marks from someone else's work
- Bypass usage restrictions
- Misrepresent video ownership or origin

You are responsible for ensuring your usage is legal and ethical.

---

## License

MIT License
