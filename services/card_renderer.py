"""原神のビルドカード画像（計算機風レイアウト）。"""

from __future__ import annotations

import io
import re
from pathlib import Path

import messages as msg
from games.base import CharacterBuild, ParsedPiece
from games.genshin import GenshinGame
from games.genshin.score import score_piece
from games.genshin.stats import format_stat_value
from services.copy import t
from services.enka_client import EnkaAvatar, EnkaShowcase

_ELEMENT_COLORS = {
    "pyro": (232, 88, 66),
    "hydro": (75, 160, 232),
    "cryo": (120, 200, 230),
    "electro": (176, 112, 224),
    "anemo": (96, 200, 172),
    "geo": (232, 184, 72),
    "dendro": (128, 200, 80),
}

_ELEMENT_BG = {
    "pyro": (48, 22, 18),
    "hydro": (16, 28, 44),
    "cryo": (16, 34, 42),
    "electro": (34, 20, 48),
    "anemo": (16, 40, 34),
    "geo": (46, 34, 16),
    "dendro": (22, 40, 18),
}

_SLOT_ORDER = ["flower", "feather", "sands", "goblet", "circlet"]
_RELIC_SET_RE = re.compile(r"^UI_RelicIcon_(\d+)_")
_PANEL_X = 1070

_RANK_COLOR = {
    "godly": (240, 196, 72),
    "great": (120, 214, 132),
    "good": (232, 140, 64),
    "ok": (80, 160, 220),
    "growing": (150, 154, 160),
}

_TEXT = (252, 248, 240)
_MUTED = (196, 184, 164)
_LABEL = (232, 222, 204)
_SUB = (236, 228, 214)
_INK = (18, 14, 10)

_FONT_CANDIDATES = [
    Path(r"C:\Windows\Fonts\YuGothB.ttc"),
    Path(r"C:\Windows\Fonts\YuGothM.ttc"),
    Path(r"C:\Windows\Fonts\YuGothR.ttc"),
    Path(r"C:\Windows\Fonts\meiryo.ttc"),
    Path(r"C:\Windows\Fonts\msgothic.ttc"),
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"),
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    Path("/usr/share/fonts/opentype/noto-cjk/NotoSansCJK-Bold.ttc"),
    Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
    Path("/usr/share/fonts/truetype/noto-cjk/NotoSansCJK-Regular.ttc"),
]


def _font(size: int, *, bold: bool = False):
    from PIL import ImageFont

    paths = list(_FONT_CANDIDATES)
    if bold:
        paths = [p for p in paths if "Bold" in p.name or "GothB" in p.name] + paths
    else:
        paths = [p for p in paths if "GothB" not in p.name and "Bold" not in p.name] + paths
    for path in paths:
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size, index=0)
            except OSError:
                continue
    return ImageFont.load_default()


