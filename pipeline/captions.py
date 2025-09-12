#!/usr/bin/env python3
"""Caption generation script using BLIP."""

import os
import sys
import argparse
import json
from pathlib import Path
import torch
from PIL import Image
from transformers import BlipProcessor, BlipForConditionalGeneration
from tqdm import tqdm

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.database import get_db_session
from pipeline.models import Segment


class CaptionGenerator:
    """BLIP-2 caption generator."""
    
    def __init__(self, model_name="Salesforce/blip-image-captioning-base"):
        """Initialize the caption generator."""
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Using device: {self.device}")
        
        print("Loading fast BLIP model... (much smaller and faster)")
        self.processor = BlipProcessor.from_pretrained(model_name)
        self.model = BlipForConditionalGeneration.from_pretrained(
            model_name, torch_dtype=torch.float16 if self.device == "cuda" else torch.float32
        )
        self.model.to(self.device)
        print("Model loaded successfully")
    
    def generate_caption(self, image_path):
        """Generate caption for a single image."""
        try:
            image = Image.open(image_path).convert("RGB")
            inputs = self.processor(image, return_tensors="pt").to(self.device)
            
            with torch.no_grad():
                generated_ids = self.model.generate(**inputs, max_length=50)
            
            caption = self.processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
            return caption.strip()
        except Exception as e:
            print(f"Error generating caption for {image_path}: {e}")
            return None


def generate_captions_for_frames(frames_dir, output_file="artifacts/captions.json"):
    """Generate captions for all frames in a directory."""
    frames_dir = Path(frames_dir)
    output_file = Path(output_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    if not frames_dir.exists():
        raise FileNotFoundError(f"Frames directory not found: {frames_dir}")
    
    # Find all image files
    image_extensions = {".jpg", ".jpeg", ".png", ".bmp"}
    image_files = []
    
    if frames_dir.is_file():
        # Single image file
        if frames_dir.suffix.lower() in image_extensions:
            image_files = [frames_dir]
        else:
            raise ValueError(f"Not an image file: {frames_dir}")
    else:
        # Directory of images
        for ext in image_extensions:
            image_files.extend(frames_dir.glob(f"**/*{ext}"))
        image_files.sort()
    
    if not image_files:
        raise ValueError(f"No image files found in: {frames_dir}")
    
    print(f"Found {len(image_files)} images to caption")
    
    # Initialize caption generator
    caption_generator = CaptionGenerator()
    
    # Generate captions
    results = []
    db = get_db_session()
    
    try:
        for image_path in tqdm(image_files, desc="Generating captions"):
            caption = caption_generator.generate_caption(image_path)
            
            if caption:
                try:
                    rel_path = str(image_path.relative_to(Path.cwd()))
                except ValueError:
                    rel_path = str(image_path)
                
                result = {
                    "image_path": rel_path,
                    "caption": caption,
                    "confidence": 1.0  # BLIP doesn't provide confidence scores
                }
                results.append(result)
                
                # Update database if this frame exists
                try:
                    relative_path = str(image_path.relative_to(Path.cwd()))
                except ValueError:
                    # If relative_to fails, use absolute path
                    relative_path = str(image_path)
                segment = db.query(Segment).filter(Segment.keyframe_path == relative_path).first()
                if segment:
                    segment.caption = caption
                    segment.caption_confidence = 1.0
        
        # Save results to JSON
        with open(output_file, "w") as f:
            json.dump(results, f, indent=2)
        
        # Commit database changes
        db.commit()
        print(f"✅ Database updated with {len(results)} captions")
        
    except Exception as e:
        db.rollback()
        raise
    finally:
        db.close()
    
    print(f"Generated {len(results)} captions")
    print(f"Results saved to: {output_file}")
    
    return results


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Generate captions for video frames")
    parser.add_argument("frames_path", help="Path to frames directory or single image")
    parser.add_argument("--output", default="artifacts/captions.json",
                       help="Output JSON file")
    
    args = parser.parse_args()
    
    try:
        results = generate_captions_for_frames(args.frames_path, args.output)
        print(f"Caption generation complete! {len(results)} captions generated")
        
        # Show sample captions
        if results:
            print("\nSample captions:")
            for i, result in enumerate(results[:3]):
                print(f"  {i+1}. {Path(result['image_path']).name}: {result['caption']}")
            if len(results) > 3:
                print(f"  ... and {len(results) - 3} more")
                
    except Exception as e:
        print(f"Caption generation failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()