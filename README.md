# Polygon Metre
A simple time signature vizualizer video tool with a polygon graphic. It's not the only one out there, but this one caters to me.

## Requirements
```sh
pip install moviepy pillow numpy
```

## Usage
Visualizations are generated from a JSON file containing relevant data (audio location, timings info) in the following structure:

```json
{
  "wav": "location/audio_file.wav",
  "map": [
    {"sig": [4, 4], "bpm": 120, "bars": 8},
    {"sig": [3, 4], "bpm": 140, "bars": 4},
    {"sig": [7, 8], "bpm": 160, "bars": 2}
  ]
}
```

A visualization can then be generated using a simple function call:
```py
import create_signature_video
create_signature_video("song_data.json", "output.mp4", scale=2)
```
With parameters
- `map_file`: Path to JSON file with timing data
- `output_file`: Output video filename (default: "output.mp4")
- `scale`: Video resolution multiplier (default: 1, creates 200x200px video)

Before usage, change the values of FONT_DEF, FONT_SIG and ACCENT_COLOR to what you personally want.

## Output
Currently, this script creates an MP4 video with:
200x200 pixel resolution (multiplied by scale), 24 FPS and synchronized audio from the input WAV file.