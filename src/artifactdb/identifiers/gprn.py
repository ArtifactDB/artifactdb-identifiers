"""
Utility functions to manipulate Genomics Platform Resource Names (GPRNs)
"""

import copy

from .aid import unpack_id, pack_id


class GPRNError(Exception): pass
class FormatError(GPRNError): pass
class UnsupportedTypeID(GPRNError): pass
class NoSuchGPRN(GPRNError): pass


VALID_TYPE_IDS = ("artifact", "project", "doc", "changelog", "backup")

def parse(gprn):
    """
    Return a dict where keys follow the GPRN spec
    """
    parsed = {
        "environment": "prd",  # default if not specified, empty means "prd"
        "service": None,
        "placeholder": None,
        "type-id": None,
        "resource-id": None,
    }

    parts = gprn.split(":")
    prefix = parts[0]
    if prefix != "gprn":
        raise FormatError(f"Expecting prefix 'gprn', got '{prefix}'")
    if len(parts) == 2:
        parsed["environment"] = parts[1]
        return parsed
    prefix = parts.pop(0)
    if prefix != "gprn":
        raise FormatError(f"Expecting prefix 'gprn', got '{prefix}'")
    env = parts and parts.pop(0)
    if env:
        parsed["environment"] = env
    svc = parts and parts.pop(0)
    if not svc:
        raise FormatError("'service' is mandatory")
    parsed["service"] = svc
    # remaining are optional parts
    _ph = parts and parts.pop(0)
    if _ph:
        parsed["placeholder"] = _ph
    type_id = parts and parts.pop(0)
    if type_id:
        parsed["type-id"] = type_id
    res_id = parts and ":".join(parts)  # the resource-id can contain ":", we just take the remaining@
    if res_id:
        if not type_id:
            raise FormatError("'resource-id' requires 'type-id'")
        parsed["resource-id"] = res_id

    return parsed


def parse_resource_id(type_id, res_id):
    if res_id:
        if type_id == "artifact":
            res_id = unpack_id(res_id)
        elif type_id in ["project","changelog"]:
            if "@" in res_id:
                res_id = res_id.rsplit("@", 1)
                # or..: ? (found that from a stash...)
                res_id = {"project_id": res_id[0], "version": res_id[1]}
            else:
                # normalize res_id as a dict
                res_id = {"project_id": res_id}
    else:
        res_id = {}

    return res_id


def unparse_resource_id(parsed, resource_id):
    # build back GPRN with the version
    if parsed["type-id"] == "artifact":
        res_id = pack_id(resource_id)
    elif resource_id.get("version"):
        res_id = "{}@{}".format(resource_id["project_id"],resource_id["version"])
    else:
        res_id = resource_id["project_id"]

    return res_id


def generate(dgprn):
    try:
        # normalize prd/""
        if dgprn.get("environment") == "prd":
            dgprn["environment"] = ""
        idx = {"environment" : 1, "placeholder": 3, "type-id": 4, "resource-id": 5}
        # if service not set, during join(), it will raise a TypeError => GPRNError, see below
        lgprn = ["gprn","",dgprn.get("service"),"","",""]
        for key,val in idx.items():
            if dgprn.get(key):
                lgprn[val] = dgprn[key]
        gprn = ":".join(lgprn)
        # remove extra : at the end, when some optional fields aren't set
        gprn = gprn.rstrip(":")
        return gprn
    except KeyError as exc:
        raise GPRNError(f"Missing key in GPRN dict: {exc}")
    except TypeError as exc:
        raise GPRNError(f"GRPN parts not properly set ({dgprn}): {exc}")


def prepare_parents_list(parents):
    parent_list = []
    by_types = set()
    found_version = False
    for parent in parents:
        typ = None
        if len(parent.split(":")) <= 2:
            for each in parent.split(":"):
                typ = "root" if each == "gprn" else "environment"
        else:
            parsed = parse(parent)
            typ = parsed["type-id"]
            if parsed["type-id"] == "project":
                typ = "projects"
                if parsed["resource-id"]:
                    typ = "project"
                    if not found_version and "@" in parsed["resource-id"]:
                        typ = "version"
                        found_version = True
            elif parsed["type-id"] in ("changelog", "doc") and parsed["resource-id"]:
                typ = "version"
            if not parsed["type-id"]:
                if parsed["service"]:
                    typ = "service"
                if not parsed["service"] and parsed["environment"]:
                    typ = "environment"

        # alright, so this is tricky there. Someone (me) got the wonderful idea to allow GPRN within
        # GPRN (for Poseidon mainly), challenging the GPRN specification and parsing. So if we have:
        #   gprn:dev:poseidon::artifact:gprn:dev:cerberus::project:DS000000267@1:experiment-1/coldata/column8/simple.csv@4
        # this is project_id="gprn:dev:cerberus::project:DS000000267@1" at version=4 for path=experiment-1/coldata/column8/simple.csv
        # living in dev.poseidon service (it's a Poseidon artifact)
        # Parents:
        # version: gprn:dev:poseidon::project:gprn:dev:cerberus::project:DS000000267@1@4
        # project: gprn:dev:poseidon::project:gprn:dev:cerberus::project:DS000000267@1
        # projects: gprn:dev:poseidon::project
        # The tricky part is when project: gprn:dev:poseidon::project:gprn:dev:cerberus::project:DS000000267@1
        # If we consider it alone, it could mean project_id=gprn:dev:cerberus::project:DS000000267 at version=1
        # but in the context of previous parent, we already set the project-level GPRN, it's just that it
        # happens to look like a "version-aware" GPRN with an "@".
        # So this function walks up the tree of parents and sets the type it already explored.
        # First project-level GPRN was gprn:dev:poseidon::project:gprn:dev:cerberus::project:DS000000267@1
        # so any subsequent GPRN which could be interpreted are ignored...
        # Epilogue; I don't know how long this will last...
        if not typ in by_types:
            by_types.add(typ)
            parent_list.append({
                'type': typ,
                'gprn': parent
            })
    return parent_list


