import logging
from typing import Dict, Any, Tuple
from hardware_scan import HardwareProfile

logger = logging.getLogger("ValorantOptimizer")

# Points structure: LOW = 1, MID = 2, HIGH = 3, ENTHUSIAST = 4
TIER_KEYWORDS = {
    "LOW": [
        "intel", "uhd", "hd graphics", "vega", "gt 1030", "gtx 750", "rx 550", 
        "mx150", "mx250", "mx350", "mx450", "celeron", "pentium", "athlon"
    ],
    "MID": [
        "gtx 1060", "gtx 1660", "rtx 3050", "rx 580", "rx 6500", "rtx 2060", 
        "gtx 1070", "gtx 1650", "rx 570", "ryzen 5", "core i5"
    ],
    "HIGH": [
        "rtx 3060", "rtx 3070", "rtx 4060", "rx 6700", "rx 7600", "rtx 2070", 
        "rtx 2080", "ryzen 7", "core i7"
    ],
    "ENTHUSIAST": [
        "rtx 3080", "rtx 3090", "rtx 4070", "rtx 4080", "rtx 4090", "rx 6800", 
        "rx 6900", "rx 7800", "rx 7900", "ryzen 9", "core i9", "threadripper"
    ]
}

TIERS = {
    "LOW": {
        "label": "Low-End Performance",
        "description": "Optimized for maximum frame rate stability on entry-level or integrated graphics systems.",
        "settings": {
            "[/Script/ShooterGame.ShooterGameUserSettings]": {
                "bUseVSync": "False",
                "FrameRateLimit": "0.000000",
                "FullscreenMode": "0",
                "LastConfirmedFullscreenMode": "0"
            },
            "ScalabilityGroups": {
                "sg.ResolutionQuality": "100.000000",
                "sg.ViewDistanceQuality": "0",
                "sg.AntiAliasingQuality": "0",
                "sg.ShadowQuality": "0",
                "sg.PostProcessQuality": "0",
                "sg.TextureQuality": "0",
                "sg.EffectsQuality": "0",
                "sg.FoliageQuality": "0",
                "sg.ShadingQuality": "0"
            }
        }
    },
    "MID": {
        "label": "Mid-Range Balanced",
        "description": "Balanced configuration for steady 144+ FPS while retaining competitive visual clarity.",
        "settings": {
            "[/Script/ShooterGame.ShooterGameUserSettings]": {
                "bUseVSync": "False",
                "FrameRateLimit": "0.000000",
                "FullscreenMode": "0",
                "LastConfirmedFullscreenMode": "0"
            },
            "ScalabilityGroups": {
                "sg.ResolutionQuality": "100.000000",
                "sg.ViewDistanceQuality": "1",
                "sg.AntiAliasingQuality": "1",
                "sg.ShadowQuality": "1",
                "sg.PostProcessQuality": "1",
                "sg.TextureQuality": "1",
                "sg.EffectsQuality": "1",
                "sg.FoliageQuality": "1",
                "sg.ShadingQuality": "1"
            }
        }
    },
    "HIGH": {
        "label": "High-End Quality",
        "description": "Designed for modern high-refresh monitors, offering excellent graphics without input lag.",
        "settings": {
            "[/Script/ShooterGame.ShooterGameUserSettings]": {
                "bUseVSync": "False",
                "FrameRateLimit": "0.000000",
                "FullscreenMode": "0",
                "LastConfirmedFullscreenMode": "0"
            },
            "ScalabilityGroups": {
                "sg.ResolutionQuality": "100.000000",
                "sg.ViewDistanceQuality": "2",
                "sg.AntiAliasingQuality": "2",
                "sg.ShadowQuality": "1",  # Keep shadows medium for competitive visibility advantage
                "sg.PostProcessQuality": "2",
                "sg.TextureQuality": "2",
                "sg.EffectsQuality": "2",
                "sg.FoliageQuality": "2",
                "sg.ShadingQuality": "2"
            }
        }
    },
    "ENTHUSIAST": {
        "label": "Enthusiast Max",
        "description": "Ultra settings for high-spec processors and flagship graphics hardware.",
        "settings": {
            "[/Script/ShooterGame.ShooterGameUserSettings]": {
                "bUseVSync": "False",
                "FrameRateLimit": "0.000000",
                "FullscreenMode": "0",
                "LastConfirmedFullscreenMode": "0"
            },
            "ScalabilityGroups": {
                "sg.ResolutionQuality": "100.000000",
                "sg.ViewDistanceQuality": "3",
                "sg.AntiAliasingQuality": "3",
                "sg.ShadowQuality": "2",  # Avoid max shadow quality to prevent visual distraction in tournaments
                "sg.PostProcessQuality": "3",
                "sg.TextureQuality": "3",
                "sg.EffectsQuality": "3",
                "sg.FoliageQuality": "3",
                "sg.ShadingQuality": "3"
            }
        }
    }
}

