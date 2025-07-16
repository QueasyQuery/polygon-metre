import json
from moviepy import AudioFileClip, CompositeVideoClip, VideoClip
from moviepy.video.VideoClip import TextClip
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

FONT_DEF = Path('C:/Users/quint/AppData/Local/Microsoft/Windows/Fonts/JetBrainsMono[wght].ttf')
FONT_SIG = Path('C:/Users/quint/AppData/Local/Microsoft/Windows/Fonts/JetBrainsMono-ExtraBold.ttf')
ACCENT_COLOR = (0,100,255)
AA_SCALE = 2

def create_signature_video(map_file, output_file="output.mp4",scale=1):
    ''' Creates a simple time signature visualization with a polygon graphic,
        using a json file with relevant information. Exports a default video
        size of 200x200, can be higher with scale=2, 3 etc...'''
    # load json
    with open(map_file, 'r') as f:
        data = json.load(f)

    # load audio from json
    audio = AudioFileClip(data['wav'])
    total_duration = audio.duration  # in seconds

    # get time segments from json
    *time_segments, current_time = _get_segments(data)

    # Create video text clips for each segment
    clips = []
    for i,segment in enumerate(time_segments):
        # encode next segment in segment
        segment['next'] = time_segments[i + 1] if i + 1 < len(time_segments) else None
        # clips put on top
        clips.append(_polygon_clip(segment,scale))
        clips.append(_sig_clip(segment,scale))
        clips.append(_bpm_clip(segment,scale))
        clips.append(_next_clip(segment,scale))
        clips.append(_preview_clip(segment, scale))

    # composite and export
    resolution = (200*scale, 200*scale)
    video = CompositeVideoClip(clips, size=resolution).with_duration(min(current_time, total_duration)).with_audio(audio)
    video.write_videofile(output_file, codec='libx264', audio_codec='aac', fps=24)

def _get_segments(data):
    current_time = 0.0
    for segment in data['map']:
        sig = segment['sig']
        bpm = segment['bpm']
        bars = segment['bars']

        beats_per_bar = sig[0]
        beat_duration = 60 / bpm
        segment_duration = bars * beats_per_bar * beat_duration

        # save calculated segment info
        yield {'start': current_time,'end': current_time + segment_duration,'dur': segment_duration,'sig': sig,'bpm': bpm,'last':False}

        # go to start of next segment
        current_time += segment_duration
    # dummy final bar
    yield {'start': current_time,'end': current_time+sig[0]*60/bpm,'dur': sig[0]*60/bpm,'sig': sig,'bpm': bpm,'last':True}
    # final time
    yield current_time + segment_duration

