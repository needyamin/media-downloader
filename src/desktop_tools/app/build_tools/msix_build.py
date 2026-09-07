"""Package the Windows hub build as an MSIX for Microsoft Store / sideload."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from desktop_tools.app.build_tools.build_manifest import APP_FLAGS_PATH, ICON_PATH, REPO_ROOT

APP_NAME = "Media Downloader 4K"
OUTPUT_EXE_NAME = "Media-Downloader.exe"
DEFAULT_IDENTITY_NAME = "ANSNEWTECH.AnsNewTech.MediaDownloader4K"
DEFAULT_PUBLISHER = "CN=087A9974-75CB-44FC-B893-8D3999E5E5E5"
DEFAULT_PUBLISHER_DISPLAY = "ANSNEW TECH."
PARTNER_CENTER_ID = "8a8d4a0e-0564-4c7e-9ac9-17c748e8a806"
STORE_ID = "9PHDQLBB8QCK"
PACKAGE_FAMILY_NAME = "ANSNEWTECH.AnsNewTech.MediaDownloader4K_7gnedkmjvvvj0"
MSIX_TEMPLATE_DIR = REPO_ROOT / "src" / "desktop_tools" / "app" / "installer" / "msix"
WINDOWS_RELEASE_DIR = REPO_ROOT / "release" / "windows"
WINDOWS_BUILD_OUTPUT_DIR = WINDOWS_RELEASE_DIR / "build" / "pyinstaller" / "output"
SDK_SIGNTOOL = Path(r"C:\Program Files (x86)\Windows Kits\10\bin\10.0.26100.0\x64\signtool.exe")
SDK_MAKEAPPX = Path(r"C:\Program Files (x86)\Windows Kits\10\bin\10.0.26100.0\x64\makeappx.exe")


def env_value(name: str, default: str) -> str:
    value = os.environ.get(name, "").strip()
    return value or default


def read_package_version() -> str:
    env_version = os.environ.get("MD_RELEASE_VERSION", "").strip().lstrip("v")
    if env_version:
        parts = env_version.split(".")
    else:
        parts = ["2", "0", "0"]
        try:
            flags = json.loads(APP_FLAGS_PATH.read_text(encoding="utf-8"))
            raw = str(flags.get("versions", {}).get("media_downloader") or "3.0.0")
            parts = raw.lstrip("v").split(".")
        except Exception:
            pass
    numbers = [(part if part.isdigit() else "0") for part in parts[:4]]
    while len(numbers) < 4:
        numbers.append("0")
    return ".".join(numbers)


def find_sdk_tool(name: str, preferred: Path) -> Path | None:
    if preferred.is_file():
        return preferred
    kits = Path(r"C:\Program Files (x86)\Windows Kits\10\bin")
    if kits.is_dir():
        matches = sorted(kits.glob(f"*/x64/{name}"), reverse=True)
        if matches:
            return matches[0]
    return shutil.which(name)


def resolve_hub_dist_dir() -> Path:
    pyinstaller_name = OUTPUT_EXE_NAME.removesuffix(".exe")
    candidates = [
        WINDOWS_BUILD_OUTPUT_DIR / "media_download.dist",
        WINDOWS_BUILD_OUTPUT_DIR / pyinstaller_name,
        WINDOWS_RELEASE_DIR / "media_download.dist",
    ]
    for dist_dir in candidates:
        if (dist_dir / OUTPUT_EXE_NAME).is_file():
            return dist_dir
    raise SystemExit(
        "No Media-Downloader.exe build found. Build first:\n"
        "  $env:PYTHONPATH='src'\n"
        "  python -m desktop_tools.app.build_tools.pyinstaller"
    )


def write_store_assets(assets_dir: Path) -> None:
    from PIL import Image, ImageDraw

    assets_dir.mkdir(parents=True, exist_ok=True)
    source = Image.open(ICON_PATH).convert("RGBA")

    def square(size: int) -> Image.Image:
        return source.resize((size, size), Image.Resampling.LANCZOS)

    def save_square(name: str, size: int) -> None:
        square(size).save(assets_dir / name, "PNG")

    save_square("StoreLogo.png", 50)
    save_square("Square44x44Logo.png", 44)
    save_square("Square71x71Logo.png", 71)
    save_square("Square150x150Logo.png", 150)

    wide = Image.new("RGBA", (310, 150), (7, 17, 31, 255))
    icon = square(110)
    wide.paste(icon, (24, 20), icon)
    wide.save(assets_dir / "Wide310x150Logo.png", "PNG")

    splash = Image.new("RGBA", (620, 300), (7, 17, 31, 255))
    icon = square(128)
    splash.paste(icon, ((620 - 128) // 2, 56), icon)
    draw = ImageDraw.Draw(splash)
    draw.text((310, 220), APP_NAME, fill=(248, 250, 252, 255), anchor="mm")
    splash.save(assets_dir / "SplashScreen.png", "PNG")


def write_manifest(package_dir: Path) -> None:
    template = (MSIX_TEMPLATE_DIR / "AppxManifest.xml.template").read_text(encoding="utf-8")
    rendered = (
        template.replace("{{IDENTITY_NAME}}", env_value("MD_MSIX_IDENTITY_NAME", DEFAULT_IDENTITY_NAME))
        .replace("{{PUBLISHER}}", env_value("MD_MSIX_PUBLISHER", DEFAULT_PUBLISHER))
        .replace("{{PUBLISHER_DISPLAY_NAME}}", env_value("MD_MSIX_PUBLISHER_DISPLAY", DEFAULT_PUBLISHER_DISPLAY))
        .replace("{{DISPLAY_NAME}}", env_value("MD_MSIX_DISPLAY_NAME", APP_NAME))
        .replace("{{VERSION}}", read_package_version())
    )
    (package_dir / "AppxManifest.xml").write_text(rendered, encoding="utf-8")


def copy_listing(dest_dir: Path) -> Path:
    listing_src = MSIX_TEMPLATE_DIR / "store_listing.json"
    listing_dest = dest_dir / "store_listing.json"
    shutil.copy2(listing_src, listing_dest)
    return listing_dest


def pack_msix(package_dir: Path, output_msix: Path) -> None:
    makeappx = find_sdk_tool("makeappx.exe", SDK_MAKEAPPX)
    if makeappx is None:
        raise SystemExit(
            "MakeAppx.exe not found. Install the Windows SDK, then retry.\n"
            "  winget install --id Microsoft.WindowsSDK.10.0.26100 --source winget"
        )
    if output_msix.exists():
        output_msix.unlink()
    subprocess.run(
        [str(makeappx), "pack", "/d", str(package_dir), "/p", str(output_msix), "/o"],
        check=True,
        cwd=str(REPO_ROOT),
    )


def sign_msix_if_possible(output_msix: Path) -> bool:
    publisher = env_value("MD_MSIX_PUBLISHER", DEFAULT_PUBLISHER)
    if publisher.upper().startswith("CN=087A9974-75CB-44FC-B893-8D3999E5E5E5"):
        print("MSIX left unsigned so Partner Center can sign it with the Store publisher identity.")
        return False
    pfx = REPO_ROOT / "certs" / "codesign-test.pfx"
    password_file = REPO_ROOT / "certs" / "pfx-password.txt"
    signtool = find_sdk_tool("signtool.exe", SDK_SIGNTOOL)
    if not pfx.is_file() or not password_file.is_file() or signtool is None:
        print("MSIX left unsigned (no local test PFX). Partner Center will sign Store uploads.")
        return False
    password = password_file.read_text(encoding="utf-8").strip()
    subprocess.run(
        [
            str(signtool),
            "sign",
            "/fd",
            "SHA256",
            "/td",
            "SHA256",
            "/tr",
            "http://timestamp.digicert.com",
            "/f",
            str(pfx),
            "/p",
            password,
            "/d",
            APP_NAME,
            str(output_msix),
        ],
        check=True,
        cwd=str(REPO_ROOT),
    )
    print(f"Signed MSIX with local test certificate: {output_msix}")
    return True


def main() -> None:
    if os.name != "nt":
        raise SystemExit("MSIX packaging must run on Windows.")

    dist_dir = resolve_hub_dist_dir()
    package_dir = WINDOWS_RELEASE_DIR / "msix-package"
    output_msix = WINDOWS_RELEASE_DIR / "MediaDownloader.msix"
    if package_dir.exists():
        shutil.rmtree(package_dir)
    package_dir.mkdir(parents=True, exist_ok=True)

    print(f"Staging MSIX from {dist_dir}")
    shutil.copytree(dist_dir, package_dir, dirs_exist_ok=True)
    write_store_assets(package_dir / "Assets")
    write_manifest(package_dir)
    listing = copy_listing(WINDOWS_RELEASE_DIR)
    pack_msix(package_dir, output_msix)
    signed = sign_msix_if_possible(output_msix)

    print(f"MSIX package: {output_msix}")
    print(f"Store listing copy: {listing}")
    print(f"Identity Name: {DEFAULT_IDENTITY_NAME}")
    print(f"Publisher: {DEFAULT_PUBLISHER}")
    print(f"Partner Center ID: {PARTNER_CENTER_ID}")
    print(f"Store ID: {STORE_ID}")
    print(f"Package family name: {PACKAGE_FAMILY_NAME}")
    if signed:
        print("Sideload test: Add-AppxPackage .\\release\\windows\\MediaDownloader.msix")
    print("Upload this MSIX on the Packages tab. Partner Center signs Store builds.")
    print("Privacy URL: https://needyamin.github.io/media-downloader/privacy.html")


if __name__ == "__main__":
    main()
