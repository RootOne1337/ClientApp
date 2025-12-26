from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path


TEMPLATE_XML = """<?xml version=\"1.0\" encoding=\"UTF-8\"?>

<Settings>
    <version value=\"27\" />
    <configSource>SMC_AUTO</configSource>
    <graphics>
        <Tessellation value=\"0\" />
        <LodScale value=\"0.000000\" />
        <PedLodBias value=\"0.000000\" />
        <VehicleLodBias value=\"0.000000\" />
        <ShadowQuality value=\"1\" />
        <ReflectionQuality value=\"0\" />
        <ReflectionMSAA value=\"0\" />
        <SSAO value=\"0\" />
        <AnisotropicFiltering value=\"0\" />
        <MSAA value=\"0\" />
        <MSAAFragments value=\"0\" />
        <MSAAQuality value=\"0\" />
        <SamplingMode value=\"1\" />
        <TextureQuality value=\"0\" />
        <ParticleQuality value=\"0\" />
        <WaterQuality value=\"0\" />
        <GrassQuality value=\"0\" />
        <ShaderQuality value=\"0\" />
        <Shadow_SoftShadows value=\"0\" />
        <UltraShadows_Enabled value=\"false\" />
        <Shadow_ParticleShadows value=\"true\" />
        <Shadow_Distance value=\"1.000000\" />
        <Shadow_LongShadows value=\"false\" />
        <Shadow_SplitZStart value=\"0.930000\" />
        <Shadow_SplitZEnd value=\"0.890000\" />
        <Shadow_aircraftExpWeight value=\"0.990000\" />
        <Shadow_DisableScreenSizeCheck value=\"false\" />
        <Reflection_MipBlur value=\"true\" />
        <FXAA_Enabled value=\"false\" />
        <TXAA_Enabled value=\"false\" />
        <Lighting_FogVolumes value=\"true\" />
        <Shader_SSA value=\"false\" />
        <DX_Version value=\"2\" />
        <CityDensity value=\"0.000000\" />
        <PedVarietyMultiplier value=\"0.000000\" />
        <VehicleVarietyMultiplier value=\"0.000000\" />
        <PostFX value=\"0\" />
        <DoF value=\"false\" />
        <HdStreamingInFlight value=\"false\" />
        <MaxLodScale value=\"0.000000\" />
        <MotionBlurStrength value=\"0.000000\" />
    </graphics>
    <system>
        <numBytesPerReplayBlock value=\"9000000\" />
        <numReplayBlocks value=\"30\" />
        <maxSizeOfStreamingReplay value=\"1024\" />
        <maxFileStoreSize value=\"65536\" />
    </system>
    <audio>
        <Audio3d value=\"false\" />
    </audio>
    <video>
        <AdapterIndex value=\"0\" />
        <OutputIndex value=\"0\" />
        <ScreenWidth value=\"1280\" />
        <ScreenHeight value=\"720\" />
        <RefreshRate value=\"59\" />
        <Windowed value=\"2\" />
        <VSync value=\"2\" />
        <Stereo value=\"0\" />
        <Convergence value=\"0.100000\" />
        <Separation value=\"1.000000\" />
        <PauseOnFocusLoss value=\"1\" />
        <AspectRatio value=\"0\" />
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

    # Extremely defensive fallback.
    return Path.cwd() / "settings.xml"


def get_gpu_name_via_powershell() -> str:
    ps = r"""
