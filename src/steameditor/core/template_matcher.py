"""steameditor.core.template_matcher — AI-powered template recommendation engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from PIL import Image, ImageStat

from steameditor.core.models import Template, BUILTIN_TEMPLATES, MultiPart


@dataclass
class TemplateMatch:
    template: Template
    score: float
    reasons: list[str]
    confidence: Literal["high", "medium", "low"]


class TemplateMatcher:
    """Analyzes source images and recommends optimal Steam showcase templates."""

    # Aspect ratio buckets for common template types
    RATIO_BUCKETS = {
        "vertical_tall": (0.4, 0.65),      # ~1:2.5 to 1:1.5 (Artwork 506x1000 = 0.506)
        "vertical_medium": (0.65, 0.85),   # ~1:1.5 to 1:1.2 (Workshop 754x1250 = 0.603)
        "vertical_short": (0.85, 1.1),     # ~1:1.2 to 1:1 (Screenshot 650x1000 = 0.65)
        "horizontal": (1.1, 3.0),          # Landscape
    }

    # Steam official showcase dimensions (width x height)
    STEAM_SHOWCASE_SPECS = [
        {"name": "Artwork Showcase", "ratio": 0.506, "template": "art", "desc": "Dikey sanat eseri (506×1000)"},
        {"name": "Workshop Showcase", "ratio": 0.603, "template": "work", "desc": "5-parça vitrin (754×1250)"},
        {"name": "Screenshot Showcase", "ratio": 0.65, "template": "shot", "desc": "Tek parça ekran görüntüsü (650×1000)"},
    ]

    def __init__(self):
        self._builtin_by_prefix = {t.prefix: t for t in BUILTIN_TEMPLATES if t.prefix in ("work", "art", "shot")}

    def analyze_image(self, img: Image.Image) -> dict:
        """Extract features from source image for matching."""
        img_rgb = img.convert("RGB")
        w, h = img.size
        ratio = w / h if h > 0 else 1.0

        # Color analysis
        stat = ImageStat.Stat(img_rgb)
        mean_r, mean_g, mean_b = stat.mean
        std_r, std_g, std_b = stat.stddev
        brightness = (mean_r + mean_g + mean_b) / 3
        color_variance = (std_r**2 + std_g**2 + std_b**2) / 3

        # Edge detection for content type hints
        edges = img_rgb.convert("L").filter(Image.FILTER_FIND_EDGES)
        edge_stat = ImageStat.Stat(edges)
        edge_density = edge_stat.mean[0] / 255.0

        # Dominant color check (for solid backgrounds)
        colors = img_rgb.getcolors(maxcolors=256 * 256 * 256)
        if colors:
            dominant_count, dominant_color = max(colors, key=lambda x: x[0])
            dominant_ratio = dominant_count / (w * h)
        else:
            dominant_ratio = 0

        # Aspect ratio bucket
        ratio_bucket = self._classify_ratio(ratio)

        return {
            "width": w,
            "height": h,
            "aspect_ratio": ratio,
            "ratio_bucket": ratio_bucket,
            "brightness": brightness,
            "color_variance": color_variance,
            "edge_density": edge_density,
            "dominant_color_ratio": dominant_ratio,
            "is_landscape": ratio > 1.0,
            "is_squareish": 0.9 <= ratio <= 1.1,
        }

    def _classify_ratio(self, ratio: float) -> str:
        for bucket, (lo, hi) in self.RATIO_BUCKETS.items():
            if lo <= ratio < hi:
                return bucket
        return "vertical_tall" if ratio < 1.0 else "horizontal"

    def _score_template(self, template: Template, features: dict) -> tuple[float, list[str]]:
        """Score a template against image features. Returns (score, reasons)."""
        score = 0.0
        reasons = []

        tmpl_ratio = template.width / template.height if template.height > 0 else 1.0
        img_ratio = features["aspect_ratio"]
        ratio_diff = abs(tmpl_ratio - img_ratio) / max(tmpl_ratio, img_ratio)

        # 1. Aspect ratio match (weight: 40%)
        if ratio_diff < 0.05:
            score += 40
            reasons.append(f"✓ En boy oranı mükemmel ({img_ratio:.2f} ≈ {tmpl_ratio:.2f})")
        elif ratio_diff < 0.15:
            score += 25
            reasons.append(f"✓ En boy oranı uygun ({img_ratio:.2f} ≈ {tmpl_ratio:.2f})")
        elif ratio_diff < 0.3:
            score += 10
            reasons.append(f"~ En boy oranı kabul edilebilir ({img_ratio:.2f} vs {tmpl_ratio:.2f})")
        else:
            reasons.append(f"✗ En boy oranı uyumsuz ({img_ratio:.2f} vs {tmpl_ratio:.2f})")

        # 2. Template mode suitability (weight: 25%)
        if template.mode == "uniform":
            if features["ratio_bucket"] in ("vertical_medium", "vertical_tall"):
                score += 25
                reasons.append("✓ Uniform mod: Vitrin parçalarına uygun")
            elif features["is_landscape"]:
                score -= 10
                reasons.append("✗ Uniform mod: Yatay görsellerde parça sayısı az kalabilir")
        elif template.mode == "multi":
            if features["ratio_bucket"] == "vertical_tall":
                score += 25
                reasons.append("✓ Multi mod: Sanat eseri vitrini için ideal")
            else:
                score += 5
        else:  # single
            if features["ratio_bucket"] in ("vertical_short", "vertical_medium"):
                score += 25
                reasons.append("✓ Tek parça: Ekran görüntüsü vitrini için uygun")
            else:
                score += 5

        # 3. Content type hints (weight: 20%)
        edge_density = features["edge_density"]
        dominant_ratio = features["dominant_color_ratio"]

        if template.prefix == "art":
            # Artwork: high edge detail, low solid color
            if edge_density > 0.15 and dominant_ratio < 0.3:
                score += 20
                reasons.append("✓ Detaylı sanat eseri tespit edildi")
            elif edge_density < 0.05:
                score -= 10
                reasons.append("~ Düşük kenar yoğunluğu - sanat eseri olmayabilir")
        elif template.prefix == "shot":
            # Screenshots: often have UI elements, medium edges
            if 0.05 < edge_density < 0.2 and dominant_ratio < 0.4:
                score += 15
                reasons.append("✓ Ekran görüntüsü özellikleri tespit edildi")
        elif template.prefix == "work":
            # Workshop: general purpose, moderate edges
            if 0.08 < edge_density < 0.25:
                score += 15
                reasons.append("✓ Genel amaçlı vitrin içeriği")

        # 4. Brightness/contrast suitability (weight: 10%)
        brightness = features["brightness"]
        if template.patch and brightness < 60:
            score += 10
            reasons.append("✓ Koyu görsel - PNG patch faydalı olabilir")
        elif not template.patch and brightness > 180:
            score += 5
            reasons.append("✓ Açık görsel - patch gerekmiyor")

        # 5. Resolution match (weight: 5%)
        if features["width"] >= template.width and features["height"] >= template.height:
            score += 5
            reasons.append("✓ Kaynak çözünürlük hedef çözünürlüğü karşılıyor")
        else:
            score -= 5
            reasons.append("~ Kaynak çözünürlük hedeften düşük - upscale gerekebilir")

        return max(0, min(100, score)), reasons

    def recommend(self, img: Image.Image, top_k: int = 3) -> list[TemplateMatch]:
        """Return top-K template recommendations for the image."""
        features = self.analyze_image(img)

        scored = []
        for template in BUILTIN_TEMPLATES:
            score, reasons = self._score_template(template, features)
            confidence = "high" if score >= 75 else "medium" if score >= 50 else "low"
            scored.append(TemplateMatch(template=template, score=score, reasons=reasons, confidence=confidence))

        scored.sort(key=lambda m: m.score, reverse=True)
        return scored[:top_k]

    def recommend_for_path(self, path: str, top_k: int = 3) -> list[TemplateMatch]:
        """Convenience: load image from path and recommend."""
        with Image.open(path) as img:
            return self.recommend(img.copy(), top_k)

    def get_steam_showcase_recommendation(self, img: Image.Image) -> dict:
        """Get Steam's official showcase type recommendation."""
        features = self.analyze_image(img)
        img_ratio = features["aspect_ratio"]

        best = min(self.STEAM_SHOWCASE_SPECS, key=lambda s: abs(s["ratio"] - img_ratio))
        diff = abs(best["ratio"] - img_ratio)

        if diff < 0.05:
            confidence = "high"
        elif diff < 0.15:
            confidence = "medium"
        else:
            confidence = "low"

        return {
            "showcase_type": best["name"],
            "template_prefix": best["template"],
            "description": best["desc"],
            "confidence": confidence,
            "ratio_diff": diff,
        }


def get_template_matcher() -> TemplateMatcher:
    return TemplateMatcher()