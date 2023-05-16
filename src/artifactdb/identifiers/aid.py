"""Utility functions and definitions to manipulate ArtifactDB IDs (AIDs)."""

import logging
from re import match
from typing import Dict, List, Tuple


class MalformedID(Exception):
    """An exception for a malformed ID."""


class MalformedKey(Exception):
    """An exception for a malformed S3 key."""


def parse_key(key: str) -> Dict[str, str]:
    """Parse an S3 key pointing to an ArtifactDB file.

    Parameters
    ----------
    key : str
        The S3 key to parse.

    Returns
    -------
    parsed_key : Dict[str, str]
        A `dict` with the keys: `"project_id"`, `"metapath"`, and `"version"`.
        Note: `"metapath"` is the path to metadata file describing the
        ArtifactDB file, not the resource file. It is different from `"path"`
        in the metadata file itself.
    """
    matches = match(r"^/?(.*?)/(.*?)/(.*)", key)
    if matches is None:
        raise MalformedKey("S3 key could not be parsed.")

    project_id, version, metapath = matches.groups()

    errors: List[str] = []
    if not isinstance(project_id, str):
        errors.append(f"Can't unpack project ID from {key}")
    if not isinstance(metapath, str):
        errors.append(f"Can't unpack metapath from {key}")
    if not isinstance(version, str):
        errors.append(f"Can't unpack version from {key}")
    if len(errors) > 0:
        raise MalformedKey(" ".join(errors))

    return {"project_id": project_id, "metapath": metapath, "version": version}


def unpack_id(_id: str) -> Dict[str, str]:
    """Unpack an ArtifactDB ID.

    Parameters
    ----------
    aid : str
        The ArtifactDB ID to unpack.

    Returns
    -------
    unpacked_aid : Dict[str, str]
        The unpacked ArtifactDB ID in the form of a `dict` with keys:
        `"project_id"`, `"path"`, and `"version"`.
    """
    try:
        if _id.startswith("gprn:"):
            # TODO: while we have a `gprn:...` notation there, we're not parsing a GPRN per se, but still an ArtifactDB ID,
            # with project ID as a GPRN. That's why we need to capture the (gprn...) group below. Such cases exists
            # with GPRN of GPRNs, that is , when a system with its own GPRN root (eg. gprn:dev:mysystem:...) embeds a GPRN
            # of another system (eg. gprn::myothersystem:artifact:PRJ01:dir1/file1.txt@1), which results in eg.:
            # - gprn:dev:mysystem::artifact:gprn::myothersystem::artifact:PRJ01:dir1/file1.txt@1:somefile.csv@3
            # The corresponding ArtifactDB ID (after some GPRN parsing) would then be (notice it is *not* a GPRN, the
            # syntax doesn't match a GPRN):
            # - gprn::myothersystem::artifact:PRJ01:dir1/file1.txt@1:somefile.csv@3
            # Parsing this ArtifactDB ID should give:
            # - project_id: gprn::myothersystem::artifact:PRJ01:dir1/file1.txt@1
            # - version: 3
            # - path: somefile.csv
            # That said... the parsing result in the end is not correct... Assuming that code is dead for now, with a warning
            # to see if it resurrects...
            logging.critical(f"Parsing an ArtifactDB ID starting with a `gprn:` notation, not supported: {_id!r}")
            project_id, _, path, version = match(r"^(gprn(:.*?){5}.*?):(.*)@([.\w\d-]+)",_id).groups()
        else:
            project_id, path, version = match(r"^(.*?):(.*?)@([.\w\d-]+)",_id).groups()
        assert project_id, "can't unpack project_id from '%s'" % _id
        assert path, "can't unpack path from '%s'" % _id
        assert version, "can't unpack version from '%s'" % _id

        return {"project_id": project_id, "path": path, "version": version}

    except AssertionError as exc:
        raise MalformedID(exc)
    except AttributeError as exc:
        raise MalformedID(f"Unable to parse ID: {exc}")


def _get_parts(parts: Dict[str, str]) -> Tuple[str, str, str]:
    """Get all the parts of an ArtifactDB from a `dict`.

    Parameters
    ----------
    parts : Dict[str, str]
        The unpacked ArtifactDB ID in the form of a `dict` with keys:
        `"project_id"`, `"path"`, and `"version"`.

    Returns
    -------
    project_id : str
        The ID of the project.
    path : str
        The path to the resource in the project.
    version : str
        The version of the project.
    """
    try:
        project_id = parts["project_id"]
    except KeyError as exc:
        raise MalformedID(
            "Given parts does not contain a 'project_id' key."
        ) from exc
    try:
        path = parts["path"]
    except KeyError as exc:
        raise MalformedID(
            "Given parts does not contain a 'path' key."
        ) from exc
    try:
        version = parts["version"]
    except KeyError as exc:
        raise MalformedID(
            "Given parts does not contain a 'version' key."
        ) from exc

    return project_id, path, version


def pack_id(parts: Dict[str, str]) -> str:
    """Pack the parts of an ArtifactDB ID together.

    Parameters
    ----------
    parts : Dict[str, str]
        The unpacked ArtifactDB ID in the form of a `dict` with keys:
        `"project_id"`, `"path"`, and `"version"`.

    Returns
    -------
    artifactdb_id : str
        The parts packed into an ArtifactDB ID in the format
        <project_id>:<path>@<version>.
    """
    project_id, path, version = _get_parts(parts)

    return f"{project_id}:{path}@{version}"


# TODO: @Sebastien what is an artifact_doc? what is its type?
def generate_id(artifact_doc):
    # by convention, all those fields must exist and be set
    ids = dict(
        project_id=artifact_doc._extra.project_id,
        version=artifact_doc._extra.version,
        path=artifact_doc.path,
    )
    return pack_id(ids)


def parse_arn(arn: str) -> Dict[str, str]:
    """Parse an S3 key with a prepended bucket.

    Parameters
    ----------
    arn : str
        The S3 key with the prepended bucket.

    Returns
    -------
    unpacked_arn : Dict[str, str]
        The unpacked ArtifactDB ID in the form of a `dict` with keys:
        `"project_id"`, `"path"`, `"version"`, and `"bucket"`.
    """
    bucket, key = arn.split(":")[5:][0].split("/", maxsplit=1)
    ids = parse_key(key)
    ids["path"] = ids.pop("metapath")
    ids["bucket"] = bucket
    return ids


def generate_key(parts: Dict[str, str]) -> str:
    """Generate a key from the parts of an ArtifactDB ID.

    Parameters
    ----------
    parts : Dict[str, str]
        The unpacked ArtifactDB ID in the form of a `dict` with keys:
        `"project_id"`, `"path"`, and `"version"`.

    Returns
    -------
    key : str
        A str of the format: `"<project_id>/<version>/<path>"`
    """
    project_id, path, version = _get_parts(parts)

    return f"{project_id}/{version}/{path}"
