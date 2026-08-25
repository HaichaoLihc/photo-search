import argparse
import json
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image, ImageOps
from tqdm import tqdm
from transformers import AutoModel, AutoProcessor


MODEL_ID = "google/siglip2-base-patch16-384"
EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def get_device():
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("photo_dir")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--append", action="store_true", help="Append new images to existing embeddings.npy and paths.json instead of overwriting")
    args = parser.parse_args()

    photo_dir = Path(args.photo_dir).expanduser().resolve()

    # Load existing index if append flag is set
    existing_paths_set = set()
    existing_paths_list = []
    existing_embeddings = None

    if args.append:
        emb_file = Path("embeddings.npy")
        paths_file = Path("paths.json")
        if emb_file.exists() and paths_file.exists():
            existing_embeddings = np.load(emb_file)
            with open(paths_file, "r", encoding="utf-8") as f:
                existing_paths_list = json.load(f)
            existing_paths_set = set(existing_paths_list)
            print(f"Loaded existing index with {len(existing_paths_list)} images.")
        else:
            print("No existing embeddings.npy or paths.json found. Creating a new index.")

    all_found_paths = sorted(
        p for p in photo_dir.rglob("*")
        if p.suffix.lower() in EXTENSIONS
    )

    # Filter out already indexed paths if --append is set
    if args.append and existing_paths_set:
        paths = [p for p in all_found_paths if str(p) not in existing_paths_set]
        print(f"Found {len(all_found_paths)} total images ({len(paths)} new unindexed images)")
    else:
        paths = all_found_paths
        print(f"Found {len(paths)} images")

    if not paths:
        print("No new images to index!")
        return

    device = get_device()
    print(f"Using device: {device}")

    processor = AutoProcessor.from_pretrained(MODEL_ID)
    model = AutoModel.from_pretrained(MODEL_ID)
    model.eval().to(device)

    all_embeddings = []
    valid_paths = []

    for i in tqdm(range(0, len(paths), args.batch_size)):
        batch_paths = paths[i:i + args.batch_size]

        images = []
        good_paths = []

        for path in batch_paths:
            try:
                with Image.open(path) as im:
                    im = ImageOps.exif_transpose(im)
                    images.append(im.convert("RGB"))
                good_paths.append(path)
            except Exception as e:
                print(f"\nSkipping {path}: {e}")

        if not images:
            continue

        inputs = processor(
            images=images,
            return_tensors="pt",
        ).to(device)

        with torch.inference_mode():
            features = model.get_image_features(**inputs)

        # Future/current Transformers compatibility
        if hasattr(features, "pooler_output"):
            features = features.pooler_output

        # Normalize -> cosine similarity becomes dot product
        features = F.normalize(features, dim=-1)

        all_embeddings.append(
            features.cpu().float().numpy()
        )
        valid_paths.extend(str(p) for p in good_paths)

    new_embeddings = np.concatenate(all_embeddings, axis=0)

    if args.append and existing_embeddings is not None and existing_embeddings.size > 0:
        embeddings = np.concatenate([existing_embeddings, new_embeddings], axis=0)
        final_paths = existing_paths_list + valid_paths
    else:
        embeddings = new_embeddings
        final_paths = valid_paths

    np.save("embeddings.npy", embeddings)

    with open("paths.json", "w", encoding="utf-8") as f:
        json.dump(final_paths, f, indent=2)

    print()
    print(f"Successfully indexed {len(valid_paths)} new images (Total indexed: {len(final_paths)})")
    print(f"Embedding shape: {embeddings.shape}")
    print("Saved embeddings.npy + paths.json")



if __name__ == "__main__":
    main()