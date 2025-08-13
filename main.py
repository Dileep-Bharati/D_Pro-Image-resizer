from flask import Flask, render_template, request, send_file, jsonify, url_for
from PIL import Image
import io
import os
import uuid
import zipfile # For creating .zip files
import shutil # For deleting temporary folders

app = Flask(__name__)
app.secret_key = 'a_super_secret_key_for_production'

# --- Core processing functions (no changes to these three) ---
def resize_by_dimension(form, image_file):
    # (Unchanged)
    try:
        unit, width, height, output_format, maintain_aspect_ratio, transform = form.get('unit'), float(form.get('width')), float(form.get('height')), form.get('format', 'jpeg'), form.get('aspect_ratio'), form.get('transform')
        if unit in ['cm', 'mm']:
            dpi = int(form.get('dpi', 96)); INCH_TO_CM = 2.54
            if unit == 'cm': width_px, height_px = round((width / INCH_TO_CM) * dpi), round((height / INCH_TO_CM) * dpi)
            else: width_px, height_px = round((width / (INCH_TO_CM * 10)) * dpi), round((height / (INCH_TO_CM * 10)) * dpi)
        else: width_px, height_px = int(width), int(height)
        img = Image.open(image_file.stream)
        if transform == 'rotate_90': img = img.transpose(Image.Transpose.ROTATE_90)
        elif transform == 'rotate_180': img = img.transpose(Image.Transpose.ROTATE_180)
        elif transform == 'rotate_270': img = img.transpose(Image.Transpose.ROTATE_270)
        elif transform == 'flip_horizontal': img = img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        elif transform == 'flip_vertical': img = img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        if maintain_aspect_ratio: img.thumbnail((width_px, height_px)); resized_img = img
        else: resized_img = img.resize((width_px, height_px), Image.Resampling.LANCZOS)
        if output_format == 'jpeg' and resized_img.mode == 'RGBA': resized_img = resized_img.convert('RGB')
        format_to_save = 'JPEG' if output_format == 'jpeg' else output_format.upper()
        unique_filename = f"{uuid.uuid4()}.{output_format}"
        save_path = os.path.join('temp', unique_filename)
        save_params = {}
        if output_format in ['jpeg', 'webp']: save_params['quality'] = int(form.get('quality', 85))
        resized_img.save(save_path, format_to_save, **save_params)
        return save_path
    except Exception: return None

def reduce_by_filesize(form, image_file):
    # (Unchanged)
    try:
        target_size, size_unit = int(form.get('target_size')), form.get('size_unit')
        target_bytes = target_size * 1024 if size_unit == 'KB' else target_size * 1024 * 1024
        img = Image.open(image_file.stream)
        if img.mode == 'RGBA': img = img.convert('RGB')
        quality, step, img_io = 95, 5, io.BytesIO()
        while quality > 0:
            img_io.seek(0); img_io.truncate()
            img.save(img_io, format='JPEG', quality=quality, optimize=True)
            if img_io.tell() <= target_bytes: break
            quality -= step
        unique_filename, save_path = f"{uuid.uuid4()}.jpg", os.path.join('temp', unique_filename)
        with open(save_path, 'wb') as f: f.write(img_io.getvalue())
        return save_path
    except Exception: return None

def crop_image(form, image_file):
    # (Unchanged)
    try:
        img = Image.open(image_file.stream)
        x, y, width, height = int(float(form.get('crop_x'))), int(float(form.get('crop_y'))), int(float(form.get('crop_width'))), int(float(form.get('crop_height')))
        box, cropped_img = (x, y, x + width, y + height), img.crop(box)
        original_format = img.format or 'PNG'
        unique_filename, save_path = f"cropped-{uuid.uuid4()}.{original_format.lower()}", os.path.join('temp', unique_filename)
        cropped_img.save(save_path, format=original_format)
        return save_path
    except Exception: return None