def _mix(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(int(a[i] * (1 - t) + b[i] * t) for i in range(3))


def _substat_upgrades(rolls: int) -> int:
    """初期付与を除いた伸び回数。1回目は出さない。"""
    return max(0, int(rolls) - 1)


def _fit_text(draw, text: str, font, max_width: int) -> str:
    if not text or draw.textlength(text, font=font) <= max_width:
        return text
    while len(text) > 1 and draw.textlength(text + "…", font=font) > max_width:
        text = text[:-1]
    return text + "…"


def _open_bytes(data: bytes | None):
    from PIL import Image

    if not data:
        return None
    try:
        return Image.open(io.BytesIO(data)).convert("RGBA")
    except OSError:
        return None


def _opaque_ratio(image) -> float:
    if image.mode != "RGBA":
        return 1.0
    hist = image.getchannel("A").histogram()
    visible = sum(hist[16:])
    area = image.width * image.height
    return visible / area if area else 0.0


def _visible_mask(image):
    """透明と真っ黒を余白として除いたマスク。"""
    from PIL import ImageChops

    img = image.convert("RGBA")
    luma_ok = img.convert("L").point(lambda p: 255 if p > 16 else 0)
    alpha_ok = img.getchannel("A").point(lambda p: 255 if p > 24 else 0)
    return ImageChops.multiply(luma_ok, alpha_ok)


def _content_bbox(image, pad: int = 12) -> tuple[int, int, int, int]:
    bbox = _visible_mask(image).getbbox()
    if not bbox:
        return (0, 0, image.width, image.height)
    x0, y0, x1, y1 = bbox
    return (
        max(0, x0 - pad),
        max(0, y0 - pad),
        min(image.width, x1 + pad),
        min(image.height, y1 + pad),
    )


def _content_crop_x(image, width: int) -> int:
    """絵の重心が枠のやや左に来る切り出し位置。"""
    from PIL import Image

    if image.width <= width:
        return 0
    col = _visible_mask(image).resize((image.width, 1), Image.Resampling.BOX)
    pixels = list(col.getdata())
    total = sum(int(p) if not isinstance(p, tuple) else int(p[0]) for p in pixels)
    if total <= 0:
        return (image.width - width) // 2
    acc = 0
    centroid = image.width // 2
    half = total / 2
    for i, raw in enumerate(pixels):
        acc += int(raw) if not isinstance(raw, tuple) else int(raw[0])
        if acc >= half:
            centroid = i
            break
    x = centroid - int(width * 0.42)
    return max(0, min(x, image.width - width))


def _cover(image, size: tuple[int, int], *, bottom: bool = True):
    from PIL import Image

    if image.mode == "RGBA":
        bbox = image.getchannel("A").getbbox()
        if bbox:
            image = image.crop(bbox)
    tw, th = size
    scale = max(tw / image.width, th / image.height)
    nw, nh = int(image.width * scale), int(image.height * scale)
    fitted = image.resize((nw, nh), Image.Resampling.LANCZOS)
    x = (nw - tw) // 2
    y = nh - th if bottom else (nh - th) // 2
    return fitted.crop((x, max(0, y), x + tw, max(0, y) + th))


def _fit_portrait(image, size: tuple[int, int]):
    """立ち絵を枠に収める。黒帯や透明の余白は除き、キャラが左寄りに残るように切る。"""
    from PIL import Image

    image = image.convert("RGBA")
    image = image.crop(_content_bbox(image))
    tw, th = size
    src_aspect = image.width / max(image.height, 1)
    box_aspect = tw / th
    if src_aspect < box_aspect:
        scale = th / image.height
        nw = max(1, int(image.width * scale))
        fitted = image.resize((nw, th), Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", size, (0, 0, 0, 0))
        canvas.paste(fitted, ((tw - nw) // 2, 0), fitted)
        return canvas
    scale = th / image.height
    nw = max(1, int(image.width * scale))
    fitted = image.resize((nw, th), Image.Resampling.LANCZOS)
    if nw <= tw:
        canvas = Image.new("RGBA", size, (0, 0, 0, 0))
        canvas.paste(fitted, ((tw - nw) // 2, 0), fitted)
        return canvas
    x = _content_crop_x(fitted, tw)
    return fitted.crop((x, 0, x + tw, th))


def _fade_value(i: int, span: int, *, fade_out: bool = False) -> int:
    if span <= 1:
        return 0
    t = i / (span - 1)
    if fade_out:
        return int(255 * (1 - t) * (1 - t))
    return int(255 * (1 - (1 - t) * (1 - t)))


def _feather_edges(image, *, left: int = 0, right: int = 240, top: int = 8, bottom: int = 48):
    """立ち絵の端を透明にして、切り抜き枠に見えないようにする。"""
    from PIL import Image, ImageChops, ImageDraw

    img = image.convert("RGBA")
    w, h = img.size
    fade = Image.new("L", (w, h), 255)
    draw = ImageDraw.Draw(fade)
    if right > 0:
        span = min(right, w)
        for i in range(span):
            x = w - span + i
            draw.line([(x, 0), (x, h - 1)], fill=_fade_value(i, span, fade_out=True))
    if left > 0:
        span = min(left, w)
        for i in range(span):
            draw.line([(i, 0), (i, h - 1)], fill=_fade_value(i, span))
    if top > 0:
        span = min(top, h)
        band = Image.new("L", (w, h), 255)
        bdraw = ImageDraw.Draw(band)
        for i in range(span):
            bdraw.line([(0, i), (w - 1, i)], fill=_fade_value(i, span))
        fade = ImageChops.multiply(fade, band)
    if bottom > 0:
        span = min(bottom, h)
        band = Image.new("L", (w, h), 255)
        bdraw = ImageDraw.Draw(band)
        for i in range(span):
            y = h - span + i
            bdraw.line([(0, y), (w - 1, y)], fill=_fade_value(i, span, fade_out=True))
        fade = ImageChops.multiply(fade, band)
    img.putalpha(ImageChops.multiply(img.getchannel("A"), fade))
    return img


def _soften_opaque_box(image):
    """不透明な立ち絵の角を落として、写真枠に見えないようにする。"""
    from PIL import Image, ImageChops, ImageDraw, ImageFilter

    img = image.convert("RGBA")
    w, h = img.size
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((2, 2, w - 3, h - 3), radius=64, fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(radius=28))
    img.putalpha(ImageChops.multiply(img.getchannel("A"), mask))
    return img


def _paste(base, src, xy: tuple[int, int], size: tuple[int, int] | None = None) -> None:
    from PIL import Image

    if src is None:
        return
    img = src
    if size:
        img = img.copy()
        img.thumbnail(size, Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", size, (0, 0, 0, 0))
        ox = (size[0] - img.width) // 2
        oy = (size[1] - img.height) // 2
        canvas.paste(img, (ox, oy), img)
        img = canvas
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    base.paste(img, xy, img)


def _relic_tile(src, size: int, accent: tuple[int, int, int]):
    """聖遺物アイコンを金縁の角丸タイルにする。"""
    from PIL import Image, ImageChops, ImageDraw, ImageFilter

    pad = 8
    canvas = Image.new("RGBA", (size + pad, size + pad), (0, 0, 0, 0))
    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle((6, 8, size + 2, size + 4), radius=18, fill=(0, 0, 0, 110))
    canvas.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(3)))
    tile = Image.new("RGBA", (size, size), (18, 14, 12, 230))
    if src is not None:
        fitted = _cover(src.convert("RGBA"), (size, size), bottom=False)
        tile = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        tile.paste(fitted, (0, 0), fitted)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle((1, 1, size - 2, size - 2), radius=16, fill=255)
    tile.putalpha(ImageChops.multiply(tile.getchannel("A"), mask))
    rim = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    gold = _mix(accent, (240, 196, 72), 0.55)
    ImageDraw.Draw(rim).rounded_rectangle((1, 1, size - 2, size - 2), radius=16, outline=gold + (230,), width=2)
    tile = Image.alpha_composite(tile, rim)
    canvas.alpha_composite(tile, (0, 0))
    return canvas


def _paste_relic_fan(base, tiles: list, center: tuple[int, int], *, spread: int = 62, tilt: float = 8) -> None:
    """聖遺物を扇状に少し重ねて置く。"""
    from PIL import Image

    if not tiles:
        return
    n = len(tiles)
    for i, tile in enumerate(tiles):
        t = i - (n - 1) / 2
        angle = t * tilt
        x = int(center[0] + t * spread)
        y = int(center[1] + abs(t) * 7)
        rot = tile.rotate(-angle, resample=Image.Resampling.BICUBIC, expand=True)
        base.alpha_composite(rot, (x - rot.width // 2, y - rot.height // 2))


def _paste_relic_row(base, tiles: list, center: tuple[int, int], *, gap: int = 8) -> None:
    """セットが揃っていないときは横一列。"""
    if not tiles:
        return
    widths = [t.width for t in tiles]
    total = sum(widths) + gap * (len(tiles) - 1)
    x = center[0] - total // 2
    y = center[1]
    for tile in tiles:
        base.alpha_composite(tile, (x, y - tile.height // 2))
        x += tile.width + gap


def _dim_icon(src, opacity: int):
    from PIL import Image

    img = src.convert("RGBA")
    alpha = img.getchannel("A").point(lambda p: int(p * opacity / 255))
    img.putalpha(alpha)
    return img


def _circle_icon(src, size: int, *, dim: bool = False):
    from PIL import Image, ImageDraw

    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    if src is not None:
        fitted = _cover(src, (size, size), bottom=False)
        canvas.paste(fitted, (0, 0), fitted)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((1, 1, size - 2, size - 2), fill=255)
    canvas.putalpha(mask)
    if dim:
        overlay = Image.new("RGBA", (size, size), (0, 0, 0, 140))
        overlay.putalpha(mask.point(lambda p: int(p * 0.7)))
        canvas = Image.alpha_composite(canvas, overlay)
    return canvas


def _text_with_shadow(
    draw,
    xy: tuple[int, int],
    text: str,
    font,
    fill,
    *,
    stroke: int = 2,
    anchor: str = "lt",
) -> None:
    """背景なしで読めるよう、暗い縁と影を付ける。"""
    x, y = xy
    shadow = (0, 0, 0, 170)
    for dx, dy in ((2, 2), (1, 3)):
        draw.text((x + dx, y + dy), text, font=font, fill=shadow, anchor=anchor)
    draw.text(
        (x, y),
        text,
        font=font,
        fill=fill,
        stroke_width=stroke,
        stroke_fill=(0, 0, 0),
        anchor=anchor,
    )


def _badge(draw, box: tuple[int, int, int, int], text: str, font, fill, bg, *, radius: int = 10) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=bg)
    cx = (box[0] + box[2]) / 2
    cy = (box[1] + box[3]) / 2
    draw.text((cx, cy), text, font=font, fill=fill, anchor="mm")


def _text_size(draw, text: str, font) -> tuple[float, float]:
    if not text:
        return 0.0, float(getattr(font, "size", 0) or 0)
    bbox = draw.textbbox((0, 0), text, font=font)
    return float(bbox[2] - bbox[0]), float(bbox[3] - bbox[1])


def _chip_size(
    draw,
    text: str,
    font,
    *,
    pad_x: float = 8,
    pad_y: float = 3,
    min_w: float = 24,
) -> tuple[float, float]:
    tw, th = _text_size(draw, text, font)
    return max(min_w, tw + pad_x * 2), th + pad_y * 2


def _draw_chip(
    draw,
    xy: tuple[float, float],
    text: str,
    font,
    fill,
    bg,
    *,
    radius: int = 8,
    pad_x: float = 8,
    pad_y: float = 3,
    min_w: float = 24,
) -> tuple[float, float]:
    w, h = _chip_size(draw, text, font, pad_x=pad_x, pad_y=pad_y, min_w=min_w)
    x, y = xy
    _badge(draw, (x, y, x + w, y + h), text, font, fill, bg, radius=radius)
    return w, h


def _flex_xs(
    widths: list[float],
    *,
    left: float,
    right: float,
    gap: float = 8,
    justify: str = "center",
) -> list[float]:
    """横並びアイテムの左端 x。justify は start / center / end / space-between。"""
    if not widths:
        return []
    inner = max(0.0, right - left)
    n = len(widths)
    total = float(sum(widths))
    gaps = n - 1
    if justify == "space-between" and n >= 2:
        extra = inner - total
        step = extra / gaps if extra > 0 else float(gap)
        x = left
        xs: list[float] = []
        for w in widths:
            xs.append(x)
            x += w + step
        return xs
    packed = total + float(gap) * gaps
    if justify == "end":
        x = right - packed
    elif justify == "center":
        x = left + (inner - packed) / 2
    else:
        x = left
    if x < left:
        x = left
    xs = []
    for w in widths:
        xs.append(x)
        x += w + gap
    return xs


def _measure_labeled_chip(
    draw,
    label: str,
    chip: str | None,
    font_label,
    font_chip,
    *,
    avail: float,
    gap: float = 8,
) -> tuple[str, float, float, float, float]:
    chip_w = 0.0
    chip_h = 0.0
    if chip:
        chip_w, chip_h = _chip_size(draw, chip, font_chip)
    fitted = _fit_text(draw, label, font_label, max(24.0, avail - (chip_w + gap if chip else 0.0)))
    name_w = float(draw.textlength(fitted, font=font_label)) if fitted else 0.0
    packed = name_w + ((gap + chip_w) if chip else 0.0)
    return fitted, name_w, chip_w, chip_h, packed


def _draw_labeled_chip_rows(
    draw,
    *,
    left: float,
    right: float,
    top: float,
    rows: list[tuple[str, str | None]],
    font_label,
    font_chip,
    label_fill,
    chip_fill,
    chip_bg,
    gap: float = 8,
    row_h: int = 30,
    pad_y: int = 8,
) -> None:
    """名前と件数を左揃えの一塊にし、その列を枠の中央に置く。"""
    if not rows:
        return
    avail = max(24.0, right - left)
    measured = [
        _measure_labeled_chip(draw, label, chip, font_label, font_chip, avail=avail, gap=gap)
        for label, chip in rows
    ]
    col_w = max(item[4] for item in measured)
    col_x = _flex_xs([col_w], left=left, right=right, justify="center")[0]
    for i, ((fitted, name_w, _chip_w, chip_h, _packed), (_label, chip)) in enumerate(zip(measured, rows)):
        cy = top + pad_y + i * row_h + row_h / 2
        draw.text((col_x, cy), fitted, font=font_label, fill=label_fill, anchor="lm")
        if chip:
            _draw_chip(draw, (col_x + name_w + gap, cy - chip_h / 2), chip, font_chip, chip_fill, chip_bg)


def _draw_labeled_chip_row(
    draw,
    *,
    left: float,
    right: float,
    cy: float,
    label: str,
    chip: str | None,
    font_label,
    font_chip,
    label_fill,
    chip_fill,
    chip_bg,
    gap: float = 8,
) -> None:
    row_h = int(max(float(getattr(font_label, "size", 18) or 18), _chip_size(draw, chip or "8", font_chip)[1]) + 10)
    _draw_labeled_chip_rows(
        draw,
        left=left,
        right=right,
        top=cy - row_h / 2 - 8,
        rows=[(label, chip)],
        font_label=font_label,
        font_chip=font_chip,
        label_fill=label_fill,
        chip_fill=chip_fill,
        chip_bg=chip_bg,
        gap=gap,
        row_h=row_h,
        pad_y=8,
    )


def _icon_set_id(icon: str | None) -> str:
    if not icon:
        return ""
    matched = _RELIC_SET_RE.match(icon)
    return matched.group(1) if matched else ""


def _set_key(piece: ParsedPiece) -> str:
    """同じセットか判定する。名前が空でもアイコン番号で揃える。"""
    icon_id = _icon_set_id(piece.icon)
    if icon_id:
        return f"icon:{icon_id}"
    if piece.set_id:
        return f"id:{piece.set_id}"
    if piece.set_name_ja:
        return f"name:{piece.set_name_ja}"
    return ""


def _group_label(group: list[ParsedPiece]) -> str:
    from games.genshin.catalog import set_from_icon

    for piece in group:
        if piece.set_name_ja:
            return piece.set_name_ja
    for piece in group:
        row = set_from_icon(piece.icon)
        if row and row.get("name_ja"):
            return str(row["name_ja"])
    return ""


def _set_groups(pieces: list[ParsedPiece]) -> list[tuple[str, list[ParsedPiece]]]:
    buckets: dict[str, list[ParsedPiece]] = {}
    for piece in pieces:
        key = _set_key(piece)
        if not key:
            continue
        buckets.setdefault(key, []).append(piece)
    groups = [(_group_label(group) or key, group) for key, group in buckets.items()]
    groups.sort(key=lambda item: (-len(item[1]), item[0]))
    return groups


def _set_layout(pieces: list[ParsedPiece]) -> tuple[str, list[tuple[str, int]], list[ParsedPiece]]:
    """装備の分け方。

    5枠の中身は 5 / 4+1 / 3+2 / 2+2+1 / 3+1+1 / 2+1+1+1 / 1+1+1+1+1。
    2+3 は 3+2、1+4 は 4+1 と同じ。欠枠（0〜4個）も同じ規則。
    ボーナスは 4以上で4セット、2以上で2セット。名称行の数字は実数。
    """
    if not pieces:
        return "empty", [], []
    groups = _set_groups(pieces)
    ungrouped = [p for p in pieces if not _set_key(p)]
    bonus = [(name, len(group)) for name, group in groups if len(group) >= 2]
    off = [p for name, group in groups if len(group) < 2 for p in group]
    off.extend(ungrouped)
    if not bonus:
        return ("mixed" if len(pieces) >= 2 else "none"), [], list(pieces)
    top = bonus[0][1]
    if top >= 5:
        return "match", bonus[:1], off
    if top >= 4:
        return ("four_one" if off else "match"), bonus[:1], off
    if len(bonus) >= 2:
        return ("two_two_one" if off else "two_two"), bonus[:2], off
    return "two", bonus[:1], off


def render_build_card(
    showcase: EnkaShowcase,
    avatar: EnkaAvatar,
    build: CharacterBuild,
    *,
    portrait_bytes: bytes | list[bytes] | None,
    weapon_bytes: bytes | None,
    icon_bytes: dict[str, bytes] | None = None,
) -> bytes:
    """紹介キャラ1体のカード PNG を返す。"""
    from PIL import Image, ImageChops, ImageDraw, ImageFilter

    icons = icon_bytes or {}
    game = GenshinGame()
    accent = _ELEMENT_COLORS.get(avatar.element, (180, 180, 180))
    bg = _ELEMENT_BG.get(avatar.element, (28, 24, 20))
    panel = _mix(bg, (255, 236, 200), 0.10)
    panel2 = _mix(bg, (255, 236, 200), 0.16)
    width, height = 1600, 900
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    body = Image.new("RGBA", (width, height), bg + (255,))
    gdraw = ImageDraw.Draw(body)
    for y in range(height):
        t_y = y / max(height - 1, 1)
        color = _mix(_mix(bg, accent, 0.16), (8, 8, 8), t_y * 0.35)
        gdraw.line([(0, y), (width, y)], fill=color + (255,))
    body = body.filter(ImageFilter.GaussianBlur(radius=0.6))
    mask = Image.new("L", (width, height), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, width - 1, height - 1), radius=28, fill=255)
    image.paste(body, (0, 0), mask)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((2, 2, width - 3, height - 3), radius=26, outline=_mix(accent, (255, 220, 150), 0.35), width=3)

    font_name = _font(46, bold=True)
    font_xl = _font(70, bold=True)
    font_rank = _font(36, bold=True)
    font_main = _font(34, bold=True)
    font_lg = _font(26, bold=True)
    font_md = _font(22, bold=True)
    font_label = _font(22, bold=True)
    font_body = _font(18, bold=True)
    font_sm = _font(20)
    font_xs = _font(16)

    splash_h = 540
    splash_w = 760
    blobs: list[bytes] = []
    if isinstance(portrait_bytes, (bytes, bytearray)):
        blobs.append(bytes(portrait_bytes))
    elif portrait_bytes:
        blobs.extend(bytes(item) for item in portrait_bytes if item)
    for key in (avatar.splash_icon, avatar.icon):
        extra = icons.get(key) if key else None
        if extra:
            blobs.append(extra)
    covered = None
    for blob in blobs:
        src = _open_bytes(blob)
        if src is None:
            continue
        fitted = _fit_portrait(src, (splash_w, splash_h))
        if _opaque_ratio(fitted) < 0.08:
            continue
        covered = fitted
        break
    if covered is not None:
        if _opaque_ratio(covered) > 0.88:
            covered = _soften_opaque_box(covered)
        art = _feather_edges(covered, left=0, right=260, top=10, bottom=56)
        image.alpha_composite(art, (4, 4))
        image.putalpha(ImageChops.multiply(image.getchannel("A"), mask))

    _text_with_shadow(draw, (40, 36), avatar.name_ja, font_name, _TEXT, stroke=3)
    meta = f"Lv.{avatar.level}    {t(msg.MSG_38, level=avatar.friendship)}"
    _text_with_shadow(draw, (42, 92), meta, font_sm, _MUTED, stroke=2)

    for i, (icon_name, level) in enumerate(avatar.skills[:3]):
        y = 360 + i * 56
        icon = _open_bytes(icons.get(icon_name))
        badge = _circle_icon(icon, 46)
        image.alpha_composite(badge, (32, y))
        draw.text((86, y + 23), f"Lv.{level}", font=font_body, fill=_TEXT, anchor="lm")

    for i, icon_name in enumerate(avatar.constellation_icons[:6]):
        y = 128 + i * 52
        icon = _open_bytes(icons.get(icon_name))
        locked = i >= avatar.constellations
        badge = _circle_icon(icon, 42, dim=locked)
        image.alpha_composite(badge, (490, y))

    rx, ry, rw = _PANEL_X, 24, 506
    stats = avatar.stats
    def _split(total: float, base: float) -> str:
        if base <= 0:
            return ""
        return f"{base:,.0f}+{max(0, total - base):,.0f}"

    rows: list[tuple[str, str, str]] = [
        ("HP", f"{stats.get('hp', 0):,.0f}", _split(stats.get("hp", 0), avatar.hp_base)),
        (
            game.stat_label("atk_flat"),
            f"{stats.get('atk', 0):,.0f}",
            _split(stats.get("atk", 0), avatar.atk_base),
        ),
        (
            game.stat_label("def_flat"),
            f"{stats.get('def', 0):,.0f}",
            _split(stats.get("def", 0), avatar.def_base),
        ),
        (game.stat_label("em"), f"{stats.get('em', 0):.0f}", ""),
        (game.stat_label("crit_rate"), f"{stats.get('crit_rate', 0):.1f}%", ""),
        (game.stat_label("crit_dmg"), f"{stats.get('crit_dmg', 0):.1f}%", ""),
        (game.stat_label("er"), f"{stats.get('er', 0):.1f}%", ""),
    ]
    if avatar.dmg_bonus_key and avatar.dmg_bonus >= 0.5:
        rows.append((game.stat_label(avatar.dmg_bonus_key), f"{avatar.dmg_bonus:.1f}%", ""))

    max_label = max((draw.textlength(label, font=font_label) for label, _, _ in rows), default=80)
    max_num = max((draw.textlength(value, font=font_lg) for _, value, _ in rows), default=80)
    max_ex = max((draw.textlength(extra, font=font_xs) for _, _, extra in rows if extra), default=0)
    value_right = rx - 22
    label_left = int(value_right - max(max_num, max_ex) - 16 - max_label)
    stats_x = label_left - 18
    if showcase.nickname:
        draw.text((stats_x, 28), showcase.nickname, font=font_xs, fill=_MUTED, anchor="lt")
    for i, (label, value, extra) in enumerate(rows):
        y = 56 + i * 54
        draw.rounded_rectangle((stats_x, y + 12, stats_x + 5, y + 36), radius=2, fill=accent)
        _text_with_shadow(draw, (label_left, y + 24), label, font_label, _LABEL, stroke=2, anchor="lm")
        if extra:
            _text_with_shadow(draw, (value_right, y + 14), value, font_lg, _TEXT, stroke=2, anchor="rm")
            _text_with_shadow(draw, (value_right, y + 36), extra, font_xs, _MUTED, stroke=1, anchor="rm")
        else:
            _text_with_shadow(draw, (value_right, y + 24), value, font_lg, _TEXT, stroke=2, anchor="rm")

    panel_overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    ImageDraw.Draw(panel_overlay).rounded_rectangle((rx, ry, rx + rw, 528), radius=18, fill=panel + (210,))
    image.alpha_composite(panel_overlay)
    draw = ImageDraw.Draw(image)

    pieces_by_slot = {p.slot: p for p in avatar.pieces}
    kind, bonus_lines, off_pieces = _set_layout(avatar.pieces)
    set_groups = _set_groups(avatar.pieces)
    active_groups = [(name, group) for name, group in set_groups if len(group) >= 2]
    if kind in ("match", "four_one", "two"):
        active_groups = active_groups[:1]
    elif kind in ("two_two", "two_two_one"):
        active_groups = active_groups[:2]

    def _piece_src(piece: ParsedPiece):
        return _open_bytes(icons.get(piece.icon or ""))

    def _group_srcs(group: list[ParsedPiece]):
        srcs = []
        for piece in group:
            src = _piece_src(piece)
            if src is not None:
                srcs.append(src)
        return srcs

    relic_imgs = []
    for slot in _SLOT_ORDER:
        piece = pieces_by_slot.get(slot)
        if piece is None:
            continue
        src = _piece_src(piece)
        if src is not None:
            relic_imgs.append(src)

    if kind in ("match", "four_one", "two") and active_groups:
        mark_src = _piece_src(active_groups[0][1][0]) or (relic_imgs[0] if relic_imgs else None)
        if mark_src is not None:
            mark = _dim_icon(_cover(mark_src, (280, 280), bottom=False), 48)
            image.alpha_composite(mark, (rx + rw - 300, 250))
    elif kind in ("two_two", "two_two_one"):
        for i, (_name, group) in enumerate(active_groups):
            mark_src = _piece_src(group[0])
            if mark_src is None:
                continue
            mark = _dim_icon(_cover(mark_src, (170, 170), bottom=False), 44)
            image.alpha_composite(mark, (rx + 30 + i * 230, 290))

    fan_y = ry + 90
    content_top = ry + 28
    if relic_imgs:
        off_srcs = []
        for piece in off_pieces:
            src = _piece_src(piece)
            if src is not None:
                off_srcs.append(src)
        if kind in ("two_two", "two_two_one") and len(active_groups) >= 2:
            for i, (_name, group) in enumerate(active_groups):
                srcs = _group_srcs(group)
                size = 80 if len(group) >= 3 else 86
                tiles = [_relic_tile(src, size, accent) for src in srcs]
                cx = rx + rw // 2 + (-1 if i == 0 else 1) * (108 if kind == "two_two_one" else 100)
                _paste_relic_fan(image, tiles, (cx, fan_y), spread=34 if len(group) >= 3 else 36, tilt=10)
            if off_srcs:
                extra = _dim_icon(_relic_tile(off_srcs[0], 58, accent), 170)
                image.alpha_composite(extra, (rx + rw // 2 - extra.width // 2, fan_y + 24))
        elif kind == "four_one" and active_groups:
            tiles = [_relic_tile(src, 96, accent) for src in _group_srcs(active_groups[0][1])]
            _paste_relic_fan(image, tiles, (rx + rw // 2 - (18 if off_srcs else 0), fan_y), spread=50)
            if off_srcs:
                extra = _dim_icon(_relic_tile(off_srcs[0], 62, accent), 170)
                image.alpha_composite(extra, (rx + rw - 108, fan_y - extra.height // 2 + 8))
        elif kind == "two" and off_srcs and active_groups:
            tiles = [_relic_tile(src, 88, accent) for src in _group_srcs(active_groups[0][1])]
            _paste_relic_fan(image, tiles, (rx + rw // 2 - 70, fan_y), spread=38, tilt=8)
            off_tiles = [_dim_icon(_relic_tile(src, 58, accent), 180) for src in off_srcs]
            _paste_relic_row(image, off_tiles, (rx + rw // 2 + 130, fan_y + 6), gap=4)
        elif kind in ("mixed", "none"):
            size = 84 if len(relic_imgs) <= 2 else 72
            tiles = [_relic_tile(src, size, accent) for src in relic_imgs]
            _paste_relic_row(image, tiles, (rx + rw // 2, fan_y))
        else:
            tiles = [_relic_tile(src, 100, accent) for src in relic_imgs]
            _paste_relic_fan(image, tiles, (rx + rw // 2, fan_y))
        content_top = ry + 180

    name_rows: list[tuple[str, str | None]] = []
    if kind in ("empty", "none"):
        name_rows.append((t(msg.MSG_37), None))
    elif kind == "mixed":
        name_rows.append((t(msg.MSG_80), None))
    else:
        name_rows.extend((name, str(count)) for name, count in bonus_lines)
    if name_rows:
        name_h = float(getattr(font_sm, "size", 18) or 18)
        chip_h = 0.0
        if any(badge for _, badge in name_rows):
            chip_h = _chip_size(draw, "8", font_xs)[1]
        row_h = int(max(name_h, chip_h) + 10)
        pad_y = 8
        inset = 12
        block_h = pad_y * 2 + len(name_rows) * row_h
        draw.rounded_rectangle((rx + 16, content_top, rx + rw - 16, content_top + block_h), radius=12, fill=panel2)
        _draw_labeled_chip_rows(
            draw,
            left=rx + 16 + inset,
            right=rx + rw - 16 - inset,
            top=content_top,
            rows=name_rows,
            font_label=font_sm,
            font_chip=font_xs,
            label_fill=_TEXT,
            chip_fill=_INK,
            chip_bg=accent,
            row_h=row_h,
            pad_y=pad_y,
        )
        content_top += block_h + 16
    total = 0.0
    scored: dict[str, tuple[float, str]] = {}
    for slot in _SLOT_ORDER:
        piece = pieces_by_slot.get(slot)
        if piece is None:
            continue
        result = score_piece(piece, build)
        total += result.total
        scored[slot] = (result.total, result.band_key)
    total = round(total, 1)
    overall_band = "growing"
    if total >= 230:
        overall_band = "godly"
    elif total >= 200:
        overall_band = "great"
    elif total >= 170:
        overall_band = "good"
    elif total >= 130:
        overall_band = "ok"

    draw = ImageDraw.Draw(image)
    compact = len(name_rows) >= 2
    score_label = t(msg.MSG_35)
    rank = msg.MSG_RANK[overall_band]
    rank_w = _chip_size(draw, rank, font_rank, pad_x=12, pad_y=6, min_w=44)[0]
    label_w = float(draw.textlength(score_label, font=font_sm))
    header_xs = _flex_xs(
        [label_w, rank_w],
        left=rx + 32,
        right=rx + rw - 28,
        justify="space-between",
    )
    draw.text((header_xs[0], content_top), score_label, font=font_sm, fill=_MUTED, anchor="lt")
    _draw_chip(
        draw,
        (header_xs[1], content_top - 6),
        rank,
        font_rank,
        _INK,
        _RANK_COLOR[overall_band],
        radius=12,
        pad_x=12,
        pad_y=6,
        min_w=44,
    )
    draw.text((header_xs[0], content_top + (58 if compact else 70)), f"{total:.1f}", font=font_xl, fill=_TEXT, anchor="lt")
    caption_y = content_top + (118 if compact else 148)
    draw.text(
        (rx + 32, caption_y),
        t(msg.MSG_36, build=build.name_ja),
        font=font_xs,
        fill=_MUTED,
        anchor="lt",
    )
    if avatar.weapon:
        wy = min(456, max(caption_y + 24, 400))
        wicon = _open_bytes(weapon_bytes or icons.get(avatar.weapon.icon))
        _paste(image, wicon, (rx + 20, wy), (56, 56))
        _badge(draw, (rx + 20, wy, rx + 56, wy + 22), f"R{avatar.weapon.refine}", font_xs, _INK, accent, radius=7)
        weapon_name = _fit_text(draw, (avatar.weapon.name_ja or "").strip() or t(msg.MSG_81), font_label, rw - 108)
        draw.text((rx + 88, wy + 2), weapon_name, font=font_label, fill=_TEXT, anchor="lt")
        sub = f"Lv.{avatar.weapon.level}"
        if avatar.weapon.base_atk:
            sub += f"  {game.stat_label('atk_flat')} {avatar.weapon.base_atk:.0f}"
        if avatar.weapon.sub_key:
            sub += f"  {game.stat_label(avatar.weapon.sub_key)} {format_stat_value(avatar.weapon.sub_key, avatar.weapon.sub_value)}"
        draw.text(
            (rx + 88, wy + 34),
            _fit_text(draw, sub, font_body, rw - 108),
            font=font_body,
            fill=_LABEL,
            anchor="lt",
        )

    box_w, box_h = 300, 338
    gap = 12
    start_x = 20
    start_y = 544
    for index, slot in enumerate(_SLOT_ORDER):
        x = start_x + index * (box_w + gap)
        y = start_y
        draw.rounded_rectangle((x, y, x + box_w, y + box_h), radius=16, fill=panel)
        piece = pieces_by_slot.get(slot)
        if piece is None:
            draw.text((x + box_w / 2, y + 36), t(msg.MSG_37), font=font_md, fill=_MUTED, anchor="mt")
            continue
        icon = _open_bytes(icons.get(piece.icon or ""))
        _paste(image, icon, (x + 14, y + 14), (78, 78))
        if piece.main:
            draw.text((x + 104, y + 16), game.stat_label(piece.main.key), font=font_body, fill=_LABEL, anchor="lt")
            draw.text(
                (x + 104, y + 58),
                format_stat_value(piece.main.key, piece.main.value),
                font=font_main,
                fill=_TEXT,
                anchor="lm",
            )
        lv = piece.level if piece.level is not None else 0
        draw.text((x + box_w - 16, y + 58), f"+{lv}", font=font_sm, fill=accent, anchor="rm")

        sy = y + 108
        for sub in piece.subs[:4]:
            val = format_stat_value(sub.key, sub.value)
            val_w = draw.textlength(val, font=font_sm)
            upgrades = _substat_upgrades(sub.rolls)
            roll = f"×{upgrades}" if upgrades > 0 else ""
            roll_w = draw.textlength(roll, font=font_body) + 6 if roll else 0
            label = _fit_text(
                draw,
                game.stat_label(sub.key),
                font_body,
                max(48, box_w - 40 - val_w - roll_w),
            )
            draw.text((x + 18, sy + 14), label, font=font_body, fill=_LABEL, anchor="lm")
            if roll:
                label_w = draw.textlength(label, font=font_body)
                draw.text(
                    (x + 22 + label_w, sy + 14),
                    roll,
                    font=font_body,
                    fill=accent,
                    anchor="lm",
                )
            draw.text((x + box_w - 18, sy + 14), val, font=font_sm, fill=_TEXT, anchor="rm")
            sy += 38

        score_val, band = scored.get(slot, (0.0, "growing"))
        letter = msg.MSG_RANK.get(band, msg.MSG_44)
        _badge(
            draw,
            (x + 14, y + box_h - 50, x + 62, y + box_h - 14),
            letter,
            font_lg,
            _INK,
            _RANK_COLOR.get(band, _MUTED),
            radius=10,
        )
        draw.text((x + 74, y + box_h - 32), t(msg.MSG_39), font=font_xs, fill=_MUTED, anchor="lm")
        draw.text((x + box_w - 16, y + box_h - 32), f"{score_val:.1f}", font=font_lg, fill=_TEXT, anchor="rm")

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
