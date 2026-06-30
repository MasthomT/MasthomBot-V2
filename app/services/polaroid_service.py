import base64
import io
import logging

from PIL import Image, ImageDraw, ImageFont

from app.core.config import settings
from app.services.obs_service import obs_service
from app.services.notification_service import notification_service
from app.routes.overlays import trigger_overlay_event

logger = logging.getLogger("masthbot.polaroid")

FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
PHOTO_SIZE = (720, 900)
BORDER = 40
CAPTION_HEIGHT = 160
SHUTTER_SOUND = "/static/channelrewards/sounds/SON_AppareilPhoto.mp3"


def _cover_crop(image: Image.Image, target_size: tuple[int, int]) -> Image.Image:
    """Recadre sur le centre de l'image pour remplir target_size sans déformation
    (équivalent CSS object-fit: cover), au lieu d'écraser l'image en l'étirant."""
    target_w, target_h = target_size
    src_w, src_h = image.size
    target_ratio = target_w / target_h
    src_ratio = src_w / src_h

    if src_ratio > target_ratio:
        new_w = int(src_h * target_ratio)
        left = (src_w - new_w) // 2
        box = (left, 0, left + new_w, src_h)
    else:
        new_h = int(src_w / target_ratio)
        top = (src_h - new_h) // 2
        box = (0, top, src_w, top + new_h)

    return image.crop(box).resize(target_size, Image.LANCZOS)


def _build_polaroid(photo_bytes: bytes, caption: str) -> bytes:
    """Compose une image style Polaroïd : photo encadrée de blanc, légende en bas."""
    photo = Image.open(io.BytesIO(photo_bytes)).convert("RGB")
    photo = _cover_crop(photo, PHOTO_SIZE)

    width = photo.width + BORDER * 2
    height = photo.height + BORDER * 2 + CAPTION_HEIGHT

    card = Image.new("RGB", (width, height), "#f0f0f0")
    card.paste(photo, (BORDER, BORDER))

    draw = ImageDraw.Draw(card)
    font_size = 64
    font = ImageFont.truetype(FONT_PATH, font_size)

    text = caption.strip() or "..."
    max_width = width - BORDER * 2
    while font_size > 24:
        bbox = draw.textbbox((0, 0), text, font=font)
        if bbox[2] - bbox[0] <= max_width:
            break
        font_size -= 4
        font = ImageFont.truetype(FONT_PATH, font_size)

    bbox = draw.textbbox((0, 0), text, font=font)
    text_x = (width - (bbox[2] - bbox[0])) // 2
    text_y = photo.height + BORDER + (CAPTION_HEIGHT - (bbox[3] - bbox[1])) // 2
    draw.text((text_x, text_y), text, fill="#000000", font=font)

    buf = io.BytesIO()
    card.save(buf, format="PNG")
    return buf.getvalue()


async def send_polaroid(user_name: str, caption: str):
    """Capture la webcam OBS, compose le Polaroïd avec la légende du viewer, et l'envoie sur Discord."""
    if not settings.POLAROID_CHANNEL_ID:
        logger.error("❌ [POLAROID] POLAROID_CHANNEL_ID manquant dans la config.")
        return

    await trigger_overlay_event({
        "type": "play_sound",
        "details": {"type": "sound", "filename": SHUTTER_SOUND, "volume": 100},
    })

    # On demande le screenshot au ratio natif de la webcam (16:9) : si on demande directement
    # un cadre portrait (4:5) à OBS, OBS ÉTIRE l'image pour remplir exactement ces dimensions
    # (constaté en pratique malgré la doc obsws_python) — le recadrage centré ci-dessous doit
    # donc se faire APRÈS coup, sur une image dont le ratio d'origine est encore intact.
    screenshot_b64 = obs_service.take_source_screenshot("WebCam", width=1920, height=1080)
    if not screenshot_b64:
        logger.error("❌ [POLAROID] Capture webcam impossible (OBS injoignable ou source absente).")
        return

    try:
        photo_bytes = base64.b64decode(screenshot_b64)
        polaroid_bytes = _build_polaroid(photo_bytes, caption)
    except Exception as e:
        logger.error(f"❌ [POLAROID] Erreur lors de la composition de l'image : {e}")
        return

    await notification_service.send_discord_image(
        channel_id=settings.POLAROID_CHANNEL_ID,
        image_bytes=polaroid_bytes,
        filename="polaroid.png",
        content=f"📸 Polaroïd de **{user_name}**",
    )

    try:
        from app.services.twitch_service import twitch_bot
        channel = twitch_bot.get_channel(twitch_bot.channel_name)
        if channel:
            await channel.send(f'{user_name} a pris un Polaroïd ! Retrouve-le sur le salon "📸ᆞ𝗣𝗼𝗹𝗮𝗿𝗼𝗶̈𝗱"')
    except Exception as e:
        logger.error(f"❌ [POLAROID] Impossible d'envoyer le message chat : {e}")
