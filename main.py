from flask import Flask, render_template, request, send_file, jsonify, url_for
from PIL import Image
import io
import os
import uuid

app = Flask(__name__)
app.secret_key = 'a_super_secret_key_for_production'

# --- The core processing functions ---
def resize_by_dimension(form, image_file):
    # This function is complete and has no changes
    try:
        unit = form.get('unit')
        width = float(form.get('width'))
        height = float(form.get('height'))
        output_format = form.get('format', 'jpeg')
        maintain_aspect_ratio = form.get('aspect_ratio')
        transform = form.get('transform')
        if unit in ['cm', 'mm']:
            dpi = int(form.get('dpi', 96))
            INCH_TO_CM = 2.54
            if unit == 'cm': width_px, height_px = round((width / INCH_TO_CM) * dpi), round((height / INCH_TO_CM) * dpi)
            else: width_px, height_px = round((width / (INCH_TO_CM * 10)) * dpi), round((height / (INCH_TO_CM * 10)) * dpi)
        else: width_px, height_px = int(width), int(height)
        img = Image.open(image_file.stream)
        if transform == 'rotate_90': img = img.transpose(Image.Transpose.ROTATE_90)
        elif transform == 'rotate_180': img = img.transpose(Image.Transpose.ROTATE_180)
        elif transform == 'rotate_270': img = img.transpose(Image.Transpose.ROTATE_270)
        elif transform == 'flip_horizontal': img = img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        elif transform == 'flip_vertical': img = img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        if maintain_aspect_ratio:
            img.thumbnail((width_px, height_px))
            resized_img = img
        else: resized_img = img.resize((width_px, height_px), Image.Resampling.LANCZOS)
        if output_format == 'jpeg' and resized_img.mode == 'RGBA': resized_img = resized_img.convert('RGB')
        format_to_save = 'JPEG' if output_format == 'jpeg' else output_format.upper()
        unique_filename = f"{uuid.uuid4()}.{output_format}"
        save_path = os.path.join('temp', unique_filename)
        save_params = {}
        if output_format in ['jpeg', 'webp']:
            quality = int(form.get('quality', 85))
            save_params['quality'] = quality
        resized_img.save(save_path, format_to_save, **save_params)
        return save_path
    except Exception as e: return None

def reduce_by_filesize(form, image_file):
    # This function is complete and has no changes
    try:
        target_size = int(form.get('target_size'))
        size_unit = form.get('size_unit')
        target_bytes = target_size * 1024 if size_unit == 'KB' else target_size * 1024 * 1024
        img = Image.open(image_file.stream)
        if img.mode == 'RGBA': img = img.convert('RGB')
        quality, step = 95, 5
        img_io = io.BytesIO()
        while quality > 0:
            img_io.seek(0); img_io.truncate()
            img.save(img_io, format='JPEG', quality=quality, optimize=True)
            if img_io.tell() <= target_bytes: break
            quality -= step
        unique_filename = f"{uuid.uuid4()}.jpg"
        save_path = os.path.join('temp', unique_filename)
        with open(save_path, 'wb') as f: f.write(img_io.getvalue())
        return save_path
    except Exception as e: return None

# --- NEW FUNCTION FOR CROPPING ---
def crop_image(form, image_file):
    try:
        img = Image.open(image_file.stream)
        # Get coordinates from the form, sent by Cropper.js
        x = int(float(form.get('crop_x')))
        y = int(float(form.get('crop_y')))
        width = int(float(form.get('crop_width')))
        height = int(float(form.get('crop_height')))

        # Define the crop box (left, upper, right, lower)
        box = (x, y, x + width, y + height)
        cropped_img = img.crop(box)

        # Save the cropped image
        original_format = img.format or 'PNG' # Default to PNG if format is not detectable
        unique_filename = f"cropped-{uuid.uuid4()}.{original_format.lower()}"
        save_path = os.path.join('temp', unique_filename)
        cropped_img.save(save_path, format=original_format)
        return save_path
    except Exception as e:
        print(f"Error in crop_image: {e}")
        return None

# --- Main Routes ---
@app.route('/temp/<filename>')
def serve_temp_file(filename):
    return send_file(os.path.join('temp', filename))

@app.route('/')
def index():
    active_tool = request.args.get('tool', 'resizer')
    active_format = request.args.get('format', None)
    return render_template('index.html', active_tool=active_tool, active_format=active_format)

# THIS ROUTE IS NOW UPDATED
@app.route('/crop', methods=['GET', 'POST'])
def crop_page():
    if request.method == 'POST':
        image_file = request.files.get('image')
        if not image_file:
            return jsonify({'error': 'No image file uploaded!'}), 400
        
        # Call the new crop function
        file_path = crop_image(request.form, image_file)

        if file_path:
            download_url = url_for('serve_temp_file', filename=os.path.basename(file_path), _external=True)
            return jsonify({'success': True, 'download_url': download_url})
        else:
            return jsonify({'error': 'An error occurred during cropping.'}), 500

    # This handles the GET request (initial page load)
    return render_template('crop.html')

@app.route('/process', methods=['POST'])
def process_image():
    # This function is complete and has no changes
    image_file = request.files.get('image')
    if not image_file: return jsonify({'error': 'No image file selected!'}), 400
    mode = request.form.get('mode')
    file_path = None
    if mode == 'dimension': file_path = resize_by_dimension(request.form, image_file)
    elif mode == 'filesize': file_path = reduce_by_filesize(request.form, image_file)
    if file_path:
        download_url = url_for('serve_temp_file', filename=os.path.basename(file_path), _external=True)
        return jsonify({'success': True, 'download_url': download_url})
    else: return jsonify({'error': 'An error occurred during processing.'}), 500

if __name__ == '__main__':
    if not os.path.exists('temp'):
        os.makedirs('temp')
    app.run(debug=True)