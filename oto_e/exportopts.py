"""Per-format export settings: what each format lets you choose, and how that becomes Pillow save options.

Qt-free on purpose: the dialog in app.py builds its widgets from `specs()`, and Document.save() only needs
`pillow_kwargs()`. Values are keyed by Param.key, like effect settings, so the same widgets can edit them.
"""
from __future__ import annotations

from pathlib import Path

from .effects import Param

KINDS = {".png": "png", ".jpg": "jpeg", ".jpeg": "jpeg", ".webp": "webp", ".bmp": "bmp",
         ".tif": "tiff", ".tiff": "tiff", ".jp2": "jp2", ".tga": "tga"}
TITLES = {"png": "PNG", "jpeg": "JPEG", "webp": "WebP", "bmp": "BMP", "tiff": "TIFF", "jp2": "JPEG 2000", "tga": "TGA"}

_SPECS = {
    "png": [Param("level", "Compression", 6, 0, 9, 1, "", True, help="Always lossless. Higher makes smaller files and takes longer; 0 stores the pixels as they are.")],
    "jpeg": [Param("quality", "Quality", 95, 1, 100, 1, "", True, help="Lower makes smaller files with more blocks and blur. 90–95 is nearly invisible damage."),
             Param("chroma", "Colour detail", 0, 0, 2, 1, "", True, ["Full (4:4:4)", "Half (4:2:2)", "Quarter (4:2:0)"],
                   help="Lower keeps less colour detail, so colours bleed past edges. Full keeps glitched colour edges sharp."),
             Param("progressive", "Loading", 0, 0, 1, 1, "", True, ["Baseline", "Progressive"],
                   help="Progressive files appear blurry-then-sharp while loading and are often a little smaller.")],
    "webp": [Param("lossy", "Compression", 0, 0, 1, 1, "", True, ["Lossless", "Lossy"], help="Lossless keeps every pixel of your glitch exactly."),
             Param("quality", "Quality (lossy)", 90, 0, 100, 1, "", True, help="Only used when lossy. Lower makes smaller files with more smearing.")],
    "bmp": [],
    "tiff": [Param("compression", "Compression", 2, 0, 2, 1, "", True, ["None", "LZW", "Deflate"],
                   help="All lossless. LZW can make noisy glitch images bigger; Deflate is usually smallest.")],
    "jp2": [Param("lossy", "Compression", 0, 0, 1, 1, "", True, ["Lossless", "Lossy"], help="Lossless keeps every pixel of your glitch exactly."),
            Param("ratio", "Compression ratio (lossy)", 20, 2, 200, 1, ":1", True, help="Only used when lossy. 20:1 gives a file about a twentieth the size of the raw pixels.")],
    "tga": [Param("rle", "Compression", 0, 0, 1, 1, "", True, ["None", "RLE"], help="Lossless. RLE helps flat pictures and can make noisy ones bigger.")],
}


def kind(path: str) -> str | None:
    return KINDS.get(Path(path).suffix.lower())


def specs(k: str) -> list[Param]:
    return _SPECS.get(k, [])


def defaults(k: str) -> dict:
    return {p.key: p.default for p in specs(k)}


def pillow_kwargs(k: str | None, v: dict | None = None) -> dict:
    """Options for PIL.Image.save. `v` is a settings dict (missing keys take their defaults)."""
    v = {**defaults(k or ""), **(v or {})}
    if k == "png":
        return {"compress_level": int(v["level"])}
    if k == "jpeg":
        return {"quality": int(v["quality"]), "subsampling": int(v["chroma"]), "progressive": bool(v["progressive"])}
    if k == "webp":
        return {"lossless": True} if not v["lossy"] else {"lossless": False, "quality": int(v["quality"]), "method": 4}
    if k == "tiff":
        return {"compression": ["raw", "tiff_lzw", "tiff_adobe_deflate"][int(v["compression"])]}
    if k == "jp2":
        return {} if not v["lossy"] else {"quality_mode": "rates", "quality_layers": [int(v["ratio"])], "irreversible": True}
    if k == "tga":
        return {"compression": "tga_rle" if v["rle"] else "raw"}
    return {}
