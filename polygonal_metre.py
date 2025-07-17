import json
import math
import numpy as np
from pathlib import Path
from PIL import Image, ImageDraw
from moviepy.video.VideoClip import TextClip
from moviepy import AudioFileClip, CompositeVideoClip, VideoClip

def create_signature_video(json_file:str, output_file="output.mp4", scale=1,
    font_def:str=None,font_sig:str=None, accent_color=(0,100,255), aa_scale=2):
    ''' Creates a simple time signature visualization with a polygon graphic,
        using a json file with relevant information. Exports a default video
        size of 200x200, can be higher with scale=2, 3 etc...
    '''
    # Default fonts
    if font_def is None: font_def = Path(__file__).parent/'fonts/JetBrainsMono-Light.ttf'
    if font_sig is None: font_sig = Path(__file__).parent/'fonts/JetBrainsMono-ExtraBold.ttf'

    # load json
    with open(json_file, 'r') as f: data = json.load(f)

    # load audio from json
    audio = AudioFileClip(data['wav'])
    total_duration = audio.duration  # in seconds

    # get time segments from json
    time_segments, final_time = _get_segments(data)

    # create clips for each segment
    clips = []
    for i,segment in enumerate(time_segments):
        # encode next segment in segment
        segment['next'] = time_segments[i + 1] if i + 1 < len(time_segments) else None
        # clips put on top of each other
        clips.append(_polygon_clip(segment, scale, accent_color, aa_scale))
        clips.append(_sig_clip(segment, scale, font_sig))
        clips.append(_bpm_clip(segment, scale, font_def))
        clips.append(_next_clip(segment, scale, font_def))
        clips.append(_bar_clip(segment, scale, accent_color))
        clips.append(_preview_clip(segment, scale, accent_color, aa_scale))
    clips = [clip for clip in clips if clip != None]

    # composite and export
    resolution = (200*scale, 200*scale)
    video = CompositeVideoClip(clips, size=resolution).with_duration(min(final_time, total_duration)).with_audio(audio)
    video.write_videofile(output_file, codec='libx264', audio_codec='aac', fps=24)

def _get_segments(data):
    current_time = 0.0
    segments = []
    for i,segment in enumerate(data['map']):
        sig = segment['sig']
        bpm = segment['bpm']
        bars = segment['bars']

        beats_per_bar = sig[0]
        bar_duration = beats_per_bar * 60 / bpm
        segment_duration = bars * bar_duration
        segment_end = current_time + segment_duration

        # save basic info about this segment in the previous segment
        if segments: segments[i-1]['next'] = {'sig': sig,'bpm': bpm}

        # save calculated segment info & go to start of next segment
        segments.append({'start': current_time,'end': segment_end,'dur': segment_duration,'sig': sig,'bpm': bpm, 'next':None})
        current_time += segment_duration

    # dummy final bar & final time
    dummy = {'start': current_time,'end': current_time+bar_duration,'dur': bar_duration,'sig': sig,'bpm': bpm, 'next':None}
    segments[-1]['next'] = dummy
    segments.append(dummy)
    final_time = current_time + segment_duration
    return segments, final_time

