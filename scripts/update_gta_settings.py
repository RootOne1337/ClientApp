"""
GTA V Settings Generator

Detects GPU and creates optimal settings.xml with minimal graphics for VM usage.
Automatically kills GTA processes if file is locked.

Returns:
    True if settings were successfully written
    False if failed
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional

# Добавляем parent в path для импорта
sys.path.insert(0, str(Path(__file__).parent.parent))
try:
    from utils import get_logger
    logger = get_logger()
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


TEMPLATE_XML = """<?xml version="1.0" encoding="UTF-8"?>

<Settings>
    <version value="27" />
    <configSource>SMC_AUTO</configSource>
    <graphics>
        <Tessellation value="0" />
        <LodScale value="0.000000" />
        <PedLodBias value="0.000000" />
        <VehicleLodBias value="0.000000" />
        <ShadowQuality value="1" />
        <ReflectionQuality value="0" />
        <ReflectionMSAA value="0" />
        <SSAO value="0" />
        <AnisotropicFiltering value="0" />
        <MSAA value="0" />
        <MSAAFragments value="0" />
        <MSAAQuality value="0" />
        <SamplingMode value="1" />
        <TextureQuality value="0" />
        <ParticleQuality value="0" />
        <WaterQuality value="0" />
        <GrassQuality value="0" />
        <ShaderQuality value="0" />
        <Shadow_SoftShadows value="0" />
        <UltraShadows_Enabled value="false" />
        <Shadow_ParticleShadows value="true" />
        <Shadow_Distance value="1.000000" />
        <Shadow_LongShadows value="false" />
        <Shadow_SplitZStart value="0.930000" />
        <Shadow_SplitZEnd value="0.890000" />
        <Shadow_aircraftExpWeight value="0.990000" />
        <Shadow_DisableScreenSizeCheck value="false" />
        <Reflection_MipBlur value="true" />
        <FXAA_Enabled value="false" />
        <TXAA_Enabled value="false" />
        <Lighting_FogVolumes value="true" />
        <Shader_SSA value="false" />
        <DX_Version value="2" />
        <CityDensity value="0.000000" />
        <PedVarietyMultiplier value="0.000000" />
        <VehicleVarietyMultiplier value="0.000000" />
        <PostFX value="0" />
        <DoF value="false" />
        <HdStreamingInFlight value="false" />
        <MaxLodScale value="0.000000" />
        <MotionBlurStrength value="0.000000" />
    </graphics>
    <system>
        <numBytesPerReplayBlock value="9000000" />
        <numReplayBlocks value="30" />
        <maxSizeOfStreamingReplay value="1024" />
        <maxFileStoreSize value="65536" />
    </system>
    <audio>
        <Audio3d value="false" />
    </audio>
    <video>
        <AdapterIndex value="0" />
        <OutputIndex value="0" />
        <ScreenWidth value="1280" />
        <ScreenHeight value="720" />
        <RefreshRate value="59" />
        <Windowed value="2" />
        <VSync value="2" />
        <Stereo value="0" />
        <Convergence value="0.100000" />
        <Separation value="1.000000" />
        <PauseOnFocusLoss value="1" />
        <AspectRatio value="0" />
    </video>
    <VideoCardDescription>NVIDIA GeForce GTX 640</VideoCardDescription>
</Settings>
"""


def default_target_path() -> Path:
    user_profile = os.environ.get("USERPROFILE")
    if user_profile:
        return (
            Path(user_profile)
            / "Documents"
            / "Rockstar Games"
            / "GTA V"
            / "settings.xml"
        )
    return Path.cwd() / "settings.xml"


def get_gpu_name() -> Optional[str]:
    """Detect GPU name via PowerShell"""
    ps = r"""
$ErrorActionPreference = 'Stop'
Get-CimInstance Win32_VideoController |
Where-Object {
    $_.Name -notmatch "Basic|Parsec|Virtual|Remote|RDP|VMware|Hyper-V"
} |
Select-Object -First 1 -ExpandProperty Name
""".strip()

    try:
        completed = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                ps,
            ],
            capture_output=True,
            text=True,
            timeout=20,
        )

        name = (completed.stdout or "").strip()
        if completed.returncode == 0 and name:
            return name
    except Exception as e:
        logger.error(f"GPU detection failed: {e}")
    
    return None


VIDEO_TAG_RE = re.compile(
    r"(?P<indent>^[ \t]*)<VideoCardDescription>.*?</VideoCardDescription>[ \t]*$",
    flags=re.MULTILINE,
)


def apply_videocard_description(template_text: str, gpu_name: str) -> str:
    m = VIDEO_TAG_RE.search(template_text)
    if not m:
        raise ValueError("Template is missing <VideoCardDescription>")

    indent = m.group("indent") or ""
    replacement_line = f"{indent}<VideoCardDescription>{gpu_name}</VideoCardDescription>"
    return VIDEO_TAG_RE.sub(replacement_line, template_text, count=1)


def taskkill(image_name: str) -> None:
    subprocess.run(["taskkill", "/F", "/T", "/IM", image_name], capture_output=True, text=True)


KILL_LIST = [
    "GTA5.exe",
    "PlayGTAV.exe",
    "Launcher.exe",
    "RockstarLauncher.exe",
    "RockstarService.exe",
    "SocialClubHelper.exe",
    "EpicGamesLauncher.exe",
    "RAGEMP.exe",
    "ragemp_v.exe",
]


def write_atomic(target_path: Path, content: str) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        delete=False,
        dir=str(target_path.parent),
        prefix=target_path.name + ".tmp.",
        newline="\n",
    ) as tmp:
        tmp_path = Path(tmp.name)
        tmp.write(content)
        tmp.flush()
        os.fsync(tmp.fileno())

    try:
        os.replace(tmp_path, target_path)
    except Exception:
        if target_path.exists():
            target_path.unlink()
        os.replace(tmp_path, target_path)


def update_gta_settings(kill_on_failure: bool = True) -> bool:
    """
    Обновить settings.xml для GTA V с правильным GPU.
    
    Returns:
        True если успешно
        False если ошибка
    """
    logger.info("=" * 50)
    logger.info("🎮 GTA V Settings Update")
    logger.info("=" * 50)
    
    # Определяем GPU
    gpu_name = get_gpu_name()
    if not gpu_name:
        logger.warning("Could not detect GPU, using default")
        gpu_name = "NVIDIA GeForce GTX 1060"
    
    logger.info(f"GPU: {gpu_name}")
    
    # Генерируем конфиг
    try:
        updated_text = apply_videocard_description(TEMPLATE_XML, gpu_name)
    except Exception as e:
        logger.error(f"Failed to generate config: {e}")
        return False
    
    # Записываем
    target_path = default_target_path()
    logger.info(f"Target: {target_path}")
    
    for attempt in range(3):
        try:
            write_atomic(target_path, updated_text)
            logger.info("✅ Settings written successfully!")
            return True
        except PermissionError:
            if kill_on_failure and attempt < 2:
                logger.warning("File locked, killing GTA processes...")
                for proc in KILL_LIST:
                    taskkill(proc)
                time.sleep(0.5)
            else:
                logger.error("❌ Cannot write settings (file locked)")
                return False
        except Exception as e:
            logger.error(f"❌ Write failed: {e}")
            return False
    
    return False


if __name__ == "__main__":
    success = update_gta_settings()
    sys.exit(0 if success else 1)
