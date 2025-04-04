import io

from PIL import Image

from .base import Emote


async def reverse(emote: Emote) -> Emote:
    """
    Reverses emote playback.

    User:
        Plays the emote in reverse.
        Works with animated GIFs and videos.

        This effect can only be used once per emote.

        Usage:
        `:aspire_reverse:` - Plays the emote in reverse.

    Parameters:
        emote (Emote): The emote object to be reversed.

    Returns:
        Emote: The updated emote object with the reversed image data.
    """
    if emote.img_data is None:
        emote.errors["reverse"] = "No image data available"
        return emote

    import os, tempfile

    # Validate file type using file_path extension
    allowed_extensions = {'gif', 'webp', 'mp4'}
    file_ext = emote.file_path.lower().split('.')[-1]
    if file_ext not in allowed_extensions:
        emote.errors["reverse"] = f"Unsupported file type: {file_ext}. Allowed: gif, webp, mp4"
        return emote

    # Process mp4 video files
    if file_ext == 'mp4':
        try:
            from moviepy import VideoFileClip, vfx

            with tempfile.TemporaryDirectory() as temp_dir:
                tmp_clip = os.path.join(temp_dir, "input.mp4")
                with open(tmp_clip, "wb") as f:
                    f.write(emote.img_data)

                clip = VideoFileClip(tmp_clip)
                clip = clip.subclipped(-clip.end + 1, -1)
                clip = clip.with_effects([vfx.TimeMirror()])

                out_path = os.path.join(temp_dir, "output.mp4")
                temp_dir = tempfile.gettempdir()
                temp_audio = os.path.join(temp_dir, "temp_audio.m4a")

                clip.write_videofile(out_path, codec="libx264", audio_codec="aac", logger=None,
                                     temp_audiofile=temp_audio,
                                     remove_temp=True)

                with open(out_path, "rb") as f:
                    emote.img_data = f.read()

        except Exception as err:
            import traceback
            line_number = traceback.extract_tb(err.__traceback__)[-1].lineno
            emote.errors["reverse"] = f"Error reversing: {err} at line {line_number}"
            return emote

        return emote

    # Process animated images (GIF and animated WebP)
    with Image.open(io.BytesIO(emote.img_data)) as img:
        try:
            if file_ext in {'gif', 'webp'} and getattr(img, "is_animated", False):
                frames = []
                for frame in range(img.n_frames):
                    img.seek(frame)
                    frames.append(img.copy())

                frames.reverse()

                output_buffer = io.BytesIO()
                save_format = 'WEBP' if file_ext == 'webp' else 'GIF'
                frames[0].save(
                    output_buffer,
                    format=save_format,
                    save_all=True,
                    append_images=frames[1:],
                    loop=img.info.get('loop', 0),
                    duration=img.info.get('duration', 100)
                )
                emote.img_data = output_buffer.getvalue()

            # Process static images
            else:
                emote.errors["reverse"] = "Static images cannot be reversed"
                return emote

        except Exception as err:
            import traceback
            line_number = traceback.extract_tb(err.__traceback__)[-1].lineno
            emote.errors["reverse"] = f"Error reversing: {err} at line {line_number}"
            return emote

    return emote
