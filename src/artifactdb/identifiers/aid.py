"""
Utility functions and definitions to manipulate ArtifactDB IDs (AID)
"""

import re


class MalformedID(Exception):
    pass


def parse_key(key):
    """
    given a s3 key pointing to a artifact file, return:
    dict(project_id=<project_id>,metapath=<path>,version=<version>)

    note: metapath is the path to metadata file describing the artifact file,
    not the actual result file. it's different from "path" in metadata file itself.
    """
    project_id, version, metapath = re.match(r"^/?(.*?)/(.*?)(/.*)",key).groups()
    assert project_id, "can't unpack project_id from '%s'" % key
    assert version, "can't unpack versionfrom '%s'" % key
    assert metapath, "can't unpack metapath from '%s'" % key
    # remove "/" at beginning, to match "path" format
    metapath = metapath.lstrip("/")
    return {"project_id": project_id, "metapath": metapath, "version": version}


def unpack_id(_id):
    """
    given a ArtifactDB-like ID, format <project_id>:<path>@<version>
    return: dict(project_id=<project_id>,path=<path>,version=<version>)
    """
    try:
        if _id.startswith("gprn:"):
            # we expect a fix number of ":" in the GPRN/project_id component
            # if "gprn:dev:cerberus::project:DS000000267@1:experiment-1/coldata/column8/simple.csv@4"
            # we expect 6 ":" that separates project_id from the rest
            project_id,_,path,version = re.match(r"^(gprn(:.*?){5}.*?):(.*)@(\w+-*\d*)",_id).groups()
        else:
            project_id, path, version = re.match(r"^(.*?):(.*?)@(\w+-*\d*)",_id).groups()
        assert project_id, "can't unpack project_id from '%s'" % _id
        assert path, "can't unpack path from '%s'" % _id
        assert version, "can't unpack version from '%s'" % _id

        return {"project_id": project_id, "path": path, "version": version}

    except AssertionError as exc:
        raise MalformedID(exc)
    except AttributeError as exc:
        raise MalformedID(f"Unable to parse ID: {exc}")


def pack_id(ids):
    """
    Given a dict(project_id=<project_id>,path=<path>,version=<version>),
    returns an ArtifactDB ID: format <project_id>:<path>@<version>
    """
    return f"{ids['project_id']}:{ids['path']}@{ids['version']}"


def generate_id(artifact_doc):
    # by convention, all those fields must exist and be set
    ids = dict(project_id=artifact_doc._extra.project_id,
               version=artifact_doc._extra.version,
               path=artifact_doc.path)
    return pack_id(ids)


def parse_arn(arn):
    """
    Return pack_id() result with an additional `bucket` key
    """
    bucket,key = arn.split(":")[5:][0].split("/",maxsplit=1)
    ids = parse_key(key)
    ids["path"] = ids.pop("metapath")
    ids["bucket"] = bucket
    return ids

def generate_key(ids):
    for k in ids:
        ids[k] = ids[k].strip("/")
    return f"{ids['project_id']}/{ids['version']}/{ids['path']}"


