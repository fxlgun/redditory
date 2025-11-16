from typing import Dict, Any
from pathlib import Path
import io
from PIL import Image, ImageDraw, ImageFont
import requests
import html

def fetch_image(url: str):
    try:
        res = requests.get(url, timeout=10, headers={"User-Agent": "FieldingSetBot"})
        if res.status_code == 200:
            return Image.open(io.BytesIO(res.content)).convert("RGB")
    except Exception as e:
        print(f"Failed to fetch image: {e}")
    return None


# basic config
CANVAS_SIZE = (1080, 1080)
BACKGROUND_COLOR = (0, 0, 0)
TEXT_COLOR = (255, 255, 255)
TITLE_COLOR = (255, 201, 60)
SUB_COLOR = (255, 62, 126)

DEFAULT_FONT = "StackSansHeadline.ttf"
DEFAULT_BOLD_FONT = "StackSansHeadline.ttf"
LOGO_PATH = "logo.png"

# Dynamic sizing constraints
MIN_BODY_FONT = 24
MAX_BODY_FONT = 42
MIN_IMAGE_HEIGHT = 280
MAX_IMAGE_HEIGHT = 450


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    font_path = DEFAULT_BOLD_FONT if bold else DEFAULT_FONT
    try:
        return ImageFont.truetype(font_path, size=size)
    except OSError:
        return ImageFont.load_default()


def clean_text(s: str) -> str:
    return html.unescape(s or "").strip()


def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int, draw: ImageDraw.ImageDraw) -> str:
    words = (text or "").split()
    lines = []
    current = ""

    for w in words:
        test = (current + " " + w).strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        w_width = bbox[2] - bbox[0]

        if w_width <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = w

    if current:
        lines.append(current)

    return "\n".join(lines)


def calculate_text_height(text: str, font: ImageFont.FreeTypeFont, max_width: int, draw: ImageDraw.ImageDraw) -> int:
    """Calculate how much vertical space text will take"""
    if not text:
        return 0
    wrapped = wrap_text(text, font, max_width, draw)
    bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, spacing=8)
    return bbox[3] - bbox[1]


def add_logo(image: Image.Image) -> Image.Image:
    logo_file = Path(LOGO_PATH)
    if not logo_file.exists():
        return image

    logo = Image.open(logo_file).convert("RGBA")
    target_width = int(image.width * 0.10)
    ratio = target_width / logo.width
    logo = logo.resize((target_width, int(logo.height * ratio)), Image.LANCZOS)

    padding = int(image.width * 0.03)
    x = image.width - logo.width - padding
    y = image.height - logo.height - padding

    image = image.convert("RGBA")
    image.alpha_composite(logo, dest=(x, y))
    return image.convert("RGB")


def smart_truncate_text(text: str, max_chars: int) -> str:
    """Intelligently truncate text at sentence boundary if possible"""
    if len(text) <= max_chars:
        return text
    
    # Try to cut at last sentence within limit
    truncated = text[:max_chars]
    last_period = truncated.rfind('.')
    last_exclaim = truncated.rfind('!')
    last_question = truncated.rfind('?')
    
    last_sentence_end = max(last_period, last_exclaim, last_question)
    
    if last_sentence_end > max_chars * 0.7:  # If we found a sentence within 70% of limit
        return text[:last_sentence_end + 1]
    else:
        # Cut at last space
        last_space = truncated.rfind(' ')
        if last_space > 0:
            return truncated[:last_space] + "…"
        return truncated + "…"


