#  Copyright (c) 2024, Isaiah Feldt
#  ͏
#     - This program is free software: you can redistribute it and/or modify it
#     - under the terms of the GNU Affero General Public License (AGPL) as published by
#     - the Free Software Foundation, either version 3 of this License,
#     - or (at your option) any later version.
#  ͏
#     - This program is distributed in the hope that it will be useful,
#     - but without any warranty, without even the implied warranty of
#     - merchantability or fitness for a particular purpose.
#     - See the GNU Affero General Public License for more details.
#  ͏
#     - You should have received a copy of the GNU Affero General Public License
#     - If not, please see <https://www.gnu.org/licenses/#GPL>.
import io
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict

import aiohttp
from PIL import Image, ImageOps


@dataclass
class Emote:
    """
    Data class representing an emote.

    Attributes:
        id (int): The unique identifier of the emote.
        file_path (str): The file path of the emote image.
        author_id (int): The unique identifier of the emote's author.
        timestamp (datetime): The timestamp when the emote was created.
        original_url (str): The original URL from which the emote was downloaded.
        name (str): The name of the emote.
        guild_id (int): The unique identifier of the guild the emote belongs to.
        usage_count (int): The number of times the emote has been used.
        errors (Optional[str]): An optional error message associated with the emote. Defaults to `None`.

    This class is decorated with the `dataclass` decorator for convenient attribute access and comparison.

    Example usage:

        emote = Emote(
            id=1,
            file_path="352972393368780810/emote.png",
            author_id=1234,
            timestamp=datetime.now(),
            original_url="https://example.com/emote.png",
            name="emote",
            guild_id=5678,
            usage_count=10,
            errors=None
        )

    TODO: Currently the Emote

    """
    id: int
    file_path: str
    author_id: int
    timestamp: datetime
    original_url: str
    name: str
    guild_id: int
    usage_count: int
    errors: Dict[str, str] = field(default_factory=dict)
    issues: Dict[str, str] = field(default_factory=dict)
    notes: Dict[str, str] = field(default_factory=dict)
    followup: Dict[str, str] = field(default_factory=dict)
    effect_chain: Dict[str, bool] = field(default_factory=dict)
    img_data: Optional[bytes] = None


def get_emote_duration(emote: Emote) -> Optional[int]:
    """
    Gets the duration of an animated WebP or GIF file in milliseconds.
    """
    if emote.img_data is None:
        print("Error: No image data available")
        return None

    try:
        with Image.open(io.BytesIO(emote.img_data)) as img:
            file_path_lower = emote.file_path.lower()

            # Handle animated WebP files
            if file_path_lower.endswith('.webp') or file_path_lower.endswith('.gif'):
                duration = 0
                # Use getattr in case n_frames doesn't exist
                n_frames = getattr(img, "n_frames", 1)
                for i in range(n_frames):
                    img.seek(i)
                    duration += img.info.get("duration", 0)
                return duration

            else:
                print(f"Error: Unsupported file type in {emote.file_path}")
                duration = 50
                return duration

    except Exception as e:
        print(f"Error processing animated duration: {e}")
        duration = 50
        return duration


async def initialize(emote: Emote) -> Emote:
    """
    Fetch the emote image from the provided original_url and store the image data
    in-memory in the emote.img_data attribute. If an error occurs during the fetch,
    record the error in the emote.errors dictionary under the key 'initialize'.

    :param emote: The Emote object to be initialized.
    :return: The initialized Emote object with its image data loaded or an error noted.
    """
    emote.original_url = f"https://media.bellbot.xyz/emote/{emote.file_path}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(emote.original_url) as response:
                if response.status == 200:
                    emote.img_data = await response.read()
                else:
                    emote.errors["initialize"] = f"HTTP error status: {response.status}"
    except Exception as e:
        emote.errors["initialize"] = f"Exception occurred: {str(e)}"

    return emote


