import io
import math
import random
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict

import aiohttp
import numpy as np
from PIL import Image, ImageOps
from skimage import color


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


def latency(emote: Emote) -> Emote:
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


def debug(emote: Emote, mode: str = "basic") -> Emote:
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
    notes["file_path"] = str(emote.file_path)
    notes["author_id"] = str(emote.author_id)
    notes["timestamp"] = str(emote.timestamp)
    notes["original_url"] = str(emote.original_url)
    notes["guild_id"] = str(emote.guild_id)
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


def train(emote: Emote, amount: int = 3) -> Emote:
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


def reverse(emote: Emote) -> Emote:
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


def fast(emote: Emote, factor: float = 2) -> Emote:
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

    emote = speed(emote, factor)
    return emote


def slow(emote: Emote, factor: float = 0.5) -> Emote:
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

    emote = speed(emote, factor)
    return emote


def speed(emote: Emote, factor: float = 2) -> Emote:
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


def invert(emote: Emote) -> Emote:
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


def blend_arrays_np(arrays: list[np.ndarray], weights: list[float]) -> np.ndarray:
    # ... (Implementation from previous answer) ...
    if not arrays:
        raise ValueError("Input array list cannot be empty")
    stacked_arrays = np.stack(arrays, axis=0)
    weights_arr = np.array(weights, dtype=np.float32).reshape(-1, 1, 1, 1)
    alpha = stacked_arrays[..., 3:4] / 255.0
    premul_rgb = stacked_arrays[..., :3] * alpha
    weighted_premul_rgb = premul_rgb * weights_arr
    weighted_alpha = stacked_arrays[..., 3:4] * weights_arr
    summed_rgb = np.sum(weighted_premul_rgb, axis=0)
    summed_alpha = np.sum(weighted_alpha, axis=0)
    epsilon = 1e-6
    safe_alpha_normalized = np.maximum(summed_alpha / 255.0, epsilon)
    final_rgb = summed_rgb / safe_alpha_normalized
    final_rgba = np.concatenate(
        (np.clip(final_rgb, 0, 255), np.clip(summed_alpha, 0, 255)),
        axis=-1
    )
    return final_rgba.astype(np.uint8)


