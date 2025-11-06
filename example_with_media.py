"""
Example: Sending WhatsApp messages with videos/images
"""

from whatsapp_retarget_with_ai import SaudiWhatsAppRetargeterWithAI
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

if not OPENAI_API_KEY:
    print("⚠️  Warning: OPENAI_API_KEY not found in .env file")
    exit(1)

# Initialize retargeter
retargeter = SaudiWhatsAppRetargeterWithAI(
    daily_limit=40,
    openai_api_key=OPENAI_API_KEY
)

# Test contacts
test_contacts = [
    "+212628223573",
    "+33631055810"
]

# Example 1: Text-only message
text_message = "Hello! This is a text-only message."

# Example 2: Message with video
video_path = "/path/to/your/video.mp4"  # Replace with your video path
video_message = "Check out this video!"

# Example 3: Message with image
image_path = "/path/to/your/image.jpg"  # Replace with your image path
image_message = "Here's an image for you!"

# Example 4: Video with Arabic caption
video_with_caption = "شاهد هذا الفيديو!"

print("=" * 60)
print("Sending Messages with Media")
print("=" * 60)

try:
    # Send text-only message
    print("\n1. Sending text-only message...")
    retargeter.send_message_to_contact(
        phone=test_contacts[0],
        message=text_message
    )
    
    # Send video with caption
    if os.path.exists(video_path):
        print("\n2. Sending video with caption...")
        retargeter.send_message_to_contact(
            phone=test_contacts[0],
            message=video_message,
            media_path=video_path
        )
    else:
        print(f"\n⚠️  Video file not found: {video_path}")
    
    # Send image with caption
    if os.path.exists(image_path):
        print("\n3. Sending image with caption...")
        retargeter.send_message_to_contact(
            phone=test_contacts[1],
            message=image_message,
            media_path=image_path
        )
    else:
        print(f"\n⚠️  Image file not found: {image_path}")
    
    print("\n✅ Messages sent!")
    
except Exception as e:
    print(f"\n❌ Error: {str(e)}")
    
finally:
    retargeter.close()