def get_parents(gprn, parents=None, deep=False):
    """
    Given a GPRN, returns a list of parents.
    Ex: gprn:dev:resultsdb::artifact:GPA2:/file/one@3
        gives parents:
        - gprn:dev:resultsdb::project:GPA2@3  (artifact belongs to this project/version)
        - gprn:dev:resultsdb::project:GPA2    (version belongs to this project)
        - gprn:dev:resultsdb::project         (GPA2 is a project)
        - gprn:dev:resultsdb                  (belonging to service resultsdb)
        - gprn:dev                            (on dev environment) # only return if deep=True
        - gprn                                (part of the Genomics Platform) # only return if deep=True
    """
    # stop condition: we ate enough of parts
    if deep:  # if deep, return deep list of all possible values
        if ":" not in gprn:
            return prepare_parents_list(parents)
    else:
        if len(gprn.split(":")) < 4:
            return prepare_parents_list(parents)

    # validate method does not check for environment and service for API because we did not pass the gprn config.
    parsed = validate(gprn)  # validate method validate the gprn and return the parsed value

    resource_id = parse_resource_id(parsed["type-id"], parsed["resource-id"])
    parsed["type-id"] = "project" if parsed["type-id"] == "artifact" else parsed["type-id"]
    parent = None
    if resource_id:
        if resource_id.get("path"):
            # resource_id an artifactdb ID, so parent is a project with a version.
            # we just need to get rid of the "path" element.
            parsed["resource-id"] = "{}@{}".format(resource_id["project_id"], resource_id["version"])
        elif resource_id.get("version"):
            # resource_id is a project+version, parent is project (alone)
            parsed["resource-id"] = resource_id["project_id"]
        else:
            # resource_id is a project, so parent is the next gprn component up.
            # ie. no resource-id anymore
            parsed["resource-id"] = None
        parent = generate(parsed)
    if not parent:
        # remove one GPRN part
        # rstrip ":" to ignore empty part, like 'placeholder', or env=prd, skip it
        parent = ":".join(gprn.split(":")[:-1]).strip(":")

    if parents is None:
        parents = []  # init, using None in signature to prevent add to a list by ref
    parents.append(parent)

    return get_parents(parent, parents=parents, deep=deep)


def get_lineage(gprn, deep=False):
    """
    Same as get_parents() but also include `gprn` in the result
    """
    parents = get_parents(gprn,deep=deep)
    # inject selft, with the same format as get_parents()
    return prepare_parents_list([gprn]) + parents


def build(gprn_cfg, project_id=None, version=None, path=None):
    dgprn = copy.deepcopy(gprn_cfg.to_dict())
    if path:
        assert version
        ids = {"project_id":project_id, "version": version, "path": path}
        aid = pack_id(ids)
        dgprn["type-id"] = "artifact"  # by default, for ArtifactDB APIs
        dgprn["resource-id"] = aid
    elif version:
        assert project_id
        dgprn["type-id"] = "project"
        dgprn["resource-id"] = f"{project_id}@{version}"
    elif project_id:
        dgprn["type-id"] = "project"
        dgprn["resource-id"] = f"{project_id}"
    else:
        dgprn["type-id"] = "project"

    gprn = generate(dgprn)

    return gprn


def validate(gprn, gprn_cfg=None):
    parsed = parse(gprn)
    orig_parsed = copy.deepcopy(parsed)
    # normalize prd env to match gprn_cfg
    parsed["environment"] = parsed['environment'] if parsed['environment'] != 'prd' else ''
    type_id = parsed["type-id"]
    if type_id and type_id not in VALID_TYPE_IDS:
        raise UnsupportedTypeID(f"Unsupported type-id: {type_id}")
    if type_id and parsed["resource-id"]:
        parse_resource_id(type_id, parsed["resource-id"])
    if gprn_cfg:  # gprn config found then only it check for the environment and service related to API.
        if parsed["service"] != gprn_cfg.service:
            raise GPRNError("Invalid 'service' name: '{}'".format(parsed["service"]))
        if parsed["environment"] != gprn_cfg.environment:
            raise GPRNError("Invalid 'environment': '{}'".format(parsed["environment"]))
    return orig_parsed  # untouched, directly coming from parse()

def lca(gprns,inner=False):
    """
    Given a list of GPRNs, return the Least Common Ancestor
    """
    grpns = set(gprns)  # remove dups, if any
    if len(grpns) == 1:
        return gprns[0]
    lineages = {}
    min_len = float("inf")
    shortests = []

    for gprn in gprns:
        res = get_lineage(gprn,deep=True)
        if len(res) <= min_len:
            # new min? or min with same length?
            if shortests and len(res) < min_len:
                shortests = [gprn]
            else:
                shortests.append(gprn)
            min_len = len(res)
        lineages[gprn] = res

    # special case where we found more than one shortest GPRN,
    # the LCA is the first parent in the lineage, in one of them
    if not inner and len(shortests) > 1:
        return lca(shortests,inner=True)

    shortest = shortests[0]#.pop()
    shortest_lineage = lineages.pop(shortest)
    lca_gprn = shortest_lineage[-1]  # at least, the lca is the root: {'type': 'root', 'gprn': 'gprn'}
    # walk down from root to leaves, until we don't match anymore (ie. found lca)
    for elem in shortest_lineage[::-1]:
        for gprn,lineage in lineages.items():
            if elem in lineage:
                lca_gprn = elem

    return lca_gprn["gprn"]

