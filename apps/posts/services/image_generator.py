# apps/posts/services/image_generator.py

import os
import re
import io
from PIL import Image, ImageDraw, ImageFont
from django.conf import settings

try:
    from fontTools.merge import Merger
except ImportError:
    raise ImportError("Error: fontTools is not installed. Please install it using: pip install fonttools")

class InstagramPostError(Exception): pass
class FontError(InstagramPostError): pass
class InvalidParameterError(InstagramPostError): pass
class FileSystemError(InstagramPostError): pass

class InstagramPostGenerator:
    def __init__(self, username: str, post_id: str, message: str, short_date: str, title: str, **kwargs):
        self.WIDTH, self.HEIGHT, self.BG_COLOR = 1080, 1350, "#1A1A1A"
        self.border_width, self.border_radius, self.border_color = 6, 30, "#FFFFFF"
        self.HEADER_HEIGHT = int(self.HEIGHT * 0.10)
        self.HEADER_BG_COLOR = self.border_color
        self.HEADER_SIDE_TEXT_COLOR, self.HEADER_CENTER_TEXT_COLOR, self.HEADER_BORDER_COLOR = "#A0A0A0", "#3D3D3D", "#333333"
        self.AVATAR_BG_COLOR, self.AVATAR_TEXT_COLOR = "#4169E1", "#FFFFFF"
        self.USERNAME_COLOR, self.BUBBLE_COLOR, self.MESSAGE_TEXT_COLOR = "#A0A0A0", "#3E3E3E", "#FFFFFF"

        self._validate_and_set_inputs(username, post_id, message, short_date, title)
        self._apply_customizations(kwargs)
        self.font_path = self._get_or_create_merged_font()
        self.image = Image.new('RGB', (self.WIDTH, self.HEIGHT), color=self.BG_COLOR)
        self.draw = ImageDraw.Draw(self.image)

    def _validate_color(self, color_string: str, param_name: str):
        if not isinstance(color_string, str) or not re.match(r'^#(?:[A-Fa-f0-9]{3}){1,2}$', color_string):
            raise InvalidParameterError(f"Parameter '{param_name}' has an invalid hex color format: '{color_string}'")

    def _apply_customizations(self, kwargs: dict):
        for key, value in kwargs.items():
            if hasattr(self, key):
                if key in ['border_width', 'border_radius'] and (not isinstance(value, int) or value < 0):
                    raise InvalidParameterError(f"Parameter '{key}' must be a non-negative integer, got '{value}'.")
                elif key.endswith('_color'):
                    self._validate_color(value, key)
                setattr(self, key, value)
        if 'HEADER_BG_COLOR' not in kwargs:
             self.HEADER_BG_COLOR = self.border_color

    def _validate_and_set_inputs(self, username, post_id, message, short_date, title):
        if not all(isinstance(arg, str) for arg in [username, post_id, message, short_date, title]):
            raise InvalidParameterError("All text inputs (username, post_id, etc.) must be strings.")
        self.username, self.post_id, self.short_date, self.title = username, f"#{post_id}", short_date, f"@{title}"
        cleaned_message = self._remove_emojis(message)
        self.message = (cleaned_message[:750] + "...") if len(cleaned_message) > 750 else cleaned_message

    def _get_or_create_merged_font(self) -> str:
        font_dir = os.path.join(settings.BASE_DIR, "assets", "fonts")
        merged_font_path = os.path.join(font_dir, "merged_font.ttf")
        if os.path.exists(merged_font_path): return merged_font_path
        
        print("Merged font not found. Creating one...")
        font_paths = [os.path.join(font_dir, f) for f in ["NotoSans-Regular.ttf", "NotoSansGurmukhi-Regular.ttf", "NotoSansDevanagari-Regular.ttf"]]
        try:
            for path in font_paths:
                if not os.path.exists(path): raise FileNotFoundError(f"Required source font not found at {path}")
            os.makedirs(font_dir, exist_ok=True)
            merger = Merger()
            merged_font = merger.merge(font_paths)
            merged_font.save(merged_font_path)
            return merged_font_path
        except Exception as e: raise FontError(f"Failed to merge or save fonts: {e}")

    def _remove_emojis(self, text: str) -> str:
        emoji_pattern = re.compile("[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F700-\U0001FAFF\U00002702-\U000027B0\U000024C2-\U0001F251]+", flags=re.UNICODE)
        return " ".join(emoji_pattern.sub(r'', text).split())

    def _get_dynamic_font_size(self) -> int:
        min_fs, max_fs, min_len, max_len = 34, 48, 200, 750
        text_len = len(self.message)
        if text_len < min_len: return max_fs
        if text_len > max_len: return min_fs
        slope = (min_fs - max_fs) / (max_len - min_len)
        return int(max_fs + slope * (text_len - min_len))

    def _wrap_text(self, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> str:
        lines = []
        for para in text.split('\n'):
            words, line = para.split(' '), ""
            for word in words:
                if self.draw.textlength(line + word + " ", font=font) <= max_width: line += word + " "
                else:
                    if self.draw.textlength(word, font=font) > max_width:
                        if line.strip(): lines.append(line.strip())
                        temp_word, line = "", ""
                        for char in word:
                            if self.draw.textlength(temp_word + char, font=font) <= max_width: temp_word += char
                            else: lines.append(temp_word); temp_word = char
                        line = temp_word + " "
                    else: lines.append(line.strip()); line = word + " "
            if line.strip(): lines.append(line.strip())
        return "\n".join(lines)

    def _draw_header(self):
        self.draw.rectangle([0, 0, self.WIDTH, self.HEADER_HEIGHT], fill=self.HEADER_BG_COLOR)
        y_center, padding_x = self.HEADER_HEIGHT // 2, 50
        font_side, font_center = ImageFont.truetype(self.font_path, 36), ImageFont.truetype(self.font_path, 42)
        self.draw.text((padding_x, y_center), self.post_id, font=font_side, fill=self.HEADER_SIDE_TEXT_COLOR, anchor="lm")
        self.draw.text((self.WIDTH / 2, y_center), self.title, font=font_center, fill=self.HEADER_CENTER_TEXT_COLOR, anchor="mm")
        self.draw.text((self.WIDTH - padding_x, y_center), self.short_date, font=font_side, fill=self.HEADER_SIDE_TEXT_COLOR, anchor="rm")
        self.draw.line([(0, self.HEADER_HEIGHT - 1), (self.WIDTH, self.HEADER_HEIGHT - 1)], fill=self.HEADER_BORDER_COLOR, width=2)

    def _draw_body(self):
        px, av_s, sp_x = 50, 90, 20
        sp_y, bub_p, bub_r = 15, 35, 45
        av_f = ImageFont.truetype(self.font_path, 50)
        u_f = ImageFont.truetype(self.font_path, 36)
        m_f = ImageFont.truetype(self.font_path, self._get_dynamic_font_size())
        
        bub_x = px + av_s + sp_x
        max_tw = self.WIDTH - px - bub_x - (bub_p * 2)
        msg = self._wrap_text(self.message, m_f, max_tw)
        t_bbox = self.draw.multiline_textbbox((0, 0), msg, font=m_f, spacing=15)
        t_w, t_h = t_bbox[2] - t_bbox[0], t_bbox[3] - t_bbox[1]
        
        bub_w, bub_h = t_w + (bub_p * 2), t_h + (bub_p * 2)
        u_h = sum(u_f.getmetrics())
        total_h = u_h + sp_y + bub_h
        group_y = self.HEADER_HEIGHT + (self.HEIGHT - self.HEADER_HEIGHT - total_h) // 2
        
        av_y = group_y + total_h - av_s
        self.draw.ellipse([px, av_y, px + av_s, av_y + av_s], fill=self.AVATAR_BG_COLOR)
        self.draw.text((px + av_s/2, av_y + av_s/2), self.username[0].upper(), font=av_f, fill=self.AVATAR_TEXT_COLOR, anchor="mm")
        
        self.draw.text((bub_x + bub_p, group_y), self.username, font=u_f, fill=self.USERNAME_COLOR)
        
        bub_y = group_y + u_h + sp_y
        self.draw.rounded_rectangle([bub_x, bub_y, bub_x + bub_w, bub_y + bub_h], radius=bub_r, fill=self.BUBBLE_COLOR)
        self.draw.rectangle([bub_x, bub_y + bub_h - bub_r, bub_x + bub_r, bub_y + bub_h], fill=self.BUBBLE_COLOR)
        self.draw.multiline_text((bub_x + bub_p, bub_y + bub_p), msg, font=m_f, fill=self.MESSAGE_TEXT_COLOR, spacing=15)

    def _apply_rounded_border_and_corners(self, content_image: Image.Image) -> Image.Image:
        final_image = Image.new('RGBA', (self.WIDTH, self.HEIGHT), self.border_color)
        mask = Image.new('L', (self.WIDTH, self.HEIGHT), 0)
        inset, inner_radius = self.border_width, max(0, self.border_radius - self.border_width)
        ImageDraw.Draw(mask).rounded_rectangle((inset, inset, self.WIDTH - inset, self.HEIGHT - inset), radius=inner_radius, fill=255)
        final_image.paste(content_image, (0, 0), mask)
        
        outer_mask = Image.new('L', (self.WIDTH, self.HEIGHT), 0)
        ImageDraw.Draw(outer_mask).rounded_rectangle((0, 0, self.WIDTH, self.HEIGHT), radius=self.border_radius, fill=255)
        final_image.putalpha(outer_mask)
        return final_image

    def generate_image(self):
        self._draw_header()
        self._draw_body()
        final_image = self._apply_rounded_border_and_corners(self.image)
        buffer = io.BytesIO()
        final_image.save(buffer, format='PNG')
        buffer.seek(0)
        return buffer

def create_post_image(post_number, username, message, short_date, title, **kwargs):
    try:
        generator = InstagramPostGenerator(
            username=username, post_id=str(post_number), message=message,
            short_date=short_date, title=title, **kwargs
        )
        return generator.generate_image()
    except Exception as e:
        print(f"An error occurred during image generation: {e}")
        return None