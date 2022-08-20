import os
import numpy as np
import pygame as pg
import mido
import cv2


def get_note_range(midi_file):
    """ MIDIファイル中の最高音と最低音を取得 """
    note_min = 200
    note_max = -1

    for msg in mido.MidiFile(midi_file):
        if msg.type == "note_on":
            n = msg.note
            if n > note_max:
                note_max = n
            if n < note_min:
                note_min = n

    return note_min, note_max

def get_img_rect(filepath):
    try:
        surface = pg.image.load(filepath)
    except pg.error:
        raise SystemExit('Could not load image "%s" %s' % (filepath, pg.get_error()))
    return surface.get_rect()

def load_image(filepath, keep_alpha=False):
    try:
        surface = pg.image.load(filepath)
    except pg.error:
        raise SystemExit('Could not load image "%s" %s' % (filepath, pg.get_error()))

    # 画像のピクセル形式を最適化
    if keep_alpha:
        return surface.convert_alpha()
    else:
        return surface.convert()

def load_seq_images(img_dir, keep_alpha=False):
    imgs = []
    for f in os.listdir(img_dir):
        p = os.path.join(img_dir, f)
        img = load_image(p, keep_alpha=keep_alpha)
        imgs.append(img)
    return imgs

def load_filtered_image(filepath, alpha=0.4, black_filter=True):
    """
    元画像に半透明のフィルタを被せたものを返す. (主に背景画像を薄くするため)
    alpha: 1に近いほど元絵が濃くなる
    black_filter: Trueなら黒、Falseなら白のフィルタを被せる.
    """
    org_img = cv2.imread(filepath)

    if black_filter:
        filter = np.zeros_like(org_img)
    else: # white filter
        filter = np.ones_like(org_img) * 255

    new_img = cv2.addWeighted(org_img, alpha, filter, 1 - alpha, 0)

    tmp_imgfile = ".tmp_image.png"
    cv2.imwrite(tmp_imgfile, new_img)
    ret = load_image(tmp_imgfile)
    os.remove(tmp_imgfile)

    return ret

def set_track_type(mid: mido.MidiFile, track_max=4):
    """ Trackごとの色分け用. midiのchannelを一時的に使って設定 """
    for track_num, track in enumerate(mid.tracks):
        for i in range(len(track)):
            if track[i].type in ["note_on", "note_off"]:
                track[i].channel = min(track_num, track_max)

class MidiEvent:
    def __init__(self, ticks, type, track, msg="", bomb_end_ticks=None):
        self.ticks = ticks
        self.type = type
        self.track = track
        self.msg = msg
        self.bomb_end_ticks = bomb_end_ticks

def load_midi_events(midi_file, bomb_life_ticks=3000, set_track=True):
    """ 可視化処理に必要な各種MIDIイベントを取得 """
    events = []
    ticks = 0
    mid = mido.MidiFile(midi_file)
    if set_track:
        set_track_type(mid)

    for msg in mid:
        ticks += int(msg.time * 1000)
        if msg.type in ["note_on", "note_off"]:
            msg.time = 0
            if set_track:
                track_type = msg.channel
                msg.channel = 0 # track設定に使ったchannelを0に戻す
            else:
                track_type = 0
            e = MidiEvent(ticks, type=msg.type, track=track_type, msg=msg)
            events.append(e)

            if msg.type == "note_on":
                # note_onの場合、前もってbombを降らせるイベントも入れる
                bomb_start_ticks = ticks - bomb_life_ticks
                e = MidiEvent(bomb_start_ticks, type="bomb_start", track=track_type,
                              msg=msg, bomb_end_ticks=ticks)
                events.append(e)
    
    events.sort(key=lambda e: e.ticks)
    return events
