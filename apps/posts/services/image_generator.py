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
        self.font_cache = {}  # Cache for fonts to avoid reloading

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
        
        # Remove emojis but keep tags AND NEWLINES intact
        cleaned_message = self._remove_emojis(message)
        
        # Truncate if extremely long, but be generous to accommodate tags
        self.message = (cleaned_message[:2000] + "...") if len(cleaned_message) > 2000 else cleaned_message
        
        # Generate a clean version (no tags) for logic that depends on visible character count
        self.clean_message = self._strip_tags(self.message)

    def _strip_tags(self, text: str) -> str:
        """Removes <...> tags to get the pure display text."""
        return re.sub(r'<[^>]+>', '', text)

    def _get_or_create_merged_font(self) -> str:
        font_dir = os.path.join(settings.BASE_DIR, "assets", "fonts")
        merged_font_path = os.path.join(font_dir, "merged_font.ttf")
        if os.path.exists(merged_font_path): return merged_font_path
        
        print("Merged font not found. Creating one...")
        # Ensure these files exist in your assets/fonts directory
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
        """
        Removes emojis from the text but preserves whitespace and newlines.
        """
        emoji_pattern = re.compile("[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F700-\U0001FAFF\U00002702-\U000027B0\U000024C2-\U0001F251]+", flags=re.UNICODE)
        # FIX: Just use sub(), do not use split() which eats newlines
        return emoji_pattern.sub(r'', text)

    def _get_dynamic_font_size(self) -> int:
        # Calculate font size based on the CLEAN message length, ignoring tags
        min_fs, max_fs, min_len, max_len = 34, 48, 200, 750
        text_len = len(self.clean_message)
        if text_len < min_len: return max_fs
        if text_len > max_len: return min_fs
        slope = (min_fs - max_fs) / (max_len - min_len)
        return int(max_fs + slope * (text_len - min_len))

    def _get_font(self, size: int):
        """Helper to get cached font instance."""
        if size not in self.font_cache:
            self.font_cache[size] = ImageFont.truetype(self.font_path, size)
        return self.font_cache[size]

    # --- Rich Text Parsing & Wrapping ---

    def _parse_rich_text(self, text, default_size, default_color):
        """Parses text with tags <b>, <c:#HEX>, <s:INT> into segments."""
        tag_pattern = re.compile(r'(<b>|</b>|<c:#[0-9a-fA-F]+>|</c>|<s:\d+>|</s>)')
        parts = tag_pattern.split(text)
        
        segments = []
        style_stack = [{'bold': False, 'color': default_color, 'size': default_size}]
        
        for part in parts:
            if not part: continue
            
            lower_part = part.lower()
            if lower_part == '<b>':
                new_style = style_stack[-1].copy()
                new_style['bold'] = True
                style_stack.append(new_style)
            elif lower_part == '</b>':
                if len(style_stack) > 1: style_stack.pop()
            elif lower_part.startswith('<c:'):
                color = part[3:-1] 
                if self._validate_color_format(color):
                    new_style = style_stack[-1].copy()
                    new_style['color'] = color
                    style_stack.append(new_style)
            elif lower_part == '</c>':
                 if len(style_stack) > 1: style_stack.pop()
            elif lower_part.startswith('<s:'):
                try:
                    size = int(part[3:-1])
                    new_style = style_stack[-1].copy()
                    new_style['size'] = size
                    style_stack.append(new_style)
                except: pass
            elif lower_part == '</s>':
                 if len(style_stack) > 1: style_stack.pop()
            else:
                style = style_stack[-1]
                segments.append({
                    'text': part,
                    'color': style['color'],
                    'size': style['size'],
                    'bold': style['bold']
                })
        return segments

    def _validate_color_format(self, color):
         return isinstance(color, str) and re.match(r'^#(?:[A-Fa-f0-9]{3}){1,2}$', color)

    def _wrap_rich_text(self, segments, max_width):
        """
        Wraps parsed segments into lines based on width.
        Crucially handles explicit newlines ('\n') in text by forcing a line break.
        """
        lines = []
        current_line = []
        current_width = 0
        
        for seg in segments:
            font = self._get_font(seg['size'])
            
            # 1. Split by explicit newlines first
            # "Hello\nWorld" -> ["Hello", "\n", "World"]
            parts = re.split(r'(\n)', seg['text'])
            
            for part in parts:
                if part == '\n':
                    # Force commit of current line and start a new one (even if empty)
                    lines.append(current_line)
                    current_line = []
                    current_width = 0
                    continue
                
                # 2. Process words within this line-segment
                # NOTE: We use split(' ') here to break words but keep empty strings 
                # to respect multiple spaces if necessary, though typical wrapping consumes them.
                words = part.split(' ')
                for i, word in enumerate(words):
                    word_text = word
                    
                    # Add space if it's not the last word in this part
                    if i < len(words) - 1:
                        word_text += " "
                    
                    if not word_text: continue

                    word_w = self.draw.textlength(word_text, font=font)
                    if seg['bold']:
                        word_w += len(word_text) * 0.5 # Bold buffer
                    
                    if current_width + word_w <= max_width:
                        current_line.append({**seg, 'text': word_text})
                        current_width += word_w
                    else:
                        # Flush current line
                        if current_line:
                            lines.append(current_line)
                        # Start new line with current word
                        current_line = [{**seg, 'text': word_text}]
                        current_width = word_w
                    
        if current_line:
            lines.append(current_line)
            
        return lines

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
        
        default_font_size = self._get_dynamic_font_size()
        
        bub_x = px + av_s + sp_x
        max_tw = self.WIDTH - px - bub_x - (bub_p * 2)
        
        # 1. Parse and Wrap Rich Text
        segments = self._parse_rich_text(self.message, default_font_size, self.MESSAGE_TEXT_COLOR)
        wrapped_lines = self._wrap_rich_text(segments, max_tw)
        
        # 2. Calculate total height
        line_spacing = 15
        total_text_height = 0
        line_heights = []
        
        for line in wrapped_lines:
            # If line is empty (explicit newline), use default font height
            if not line:
                font = self._get_font(default_font_size)
                ascent, descent = font.getmetrics()
                h = ascent + descent
                line_heights.append(h)
                total_text_height += h
            else:
                max_h = 0
                for seg in line:
                    font = self._get_font(seg['size'])
                    ascent, descent = font.getmetrics()
                    max_h = max(max_h, ascent + descent)
                line_heights.append(max_h)
                total_text_height += max_h
            
        if len(line_heights) > 0:
            total_text_height += (len(line_heights) - 1) * line_spacing

        bub_w = max_tw + (bub_p * 2)
        bub_h = total_text_height + (bub_p * 2)
        u_h = sum(u_f.getmetrics())
        total_group_h = u_h + sp_y + bub_h
        
        group_y = self.HEADER_HEIGHT + (self.HEIGHT - self.HEADER_HEIGHT - total_group_h) // 2
        
        # Draw Avatar
        av_y = group_y + total_group_h - av_s
        self.draw.ellipse([px, av_y, px + av_s, av_y + av_s], fill=self.AVATAR_BG_COLOR)
        self.draw.text((px + av_s/2, av_y + av_s/2), self.username[0].upper(), font=av_f, fill=self.AVATAR_TEXT_COLOR, anchor="mm")
        
        # Draw Username
        self.draw.text((bub_x + bub_p, group_y), self.username, font=u_f, fill=self.USERNAME_COLOR)
        
        # Draw Bubble Background
        bub_y = group_y + u_h + sp_y
        self.draw.rounded_rectangle([bub_x, bub_y, bub_x + bub_w, bub_y + bub_h], radius=bub_r, fill=self.BUBBLE_COLOR)
        self.draw.rectangle([bub_x, bub_y + bub_h - bub_r, bub_x + bub_r, bub_y + bub_h], fill=self.BUBBLE_COLOR)
        
        # 3. Draw Rich Text Lines
        current_y = bub_y + bub_p
        for i, line in enumerate(wrapped_lines):
            line_h = line_heights[i]
            current_x = bub_x + bub_p
            
            for seg in line:
                font = self._get_font(seg['size'])
                stroke_w = 1 if seg['bold'] else 0
                
                self.draw.text(
                    (current_x, current_y), 
                    seg['text'], 
                    font=font, 
                    fill=seg['color'], 
                    stroke_width=stroke_w,
                    stroke_fill=seg['color']
                )
                seg_w = self.draw.textlength(seg['text'], font=font)
                current_x += seg_w
            
            current_y += line_h + line_spacing

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