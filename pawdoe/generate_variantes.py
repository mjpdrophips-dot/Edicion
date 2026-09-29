#!/usr/bin/env python3
"""
Genera variantes de vídeo corto (formato 9:16, <=15s) combinando fragmentos
aleatorios de los clips en bruto de un producto.

Uso:
    python3 generate_variantes.py --input-dir raw_clips --output-dir output_variantes
    python3 generate_variantes.py --input-dir raw_clips --num-variants 1   # solo la prueba

Requiere ffmpeg y ffprobe en el PATH.
"""

import argparse
import glob
import json
import os
import random
import subprocess
import sys

VIDEO_EXTENSIONS = (".mov", ".mp4", ".m4v", ".avi", ".mkv")

WIDTH, HEIGHT = 1080, 1920
VF = (
    f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,"
    f"pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2,setsar=1"
)


def find_clips(input_dir):
    clips = []
    for ext in VIDEO_EXTENSIONS:
        clips.extend(glob.glob(os.path.join(input_dir, f"*{ext}")))
        clips.extend(glob.glob(os.path.join(input_dir, f"*{ext.upper()}")))
    clips = sorted(set(clips))
    if not clips:
        sys.exit(f"No se encontraron clips de vídeo en {input_dir}")
    return clips


def probe_duration(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "json", path],
        capture_output=True, text=True, check=True,
    )
    return float(json.loads(out.stdout)["format"]["duration"])


def load_clip_pool(input_dir, edge_margin):
    """Cada clip aporta un rango [margin, duration-margin] del que se pueden
    tomar fragmentos; clips demasiado cortos para tener margen se usan enteros."""
    pool = []
    for path in find_clips(input_dir):
        duration = probe_duration(path)
        margin = edge_margin if duration > edge_margin * 3 else 0.0
        usable_start, usable_end = margin, duration - margin
        if usable_end - usable_start < 1.0:
            continue
        pool.append({"path": path, "usable_start": usable_start, "usable_end": usable_end})
    if not pool:
        sys.exit("Ningún clip tiene suficiente duración utilizable.")
    return pool


def plan_fragment_durations(rng, n, total_budget, frag_min, frag_max):
    durations = []
    remaining_budget = total_budget
    for i in range(n):
        remaining_after = n - i - 1
        max_this = min(frag_max, remaining_budget - remaining_after * frag_min)
        max_this = max(frag_min, max_this)
        d = round(rng.uniform(frag_min, max_this), 2)
        durations.append(d)
        remaining_budget -= d
    return durations


def pick_fragments(rng, pool, n, frag_min, frag_max, total_budget):
    durations = plan_fragment_durations(rng, n, total_budget, frag_min, frag_max)
    clip_indices = list(range(len(pool)))
    rng.shuffle(clip_indices)
    if len(clip_indices) < n:
        clip_indices = (clip_indices * (n // len(clip_indices) + 1))[:n]
        rng.shuffle(clip_indices)
    else:
        clip_indices = clip_indices[:n]

    fragments = []
    for idx, dur in zip(clip_indices, durations):
        clip = pool[idx]
        span = clip["usable_end"] - clip["usable_start"]
        dur = min(dur, span)
        latest_start = clip["usable_end"] - dur
        start = rng.uniform(clip["usable_start"], latest_start) if latest_start > clip["usable_start"] else clip["usable_start"]
        fragments.append({"path": clip["path"], "start": round(start, 2), "duration": round(dur, 2)})
    rng.shuffle(fragments)
    return fragments


def encode_fragment(fragment, out_path):
    cmd = [
        "ffmpeg", "-y", "-ss", f"{fragment['start']:.3f}", "-i", fragment["path"],
        "-t", f"{fragment['duration']:.3f}",
        "-vf", VF, "-r", "30",
        "-c:v", "libx264", "-preset", "medium", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2",
        "-movflags", "+faststart",
        out_path,
    ]
    subprocess.run(cmd, check=True, capture_output=True)


def concat_fragments(fragment_paths, out_path):
    listfile = out_path + ".txt"
    with open(listfile, "w") as f:
        for p in fragment_paths:
            f.write(f"file '{os.path.abspath(p)}'\n")
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", listfile, "-c", "copy", out_path],
        check=True, capture_output=True,
    )
    os.remove(listfile)


def build_variant(rng, pool, variant_num, args, tmp_dir, out_dir):
    n_fragments = rng.randint(args.min_fragments, args.max_fragments)
    fragments = pick_fragments(rng, pool, n_fragments, args.frag_min, args.frag_max, args.max_duration)

    fragment_paths = []
    for i, frag in enumerate(fragments):
        seg_path = os.path.join(tmp_dir, f"v{variant_num:02d}_f{i:02d}.mp4")
        encode_fragment(frag, seg_path)
        fragment_paths.append(seg_path)

    out_path = os.path.join(out_dir, f"variante_{variant_num:02d}.mp4")
    concat_fragments(fragment_paths, out_path)
    for p in fragment_paths:
        os.remove(p)

    total = sum(f["duration"] for f in fragments)
    return out_path, fragments, total


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input-dir", default="raw_clips")
    parser.add_argument("--output-dir", default="output_variantes")
    parser.add_argument("--num-variants", type=int, default=20)
    parser.add_argument("--start-at", type=int, default=1, help="Número de variante inicial (para --num-variants 1 de prueba)")
    parser.add_argument("--min-fragments", type=int, default=4)
    parser.add_argument("--max-fragments", type=int, default=8)
    parser.add_argument("--frag-min", type=float, default=1.0)
    parser.add_argument("--frag-max", type=float, default=3.0)
    parser.add_argument("--max-duration", type=float, default=15.0)
    parser.add_argument("--edge-margin", type=float, default=0.4, help="Segundos a evitar al inicio/final de cada clip fuente")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    tmp_dir = os.path.join(args.output_dir, ".tmp_fragments")
    os.makedirs(tmp_dir, exist_ok=True)

    pool = load_clip_pool(args.input_dir, args.edge_margin)
    print(f"Clips fuente detectados: {len(pool)}")

    seen_signatures = set()
    for i in range(args.start_at, args.start_at + args.num_variants):
        rng = random.Random(args.seed + i)
        for attempt in range(5):
            out_path, fragments, total = build_variant(rng, pool, i, args, tmp_dir, args.output_dir)
            signature = tuple((os.path.basename(f["path"]), round(f["start"], 1)) for f in fragments)
            if signature not in seen_signatures:
                seen_signatures.add(signature)
                break
            rng = random.Random(args.seed + i + 1000 * (attempt + 1))

        print(f"\nVariante {i:02d} -> {out_path} (duración total: {total:.2f}s, {len(fragments)} fragmentos)")
        for f in fragments:
            print(f"  {os.path.basename(f['path'])}  [{f['start']:.2f}s -> {f['start']+f['duration']:.2f}s]  ({f['duration']:.2f}s)")

    os.rmdir(tmp_dir)


if __name__ == "__main__":
    main()
