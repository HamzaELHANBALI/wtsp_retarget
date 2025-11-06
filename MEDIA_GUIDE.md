# Sending Videos and Images with WhatsApp Messages

## Overview

You can now send videos and images along with text messages (captions) using the WhatsApp retargeting script.

## Supported Media Types

✅ **Videos**: `.mp4`, `.mov`, `.avi`, etc.  
✅ **Images**: `.jpg`, `.png`, `.gif`, etc.  
✅ **Text Captions**: Add text along with media

## How to Use

### Basic Usage

```python
from whatsapp_retarget_with_ai import SaudiWhatsAppRetargeterWithAI

retargeter = SaudiWhatsAppRetargeterWithAI(
    daily_limit=40,
    openai_api_key="your-api-key"
)

# Send text-only message
retargeter.send_message_to_contact(
    phone="+212628223573",
    message="Hello!"
)

# Send video with caption
retargeter.send_message_to_contact(
    phone="+212628223573",
    message="Check out this video!",
    media_path="/path/to/video.mp4"
)

# Send image with caption
retargeter.send_message_to_contact(
    phone="+212628223573",
    message="Here's an image!",
    media_path="/path/to/image.jpg"
)
```

### In Your Test Script

Edit `test_with_ai.py`:

```python
# Add video/image file path
media_file = "/path/to/your/video.mp4"  # or image.jpg

# The script will automatically attach it
retargeter.send_message_to_contact(
    contact, 
    initial_message, 
    media_path=media_file
)
```

## File Paths

### Absolute Paths (Recommended)
```python
media_file = "/Users/hamzaelhanbali/Desktop/video.mp4"
```

### Relative Paths
```python
media_file = "videos/promo.mp4"  # Relative to script location
```

## Examples

### Example 1: Video with Arabic Caption
```python
retargeter.send_message_to_contact(
    phone="+966501111111",
    message="شاهد هذا الفيديو المميز!",
    media_path="/path/to/promo_video.mp4"
)
```

### Example 2: Image with English Caption
```python
retargeter.send_message_to_contact(
    phone="+966501111111",
    message="Check out our new product!",
    media_path="/path/to/product_image.jpg"
)
```

### Example 3: Text-Only (No Media)
```python
retargeter.send_message_to_contact(
    phone="+966501111111",
    message="Hello! How can I help you?",
    media_path=None  # or omit the parameter
)
```

## Important Notes

### File Size Limits
- **Videos**: WhatsApp Web has size limits (usually 16MB for videos)
- **Images**: Usually up to 5MB
- Larger files may fail to send

### File Formats
- **Videos**: `.mp4`, `.mov`, `.avi`, `.mkv`
- **Images**: `.jpg`, `.jpeg`, `.png`, `.gif`, `.webp`

### Upload Time
- Media files take longer to upload
- Script waits 3 seconds after sending (vs 2 seconds for text)
- Larger files may need more time

## Error Handling

If media attachment fails:
- Script will show a warning
- Will continue with text-only message
- Won't stop the entire process

## Troubleshooting

### Media Not Attaching?
1. Check file path is correct
2. Verify file exists: `os.path.exists(media_path)`
3. Check file size (may be too large)
4. Try a different file format

### Caption Not Appearing?
1. Make sure message text is provided
2. Wait for file to upload before caption appears
3. Check if caption input is found

### File Upload Fails?
1. Check file permissions
2. Verify file isn't corrupted
3. Try a smaller file first
4. Check internet connection

## Example Script

See `example_with_media.py` for complete examples.

