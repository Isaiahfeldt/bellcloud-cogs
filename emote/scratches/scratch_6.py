import os
import random

import numpy as np
from PIL import Image


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


def create_looping_shaking_gif(
        image_path,
        output_path,
        num_frames=60,
        max_shift=50,
        duration=50,
        spring=1.3,
        damping=0.85,
        blur_exposures=10
):
    """Creates a looping shaking GIF from static or animated input."""
    if num_frames % 2 != 0:
        raise ValueError("num_frames must be even for a perfect loop.")

    # Read all frames from input (supports animated GIFs)
    img = Image.open(image_path)
    input_frames = []
    try:
        while True:
            input_frames.append(img.convert("RGBA").copy())
            img.seek(img.tell() + 1)
    except EOFError:
        pass

    # Track previous offsets for each input frame
    prev_offsets = [(0.0, 0.0) for _ in input_frames]
    frames = []

    # Generate shaking offsets
    half = num_frames // 2
    offsets = []
    curr_x, curr_y = 0.0, 0.0
    v_x, v_y = 0.0, 0.0
    step = max_shift / 10

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

    # Generate output frames
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

    # Save output GIF
    frames[0].save(
        output_path,
        save_all=True,
        append_images=frames[1:],
        duration=duration,
        loop=0,
        disposal=2
    )


if __name__ == "__main__":
    image_file = "C://Users//L378//Downloads//nofush.gif"  # Replace with your file
    if not os.path.exists(image_file):
        print(f"Error: File '{image_file}' not found.")
    else:
        create_looping_shaking_gif(
            image_file,
            "shaking_loop_transparent.gif",
            max_shift=250
        )
        print(f"Output saved to: {os.path.abspath('shaking_loop_transparent.gif')}")