def _sig_clip(segment, scale, font_sig):
    ''' creates clip with the time signature'''
    sig_text = f"{segment['sig'][0]}\n{segment['sig'][1]}"
    clip = TextClip(
        text=sig_text,
        font_size=25*scale,
        color='white',
        font=font_sig,
        text_align='center',
        method='label',
    ).with_duration(segment['dur']).with_start(segment['start'])
    return clip.with_position(((100*scale-clip.w//2),(100*scale-clip.h//2)))

def _bpm_clip(segment, scale, font_def):
    ''' creates clip with the BPM'''
    sig_text = f"BPM {segment['bpm']}"
    return TextClip(
        text=sig_text,
        font_size=10*scale,
        color='white',
        font=font_def,
        text_align='left',
        method='label',
        bg_color='black'
    ).with_position((3*scale,0)).with_duration(segment['dur']).with_start(segment['start'])

def _next_clip(segment, scale, font_def):
    ''' creates clip with the next time signature'''
    # No preview if last or second to last segment
    if (segment.get('next') == None) or (segment.get('next').get('next') == None): return None

    # text gen
    sig_text = f"{segment['next']['sig'][0]}/{segment['next']['sig'][1]} NEXT"
    return TextClip(
        text=sig_text,
        font_size=10*scale,
        text_align='right',
        horizontal_align='right',
        color='white',
        font=font_def,
        method='caption',
        size=(63*scale, None)
    ).with_position((134*scale, 0)).with_duration(segment['dur']).with_start(segment['start'])

def _bar_clip(segment, scale, accent_color):
    ''' creates clip showing progress to next time signature'''
    # No preview if last or second to last segment
    if (segment.get('next') == None) or (segment.get('next').get('next') == None): return None

    # polygon
    def make_frame(t):
        img_size = 200 * scale
        img = Image.new("RGBA", (img_size, img_size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        fraction = t/segment['dur']
        corners = [((150+fraction*47)*scale,14*scale),(197*scale,17*scale)]
        color = accent_color if t > segment['dur'] - segment['sig'][0] * 60 / segment['bpm'] else (255,255,255)
        draw.rectangle(corners, color)
        return np.array(img)

    return VideoClip(make_frame, duration=segment['dur']).with_start(segment['start'])


def _polygon_clip(segment, scale, accent_color, aa_scale):
    ''' creates clip with the polygon visual.'''
    n_beats = segment['sig'][0]
    bpm = segment['bpm']
    dur = segment['dur']

    polygon_clip = make_polygon_filler(
        beats_per_bar=n_beats,
        bpm=bpm,
        bar_duration=dur,
        scale=scale,
        accent_color=accent_color,
        aa_scale=aa_scale,
        last=(segment['next'] == None)
    ).with_start(segment['start'])
    return polygon_clip

def _preview_clip(segment, scale, accent_color, aa_scale):
    ''' creates clip with the next time signature's polygon.'''
    # no preview if last or second to last segment
    if (segment.get('next') == None) or (segment.get('next').get('next') == None): return None

    beats_per_bar = segment['sig'][0]
    preview_end = segment['end']
    preview_start = preview_end - beats_per_bar * 60 / segment['bpm']


    def make_frame(t):
        img_size = 200 * scale * aa_scale
        img = Image.new("RGBA", (img_size, img_size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        cx, cy, radius = img_size // 2, img_size // 2, img_size * 0.4

        # polygon
        angles = np.linspace(-0.5*np.pi, 1.5 * np.pi, segment['next']['sig'][0], endpoint=False)
        points = [(cx + radius * np.cos(a), cy + radius * np.sin(a)) for a in angles]
        opacity = (math.pi**-1)*math.acos(1-2*(t/(preview_end-preview_start)))
        draw.polygon(points, outline=(*accent_color, int(255*opacity)), width=scale*aa_scale)

        # Anti-Alias by resizing back to standard
        if aa_scale == 1: return np.array(img)
        return np.array(img.resize((int(200 * scale), int(200 * scale)), Image.LANCZOS))

    return VideoClip(make_frame, duration=preview_end - preview_start).with_start(preview_start)

def make_polygon_filler(beats_per_bar, bpm, bar_duration, scale, accent_color, aa_scale, last=False, fade_beats=3):
    ''' logic for the polygon slice filling. '''
    beat_duration = 60 / bpm

    def make_frame(t):
        img_size = 200 * scale * aa_scale
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
        points = [(cx + (radius-5*scale*aa_scale) * np.cos(a), cy + (radius-5*scale*aa_scale) * np.sin(a)) for a in angles]

        # outer outline
        outer_points = [(cx + radius * np.cos(a), cy + radius * np.sin(a)) for a in angles]
        draw.polygon(outer_points, outline="white",width=scale*aa_scale)

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
                    color = (int(accent_color[0]* fade),int(accent_color[1]* fade),int(accent_color[2]* fade))
                if last:
                    color = (0,0,0)
                polygon_slice = [(cx, cy), points[i], points[(i + 1) % beats_per_bar]]
                draw.polygon(polygon_slice, fill=color)

        # top black polyon
        outer_points = [(cx + radius * 0.5 * np.cos(a), cy + radius * 0.5 * np.sin(a)) for a in angles]
        draw.polygon(outer_points, fill='black')

        # Anti-Alias by resizing back to standard
        if aa_scale == 1: return np.array(img)
        return np.array(img.resize((int(200 * scale), int(200 * scale)), Image.LANCZOS))

    return VideoClip(make_frame, duration=bar_duration)