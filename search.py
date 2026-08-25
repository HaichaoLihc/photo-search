import argparse
import json

import numpy as np
import torch
import torch.nn.functional as F
from transformers import AutoModel, AutoProcessor


MODEL_ID = "google/siglip2-base-patch16-384"


def get_device():
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("query")
    parser.add_argument("-k", type=int, default=20)
    args = parser.parse_args()

    embeddings = np.load("embeddings.npy")

    with open("paths.json") as f:
        paths = json.load(f)

    device = get_device()

    processor = AutoProcessor.from_pretrained(MODEL_ID)
    model = AutoModel.from_pretrained(MODEL_ID)
    model.eval().to(device)

    inputs = processor(
        text=[args.query],
        padding="max_length",
        max_length=64,
        truncation=True,
        return_tensors="pt",
    ).to(device)

    with torch.inference_mode():
        query_embedding = model.get_text_features(**inputs)

    if hasattr(query_embedding, "pooler_output"):
        query_embedding = query_embedding.pooler_output

    query_embedding = F.normalize(
        query_embedding,
        dim=-1
    )

    query_embedding = (
        query_embedding[0]
        .cpu()
        .float()
        .numpy()
    )

    # embeddings 已经 normalized，所以 dot product = cosine similarity
    scores = embeddings @ query_embedding

    top_indices = np.argsort(scores)[::-1][:args.k]

    print(f'\nSearch: "{args.query}"\n')

    for rank, idx in enumerate(top_indices, 1):
        print(
            f"{rank:2d}. "
            f"{scores[idx]:.4f}  "
            f"{paths[idx]}"
        )


if __name__ == "__main__":
    main()