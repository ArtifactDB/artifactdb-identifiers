# artifactdb-identifiers

`artifactdb-identifiers` is a python package used to manipulate common ArtifactDB identifier types, such as 
"ArtifactDB ID" and "GPRN".


## ArtifactDB ID

ArtifactDB ID identifies an artifact, within an ArtifactDB instance. The scope
is the instance, as a consequence, all ArtifactDB IDs are unique within an instance.

Given that artifacts are organized by project and version, the general format
is the following:

```
<project_id>:<path>@<version>
```

The module `artifactdb.identifiers.aid` contains helper functions used to generate and parse this type of IDs.


## GPRN

GPRNs are inspired by Amazon AWS [ARNs](https://docs.aws.amazon.com/general/latest/gr/aws-arns-and-namespaces.html) and uniquely
identify a resource within the Genomics Platform. The scope is wider than the ArtifactDB ID, as a GPRN can deal with 
different types of resources (not just artifacts) amongst a collection of ArtifactDB instances.

A resource is a generic term describing "something" in the Genomics Platform. It can be an artifact in an ArtifactDB API, it can
be an API, an API on specific environment, etc... The format is the following, with some segments being optional or defaulting
to specific values or meaning. When omitted, the number of `:` within the GPRN must be kept (this produces things like `::`):

```
gprn:environment:service:placeholder:type-id:resource-id
```

- `gprn`: prefix, mandatory
- *environment*: optionally specify the environment on which the resource can be found. Example: `dev`, `tst`, `prd`, etc...
  If omitted, the environment is the production.
- *service*: mandatory. The service, application, api, etc... on which the resource can be found. Ex: `myapi`, `rnaseqdb`, etc...
- *placeholder*: is a placeholder, in case another segment is required. (it's `region` in original ARNs)

At this point, the segments allow to uniquely describe a service, on a specific environment. Ex:

- `gprn::myapi` means "the service `myapi`, production environment"
- `gprn:dev:myapi` means "the service `myapi`, development environment"

Continuing further, we can describe resources within services:

- *type-id*: optional if *resource-id* not specified, otherwise required. Type of resource described in *resource-id*
- *resource-id*: optional if *type-id* not specficied, otherwise required. ID of type *type-id* within the service.

Ex:

- `gprn::myapi::artifact:PROJ1:report.html@3` means the Artifact ID `PROJ1:report.html@3` in `myapi`, production.
- `gprn::myapi::project:PROJ1` means project `PROJ1` within `myapi`, production
- `gprn::myapi::project:PROJ1@3` means project `PROJ1`, version `3`, within `myapi`, production
- `gprn::myapi::doc` means the documentation for `myapi` API.

