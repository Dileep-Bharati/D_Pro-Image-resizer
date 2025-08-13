from flask import Flask, render_template, request, send_file, flash
from PIL import Image
import io

app = Flask(__name__)
# A secret key is needed for flashing messages
app.secret_key = 'a_super_secret_key_for_production'

def resize_by_dimension(form, image_file):
    """Handles the logic for the 'Resize by Dimension' tab."""
    try:
        # --- This is the logic from our previous steps ---
        unit = form.get('unit')
        width = float(form.get('width'))
        height = float(form.get('height'))
        output_format = form.get('format', 'jpeg')
        maintain_aspect_ratio = form.get('aspect_ratio')
        transform = form.get('transform')

        if unit in ['cm', 'mm']:
            dpi = int(form.get('dpi', 96))
            INCH_TO_CM = 2.54
            if unit == 'cm':
                width_px = round((width / INCH_TO_CM) * dpi)
                height_px = round((height / INCH_TO_CM) * dpi)
            else:
                width_px = round((width / (INCH_TO_CM * 10)) * dpi)
                height_px = round((height / (INCH_TO_CM * 10)) * dpi)
        else:
            width_px = int(width)
            height_px = int(height)
        
        img = Image.open(image_file.stream)

        if transform == 'rotate_90': img = img.transpose(Image.Transpose.ROTATE_90)
        elif transform == 'rotate_180': img = img.transpose(Image.Transpose.ROTATE_180)
        elif transform == 'rotate_270': img = img.transpose(Image.Transpose.ROTATE_270)
        elif transform == 'flip_horizontal': img = img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        elif transform == 'flip_vertical': img = img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)

        if maintain_aspect_ratio:
            img.thumbnail((width_px, height_px))
            resized_img = img
        else:
            resized_img = img.resize((width_px, height_px), Image.Resampling.LANCZOS)

        if output_format == 'jpeg' and resized_img.mode == 'RGBA':
            resized_img = resized_img.convert('RGB')

        img_io = io.BytesIO()
        format_to_save = 'JPEG' if output_format == 'jpeg' else output_format.upper()
        
        save_params = {}
        if output_format in ['jpeg', 'webp']:
            quality = int(form.get('quality', 85))
            save_params['quality'] = quality
        
        resized_img.save(img_io, format_to_save, **save_params)
        
        img_io.seek(0)
        download_name = f'resized_image.{output_format}'
        mimetype = f'image/{output_format}'
        return send_file(img_io, mimetype=mimetype, as_attachment=True, download_name=download_name)
    except Exception as e:
        flash(f"An error occurred: {e}")
        return render_template('index.html')


def reduce_by_filesize(form, image_file):
    """Handles the logic for the 'Reduce by File Size' tab."""
    try:
        target_size = int(form.get('target_size'))
        size_unit = form.get('size_unit')
        
        # Convert target size to bytes
        target_bytes = target_size * 1024 if size_unit == 'KB' else target_size * 1024 * 1024

        img = Image.open(image_file.stream)
        
        # This mode works best with JPEG, so we'll convert to it.
        # If the image has transparency, convert to RGB first.
        if img.mode == 'RGBA':
            img = img.convert('RGB')
        
        # --- The Iterative Search Algorithm ---
        # Start with the highest quality and decrease until the target size is met.
        quality = 95
        step = 5
        
        while quality > 0:
            img_io = io.BytesIO()
            img.save(img_io, format='JPEG', quality=quality, optimize=True)
            
            # Check the size of the saved image in memory
            current_size = img_io.tell()
            
            if current_size <= target_bytes:
                # Success! We are under the target size.
                break
            
            # If not, reduce quality and try again.
            quality -= step

        if quality <= 0:
            # This happens if we couldn't meet the target even at the lowest quality.
            # We will just send the lowest quality version.
            flash("Could not meet the target size even at lowest quality. Result is the smallest possible.")

        img_io.seek(0)
        download_name = f'reduced_to_{target_size}{size_unit}.jpg'
        return send_file(img_io, mimetype='image/jpeg', as_attachment=True, download_name=download_name)
    except Exception as e:
        flash(f"An error occurred: {e}")
        return render_template('index.html')


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        image_file = request.files.get('image')
        if not image_file:
            flash("No image file selected!")
            return render_template('index.html')

        mode = request.form.get('mode')

        if mode == 'dimension':
            return resize_by_dimension(request.form, image_file)
        elif mode == 'filesize':
            return reduce_by_filesize(request.form, image_file)
        else:
            flash("Invalid operation mode selected.")
            return render_template('index.html')

    # This is for the GET request (initial page load)
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)