import io
import math
import random

import numpy as np
from PIL import Image

from .base import Emote


async def shake(emote: Emote, intensity: float = 1, classic: bool = False) -> Emote:
    if emote.img_data is None:
        emote.errors["shake"] = "No image data available for shaking effect."
        return emote

    allowed_extensions = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
    file_ext = emote.file_path.lower().split('.')[-1]
    if file_ext not in allowed_extensions:
        emote.errors["shake"] = f"Unsupported file type: {file_ext}. Allowed: {', '.join(allowed_extensions)}"
        return emote

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
    emote.notes["original_img_size"] = str(img.size)

    if not getattr(img, "is_animated", False):
        max_dimension = 600  # Maximum size for either width or height
        if max(img.size) > max_dimension:
            # Resize while maintaining aspect ratio
            img.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
            emote.notes["new_img_size"] = str(img.size)

    input_frames = []
    try:
        while True:
            input_frames.append(img.convert("RGBA").copy())
            img.seek(img.tell() + 1)
    except EOFError:
        pass

    orig_duration = int(len(input_frames))
    if orig_duration < 25:
        duration = int(orig_duration * math.ceil(50 / orig_duration)) / 2
    else:
        duration = int(orig_duration / 2)

    # Calculate scale based on first frame
    img_width, img_height = input_frames[0].size
    scale = max(img_width, img_height) / 540.0
    spring = 1.3
    damping = 0.85
    blur_exposures = 10
    num_frames = int(duration)
    max_shift = (180 * scale) * intensity

    # Generate shaking offsets
    half = num_frames // 2
    offsets = []
    curr_x, curr_y = 0.0, 0.0
    v_x, v_y = 0.0, 0.0
    step = max_shift / 10
    prev_offsets = [(0.0, 0.0) for _ in input_frames]
    frames = []

    emote.notes["Scale"] = str(scale)
    emote.notes["max_shift after"] = str((250 * scale) if classic else (180 * scale))
    emote.notes["original_file_ext"] = str(file_ext)
    emote.notes["orig_duration"] = orig_duration
    emote.notes["new_duration"] = str(duration)

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
