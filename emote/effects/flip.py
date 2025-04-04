import io
import os
import tempfile

from PIL import Image

from .base import Emote


async def flip(emote: Emote, direction: str = "h") -> Emote:
    """
    Flips the emote image data in the specified direction(s).

    Flips the emote's image using file_path extension for validation.
    Supports: jpg, jpeg, png, gif (based on file extension).
    Directions: "h" (horizontal), "v" (vertical), "hv/vh" (both).
    Errors stored in emote.errors['flip'].

    User:
        Mirrors the emote. You can flip horizontally (h), vertically (v),
        or both (hv). Works with static images and animated GIFs.

        Default is a horizontal flip if no direction is specified.

        Usage:
        `:aspire_flip:` - Flips the emote horizontally.
        `:aspire_flip(v):` - Flips the emote vertically.
        `:aspire_flip(hv):` - Flips the emote both horizontally and vertically.

    Parameters:
        emote (Emote): The emote object containing the image data to be flipped.
        direction (str, optional): The direction to flip the image. Valid values are "h", "v", "hv", or "vh"
            (default is "h"). "h" indicates horizontal, "v" indicates vertical, and "hv" or "vh" indicate both.

    Returns:
        Emote: The updated emote object with its image data flipped, or with an error recorded if the operation failed.

    Raises:
        ValueError: If the provided direction is not one of the accepted values.
    """
    if emote.img_data is None:
        emote.errors["flip"] = "No image data available"
        return emote

    # Validate file type using file_path extension
    allowed_extensions = {'jpg', 'jpeg', 'png', 'gif', 'webp', 'mp4'}
    file_ext = emote.file_path.lower().split('.')[-1]
    emote.notes["file_ext"] = str(file_ext)
    if file_ext not in allowed_extensions:
        emote.errors["flip"] = f"Unsupported file type: {file_ext}. Allowed: jpg, jpeg, png, gif, webp, mp4"
        return emote

    # Validate direction argument
    direction = direction.lower()
    if direction not in {'h', 'v', 'hv', 'vh'}:
        raise ValueError(f"Invalid direction '{direction}'. Use h/v/hv/vh")

    # Process mp4 video files
    if file_ext == 'mp4':
        try:
            from moviepy import VideoFileClip
            from moviepy.video.fx import MirrorX, MirrorY, TimeMirror

            with tempfile.TemporaryDirectory() as temp_dir:
                tmp_clip = os.path.join(temp_dir, "input.mp4")
                with open(tmp_clip, "wb") as f:
                    f.write(emote.img_data)

                clip = VideoFileClip(tmp_clip)
                if 'h' in direction:
                    clip = clip.with_effects([MirrorX()])
                if 'v' in direction:
                    clip = clip.with_effects([MirrorY()])
                #
                # duration = clip.duration
                # clip = clip.subclipped(-clip.end + 1, -1)
                # clip = clip.with_effects([TimeMirror()])
                # clip = clip.subclipped(0, duration)  # Ensure we stay within valid time range

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
            trace = traceback.extract_tb(err.__traceback__)
            last_frame = trace[-1]
            error_details = {
                'type': err.__class__.__name__,
                'message': str(err),
                'file': last_frame.filename,
                'line': last_frame.lineno,
                'function': last_frame.name,
                'code': last_frame.line,
                'traceback': traceback.format_exc().split('\n')[-2]
            }
            emote.errors["flip"] = error_details
            return emote

        return emote

    # Process animated images (GIF and animated WebP)
    with Image.open(io.BytesIO(emote.img_data)) as img:
        try:
            if file_ext in {'gif', 'webp'} and getattr(img, "is_animated", False):
                frames = []
                for frame in range(img.n_frames):
                    img.seek(frame)
                    frame_img = img.copy()
                    if 'h' in direction:
                        frame_img = frame_img.transpose(Image.FLIP_LEFT_RIGHT)
                    if 'v' in direction:
                        frame_img = frame_img.transpose(Image.FLIP_TOP_BOTTOM)
                    frames.append(frame_img)

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
                if 'h' in direction:
                    img = img.transpose(Image.FLIP_LEFT_RIGHT)
                if 'v' in direction:
                    img = img.transpose(Image.FLIP_TOP_BOTTOM)

                output_buffer = io.BytesIO()
                img.save(output_buffer, format=file_ext.upper())
                emote.img_data = output_buffer.getvalue()
        except Exception as err:
            import traceback
            line_number = traceback.extract_tb(err.__traceback__)[-1].lineno
            emote.errors["flip"] = f"Error flipping: {err} at line {line_number}"
            return emote

    return emote
