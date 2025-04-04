import io
import os
import tempfile

from PIL import Image

from .base import Emote


async def speed(emote: Emote, factor: float = 2) -> Emote:
    """
    Changes the playback speed of the emote.

    User:
        Changes the playback speed of the emote.
        Works with animated GIFs and videos.

        Default is 2x speed if no argument is provided.
        This effect can only be used once per emote.

        Usage:
        `:aspire_speed:` - Changes the playback speed of the emote.
        `:aspire_speed(0.5):` - Slows down the emote to 0.5x speed.
        `:aspire_speed(2):` - Speeds up the emote to 2x speed.

        Alias for `:aspire_fast:` and `:aspire_slow:`.

    Parameters:
        emote (Emote): The emote object to be processed.
        factor (float): The playback speed factor. Default is 2.0.

    Returns:
        Emote: The updated emote object with the modified playback speed.
    """

    if emote.img_data is None:
        emote.errors["speed"] = "No image data available"
        return emote

    file_ext = emote.file_path.lower().split(".")[-1]

    # Only allow speeding up for MP4s when factor is greater than or equal to 1.
    if file_ext == "mp4" and factor < 1:
        emote.errors["speed"] = "MP4 files cannot be slowed down"
        return emote

    # Process video files
    if file_ext == "mp4":
        try:
            from moviepy import VideoFileClip, vfx
            with tempfile.TemporaryDirectory() as tmp_dir:
                input_path = os.path.join(tmp_dir, "input.mp4")
                with open(input_path, "wb") as f:
                    f.write(emote.img_data)

                clip = VideoFileClip(input_path)
                clip = clip.with_effects([vfx.MultiplySpeed(factor=factor)])

                output_path = os.path.join(tmp_dir, "output.mp4")
                temp_audio = os.path.join(tmp_dir, "temp_audio.m4a")
                clip.write_videofile(
                    output_path,
                    codec="libx264",
                    audio_codec="aac",
                    logger=None,
                    temp_audiofile=temp_audio,
                    remove_temp=True
                )

        except Exception as e:
            import traceback
            line_number = traceback.extract_tb(e.__traceback__)[-1].lineno
            emote.errors["speed"] = f"Error in speed effect: {e} at line {line_number}"
            return emote

        return emote

    # Process animated images (GIF and WebP)
    elif file_ext in {"gif", "webp"}:
        try:
            with Image.open(io.BytesIO(emote.img_data)) as img:
                if not getattr(img, "is_animated", False):
                    emote.errors["speed"] = "Image is not animated"
                    return emote

                frames = []
                durations = []
                for frame in range(getattr(img, "n_frames", 1)):
                    img.seek(frame)
                    frame_image = img.copy()
                    frames.append(frame_image)
                    original_duration = img.info.get("duration", 100)
                    durations.append(original_duration / factor)

                # Add emote.note for duration before and after speed
                emote.notes["original_duration"] = str(original_duration)
                emote.notes["new_duration"] = str(durations[0])

                output_buffer = io.BytesIO()
                frames[0].save(
                    output_buffer,
                    format=img.format if img.format else file_ext.upper(),
                    save_all=True,
                    append_images=frames[1:],
                    duration=durations,
                    loop=img.info.get("loop", 0)
                )
                emote.img_data = output_buffer.getvalue()
        except Exception as e:
            import traceback
            line_number = traceback.extract_tb(e.__traceback__)[-1].lineno
            emote.errors["speed"] = f"Error in speed effect: {e} at line {line_number}"
            return emote

        return emote

    # Unsupported file type
    else:
        emote.errors["speed"] = f"Unsupported file type for speed effect: {file_ext}"
        return emote


async def fast(emote: Emote, factor: float = 2) -> Emote:
    """
    Increases the playback speed of the emote.

    User:
        Speeds up the emote.
        Works with GIFs.

        Default is 2x speed if no argument is provided.
        This effect can only be used once per emote.

        Usage:
        `:aspire_fast:` - Speeds up the emote.
        `:aspire_fast(3):` - Speeds up the emote by a factor of 3.

        Alias for `:aspire_speed(2):`.

    Parameters:
        emote (Emote): The emote object to be sped up.

    Returns:
        Emote: The updated emote object with the sped-up image data.
    """

    emote = await speed(emote, factor)
    return emote


async def slow(emote: Emote, factor: float = 0.5) -> Emote:
    """
    Decreases the playback speed of the emote.

    User:
        Slows down the emote
        Works with GIFs.

        Default is 0.5x speed if no argument is provided.
        This effect can only be used once per emote.

        Usage:
        `:aspire_slow:` - Slows down the emote.
        `:aspire_slow(0.25):` - Slows down the emote by a factor of 0.25.

        Alias for `:aspire_speed(0.5):`.

    Parameters:
        emote (Emote): The emote object to be slowed down.

    Returns:
        Emote: The updated emote object with the slowed-down image data.
    """

    emote = await speed(emote, factor)
    return emote