SETTING_EXPLANATIONS = {
    "bUseVSync": "Disabled to eliminate significant mouse input lag, which is critical for competitive responsiveness.",
    "FrameRateLimit": "Set to uncapped for the lowest latency, allowing your GPU to output frames as fast as they are rendered.",
    "FullscreenMode": "Forces true fullscreen to bypass the Windows composition layer, saving resources and lowering input lag.",
    "sg.ResolutionQuality": "Set to native resolution scale (100%) to preserve perfect pixel clarity and target detection.",
    "sg.ViewDistanceQuality": "Optimizes how far background geometry is rendered to control CPU overhead.",
    "sg.AntiAliasingQuality": "Controls edge smoothing. Set to reduce jagged borders and shimmer during rapid movement.",
    "sg.ShadowQuality": "Kept at lower levels because shadow physics degrades frame rate and creates competitive clutter.",
    "sg.PostProcessQuality": "Adjusts bloom and screen distortion. Reduced to ensure maximum sight clarity.",
    "sg.TextureQuality": "Managed based on available system VRAM to prevent micro-stutters and memory throttling.",
    "sg.EffectsQuality": "Reduces smoke and particle rendering complexity, keeping FPS stable during heavy utility usage.",
    "sg.FoliageQuality": "Minimizes non-essential environmental details like grass, boosting visibility of enemies.",
    "sg.ShadingQuality": "Optimizes standard lighting computations for direct performance gains."
}

def classify_hardware(profile: HardwareProfile) -> str:
    """
    Classifies system into LOW, MID, HIGH, or ENTHUSIAST based on weighted hardware specs.
    Returns the string representing the tier.
    """
    # 1. RAM Scoring
    if profile.ram_gb < 8.0:
        ram_score = 1
    elif profile.ram_gb < 16.0:
        ram_score = 2
    elif profile.ram_gb < 32.0:
        ram_score = 3
    else:
        ram_score = 4

    # 2. CPU Scoring
    if profile.cpu_cores_physical <= 2:
        cpu_score = 1
    elif profile.cpu_cores_physical <= 4:
        cpu_score = 2
    elif profile.cpu_cores_physical <= 6:
        cpu_score = 3
    else:
        cpu_score = 4

    # 3. GPU Scoring
    gpu_model_lower = profile.gpu_model.lower()
    gpu_score = None

    # Check keyword matches
    for tier, keywords in TIER_KEYWORDS.items():
        if any(kw in gpu_model_lower for kw in keywords):
            if tier == "LOW":
                gpu_score = 1
            elif tier == "MID":
                gpu_score = 2
            elif tier == "HIGH":
                gpu_score = 3
            elif tier == "ENTHUSIAST":
                gpu_score = 4
            break

    # If no keyword matches, evaluate VRAM
    if gpu_score is None:
        if profile.gpu_vram_gb <= 2.0:
            gpu_score = 1
        elif profile.gpu_vram_gb <= 4.0:
            gpu_score = 2
        elif profile.gpu_vram_gb <= 8.0:
            gpu_score = 3
        else:
            gpu_score = 4

    # Compute overall score: GPU is heavily weighted (2x) as it is the primary bottleneck for graphics settings
    overall_score = (gpu_score * 2.0 + cpu_score * 1.0 + ram_score * 1.0) / 4.0
    
    logger.info(f"Classification details - RAM Score: {ram_score}, CPU Score: {cpu_score}, "
                f"GPU Score: {gpu_score}, Combined Score: {overall_score}")

    if overall_score < 1.75:
        return "LOW"
    elif overall_score < 2.75:
        return "MID"
    elif overall_score < 3.75:
        return "HIGH"
    else:
        return "ENTHUSIAST"

def get_recommendation(profile: HardwareProfile) -> Tuple[str, Dict[str, Any], str]:
    """
    Evaluates hardware and returns (tier_name, settings_dict, description).
    """
    tier = classify_hardware(profile)
    tier_data = TIERS[tier]
    return tier, tier_data["settings"], tier_data["description"]