def render_post_image(post: Dict[str, Any], output_path: str) -> str:
    title = clean_text(post.get("title", ""))
    text = clean_text(post.get("text", ""))
    subreddit = clean_text(post.get("subreddit", ""))
    image_url = post.get("image_url", "")

    # Base canvas
    img = Image.new("RGB", CANVAS_SIZE, BACKGROUND_COLOR)
    draw = ImageDraw.Draw(img)

    margin = 70
    max_width = CANVAS_SIZE[0] - margin * 2
    y = margin - 10
    
    # 🔹 If no text and image exists → full image layout
    if image_url and not text:
        reddit_img = fetch_image(image_url)
        if reddit_img:
            # Fit full space below title + subreddit + logo padding
            sub_height = 0
            if subreddit:
                sub_text = f"r/{subreddit}"
                sub_font = load_font(38, True)
                draw.text((margin, y), sub_text, font=sub_font, fill=SUB_COLOR)
                bbox = draw.textbbox((margin, y), sub_text, font=sub_font)
                sub_height = (bbox[3] - bbox[1]) + 10
                y += sub_height

            # Auto-size title only
            title_font_size = 45
            title_font = load_font(title_font_size, True)
            wrapped_title = wrap_text(title, title_font, max_width, draw)
            bbox_title = draw.multiline_textbbox((margin, y), wrapped_title, font=title_font)
            title_height = bbox_title[3] - bbox_title[1]
            draw.multiline_text((margin, y), wrapped_title, font=title_font, fill=TITLE_COLOR)
            y += title_height + 20

            # Remaining area for image
            logo_reserve = 80
            remaining_height = CANVAS_SIZE[1] - y - logo_reserve

            # Resize to fill remaining height
            w, h = reddit_img.size
            scale = remaining_height / h
            new_size = (int(w * scale), int(h * scale))
            reddit_img = reddit_img.resize(new_size, Image.LANCZOS)

            x_center = (CANVAS_SIZE[0] - new_size[0]) // 2
            img.paste(reddit_img, (x_center, y))

            img = add_logo(img)
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            img.save(output_path, "JPEG", quality=95)
            return output_path

    # Reserve space for logo at bottom
    logo_reserve = 80
    available_height = CANVAS_SIZE[1] - y - logo_reserve

    # 1️⃣ Subreddit
    sub_height = 0
    if subreddit:
        sub_text = f"r/{subreddit}"
        sub_font = load_font(38, True)
        draw.text((margin, y), sub_text, font=sub_font, fill=SUB_COLOR)
        bbox = draw.textbbox((margin, y), sub_text, font=sub_font)
        sub_height = (bbox[3] - bbox[1]) + 10
        y += sub_height

    # 2️⃣ Title with auto-sizing
    title_font_size = 45
    title_font = load_font(title_font_size, True)
    
    max_title_height = CANVAS_SIZE[1] * 0.25
    while title_font_size > 32:
        wrapped_title = wrap_text(title, title_font, max_width, draw)
        bbox = draw.multiline_textbbox((margin, y), wrapped_title, font=title_font)
        title_height = bbox[3] - bbox[1]
        if title_height <= max_title_height:
            break
        title_font_size -= 2
        title_font = load_font(title_font_size, True)

    draw.multiline_text((margin, y), wrapped_title, font=title_font, fill=TITLE_COLOR)
    y += title_height + 20

    # 3️⃣ Calculate remaining space
    remaining_height = available_height - sub_height - title_height - 20

    # 4️⃣ Fetch image if available
    reddit_img = None
    if image_url:
        reddit_img = fetch_image(image_url)

    # 5️⃣ SMART BALANCING: Try different combinations to find best fit
    best_config = None
    text_original = text
    
    # Define strategies: (image_ratio, max_text_chars, min_body_font)
    text_len = len(text)

    strategies = []

    # Extremely short text => HUGE image priority
    if text_len < 200:
        strategies.extend([
            (0.72, 400, MAX_BODY_FONT),   # Big image, still readable text
            (0.65, 300, MAX_BODY_FONT),
            (0.58, 250, MAX_BODY_FONT),
        ])

    # Regular short text
    if text_len < 500:
        strategies.extend([
            (0.50, 450, MAX_BODY_FONT),
            (0.45, 500, MAX_BODY_FONT - 4),
        ])

    # Longer text
    strategies.extend([
        (0.42, 800, MAX_BODY_FONT),
        (0.38, 700, MAX_BODY_FONT - 4),
        (0.35, 600, MAX_BODY_FONT),
        (0.32, 500, MAX_BODY_FONT),
        (0.30, 400, MAX_BODY_FONT),
    ])

   
    for img_ratio, max_chars, starting_font in strategies:
        # Truncate text for this strategy
        test_text = smart_truncate_text(text_original, max_chars)
        
        # Calculate image height
        if reddit_img:
            test_img_height = int(remaining_height * img_ratio)
            test_img_height = max(MIN_IMAGE_HEIGHT, min(MAX_IMAGE_HEIGHT, test_img_height))
            spacing_after_img = 25
        else:
            test_img_height = 0
            spacing_after_img = 0
        
        # Calculate available space for body
        body_space = remaining_height - test_img_height - spacing_after_img
        
        # Try to fit text with this font size
        for font_size in range(starting_font, MIN_BODY_FONT - 1, -2):
            test_font = load_font(font_size)
            test_height = calculate_text_height(test_text, test_font, max_width, draw)
            
            if test_height <= body_space:
                # Found a fit! Save this configuration
                best_config = {
                    'text': test_text,
                    'truncated': len(test_text) < len(text_original),
                    'body_font': font_size,
                    'image_height': test_img_height,
                    'image_ratio': img_ratio
                }
                break
        
        if best_config:
            break
    
    # Fallback if nothing fits (shouldn't happen with our strategies)
    if not best_config:
        best_config = {
            'text': smart_truncate_text(text_original, 300),
            'truncated': True,
            'body_font': MIN_BODY_FONT,
            'image_height': MIN_IMAGE_HEIGHT if reddit_img else 0,
            'image_ratio': 0.25
        }

    # 6️⃣ Render the image with best configuration
    image_height = 0
    if reddit_img and best_config['image_height'] > 0:
        image_height = best_config['image_height']
        w, h = reddit_img.size
        scale = image_height / h
        new_size = (int(w * scale), int(h * scale))
        reddit_img = reddit_img.resize(new_size, Image.LANCZOS)
        
        x_center = (CANVAS_SIZE[0] - new_size[0]) // 2
        img.paste(reddit_img, (x_center, y))
        y += image_height + 25

    # 7️⃣ Render body text
    body_font = load_font(best_config['body_font'])
    wrapped_body = wrap_text(best_config['text'], body_font, max_width, draw)
    draw.multiline_text((margin, y), wrapped_body, font=body_font, fill=TEXT_COLOR, spacing=8)

    # 8️⃣ Logo watermark
    img = add_logo(img)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, "JPEG", quality=95)
    
    print(f"✅ Image saved: {output_path}")
    print(f"   Title font: {title_font_size}px")
    print(f"   Body font: {best_config['body_font']}px")
    if reddit_img:
        print(f"   Image height: {image_height}px ({int(best_config['image_ratio']*100)}% of space)")
    if best_config['truncated']:
        print(f"   ⚠️  Text truncated to {len(best_config['text'])} chars")
    
    return output_path


if __name__ == "__main__":
    # Test with short text
    short_post = {
        "title": "Perfect biryani spot found!",
        "text": "Best biryani ever. Must try!",
        "subreddit": "IndianFood",
        "image_url": "https://picsum.photos/800/600",
    }
    
    # Test with long text
    long_post = {
        "title": "When you finally find the perfect biryani spot in town after months of searching",
        "text": "After searching for months, I stumbled upon this hidden gem that serves the most amazing biryani I've ever tasted. The flavors were out of this world, and the aroma alone was enough to make my mouth water. The rice was perfectly cooked, each grain separate yet fluffy. The chicken was tender and marinated to perfection. The spices were balanced beautifully - not too overpowering but definitely present. The portion size was generous and the price was reasonable. The ambiance of the place added to the whole experience. Highly recommend to all foodies out there! Don't miss out on this gem.",
        "subreddit": "IndianFoodLovers",
        "image_url": "https://picsum.photos/800/600",
    }
    
    render_post_image(short_post, "test_short.jpg")
    render_post_image(long_post, "test_long.jpg")
    print("\n✨ Both test images generated!")