async def latency(emote: Emote) -> Emote:
    """
    Toggles the latency measurement flag for subsequent processing.

    User:
        Displays how long it takes to process your emote.
        Use this to see processing time in milliseconds.

        This effect can only be used once per emote.

    Parameters:
        emote (Emote): The emote object to pass through without modification.

    Returns:
        Emote: The same emote object after toggling the latency flag.
    """
    from emote.slash_commands import SlashCommands
    SlashCommands.latency_enabled = not SlashCommands.latency_enabled

    return emote


async def debug(emote: Emote, mode: str = "basic") -> Emote:
    """
        User:
            Shows detailed information about the emote. Including its ID, file path, and other technical details.
            Useful when you need help troubleshooting issues with an emote.

            This effect can only be used once per emote.

        Parameters:
            emote (Emote): The emote object to pass through without modification.
            mode (str): The debug mode to use (currently only 'basic' is supported).

        Returns:
            Emote: The same emote object with debug information added.
    """
    from emote.slash_commands import SlashCommands

    SlashCommands.debug_enabled = True
    # emote.notes["was_cached"] = SlashCommands.was_cached

    # Create a dictionary to hold the debug information.
    notes = emote.notes

    # Add key-value pairs for each debug detail.
    notes["emote_id"] = str(emote.id)
    notes["file_path"] = emote.file_path
    notes["author_id"] = emote.author_id
    notes["timestamp"] = emote.timestamp
    notes["original_url"] = emote.original_url
    notes["guild_id"] = emote.guild_id
    notes["usage_count"] = str(emote.usage_count + 1)

    emote.notes["debug_mode"] = mode

    # TODO move this logic to send_debug_embed in chat.py
    # if emote.errors is not None:
    #     notes["error"] = str(emote.error)
    # else:
    #     notes["error"] = "None"

    if emote.img_data is not None:
        notes["img_data_length"] = f"{len(emote.img_data)} bytes"
    elif emote.effect_chain:
        notes["effect_chain"] = ", ".join(emote.effect_chain.keys())
    else:
        notes["img_data"] = "None"

    emote.notes = notes
    return emote


async def train(emote: Emote, amount: int = 3) -> Emote:
    """
        Duplicate the provided Emote for a specified number of times within a valid range.

        User:
            Creates multiple copies of the emote in a row. You can specify a
            number between 1-6 to control how many copies appear.

            Default is 3 if no number is provided.
            This effect can only be used once per emote.

            Usage:
            `:aspire_train:` - Creates 3 copies of the emote.
            `:aspire_train(5):` - Creates 5 copies of the emote.


        Parameters:
            emote (Emote): The emote object to be trained.
            amount (int): The number of times to train the emote. If invalid, defaults
                to 3. Must be an integer between 1 and 6, inclusive.

        Returns:
            Emote: The updated emote object with the training details and potential
                error messages.
    """
    from emote.slash_commands import SlashCommands

    try:
        amount = int(amount)
    except (ValueError, TypeError):
        amount = 3
        emote.errors["train"] = "Train amount must be a number."
    else:
        if not 1 <= amount <= 6:
            amount = min(max(amount, 1), 6)
            emote.errors["train"] = "Train amount must be between values of 1 and 6."
            emote.followup["Train"] = (
                "This effect is capped at 6 to avoid Discord rate limits and to"
                "prevent spamming, which can lead to Bell being blacklisted. Sorry!"
            )

    SlashCommands.train_count = amount
    return emote


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

    import io, os, tempfile
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