def _sig_clip(segment,scale):
    ''' creates clip with the time signature'''
    sig_text = f"{segment['sig'][0]}\n{segment['sig'][1]}"
    clip = TextClip(
        text=sig_text,
        font_size=25*scale,
        color='white',
        font=FONT_SIG,
        text_align='center',
        method='label',
    ).with_duration(segment['dur']).with_start(segment['start'])
    return clip.with_position(((100*scale-clip.w//2),(100*scale-clip.h//2)))

def _bpm_clip(segment,scale):
    ''' creates clip with the BPM'''
    sig_text = f"BPM {segment['bpm']}"
    return TextClip(
        text=sig_text,
        font_size=10*scale,
        color='white',
        font=FONT_DEF,
        text_align='left',
        method='label',
        bg_color='black'
    ).with_position((3*scale,0)).with_duration(segment['dur']).with_start(segment['start'])

def _next_clip(segment,scale):
    ''' creates clip with the next time signature'''
    # No preview if last or second to last segment
    if (segment.get('next') == None) or (segment['next'].get('last') == True):
        return VideoClip(lambda t: np.zeros((200*scale, 200*scale,3),dtype=np.uint8),duration=0)
    # text gen
    sig_text = f"{segment['next']['sig'][0]}/{segment['next']['sig'][1]} NEXT"
    return TextClip(
        text=sig_text,
        font_size=10*scale,
        text_align='right',
        horizontal_align='right',
        color='white',
        font=FONT_DEF,
        method='caption',
        size=(63*scale, None)
    ).with_position((134*scale, 0)).with_duration(segment['dur']).with_start(segment['start'])

def _polygon_clip(segment,scale):
    ''' creates clip with the polygon visual.'''
    n_beats = segment['sig'][0]
    bpm = segment['bpm']
    dur = segment['dur']

    polygon_clip = make_polygon_filler(
        beats_per_bar=n_beats,
        bpm=bpm,
        bar_duration=dur,
        scale=scale,
        last=segment['last']
    ).with_start(segment['start'])
    return polygon_clip

def _preview_clip(segment, scale):
    ''' creates clip with the next time signature's polygon.'''
    # No preview if last or second to last segment
    if (segment.get('next') == None) or (segment['next'].get('last') == True):
        return VideoClip(lambda t: np.zeros((200*scale, 200*scale,3),dtype=np.uint8),duration=0)

    beats_per_bar = segment['sig'][0]
    preview_start = segment['next']['start'] - beats_per_bar * 60 / segment['bpm']
    preview_end = segment['next']['start']

    def make_frame(t):
        img_size = 200 * scale * AA_SCALE
        img = Image.new("RGBA", (img_size, img_size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        cx, cy = img_size // 2, img_size // 2
        radius = img_size * 0.4

        # polygon
        angles = np.linspace(-0.5*np.pi, 1.5 * np.pi, segment['next']['sig'][0], endpoint=False)
        points = [(cx + radius * np.cos(a), cy + radius * np.sin(a)) for a in angles]
        opacity = (t/(preview_end-preview_start))**1.5
        draw.polygon(points, outline=(*ACCENT_COLOR, int(255*opacity)), width=scale*AA_SCALE)

        # Anti-Alias by resizing back to standard
        return np.array(img.resize((int(200 * scale), int(200 * scale)), Image.LANCZOS))

    return VideoClip(make_frame, duration=preview_end - preview_start).with_start(preview_start)

def make_polygon_filler(beats_per_bar, bpm, bar_duration, scale, last=False,fade_beats=3):
    ''' logic for the polygon slice filling. '''
    beat_duration = 60 / bpm

    def make_frame(t):
        img_size = 200 * scale * AA_SCALE
        img = Image.new("RGB", (img_size, img_size), (0, 0, 0))
        draw = ImageDraw.Draw(img)

        # polygon properties
        cx, cy = img_size // 2, img_size // 2
        radius = img_size * 0.4

        # get current beat (float for sub-beat precision) and beat-phase
        beat_pos = (t % bar_duration) / beat_duration
        beat_phase = ((t % bar_duration) / beat_duration) % beats_per_bar

        # inner polygon coordinates
        angles = np.linspace(-0.5*np.pi, 1.5 * np.pi, beats_per_bar, endpoint=False)
        points = [(cx + (radius-5*scale*AA_SCALE) * np.cos(a), cy + (radius-5*scale*AA_SCALE) * np.sin(a)) for a in angles]

        # outer outline
        outer_points = [(cx + radius * np.cos(a), cy + radius * np.sin(a)) for a in angles]
        draw.polygon(outer_points, outline="white",width=scale*AA_SCALE)

        # fading slices
        for i in range(beats_per_bar):
            beats_ago = beat_phase - i
            if (beat_pos - i < 0) and not last:
                 continue
            if beats_ago < 0:
                beats_ago += beats_per_bar
            
            if (beats_ago < fade_beats) or last:
                x = 1-(beats_ago / fade_beats)
                fade = x  # fade function,fade=(1->0) x=(1->0)
                brightness = int(255 * fade)
                color = (brightness, brightness, brightness)
                if i == 0:
                    color = (int(ACCENT_COLOR[0]* fade),int(ACCENT_COLOR[1]* fade),int(ACCENT_COLOR[2]* fade))
                if last:
                    color = (0,0,0)
                polygon_slice = [(cx, cy), points[i], points[(i + 1) % beats_per_bar]]
                draw.polygon(polygon_slice, fill=color)
        
        # top black polyon
        outer_points = [(cx + radius * 0.5 * np.cos(a), cy + radius * 0.5 * np.sin(a)) for a in angles]
        draw.polygon(outer_points, fill='black')

        # Anti-Alias by resizing back to standard
        return np.array(img.resize((int(200 * scale), int(200 * scale)), Image.LANCZOS))

    return VideoClip(make_frame, duration=bar_duration)
    