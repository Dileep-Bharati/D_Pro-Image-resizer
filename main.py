from flask import Flask, render_template, request, send_file, jsonify, url_for
from PIL import Image, ImageDraw, ImageFont
import io
import os
import uuid
import zipfile
import shutil
import textwrap

app = Flask(__name__)
app.secret_key = 'a_super_secret_key_for_production'


# --- Core processing functions ---

def resize_by_dimension(form, image_file):
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
            if unit == 'cm':
                width_px, height_px = round((width / INCH_TO_CM) * dpi), round((height / INCH_TO_CM) * dpi)
            else:
                width_px, height_px = round((width / (INCH_TO_CM * 10)) * dpi), round((height / (INCH_TO_CM * 10)) * dpi)
        else:
            width_px, height_px = int(width), int(height)
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
        format_to_save = 'JPEG' if output_format == 'jpeg' else output_format.upper()
        unique_filename = f"{uuid.uuid4()}.{output_format}"
        save_path = os.path.join('temp', unique_filename)
        save_params = {}
        if output_format in ['jpeg', 'webp']:
            save_params['quality'] = int(form.get('quality', 85))
        resized_img.save(save_path, format_to_save, **save_params)
        return save_path
    except Exception as e:
        print(f"Error in resize_by_dimension: {e}")
        return None

def reduce_by_filesize(form, image_file):
    try:
        target_size = int(form.get('target_size'))
        size_unit = form.get('size_unit')
        target_bytes = target_size * 1024 if size_unit == 'KB' else target_size * 1024 * 1024
        img = Image.open(image_file.stream)
        if img.mode == 'RGBA':
            img = img.convert('RGB')
        quality, step, img_io = 95, 5, io.BytesIO()
        while quality > 0:
            img_io.seek(0); img_io.truncate()
            img.save(img_io, format='JPEG', quality=quality, optimize=True)
            if img_io.tell() <= target_bytes:
                break
            quality -= step
        unique_filename = f"{uuid.uuid4()}.jpg"
        save_path = os.path.join('temp', unique_filename)
        with open(save_path, 'wb') as f:
            f.write(img_io.getvalue())
        return save_path
    except Exception as e:
        print(f"Error in reduce_by_filesize: {e}")
        return None

def crop_image(form, image_file):
    try:
        img = Image.open(image_file.stream)
        x = int(float(form.get('crop_x')))
        y = int(float(form.get('crop_y')))
        width = int(float(form.get('crop_width')))
        height = int(float(form.get('crop_height')))
        box = (x, y, x + width, y + height)
        cropped_img = img.crop(box)
        original_format = img.format or 'PNG'
        unique_filename = f"cropped-{uuid.uuid4()}.{original_format.lower()}"
        save_path = os.path.join('temp', unique_filename)
        cropped_img.save(save_path, format=original_format)
        return save_path
    except Exception as e:
        print(f"Error in crop_image: {e}")
        return None

def bulk_resize_images(form, image_files):
    try:
        job_id = str(uuid.uuid4())
        job_folder = os.path.join('temp', job_id)
        os.makedirs(job_folder)
        for image_file in image_files:
            try:
                resized_path = resize_by_dimension(form, image_file)
                if resized_path:
                    shutil.move(resized_path, os.path.join(job_folder, os.path.basename(resized_path)))
            except Exception as e:
                print(f"Could not process {image_file.filename} in bulk: {e}")
                continue
        zip_filename = f"{job_id}.zip"
        zip_path = os.path.join('temp', zip_filename)
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for root, _, files in os.walk(job_folder):
                for file in files:
                    zipf.write(os.path.join(root, file), arcname=file)
        shutil.rmtree(job_folder)
        return zip_path
    except Exception as e:
        if 'job_folder' in locals() and os.path.exists(job_folder):
            shutil.rmtree(job_folder)
        print(f"Error in bulk_resize_images: {e}")
        return None

def convert_image(form, image_file):
    try:
        img = Image.open(image_file.stream)
        output_format = form.get('format', 'jpeg')
        if output_format == 'jpeg' and img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        format_to_save = 'JPEG' if output_format == 'jpeg' else output_format.upper()
        unique_filename = f"converted-{uuid.uuid4()}.{output_format}"
        save_path = os.path.join('temp', unique_filename)
        img.save(save_path, format=format_to_save)
        return save_path
    except Exception as e:
        print(f"Error in convert_image: {e}")
        return None