async def invert(emote: Emote) -> Emote:
    """
    Inverts the colors of the emote image data.

    User:
        Inverts the colors of your emote.
        Works with static images and animated GIFs.

        Usage:
        `:aspire_invert:` - Inverts the colors of the emote.

    Parameters:
        emote (Emote): The emote object containing the image data to be processed.

    Returns:
        Emote: The updated emote object with the inverted image data or with
        an error recorded if the operation failed.
    """

    if emote.img_data is None:
        emote.errors["invert"] = "No image data available"
        return emote

    allowed_extensions = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
    file_ext = emote.file_path.lower().split('.')[-1]
    if file_ext not in allowed_extensions:
        emote.errors["invert"] = f"Unsupported file type: {file_ext}. Allowed: jpg, jpeg, png, gif, webp"
        return emote

    try:
        with Image.open(io.BytesIO(emote.img_data)) as img:
            # For animated images: process each frame
            if file_ext in {'gif', 'webp'} and getattr(img, "is_animated", False):
                frames = []
                durations = []
                for frame_index in range(img.n_frames):
                    img.seek(frame_index)
                    # Convert frame to RGBA to preserve transparency if available.
                    frame_img = img.convert("RGBA")
                    r, g, b, a = frame_img.split()
                    rgb_image = Image.merge("RGB", (r, g, b))
                    inverted_rgb = ImageOps.invert(rgb_image)
                    inverted_frame = Image.merge("RGBA", (*inverted_rgb.split(), a))
                    frames.append(inverted_frame)
                    durations.append(img.info.get('duration', 100))

                output_buffer = io.BytesIO()
                save_format = 'WEBP' if file_ext == 'webp' else 'GIF'
                frames[0].save(
                    output_buffer,
                    format=save_format,
                    save_all=True,
                    append_images=frames[1:],
                    loop=img.info.get('loop', 0),
                    duration=durations,
                    disposal=2
                )
                emote.img_data = output_buffer.getvalue()
            else:
                # Process static images
                # Use RGBA for images with transparency
                mode = img.mode
                if 'A' in mode:
                    img = img.convert("RGBA")
                    r, g, b, a = img.split()
                    rgb_image = Image.merge("RGB", (r, g, b))
                    inverted_rgb = ImageOps.invert(rgb_image)
                    inverted_img = Image.merge("RGBA", (*inverted_rgb.split(), a))
                else:
                    img = img.convert("RGB")
                    inverted_img = ImageOps.invert(img)
                output_buffer = io.BytesIO()
                inverted_img.save(output_buffer, format=img.format if img.format else file_ext.upper())
                emote.img_data = output_buffer.getvalue()
    except Exception as err:
        import traceback
        line_number = traceback.extract_tb(err.__traceback__)[-1].lineno
        emote.errors["invert"] = f"Error inverting: {err} at line {line_number}"
        return emote

    return emote