$ErrorActionPreference = 'Stop'
Get-CimInstance Win32_VideoController |
Where-Object {
    $_.Name -notmatch "Basic|Parsec|Virtual|Remote|RDP|VMware|Hyper-V"
} |
Select-Object -First 1 -ExpandProperty Name
""".strip()

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
    if completed.returncode != 0 or not name:
        stderr = (completed.stderr or "").strip()
        raise RuntimeError(f"GPU detection failed. {stderr}".strip())

    return name


VIDEO_TAG_RE = re.compile(
    r"(?P<indent>^[ \t]*)<VideoCardDescription>.*?</VideoCardDescription>[ \t]*$",
    flags=re.MULTILINE,
)


def apply_videocard_description(template_text: str, gpu_name: str) -> str:
    if "<Settings" not in template_text or "</Settings>" not in template_text:
        raise ValueError("Template does not look like a GTA settings.xml (missing <Settings> root).")

    m = VIDEO_TAG_RE.search(template_text)
    if not m:
        raise ValueError("Template is missing <VideoCardDescription>...</VideoCardDescription>.")

    indent = m.group("indent") or ""
    replacement_line = f"{indent}<VideoCardDescription>{gpu_name}</VideoCardDescription>"
    return VIDEO_TAG_RE.sub(replacement_line, template_text, count=1)


def ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def taskkill(image_name: str) -> None:
    subprocess.run(["taskkill", "/F", "/T", "/IM", image_name], capture_output=True, text=True)


DEFAULT_KILL_LIST = [
    # GTA / Rockstar
    "GTA5.exe",
    "PlayGTAV.exe",
    "Launcher.exe",
    "RockstarLauncher.exe",
    "RockstarService.exe",
    "SocialClubHelper.exe",
    "SocialClubUI.exe",
    # Epic
    "EpicGamesLauncher.exe",
    "EpicWebHelper.exe",
    # RAGE MP / Majestic / common mod launchers
    "RAGEMP.exe",
    "ragemp_v.exe",
    "RAGEPluginHook.exe",
    "FiveM.exe",
    "altv.exe",
]


def write_atomic(target_path: Path, content: str) -> None:
    ensure_parent_dir(target_path)

    # Write temp file in same dir, then replace.
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
        # Try remove then replace (sometimes helps if file exists and is not locked).
        try:
            if target_path.exists():
                target_path.unlink()
        except Exception:
            pass
        os.replace(tmp_path, target_path)


def write_with_retries(
    target_path: Path,
    content: str,
    *,
    kill_on_failure: bool,
    kill_list: list[str],
    attempts: int = 3,
) -> None:
    last_exc: Exception | None = None

    for attempt in range(1, attempts + 1):
        try:
            write_atomic(target_path, content)
            return
        except Exception as exc:
            last_exc = exc
            if not kill_on_failure:
                break

            for proc in kill_list:
                taskkill(proc)

            time.sleep(0.4 * attempt)

    raise last_exc or RuntimeError("Write failed")


def verify_output_is_full_config(text: str) -> None:
    # Minimal sanity checks to avoid writing a truncated file.
    required_markers = [
        "<?xml",
        "<Settings>",
        "<graphics>",
        "</graphics>",
        "<video>",
        "</video>",
        "<VideoCardDescription>",
        "</Settings>",
    ]
    missing = [m for m in required_markers if m not in text]
    if missing:
        raise ValueError(f"Generated config seems incomplete; missing markers: {missing}")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Detect GPU name and rewrite GTA V settings.xml using a full template, replacing only <VideoCardDescription>."
    )
    parser.add_argument(
        "--target",
        default=None,
        help="Target settings.xml path",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print what would happen; do not write.")
    parser.add_argument("--no-kill", action="store_true", help="Do not kill processes if file is locked.")
    parser.add_argument(
        "--kill",
        action="append",
        default=[],
        help="Additional process image names to kill (can be repeated), e.g. --kill Majestic.exe",
    )
    args = parser.parse_args(argv)

    gpu_name = get_gpu_name_via_powershell()

    updated_text = apply_videocard_description(TEMPLATE_XML, gpu_name)
    verify_output_is_full_config(updated_text)

    target_path = Path(args.target) if args.target else default_target_path()

    if args.dry_run:
        print(f"GPU: {gpu_name}")
        print(f"Would write: {target_path}")
        print(f"Line: <VideoCardDescription>{gpu_name}</VideoCardDescription>")
        return 0

    kill_list = DEFAULT_KILL_LIST + list(args.kill)
    try:
        write_with_retries(
            target_path,
            updated_text,
            kill_on_failure=not args.no_kill,
            kill_list=kill_list,
            attempts=3,
        )
    except PermissionError:
        # If the caller didn't explicitly choose a target, fall back to the current user's Documents.
        if args.target:
            raise
        fallback = default_target_path()
        if fallback != target_path:
            target_path = fallback
            write_with_retries(
                target_path,
                updated_text,
                kill_on_failure=not args.no_kill,
                kill_list=kill_list,
                attempts=3,
            )
        else:
            raise

    # Post-write verification (read back and check markers + exact GPU line)
    written = target_path.read_text(encoding="utf-8", errors="replace")
    verify_output_is_full_config(written)
    if f"<VideoCardDescription>{gpu_name}</VideoCardDescription>" not in written:
        raise RuntimeError("Post-write verification failed: VideoCardDescription mismatch.")

    print(f"OK: Wrote {target_path}")
    print(f"GPU: {gpu_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
