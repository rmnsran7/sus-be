from PIL import Image, ImageDraw, ImageFont
import os
import re

# We need the fontTools library for merging fonts.
try:
    from fontTools.merge import Merger
except ImportError:
    print("Error: fontTools is not installed. Please install it using: pip install fonttools")
    exit()

# --- Custom Exceptions for Clear Error Handling ---
class InstagramPostError(Exception):
    """Base exception for all errors related to this image generator."""
    pass

class FontError(InstagramPostError):
    """Raised for errors related to finding, loading, or merging fonts."""
    pass

class InvalidParameterError(InstagramPostError):
    """Raised when an invalid parameter (e.g., bad color format, negative width) is provided."""
    pass

class FileSystemError(InstagramPostError):
    """Raised for errors related to reading from or writing to the filesystem."""
    pass


class InstagramPostGenerator:
    """
    A class to generate an Instagram post image (1080x1350) that looks like a chat screenshot.
    This version includes robust error handling for use in production environments like Django.
    """
    def __init__(self, username: str, post_id: str, message: str, short_date: str, title: str, **kwargs):
        """
        Initializes and validates the post generator.

        Args:
            username (str): The username to display.
            post_id (str): The ID for the post (e.g., '#P01').
            message (str): The main chat message content.
            short_date (str): The date string (e.g., '15 Oct').
            title (str): The title string (e.g., '@some_account').
            **kwargs: Optional keyword arguments to customize appearance.
                - border_width (int): The width of the border in pixels. Default: 6.
                - border_radius (int): The radius for the rounded corners. Default: 30.
                - border_color (str): The default color of the border. Default: "#FFFFFF".
                - All other color attributes (e.g., 'HEADER_BG_COLOR', 'MESSAGE_TEXT_COLOR').
        """
        # --- Image and Layout Constants ---
        self.WIDTH = 1080
        self.HEIGHT = 1350
        self.BG_COLOR = "#1A1A1A"

        # --- Default Settable Attributes ---
        self.border_width = 6
        self.border_radius = 30
        self.border_color = "#FFFFFF"
        self.HEADER_HEIGHT = int(self.HEIGHT * 0.10)
        self.HEADER_BG_COLOR = self.border_color
        self.HEADER_SIDE_TEXT_COLOR = "#A0A0A0"
        self.HEADER_CENTER_TEXT_COLOR = "#3D3D3D"
        self.HEADER_BORDER_COLOR = "#333333"
        self.AVATAR_BG_COLOR = "#4169E1"
        self.AVATAR_TEXT_COLOR = "#FFFFFF"
        self.USERNAME_COLOR = "#A0A0A0"
        self.BUBBLE_COLOR = "#3E3E3E"
        self.MESSAGE_TEXT_COLOR = "#FFFFFF"

        # --- Process and Validate Inputs ---
        self._validate_and_set_inputs(username, post_id, message, short_date, title)
        self._apply_customizations(kwargs)

        # --- Initialize Fonts (can raise FontError) ---
        self.font_path = self._get_or_create_merged_font()

        # --- Initialize Image Canvas ---
        try:
            self.image = Image.new('RGB', (self.WIDTH, self.HEIGHT), color=self.BG_COLOR)
            self.draw = ImageDraw.Draw(self.image)
        except ValueError as e:
            # This can happen if self.BG_COLOR is somehow invalid, as a safeguard.
            raise InvalidParameterError(f"Failed to create image canvas. Invalid background color '{self.BG_COLOR}': {e}")

    def _validate_color(self, color_string: str, param_name: str):
        """Validates if a string is a valid hex color code."""
        if not isinstance(color_string, str) or not re.match(r'^#(?:[A-Fa-f0-9]{3}){1,2}$', color_string):
            raise InvalidParameterError(f"Parameter '{param_name}' has an invalid hex color format: '{color_string}'")

    def _apply_customizations(self, kwargs: dict):
        """Applies and validates optional customizations from kwargs."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                # Validate parameter types and values
                if key in ['border_width', 'border_radius']:
                    if not isinstance(value, int) or value < 0:
                        raise InvalidParameterError(f"Parameter '{key}' must be a non-negative integer, got '{value}'.")
                elif key.endswith('_color'):
                    self._validate_color(value, key)
                
                setattr(self, key, value)
            else:
                # To prevent silent failures from typos in kwargs
                print(f"Warning: Ignoring unknown customization parameter '{key}'.")

        # Special case: Header background defaults to border color if not explicitly set
        if 'HEADER_BG_COLOR' not in kwargs:
             self.HEADER_BG_COLOR = self.border_color

    def _validate_and_set_inputs(self, username, post_id, message, short_date, title):
        """Validates core text inputs and cleans the message."""
        if not all(isinstance(arg, str) for arg in [username, post_id, message, short_date, title]):
            raise InvalidParameterError("All text inputs (username, post_id, etc.) must be strings.")

        self.username = username
        self.post_id = f"#{post_id}"
        self.short_date = short_date
        self.title = f"@{title}"

        cleaned_message = self._remove_emojis(message)
        if len(cleaned_message) > 750:
            self.message = cleaned_message[:750] + "..."
        else:
            self.message = cleaned_message

    def _get_or_create_merged_font(self) -> str:
        font_dir = "fonts"
        merged_font_path = os.path.join(font_dir, "merged_font.ttf")
        if os.path.exists(merged_font_path):
            return merged_font_path
        
        print("Merged font not found. Creating one (this is a one-time process)...")
        font_paths = [
            os.path.join(font_dir, "NotoSans-Regular.ttf"),
            os.path.join(font_dir, "NotoSansGurmukhi-Regular.ttf"),
            os.path.join(font_dir, "NotoSansDevanagari-Regular.ttf"),
        ]
        
        try:
            for path in font_paths:
                if not os.path.exists(path):
                    raise FileNotFoundError(f"Required source font not found at {path}")
            
            merger = Merger()
            merged_font = merger.merge(font_paths)
            merged_font.save(merged_font_path)
            print(f"Successfully created merged font at '{merged_font_path}'")
            return merged_font_path
        except FileNotFoundError as e:
            raise FontError(e)
        except Exception as e:
            # Catch potential errors from fontTools merge/save operations
            raise FontError(f"Failed to merge or save fonts: {e}")

    def _remove_emojis(self, text: str) -> str:
        """
        Removes emojis but PRESERVES newlines.
        """
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F" "\U0001F300-\U0001F5FF" "\U0001F680-\U0001F6FF"
            "\U0001F700-\U0001F77F" "\U0001F780-\U0001F7FF" "\U0001F800-\U0001F8FF"
            "\U0001F900-\U0001F9FF" "\U0001FA00-\U0001FA6F" "\U0001FA70-\U0001FAFF"
            "\U00002702-\U000027B0" "\U000024C2-\U0001F251" 
            "]+", flags=re.UNICODE)
        no_emojis_text = emoji_pattern.sub(r'', text)
        
        # We strip leading/trailing whitespace, but we DO NOT split/join on all whitespace
        return no_emojis_text.strip()

    def _get_dynamic_font_size(self) -> int:
        min_font_size, max_font_size = 34, 48
        min_len, max_len = 200, 750
        text_len = len(self.message)
        if text_len < min_len: return max_font_size
        if text_len > max_len: return min_font_size
        slope = (min_font_size - max_font_size) / (max_len - min_len)
        return int(max_font_size + slope * (text_len - min_len))

    def _wrap_text(self, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> str:
        """
        Wraps text while respecting existing newlines and handling long words.
        """
        lines = []
        paragraphs = text.split('\n')
        
        for para in paragraphs:
            # If the paragraph is empty (a blank line), add an empty string to preserve vertical space
            if not para.strip():
                lines.append("")
                continue

            words = para.split(' ')
            current_line = ""
            
            for word in words:
                test_line = current_line + word + " "
                if self.draw.textlength(test_line, font=font) <= max_width:
                    current_line = test_line
                else:
                    # Handle word longer than max_width (character wrapping)
                    if self.draw.textlength(word, font=font) > max_width:
                        if current_line.strip(): lines.append(current_line.strip())
                        current_line = ""
                        temp_word = ""
                        for char in word:
                            if self.draw.textlength(temp_word + char, font=font) <= max_width:
                                temp_word += char
                            else:
                                lines.append(temp_word)
                                temp_word = char
                        current_line = temp_word + " "
                    else: # Regular word wrap
                        lines.append(current_line.strip())
                        current_line = word + " "
            if current_line.strip(): lines.append(current_line.strip())
        return "\n".join(lines)

    def _draw_header(self):
        self.draw.rectangle([0, 0, self.WIDTH, self.HEADER_HEIGHT], fill=self.HEADER_BG_COLOR)
        y_center = self.HEADER_HEIGHT // 2
        padding_x = 50
        try:
            font_side = ImageFont.truetype(self.font_path, 36)
            font_center = ImageFont.truetype(self.font_path, 42)
        except IOError as e:
            raise FontError(f"Failed to load font from '{self.font_path}': {e}")
            
        self.draw.text((padding_x, y_center), self.post_id, font=font_side, fill=self.HEADER_SIDE_TEXT_COLOR, anchor="lm")
        self.draw.text((self.WIDTH / 2, y_center), self.title, font=font_center, fill=self.HEADER_CENTER_TEXT_COLOR, anchor="mm")
        self.draw.text((self.WIDTH - padding_x, y_center), self.short_date, font=font_side, fill=self.HEADER_SIDE_TEXT_COLOR, anchor="rm")
        self.draw.line([(0, self.HEADER_HEIGHT - 1), (self.WIDTH, self.HEADER_HEIGHT - 1)], fill=self.HEADER_BORDER_COLOR, width=2)

    def _draw_body(self):
        padding_x, avatar_size, group_spacing_x = 50, 90, 20
        username_bubble_spacing_y, bubble_padding, bubble_radius = 15, 35, 45
        
        try:
            avatar_font = ImageFont.truetype(self.font_path, 50)
            username_font = ImageFont.truetype(self.font_path, 36)
            message_font = ImageFont.truetype(self.font_path, self._get_dynamic_font_size())
        except IOError as e:
            raise FontError(f"Failed to load font from '{self.font_path}': {e}")
            
        bubble_left_x = padding_x + avatar_size + group_spacing_x
        max_text_width = self.WIDTH - padding_x - bubble_left_x - (bubble_padding * 2)
        
        wrapped_message = self._wrap_text(self.message, message_font, max_text_width)
        text_bbox = self.draw.multiline_textbbox((0, 0), wrapped_message, font=message_font, spacing=15)
        text_width, text_height = text_bbox[2] - text_bbox[0], text_bbox[3] - text_bbox[1]
        
        bubble_width = text_width + (bubble_padding * 2)
        bubble_height = text_height + (bubble_padding * 2)
        
        ascent, descent = username_font.getmetrics()
        username_height = ascent + descent
        total_content_height = username_height + username_bubble_spacing_y + bubble_height
        
        body_height = self.HEIGHT - self.HEADER_HEIGHT
        group_y_start = self.HEADER_HEIGHT + (body_height - total_content_height) // 2
        
        # Avatar
        avatar_x = padding_x
        avatar_y = group_y_start + total_content_height - avatar_size
        self.draw.ellipse([avatar_x, avatar_y, avatar_x + avatar_size, avatar_y + avatar_size], fill=self.AVATAR_BG_COLOR)
        avatar_initial = self.username[0].upper() if self.username else "S"
        self.draw.text((avatar_x + avatar_size/2, avatar_y + avatar_size/2), avatar_initial, font=avatar_font, fill=self.AVATAR_TEXT_COLOR, anchor="mm")
        
        # Username
        username_x, username_y = bubble_left_x + bubble_padding, group_y_start
        self.draw.text((username_x, username_y), self.username, font=username_font, fill=self.USERNAME_COLOR)
        
        # Message Bubble & Text
        bubble_y = username_y + username_height + username_bubble_spacing_y
        self.draw.rounded_rectangle([bubble_left_x, bubble_y, bubble_left_x + bubble_width, bubble_y + bubble_height], radius=bubble_radius, fill=self.BUBBLE_COLOR)
        # Fix bottom-left corner to be sharp
        self.draw.rectangle([bubble_left_x, bubble_y + bubble_height - bubble_radius, bubble_left_x + bubble_radius, bubble_y + bubble_height], fill=self.BUBBLE_COLOR)
        
        text_x, text_y = bubble_left_x + bubble_padding, bubble_y + bubble_padding
        self.draw.multiline_text((text_x, text_y), wrapped_message, font=message_font, fill=self.MESSAGE_TEXT_COLOR, spacing=15)

    def _apply_rounded_border_and_corners(self, content_image: Image.Image) -> Image.Image:
        final_image = Image.new('RGBA', (self.WIDTH, self.HEIGHT), self.border_color)
        content_mask = Image.new('L', (self.WIDTH, self.HEIGHT), 0)
        mask_draw = ImageDraw.Draw(content_mask)
        
        inset = self.border_width
        inner_radius = max(0, self.border_radius - inset)
        
        mask_draw.rounded_rectangle(
            (inset, inset, self.WIDTH - inset, self.HEIGHT - inset),
            radius=inner_radius, fill=255
        )
        final_image.paste(content_image, (0, 0), content_mask)

        outer_mask = Image.new('L', (self.WIDTH, self.HEIGHT), 0)
        ImageDraw.Draw(outer_mask).rounded_rectangle(
            (0, 0, self.WIDTH, self.HEIGHT), radius=self.border_radius, fill=255
        )
        final_image.putalpha(outer_mask)
        return final_image

    def generate_image(self, output_path: str):
        """
        Orchestrates the drawing process and saves the final image.

        Args:
            output_path (str): The path to save the final PNG image.
        
        Raises:
            FileSystemError: If the output directory doesn't exist or if saving fails due to permissions.
        """
        # --- Draw Main Content ---
        self._draw_header()
        self._draw_body()

        # --- Apply Final Border and Corners ---
        final_image = self._apply_rounded_border_and_corners(self.image)
        
        # --- Save with Error Handling ---
        try:
            output_dir = os.path.dirname(output_path)
            if output_dir and not os.path.exists(output_dir):
                raise FileSystemError(f"Output directory does not exist: '{output_dir}'")
            final_image.save(output_path)
            print(f"Image successfully saved to {output_path}")
        except (IOError, PermissionError) as e:
            raise FileSystemError(f"Failed to save image to '{output_path}'. Check permissions. Original error: {e}")
        except Exception as e:
            raise FileSystemError(f"An unexpected error occurred while saving the image: {e}")


# ==============================================================================
# ======================== MAIN EXECUTION BLOCK (UPDATED) ======================
# ==============================================================================
if __name__ == '__main__':
    
    # Test cases including ones designed to fail gracefully.
    extreme_test_cases = [
        # --- SUCCESS CASES ---
        {
            "case_id": "multiline_case", 
            "username": "LineBreaker", 
            "post_id": "M01", 
            "short_date": "15 Oct", 
            "title": "multiline-post",
            "message": "This is line 1.\nThis is line 2.\n\nThis is line 4 after a blank line.",
            "comment": "Tests if newlines and blank lines are preserved."
        },
        {
            "case_id": "standard_case", "username": "StandardUser", "post_id": "S01", "short_date": "15 Oct", "title": "standard-post",
            "message": "This is a standard, well-behaved message that should render perfectly fine without any issues.",
            "comment": "A baseline success case."
        },
        {
            "case_id": "long_unbreakable_word", "username": "URLSharer", "post_id": "L01", "short_date": "15 Oct", "title": "long-word",
            "message": "https://this.is.a.very.long.url.that.is.designed.to.be.completely.unbreakable.by.normal.word.wrapping.and.must.be.character.wrapped.to.fit.within.the.bubble.without.overflowing.pneumonoultramicroscopicsilicovolcanokoniosis",
            "comment": "Crucial test for the character-level wrapping logic."
        },
        {
             "case_id": "devanagari_hindi_text", "username": "हिन्दी", "post_id": "H01", "short_date": "१५ अक्टूबर", "title": "देवनागरी",
             "message": "यह देवनागरी में एक परीक्षण संदेश है।\nनई लाइन यहाँ है।\n\nएक और खाली लाइन।",
             "comment": "Tests the NotoSansDevanagari font merging with newlines."
        },
    ]

    output_dir = "final_output_images_fixed_v7"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    print(f"Generating {len(extreme_test_cases)} robust test images...")
    print("-" * 70)

    for i, case in enumerate(extreme_test_cases, 1):
        print(f"Running Case {i:02d}: {case['case_id']}...")
        print(f"  > {case['comment']}")
        
        output_path = os.path.join(output_dir, f"{i:02d}_{case['case_id']}.png")
        
        try:
            # Use a dictionary of parameters for cleaner instantiation
            params = {
                "username": case["username"],
                "post_id": case["post_id"],
                "message": case["message"],
                "short_date": case["short_date"],
                "title": case["title"],
            }
            # Add kwargs for customization if they exist
            params.update(case.get("kwargs", {}))

            generator = InstagramPostGenerator(**params)
            generator.generate_image(output_path)

            if "expected_error" in case:
                print(f"  [FAIL] Expected an error ({case['expected_error'].__name__}) but none was raised.")

        except InstagramPostError as e:
            # This is the catch-all for our custom errors
            if "expected_error" in case and isinstance(e, case["expected_error"]):
                print(f"  [SUCCESS] Correctly caught expected error: {type(e).__name__} - {e}")
            else:
                print(f"  [FAIL] Caught an unexpected error: {type(e).__name__} - {e}")
        except Exception as e:
            # Catch any other unexpected errors
            print(f"  [CRITICAL FAIL] Caught a non-library error: {type(e).__name__} - {e}")
    
    print("-" * 70)
    print(f"\nAll robust tests completed. Check the '{output_dir}' directory and console output.")