async def shake(emote: Emote, intensity: float = 1, classic: bool = False) -> Emote:
    if emote.img_data is None:
        emote.errors["shake"] = "No image data available for shaking effect."
        return emote

    allowed_extensions = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
    file_ext = emote.file_path.lower().split('.')[-1]
    if file_ext not in allowed_extensions:
        emote.errors["shake"] = f"Unsupported file type: {file_ext}. Allowed: {', '.join(allowed_extensions)}"
        return emote

    import random
    import numpy as np
    import math

    def blend_images(images, weights):
        """Blend a list of RGBA images using premultiplied alpha to avoid dark edges."""
        result_rgb = None
        result_alpha = None

        for img, weight in zip(images, weights):
            arr = np.array(img).astype(np.float32)
            alpha = arr[..., 3:4] / 255.0
            premul = arr[..., :3] * alpha
            if result_rgb is None:
                result_rgb = weight * premul
                result_alpha = weight * arr[..., 3:4]
            else:
                result_rgb += weight * premul
                result_alpha += weight * arr[..., 3:4]

        safe_alpha = np.where(result_alpha == 0, 1, result_alpha)
        rgb = result_rgb / (safe_alpha / 255.0)
        rgb = np.clip(rgb, 0, 255)
        alpha = np.clip(result_alpha, 0, 255)
        result = np.concatenate([rgb, alpha], axis=-1).astype(np.uint8)
        return Image.fromarray(result)

    img = Image.open(io.BytesIO(emote.img_data))
    input_frames = []
    try:
        while True:
            input_frames.append(img.convert("RGBA").copy())
            img.seek(img.tell() + 1)
    except EOFError:
        pass

    orig_duration = len(input_frames)

    # Calculate scale based on first frame
    img_width, img_height = input_frames[0].size
    scale = max(img_width, img_height) / 540.0
    spring = 1.3
    damping = 0.85
    blur_exposures = 8

    if classic:
        max_shift = (250 * scale) * intensity
        num_frames = 2
        # duration = 50
    else:
        max_shift = (180 * scale) * intensity
        num_frames = 2
        # duration = 25

    if len(input_frames) < 25:
        duration = orig_duration * math.ceil(50 / orig_duration)
    else:
        duration = orig_duration

    emote.notes["Scale"] = str(scale)
    emote.notes["max_shift after"] = str((250 * scale) if classic else (180 * scale))
    emote.notes["original_file_ext"] = str(file_ext)
    emote.notes["orig_duration"] = orig_duration
    emote.notes["new_duration"] = str(duration)

    # Generate shaking offsets
    half = num_frames // 2
    offsets = []
    curr_x, curr_y = 0.0, 0.0
    v_x, v_y = 0.0, 0.0
    step = max_shift / 10
    prev_offsets = [(0.0, 0.0) for _ in input_frames]
    frames = []

    for _ in range(half + 1):
        force_x = random.uniform(-step, step)
        force_y = random.uniform(-step, step)
        v_x = damping * (v_x + force_x - spring * curr_x)
        v_y = damping * (v_y + force_y - spring * curr_y)
        curr_x += v_x
        curr_y += v_y
        curr_x = max(min(curr_x, max_shift), -max_shift)
        curr_y = max(min(curr_y, max_shift), -max_shift)
        offsets.append((curr_x, curr_y))

    offsets_rev = list(reversed(offsets[1:]))
    all_offsets = offsets + offsets_rev

    for idx, (offset_x, offset_y) in enumerate(all_offsets):
        i_input = idx % len(input_frames)
        current_img = input_frames[i_input]
        prev_offset = prev_offsets[i_input]

        if idx == 0 or blur_exposures <= 1:
            shifted_img = current_img.copy().transform(
                current_img.size,
                Image.AFFINE,
                (1, 0, int(offset_x), 0, 1, int(offset_y)),
                resample=Image.BILINEAR,
                fillcolor=(0, 0, 0, 0)
            )
            final_img = shifted_img
        else:
            sub_images = []
            for j in range(blur_exposures):
                f = (j + 1) / blur_exposures
                inter_x = prev_offset[0] + f * (offset_x - prev_offset[0])
                inter_y = prev_offset[1] + f * (offset_y - prev_offset[1])
                shifted_img = current_img.copy().transform(
                    current_img.size,
                    Image.AFFINE,
                    (1, 0, int(inter_x), 0, 1, int(inter_y)),
                    resample=Image.BILINEAR,
                    fillcolor=(0, 0, 0, 0)
                )
                sub_images.append(shifted_img)
            weights = [1 / blur_exposures] * blur_exposures
            final_img = blend_images(sub_images, weights)

        frames.append(final_img)
        prev_offsets[i_input] = (offset_x, offset_y)

    output_buffer = io.BytesIO()
    save_format = 'webp' if file_ext == 'webp' else 'gif'
    emote.notes["save_format"] = str(save_format)
    frames[0].save(
        output_buffer,
        format=save_format.upper(),
        save_all=True,
        append_images=frames[1:],
        duration=duration,
        loop=0,
        disposal=2
    )

    emote.img_data = output_buffer.getvalue()
    emote.file_path = f"{emote.file_path.rsplit('.', 1)[0]}.{save_format}"

    return emote


async def shake_classic(emote: Emote, intensity: float = 1) -> Emote:
    """
        Applies a shaking effect to the emote image data by creating a looping shaking GIF.

        User:
            Shakes the emote, but differently...
            Works with static images.

            Default is 1x intensity if no argument is provided.
            This effect can only be used once per emote.

            Usage:
                :aspire_shake:          - Applies a shake effect with default intensity.
                :aspire_shake(2):       - Applies a shake effect by a factor of 2.

            Alias for `:aspire_speed(2):`.

        Parameters:
            emote (Emote): The emote object containing the image data.
            intensity (int): Maximum pixel offset to apply (default is 50).
            classic (int): Shift factor to apply (default is 180).

        Returns:
            Emote: The updated emote object with the shaken animated GIF.

        Notes:
            This effect uses a spring/damping simulation to generate a looping shaking GIF.
            Image data is temporarily written to disk for processing.
        """

    emote = await shake(emote, intensity, classic=True)
    return emote


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

    import os, tempfile
    from PIL import Image

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
