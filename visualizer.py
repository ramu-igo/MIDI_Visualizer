import os
import os.path as osp
import mido
import pygame as pg

from tools import *

# ------------------------------------------------------------------------------

# 使用するMIDIファイル指定
MIDI_FILE = "midi/sample_Alla_Turca.mid"

# 背景画像と透明度を指定
BG_IMG_FILE = "data/black.jpg"
BG_IMG_ALPHA = 0.60

# 最初のボムが表れるまでの待ち時間
FIRST_WAIT_MS = 1000

# ボム落下時間 (この時間をかけて上から下まで落ちる)
BOMB_LIFE_MS = 6000

# 最後のnote処理から終了までの時間
FINISH_WAIT_MS = 1000

# ボムを降らせる領域の上下左右に設けるマージン (背景画像サイズに対する相対値)
MARGIN_TOP, MARGIN_BOTTOM = 0.15, 0.12
MARGIN_LEFT, MARGIN_RIGHT = 0.15, 0.15

# ボムに使用する画像
BOMB_IMG_ROOT = "data/bomb"
HAMON_IMG_ROOT = "data/hamon"

# MIDIポート指定
MIDI_PORT_NAME = mido.get_output_names()[0] # default port

# フレームレート (fps)
FRAME_RATE = 120

# ------------------------------------------------------------------------------

# ボムを降らせる領域の決定
_bg_rect = get_img_rect(BG_IMG_FILE)
_x = int(_bg_rect.width * MARGIN_LEFT)
_y = int(_bg_rect.height * MARGIN_TOP)
_w = int(_bg_rect.width * (1 - MARGIN_LEFT - MARGIN_RIGHT))
_h = int(_bg_rect.height * (1 - MARGIN_TOP - MARGIN_BOTTOM))
BOMB_AREA = pg.Rect(_x, _y, _w, _h)

NOTE_L, NOTE_H = get_note_range(MIDI_FILE)

def calc_x_from_note(note):
    """ 音高からボムのX座標を算出 """
    x = BOMB_AREA.left + int(BOMB_AREA.width * (note - NOTE_L) / (NOTE_H - NOTE_L))
    return x


MY_TICKS_DIFF = BOMB_LIFE_MS + FIRST_WAIT_MS
def get_my_tick():
    return pg.time.get_ticks() - MY_TICKS_DIFF

class Explosion(pg.sprite.Sprite):
    all_images = []
    life_ticks = 1000

    def __init__(self, e: MidiEvent):
        pg.sprite.Sprite.__init__(self, self.containers)
        self.images = self.all_images[e.track]

        self.image = self.images[0]
        x = calc_x_from_note(e.msg.note)
        pos = (x, BOMB_AREA.bottom)
        self.rect = self.image.get_rect(center=pos)

        self.cur_img_id = 0
        self.img_id_max = len(self.images) - 1
        self.ini_tick = get_my_tick()
        self.end_tick = self.ini_tick + self.life_ticks

    def update(self):
        past_t = get_my_tick() - self.ini_tick
        img_id = min(int(self.img_id_max * past_t / self.life_ticks), self.img_id_max)
        if img_id > self.cur_img_id:
            self.image = self.images[img_id]
            self.cur_img_id = img_id
        if past_t >= self.life_ticks:
            self.kill()

    @classmethod
    def load_images(cls):
        for _d in os.listdir(HAMON_IMG_ROOT):
            subdir = osp.join(HAMON_IMG_ROOT, _d)
            cls.all_images.append(load_seq_images(subdir, keep_alpha=True))
            

class Bomb(pg.sprite.Sprite):
    all_images = []
    bottom_margin = 20

    def __init__(self, e: MidiEvent, ini_ticks):
        pg.sprite.Sprite.__init__(self, self.containers)

        self.image = self.all_images[e.track]

        self.evt = e
        x = calc_x_from_note(e.msg.note)
        self.rect = self.image.get_rect(midbottom=(x, BOMB_AREA.top))
        self.ini_ticks = ini_ticks
        self.end_ticks = e.bomb_end_ticks
        self.ini_y = self.rect.y
        self.end_y = BOMB_AREA.bottom - self.rect.height + self.bottom_margin
        self.update_count = 0

    def calc_new_y(self, cur_ticks):
        # end_ticksにちょうどend_yに到達するように、線形に移動させる
        new_y = self.ini_y + int((self.end_y - self.ini_y) * (cur_ticks - self.ini_ticks) / (self.end_ticks - self.ini_ticks))
        return new_y

    def update(self):
        self.update_count += 1
        ticks = get_my_tick()
        new_y = self.calc_new_y(ticks)
        if new_y > self.rect.y:
            self.rect.y = new_y
        if ticks >= self.end_ticks:
            self.kill()

    @classmethod
    def load_images(cls):
        for _d in os.listdir(BOMB_IMG_ROOT):
            subdir = osp.join(BOMB_IMG_ROOT, _d)
            bomb_img = osp.join(subdir, "bomb.png")
            cls.all_images.append(load_image(bomb_img, keep_alpha=True))


def main():
    pg.display.set_caption("MIDI Visualizer")  

    screen_rect = get_img_rect(BG_IMG_FILE)
    winstyle = 0
    bestdepth = pg.display.mode_ok(screen_rect.size, winstyle, 32)
    screen = pg.display.set_mode(screen_rect.size, winstyle, bestdepth)
    pg.mouse.set_visible(False)

    Explosion.load_images()
    Bomb.load_images()

    background = load_filtered_image(BG_IMG_FILE, alpha=BG_IMG_ALPHA)
    screen.blit(background, (0, 0))
    pg.display.flip()

    bombs = pg.sprite.Group()
    all = pg.sprite.RenderUpdates()
    Bomb.containers = bombs, all
    Explosion.containers = all

    midi_out_port = mido.open_output(MIDI_PORT_NAME)
    midi_evts = load_midi_events(MIDI_FILE, bomb_life_ticks=BOMB_LIFE_MS,
                                 set_track=True)
    evt_num = len(midi_evts)
    evt_p = 0

    finishing_start_tick = None
    clock = pg.time.Clock()
    while True:
        ticks = get_my_tick()

        while evt_p < evt_num and midi_evts[evt_p].ticks <= ticks:
            e = midi_evts[evt_p]
            if e.type == "bomb_start":
                Bomb(e, ticks)
            elif e.type == "note_on":
                midi_out_port.send(e.msg)
                Explosion(e)
            elif e.type == "note_off":
                midi_out_port.send(e.msg)

            evt_p += 1

        if evt_p >= evt_num:
            # 全MIDIイベント処理完了
            if finishing_start_tick is None:
                finishing_start_tick = get_my_tick()
            if get_my_tick() - finishing_start_tick >= FINISH_WAIT_MS:
                print("finish.")
                return

        for event in pg.event.get():
            if event.type == pg.QUIT:
                return
            if event.type == pg.KEYDOWN and event.key == pg.K_ESCAPE:
                return

        # 画面更新
        all.clear(screen, background)
        all.update()
        dirty = all.draw(screen)
        pg.display.update(dirty)

        clock.tick(FRAME_RATE)


if __name__ == "__main__":
    pg.init()
    main()
    pg.quit()