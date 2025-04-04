import io

from PIL import Image, ImageOps

from .base import Emote


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