def shake(emote: Emote, intensity: float = 1, classic: bool = False) -> Emote:
    """
    Applies a shaking effect to the emote image data by creating a looping shaking GIF.

    User:
        Shakes the emote, but differently...
        Works with static and animated images.

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
    if emote.img_data is None:
        emote.errors["shake_res"] = "No image data available."
        return emote

    allowed_extensions = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
    file_ext = emote.file_path.lower().split('.')[-1] if '.' in emote.file_path else ''
    if file_ext not in allowed_extensions:
        emote.errors["shake_res"] = f"Unsupported file type: {file_ext}. Allowed: {', '.join(allowed_extensions)}"
        return emote

    input_frames_data = []  # Store tuples: (pil_image, duration_ms)
    output_frames_pil = []  # Store final PIL frames for saving
    total_input_duration_ms = 0

    # Define the target frame duration for the output shake animation
    OUTPUT_FRAME_DURATION_MS = 30  # ~33fps for the shake smoothness
    OUTPUT_FRAME_DURATION_MS = max(20, OUTPUT_FRAME_DURATION_MS)  # Ensure min 20ms

    try:
        with Image.open(io.BytesIO(emote.img_data)) as img:
            emote.notes["original_img_size"] = str(img.size)
            n_frames = getattr(img, "n_frames", 1)
            is_animated_input = n_frames > 1

            # --- Load Input Frames & Durations ---
            last_duration = 100  # Fallback
            if is_animated_input:
                for i in range(n_frames):
                    img.seek(i)
                    current_frame_pil = img.convert("RGBA").copy()
                    duration_ms = img.info.get('duration', last_duration)
                    if not isinstance(duration_ms, (int, float)) or duration_ms <= 0:
                        duration_ms = last_duration
                    duration_ms = max(10, int(duration_ms))  # Min duration read
                    input_frames_data.append((current_frame_pil, duration_ms))
                    total_input_duration_ms += duration_ms
                    last_duration = duration_ms
            else:
                # Static image: Treat as one frame with a default duration for calculations
                img.seek(0)
                # Optional resizing for static only could go here
                input_frames_data.append((img.convert("RGBA").copy(), 1000))
                total_input_duration_ms = 1000  # Or base on OUTPUT_FRAME_DURATION_MS? Let's use 1s.

            if not input_frames_data:
                emote.errors["shake_res"] = "Could not read frames from image."
                return emote

            emote.notes["shake_res_input_frames"] = str(len(input_frames_data))
            emote.notes["shake_res_total_input_duration_ms"] = str(total_input_duration_ms)

            if total_input_duration_ms <= 0:
                emote.errors["shake_res"] = "Input animation has zero or negative total duration."
                return emote

            # --- Calculate Number of Output Frames ---
            num_output_frames = math.ceil(total_input_duration_ms / OUTPUT_FRAME_DURATION_MS)
            max_frames = 500  # Prevent excessive frames
            if num_output_frames > max_frames:
                num_output_frames = max_frames
                # Adjust output duration to cover the total time with fewer frames
                OUTPUT_FRAME_DURATION_MS = math.ceil(total_input_duration_ms / num_output_frames)
                OUTPUT_FRAME_DURATION_MS = max(20, OUTPUT_FRAME_DURATION_MS)  # Ensure minimum
                emote.issues[
                    "shake_res_frame_limit"] = f"Frame count limited to {max_frames}, output duration adjusted to {OUTPUT_FRAME_DURATION_MS}ms"

            emote.notes["shake_res_num_output_frames"] = str(num_output_frames)
            emote.notes["shake_res_output_delay_ms"] = str(OUTPUT_FRAME_DURATION_MS)

            # --- Calculate Shake Parameters ---
            img_width, img_height = input_frames_data[0][0].size
            scale = max(img_width, img_height) / 540.0
            spring = 1.3
            damping = 0.85
            blur_exposures = 10
            max_shift = (180 * scale) * intensity

            # --- Generate Shaking Offsets for OUTPUT Frames ---
            all_offsets = [(0.0, 0.0)] * num_output_frames  # Pre-allocate
            curr_x, curr_y = 0.0, 0.0
            v_x, v_y = 0.0, 0.0
            step = max_shift / 10.0

            # Generate offsets for the required number of output frames using simulation step
            # We can use the ping-pong approach if desired for looping.
            half_frames = math.ceil(num_output_frames / 2.0)
            temp_offsets = []
            for i in range(half_frames + 1):  # Generate a bit more than half
                force_x = random.uniform(-step, step)
                force_y = random.uniform(-step, step)
                v_x = damping * (v_x + force_x - spring * curr_x)
                v_y = damping * (v_y + force_y - spring * curr_y)
                curr_x += v_x
                curr_y += v_y
                curr_x = max(min(curr_x, max_shift), -max_shift)
                curr_y = max(min(curr_y, max_shift), -max_shift)
                temp_offsets.append((curr_x, curr_y))

            # Construct the full list ensuring it has exactly num_output_frames
            # Use the first half, then reverse the middle part
            first_half = temp_offsets[:half_frames]
            # Reverse part excluding the very first and potentially the last elements generated
            reversed_part = list(reversed(temp_offsets[1:half_frames]))  # Adjust indices carefully

            all_offsets_generated = first_half + reversed_part
            # Trim or pad if necessary to match num_output_frames exactly
            all_offsets = all_offsets_generated[:num_output_frames]
            # If too short (e.g., num_output_frames=1), ensure it has at least one element
            if not all_offsets and temp_offsets:
                all_offsets = [temp_offsets[0]] * num_output_frames
            elif len(all_offsets) < num_output_frames:  # Pad if needed
                all_offsets.extend([all_offsets[-1]] * (num_output_frames - len(all_offsets)))

            # --- Resampling Loop ---
            input_frame_index = 0
            current_input_frame_end_time = 0  # Tracks end time of input_frame_index

            blur_weights = [1.0 / blur_exposures] * blur_exposures

            for j in range(num_output_frames):  # Iterate through OUTPUT frames
                # Time at the *start* of this output frame
                current_output_time_ms = j * OUTPUT_FRAME_DURATION_MS

                # --- Find the correct input frame for this time ---
                while current_input_frame_end_time <= current_output_time_ms and input_frame_index < len(
                        input_frames_data) - 1:
                    current_input_frame_end_time += input_frames_data[input_frame_index][1]
                    input_frame_index += 1

                # Get the PIL Image of the correct input frame
                source_frame_pil = input_frames_data[input_frame_index][0]
                current_img_size = source_frame_pil.size

                # --- Get Shake Offset for CURRENT output frame ---
                offset_x, offset_y = all_offsets[j]

                # --- Determine Offsets for Motion Blur ---
                if j == 0 or blur_exposures <= 1:
                    # --- No Motion Blur ---
                    shifted_pil = source_frame_pil.transform(
                        current_img_size, Image.AFFINE,
                        (1, 0, int(offset_x), 0, 1, int(offset_y)),
                        resample=Image.BILINEAR, fillcolor=(0, 0, 0, 0)
                    )
                    final_img_pil = shifted_pil
                else:
                    # --- Apply Motion Blur ---
                    # Use offset from *previous output frame* and *current output frame*
                    prev_offset_x, prev_offset_y = all_offsets[j - 1]
                    sub_arrays_f32 = []
                    for k in range(blur_exposures):
                        f = (k + 1) / blur_exposures
                        inter_x = prev_offset_x + f * (offset_x - prev_offset_x)
                        inter_y = prev_offset_y + f * (offset_y - prev_offset_y)

                        # Transform the *source* PIL image for this sub-frame
                        shifted_pil_sub = source_frame_pil.transform(
                            current_img_size, Image.AFFINE,
                            (1, 0, int(inter_x), 0, 1, int(inter_y)),
                            resample=Image.BILINEAR, fillcolor=(0, 0, 0, 0)
                        )
                        sub_arrays_f32.append(np.array(shifted_pil_sub).astype(np.float32))

                    # Blend using optimized function
                    final_np_uint8 = blend_arrays_np(sub_arrays_f32, blur_weights)
                    final_img_pil = Image.fromarray(final_np_uint8, 'RGBA')

                # Append the final PIL image for this output frame
                output_frames_pil.append(final_img_pil)

            # --- Save Output ---
            if not output_frames_pil:
                emote.errors["shake_res"] = "No output frames generated."
                return emote

            output_buffer = io.BytesIO()
            # Determine save format based on original, default to GIF
            save_format = 'webp' if file_ext == 'webp' else 'gif'
            emote.notes["shake_res_save_format"] = str(save_format)

            output_frames_pil[0].save(
                output_buffer,
                format=save_format.upper(),
                save_all=True,
                append_images=output_frames_pil[1:],
                duration=OUTPUT_FRAME_DURATION_MS,  # Use fixed output duration
                loop=0,
                disposal=2,
                optimize=True
            )

            emote.img_data = output_buffer.getvalue()
            emote.file_path = f"{emote.file_path.rsplit('.', 1)[0]}_shake.{save_format}"
            emote.notes["shake_res_method"] = "resampled_vectorized_blend"

    except MemoryError:
        emote.errors["shake_res"] = "MemoryError: Input image/animation too large or long to process."
    except Exception as e:
        tb = traceback.format_exc()
        emote.errors["shake_res"] = f"Error applying resampled shake effect: {e}\n```\n{tb}\n```"
        # Clean up potentially large lists
        input_frames_data.clear()
        output_frames_pil.clear()

    return emote


def flip(emote: Emote, direction: str = "h") -> Emote:
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
            emote.errors["flip"] = str(error_details)
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


def rainbow(emote: Emote, speed: float = 1.0) -> Emote:
    """
        Applies a continuous rainbow hue cycling effect, preserving original timing.
    
        Uses vectorized operations (skimage) and resamples the input animation onto
        a new timeline with a fixed frame rate for the rainbow effect, while showing
        the correct original frame content based on elapsed time.
    
        User:
            Adds a rainbow hue-cycling effect to the emote.
    
            You can adjust the speed of the hue cycling using the `speed` parameter. 
            A higher speed value increases the rate of hue rotation, while lower values slow it down.
    
            Works with static and animated images.
    
            Example usage:
            `:aspire_rainbow:` - Adds the rainbow effect with default speed.
            `:aspire_rainbow(0.5):` - Adds the effect with slower cycling speed.
            `:aspire_rainbow(2.0):` - Adds the effect with faster cycling speed.
    
        Parameters:
            emote (Emote): The emote object.
            speed (float): Multiplier for the hue cycle speed (cycles per second).
    
        Returns:
            Emote: The updated emote object.
    """
