#!/usr/bin/env python3
# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
"""Update to a new upstream release."""
import argparse
import json
import logging
import subprocess
import sys
import re
import urllib.request
import yaml
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Generator, List, Optional, Set, Tuple, TypedDict

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)
REPO = "https://api.github.com/repos/kubernetes-sigs/metrics-server/releases"
FILEDIR = Path(__file__).parent/"metrics-server"
VERSION_RE = re.compile(r"^v\d+\.\d+\.\d+")
IMG_RE = re.compile(r"^\s+image:\s+(\S+)")


@dataclass(frozen=True)
class Registry:
    name: str
    path: str
    user: str
    pass_file: str

    @property
    def creds(self) -> "SyncCreds":
        return {
            "registry": self.name,
            "user": self.user,
            "pass": Path(self.pass_file).read_text().strip(),
        }


@dataclass(frozen=True)
class Release:
    name: str
    path: str
    size: int = 0

    def __hash__(self) -> int:
        return hash(self.name)

    def __eq__(self, other) -> bool:
        return isinstance(other, Release) and self.name == other.name


SyncAsset = TypedDict("SyncAsset", {"source": str, "target": str, "type": str})
SyncCreds = TypedDict("SyncCreds", {"registry": str, "user": str, "pass": str})


class SyncConfig(TypedDict):
    version: int
    creds: List[SyncCreds]
    sync: List[SyncAsset]


def sync_asset(image: str, registry: Registry):
    _, tag = image.split("/", 1)
    dest = f"{registry.name}/{registry.path.strip('/')}/{tag}"
    return SyncAsset(source=image, target=dest, type="image")


def main(registry: Optional[Registry]):
    """Main update logic."""
    local_releases = gather_current()
    latest, gh_releases = gather_releases()
    new_releases = gh_releases - local_releases
    for release in new_releases:
        local_releases.add(download(release))
    if registry:
        all_images = [image for release in local_releases for image in images(release)]
        mirror_image(all_images, registry)
    return latest


def gather_releases() -> Tuple[str, Set[Release]]:
    with urllib.request.urlopen(REPO) as resp:
        releases = [
            Release(release["name"], asset["browser_download_url"], asset["size"])
            for release in json.load(resp)
            if VERSION_RE.match(release["name"])
            for asset in release["assets"]
            if asset["name"] == "components.yaml"
        ]
    return releases[0].name, set(releases)


def gather_current() -> Set[Release]:
    return set(
        Release(
            release_path.parent.name, str(release_path), release_path.stat().st_size
        )
        for release_path in (FILEDIR / "manifests").glob("*/components.yaml")
    )


def download(release: Release) -> Release:
    log.info(f"Getting Release {release.name}")
    dest = FILEDIR / "manifests" / release.name / "components.yaml"
    dest.parent.mkdir(exist_ok=True)
    urllib.request.urlretrieve(release.path, dest)
    assert dest.stat().st_size == release.size
    return Release(release.name, str(dest), release.size)


def images(component: Release) -> Generator[str, None, None]:
    """Yield all images from each release."""
    with Path(component.path).open() as fp:
        for line in fp:
            matches = IMG_RE.match(line)
            if matches:
                yield matches.groups()[0]


def mirror_image(images: List[str], registry: Registry):
    """Synchronize all source images to target registry, only pushing changed layers."""
    sync_config = SyncConfig(
        version=1,
        creds=[registry.creds],
        sync=[sync_asset(image, registry) for image in images],
    )
    with NamedTemporaryFile(mode="w") as tmpfile:
        yaml.safe_dump(sync_config, tmpfile)
        proc = subprocess.Popen(
            ["regsync", "once", "-c", tmpfile.name, "-v", "debug"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            encoding="utf-8",
        )
        while proc.returncode is None:
            for line in proc.stdout or "":
                print(line.strip())
            proc.poll()


def get_argparser():
    """Build the argparse instance."""
    parser = argparse.ArgumentParser(
        description="Update from upstream releases.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--registry",
        default=None,
        type=str,
        nargs=4,
        help="Registry to which images should be mirrored.\n\n"
        "example\n"
        "  --registry my.registry:5000 path username password-file\n"
        "\n"
        "Mirroring depends on binary regsync "
        "(https://github.com/regclient/regclient/releases)\n"
        "and that it is available in the current working directory",
    )
    return parser


class UpdateError(Exception):
    """Represents an error performing the update."""


if __name__ == "__main__":
    try:
        args = get_argparser().parse_args()
        registry = Registry(*args.registry) if args.registry else None
        version = main(registry)
        Path(FILEDIR, "version").write_text(f"{version}\n")
        print(version)
    except UpdateError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)