# --- NEW FUNCTION FOR BULK RESIZING ---
def bulk_resize_images(form, image_files):
    # Create a unique temporary folder for this job
    job_id = str(uuid.uuid4())
    job_folder = os.path.join('temp', job_id)
    os.makedirs(job_folder)
    
    # Process each file and save it in the job folder
    for image_file in image_files:
        try:
            # We reuse the single-image resize logic, but save to a different path
            # (Replicating logic here for clarity, could be refactored)
            unit, width, height, output_format, maintain_aspect_ratio = form.get('unit'), float(form.get('width')), float(form.get('height')), form.get('format', 'jpeg'), form.get('aspect_ratio')
            if unit in ['cm', 'mm']:
                dpi = int(form.get('dpi', 96)); INCH_TO_CM = 2.54
                if unit == 'cm': width_px, height_px = round((width/INCH_TO_CM)*dpi), round((height/INCH_TO_CM)*dpi)
                else: width_px, height_px = round((width/(INCH_TO_CM*10))*dpi), round((height/(INCH_TO_CM*10))*dpi)
            else: width_px, height_px = int(width), int(height)
            img = Image.open(image_file.stream)
            if maintain_aspect_ratio: img.thumbnail((width_px, height_px)); resized_img = img
            else: resized_img = img.resize((width_px, height_px), Image.Resampling.LANCZOS)
            if output_format == 'jpeg' and resized_img.mode == 'RGBA': resized_img = resized_img.convert('RGB')
            format_to_save = 'JPEG' if output_format == 'jpeg' else output_format.upper()
            save_params = {}
            if output_format in ['jpeg', 'webp']: save_params['quality'] = int(form.get('quality', 85))
            # Use original filename and save to job folder
            save_path = os.path.join(job_folder, f"resized-{os.path.splitext(image_file.filename)[0]}.{output_format}")
            resized_img.save(save_path, format_to_save, **save_params)
        except Exception:
            continue # Skip files that cause errors

    # Zip the contents of the job folder
    zip_filename = f"{job_id}.zip"
    zip_path = os.path.join('temp', zip_filename)
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for root, _, files in os.walk(job_folder):
            for file in files:
                zipf.write(os.path.join(root, file), arcname=file)
    
    # Clean up by deleting the temporary job folder
    shutil.rmtree(job_folder)
    
    return zip_path

# --- Main Routes ---
@app.route('/temp/<filename>')
def serve_temp_file(filename):
    return send_file(os.path.join('temp', filename), as_attachment=True)

@app.route('/')
def index():
    active_tool, active_format = request.args.get('tool', 'resizer'), request.args.get('format', None)
    return render_template('index.html', active_tool=active_tool, active_format=active_format)

@app.route('/crop', methods=['GET', 'POST'])
def crop_page():
    if request.method == 'POST':
        image_file = request.files.get('image')
        if not image_file: return jsonify({'error': 'No image file uploaded!'}), 400
        file_path = crop_image(request.form, image_file)
        if file_path:
            download_url = url_for('serve_temp_file', filename=os.path.basename(file_path))
            return jsonify({'success': True, 'download_url': download_url})
        else: return jsonify({'error': 'An error occurred during cropping.'}), 500
    return render_template('crop.html')

# THIS ROUTE IS NOW UPDATED
@app.route('/bulk-resize', methods=['GET', 'POST'])
def bulk_resize_page():
    if request.method == 'POST':
        # Get the list of all uploaded files
        image_files = request.files.getlist('images[]')
        if not image_files:
            return jsonify({'error': 'No image files uploaded!'}), 400
        
        # Call the new bulk resize function
        file_path = bulk_resize_images(request.form, image_files)

        if file_path:
            download_url = url_for('serve_temp_file', filename=os.path.basename(file_path))
            return jsonify({'success': True, 'download_url': download_url})
        else:
            return jsonify({'error': 'An error occurred during bulk processing.'}), 500

    return render_template('bulk-resize.html')

@app.route('/process', methods=['POST'])
def process_image():
    # (Unchanged)
    image_file = request.files.get('image')
    if not image_file: return jsonify({'error': 'No image file selected!'}), 400
    mode = request.form.get('mode')
    file_path = None
    if mode == 'dimension': file_path = resize_by_dimension(request.form, image_file)
    elif mode == 'filesize': file_path = reduce_by_filesize(request.form, image_file)
    if file_path:
        download_url = url_for('serve_temp_file', filename=os.path.basename(file_path))
        return jsonify({'success': True, 'download_url': download_url})
    else: return jsonify({'error': 'An error occurred during processing.'}), 500

if __name__ == '__main__':
    if not os.path.exists('temp'): os.makedirs('temp')
    app.run(debug=True)