def transform_image(form, image_file):
    try:
        img = Image.open(image_file.stream)
        operation = form.get('operation')
        if operation == 'rotate_90': transformed_img = img.transpose(Image.Transpose.ROTATE_90)
        elif operation == 'rotate_180': transformed_img = img.transpose(Image.Transpose.ROTATE_180)
        elif operation == 'rotate_270': transformed_img = img.transpose(Image.Transpose.ROTATE_270)
        elif operation == 'flip_horizontal': transformed_img = img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        elif operation == 'flip_vertical': transformed_img = img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        else: return None
        original_format = img.format or 'PNG'
        unique_filename = f"transformed-{uuid.uuid4()}.{original_format.lower()}"
        save_path = os.path.join('temp', unique_filename)
        transformed_img.save(save_path, format=original_format)
        return save_path
    except Exception as e:
        print(f"Error in transform_image: {e}")
        return None
        
def generate_meme(form, image_file):
    try:
        top_text = form.get('top_text', '').upper()
        bottom_text = form.get('bottom_text', '').upper()
        img = Image.open(image_file.stream).convert("RGBA")
        draw = ImageDraw.Draw(img)
        font_path = os.path.join('static', 'impact.ttf')
        font_size = int(img.width / 10)
        font = ImageFont.truetype(font_path, size=font_size)

        def draw_text_with_outline(text, position):
            lines = textwrap.wrap(text, width=20)
            if position == 'top':
                y = 10
            else: # bottom
                total_text_height = sum([font.getbbox(line)[3] + 5 for line in lines])
                y = img.height - total_text_height
            
            for line in lines:
                line_width, line_height = font.getbbox(line)[2], font.getbbox(line)[3]
                x = (img.width - line_width) / 2
                
                draw.text((x-2, y-2), line, font=font, fill='black')
                draw.text((x+2, y-2), line, font=font, fill='black')
                draw.text((x-2, y+2), line, font=font, fill='black')
                draw.text((x+2, y+2), line, font=font, fill='black')
                draw.text((x, y), line, font=font, fill='white')
                
                y += line_height + 5

        if top_text:
            draw_text_with_outline(top_text, 'top')
        if bottom_text:
            draw_text_with_outline(bottom_text, 'bottom')

        unique_filename = f"meme-{uuid.uuid4()}.jpg"
        save_path = os.path.join('temp', unique_filename)
        img = img.convert('RGB')
        img.save(save_path, 'JPEG')
        return save_path

    except Exception as e:
        print(f"CRITICAL ERROR in generate_meme: {e}")
        return None


# --- Main Routes ---
@app.route('/temp/<filename>')
def serve_temp_file(filename):
    return send_file(os.path.join('temp', filename), as_attachment=True)

@app.route('/')
def index():
    active_tool = request.args.get('tool', 'resizer')
    active_format = request.args.get('format', None)
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

@app.route('/bulk-resize', methods=['GET', 'POST'])
def bulk_resize_page():
    if request.method == 'POST':
        image_files = request.files.getlist('images[]')
        if not image_files: return jsonify({'error': 'No image files uploaded!'}), 400
        file_path = bulk_resize_images(request.form, image_files)
        if file_path:
            download_url = url_for('serve_temp_file', filename=os.path.basename(file_path))
            return jsonify({'success': True, 'download_url': download_url})
        else: return jsonify({'error': 'An error occurred during bulk processing.'}), 500
    return render_template('bulk-resize.html')

@app.route('/convert', methods=['GET', 'POST'])
def convert_page():
    if request.method == 'POST':
        image_file = request.files.get('image')
        if not image_file: return jsonify({'error': 'No image file uploaded!'}), 400
        file_path = convert_image(request.form, image_file)
        if file_path:
            download_url = url_for('serve_temp_file', filename=os.path.basename(file_path))
            return jsonify({'success': True, 'download_url': download_url})
        else: return jsonify({'error': 'An error occurred during conversion.'}), 500
    return render_template('convert.html')

@app.route('/transform', methods=['GET', 'POST'])
def transform_page():
    if request.method == 'POST':
        image_file = request.files.get('image')
        if not image_file: return jsonify({'error': 'No image file uploaded!'}), 400
        file_path = transform_image(request.form, image_file)
        if file_path:
            download_url = url_for('serve_temp_file', filename=os.path.basename(file_path))
            return jsonify({'success': True, 'download_url': download_url})
        else: return jsonify({'error': 'An error occurred during transformation.'}), 500
    return render_template('transform.html')

@app.route('/meme', methods=['GET', 'POST'])
def meme_page():
    if request.method == 'POST':
        image_file = request.files.get('image')
        if not image_file: return jsonify({'error': 'No image file uploaded!'}), 400
        file_path = generate_meme(request.form, image_file)
        if file_path:
            download_url = url_for('serve_temp_file', filename=os.path.basename(file_path))
            return jsonify({'success': True, 'download_url': download_url})
        else: return jsonify({'error': 'An error occurred during meme generation.'}), 500
    return render_template('meme.html')

@app.route('/process', methods=['POST'])
def process_image():
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