"""Util functions for s3 datasets.

# Sample command:

```
rm -rf /tmp/ported/
#                 $WORK_DIR                   $DRY_RUN
python s3_data.py /tmp/ported/{bucket}--{key} 0
```
"""

import logging
import os
import re
import sys
import tempfile
from typing import Any, Optional, Tuple, Union

from self_debug.proto import config_pb2

import boto3
from self_debug.common import github, git_repo, utils


RANDOM_LEN = 6

S3_PREFIX = "s3://"
# pylint: disable=line-too-long
S3_REPO = "s3://qnet-framework-to-core-ported-projects/007008aabb_WeiXinMPSDKsrcSenparc.Weixin.OpenSenparc.Weixin.OpenSenparc.Weixin.Open.vs2017/"
S3_REPO = "s3://self-dbg-plus/datasets/csharp--framework-to-core--v0-20240516/6bee_Remote.Linqsamples02_RemoteQueryable_AsyncCommonCommon/"
# pylint: enable=line-too-long
S3_UPLOAD_DIR = "s3://self-dbg-plus--logs/test/{root_dir}"


JSON_KEY_CSPROJ = "csproj_path"
JSON_KEY_PORTED = "porting_result"


def _resolve_s3_dir(s3_dir: str, sep=os.path.sep) -> Tuple[str, str]:
    """Resolve s3 dir."""
    if not s3_dir.endswith(sep):
        s3_dir += sep

    segments = s3_dir[:-1].replace(S3_PREFIX, "").split(sep)

    bucket_name = segments[0]
    s3_prefix = sep.join(segments[1:]) + sep

    return bucket_name, s3_prefix


# https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html
def upload_to_s3(
    work_dir: str, s3_dir: str, random_len: int = 0, dry_run: bool = False, **kwargs
) -> str:
    """Upload to s3 dir."""
    if work_dir.endswith("/"):
        work_dir = work_dir[:-1]

    if not os.path.exists(work_dir):
        logging.warning("Dir doesn't exist: `%s`.", work_dir)
        return None

    s3_dir = s3_dir.format(
        root_dir=os.path.basename(work_dir),
        root_dir_parent=os.path.basename(os.path.dirname(work_dir)),
        random=github.get_random_string(random_len) if random_len else "",
        **kwargs,
    )

    bucket_name, s3_prefix = _resolve_s3_dir(s3_dir)
    s3_client = boto3.client("s3")

    count = 0
    for root, _, files in os.walk(work_dir):
        for filename in files:
            count += 1
            local_path = os.path.join(root, filename)
            rel_path = os.path.relpath(local_path, work_dir)

            s3_key = os.path.join(s3_prefix, rel_path)
            s3_full = f"s3://{bucket_name}/{s3_key}"
            try:
                if not dry_run:
                    s3_client.upload_file(local_path, bucket_name, s3_key)
                    logging.info("Uploaded `%s` to: `%s`", rel_path, s3_full)
            except Exception as error:
                logging.exception("Unable to upload to s3: `%s`.", error)

    logging.warning("Uploaded to `%s`: # = %d for `%s`.", s3_dir, count, work_dir)
    return s3_dir


def zip_and_upload_to_s3(
    work_dir: str, s3_full_filename: str, dry_run: bool = False
) -> str:
    del dry_run

    zip_basename = os.path.basename(s3_full_filename)
    if not zip_basename.endswith(".zip"):
        raise ValueError(f"Not a zip file: `{s3_full_filename}`.")

    with tempfile.TemporaryDirectory() as temp_dir:
        # Zip to a local file.
        zip_from = work_dir
        if zip_from.endswith(os.path.sep):
            zip_from = zip_from[:-1]

        local_zip = os.path.join(temp_dir, zip_basename)

        logging.warning("Zip and upload to s3: `%s` ...", work_dir)

        # - Run zip in its parent dir.
        utils.run_command(
            [
                "zip",
                local_zip,
                "-r",
                os.path.basename(zip_from),
            ],
            cwd=os.path.dirname(zip_from),
            shell=False,
        )

        # Upload to s3.
        upload_to_s3(temp_dir, os.path.dirname(s3_full_filename))

        logging.warning(
            "ZIP: [raw]   `%s` ==>\n[local] `%s` ==>\n[s3]   `%s`.",
            zip_from,
            local_zip,
            s3_full_filename,
        )


# https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html
def download_s3_dir(
    s3_dir: str, work_dir: str, random_len: int = 0, dry_run: bool = False
):
    """Download s3 dir."""
    single_file = s3_dir.endswith(".zip")

    bucket_name, s3_prefix = _resolve_s3_dir(s3_dir)
    if single_file:
        s3_prefix = s3_prefix[:-1]
        dirs = s3_prefix.split(os.path.sep)
    else:
        dirs = s3_prefix[:-1].split(os.path.sep)

    repo = os.path.basename(s3_prefix[:-1])
    # If last dir is `date` only: Include the previous dir, as `date` is subdir.
    if re.match(r"^[\d\-_]+$", dirs[-1]):
        key = "--".join(dirs[-3:])
    elif single_file:
        repo = os.path.basename(s3_prefix)
        key = "--".join(dirs[-2:])
    else:
        key = dirs[-1]
    logging.warning(f"({repo}, {single_file}, {key}, {work_dir}): `{dirs}`.")
    work_dir = work_dir.format(
        repo=repo,
        bucket=bucket_name,
        nested_key="--".join(dirs),
        key=key,
        random=github.get_random_string(random_len) if random_len else "",
    )

    if dry_run:
        return work_dir

    if os.path.exists(work_dir):
        logging.warning("Dir exists for s3: `%s`.", work_dir)
        return None

    s3_resource = boto3.resource("s3")
    bucket = s3_resource.Bucket(bucket_name)

    if single_file:
        s3_key = s3_prefix
        # work_dir, os.path.join(dirs[-2] if len(dirs) >= 2 else "" , os.path.basename(s3_key))
        filename = os.path.join(work_dir, os.path.basename(s3_key))
        filepath = os.path.dirname(filename)
        if not os.path.exists(filepath):
            os.makedirs(filepath)

        bucket.download_file(s3_key, filename)
        return work_dir

    for obj in bucket.objects.filter(Prefix=s3_prefix):
        s3_key = obj.key
        filename = os.path.join(work_dir, s3_key.replace(s3_prefix, ""))

        filepath = os.path.dirname(filename)
        if not os.path.exists(filepath):
            os.makedirs(filepath)

        bucket.download_file(s3_key, filename)

    return work_dir


def copy_repo(
    s3_dir: str,
    work_dir: Optional[str] = None,
    dry_run: bool = False,
    random_len: int = 0,
) -> Optional[str]:
    """Clone repo at given commit id."""
    if not work_dir:
        work_dir = os.path.join(os.path.abspath("./"), os.path.basename(s3_dir[:-1]))

    logging.info("Copy s3 repo `%s`: `%s` ...", s3_dir, work_dir)

    try:
        local_dir = download_s3_dir(
            s3_dir, work_dir, random_len=random_len, dry_run=dry_run
        )
        logging.info("Copied s3 repo `%s`: `%s`.", s3_dir, local_dir)
    except Exception as error:
        logging.exception("Unable to copy repo `%s`: `%s`.", s3_dir, error)
        local_dir = None

    return local_dir


def unzip(local_dir, s3_dir: str) -> Optional[str]:
    """Unzip given a local dir, and returns the actual `zip_dir`."""
    files = utils.find_files(local_dir, "\*.zip")
    files = [f for f in files if os.path.isfile(f)]
    if len(files) != 1:
        logging.warning("#Zip files = `%d`: `%s` (%s).", len(files), s3_dir, files)
        return None

    zip_file = files[0]
    zip_dir = zip_file[:-4]  # Drop `.zip`
    for _ in range(3):
        if os.path.exists(zip_dir):
            random = github.get_random_string(RANDOM_LEN)
            zip_dir += f"--r-{random}"
        else:
            break

    if os.path.exists(zip_dir):
        logging.warning("Zipped dir exists: `%s`.", zip_dir)
        return None

    utils.run_command(["unzip", zip_file, "-d", zip_dir], shell=False)

    return zip_dir


def _maybe_copy_repo_f2c_v1_20240614(
    s3_dir: Union[str, Any],
    local_dir: str,
    **kwargs,
) -> Union[str, Tuple[str, Tuple[str]]]:
    # pylint: disable=line-too-long
    """Copy repo as is.

    sliuxl@ 17:46 /tmp/ported/self-dbg-plus--2024-06-14-16-14 $ ls *.json
    results.json  run_metrics.json  summary.json

    ***
    sliuxl@ 17:46 /tmp/ported/self-dbg-plus--2024-06-14-16-14 $ cat run_metrics.json
    {
        "isBuildAndValidationSucceeded": true,
        "isPortingSucceeded": true,
        "isLlmDebuggingSucceeded": true,
        "dotnet_build_error_count": "0"
    }

    sliuxl@ 17:46 /tmp/ported/self-dbg-plus--2024-06-14-16-14 $ cat summary.json
    {
        "createdAt":"2024-06-14T16:14:09Z",
        "overview":{
            "transformationResult":"SUCCEEDED",
            "projectsReceived":1,
            "projectsTransformed":1,
            "projectsCompletelyTransformed":1,
            "projectsPartiallyTransformed":0,
            "projectsNotTransformed":0,
            "nugetPackagesAdded":0,
            "nugetPackagesRemoved":0,
            "nugetPackagesUpdated":0,
            "apisAdded":2,
            "apisRemoved":2,
            "apisUpdated":18,
            "filesAdded":0,
            "filesRemoved":2,
            "filesUpdated":1,
            "linuxRecommendationsCount":0
        },
        "projects":[
            {
                "name":"BSTTiming",
                "transformationResult":"SUCCEEDED",
                "nugetPackagesAdded":0,
                "nugetPackagesRemoved":0,
                "nugetPackagesUpdated":0,
                "apisAdded":2,
                "apisRemoved":2,
                "apisUpdated":18,
                "filesAdded":[],
                "filesRemoved":["sourceCode/BSTTiming/App.config",
                "sourceCode/BSTTiming/.vscode/launch.json"],
                "filesUpdated":["sourceCode/BSTTiming/BSTTiming.csproj"],
                "linuxRecommendationsCount":0,
            }
        ]
    }

    ***
    sliuxl@ 18:04 /tmp/ported/self-dbg-plus--2024-06-14-16-14 $ cat MidTransformCode/post-porting-requirement.json
    {
        "EntryPath":"sourceCode/BSTTiming/BSTTiming.csproj",
        "Projects":[
            {
                "ProjectFilePath":"sourceCode/BSTTiming/BSTTiming.csproj",
                "CodeFiles":[
                    {"ContentMd5Hash":"2437e7f706ed2c158ddec6610041d071",
                    "RelativePath":"sourceCode/BSTTiming/Program.cs"},
                    {"ContentMd5Hash":"53bc39ad0865a244bb7c08259bb71699",
                    "RelativePath":"sourceCode/BSTTiming/obj/Debug/.NETFramework,
                    Version=v4.5.AssemblyAttributes.cs"},
                    {"ContentMd5Hash":"14a7e188fb7e896bbaf79b596532be98",
                    "RelativePath":"sourceCode/BSTTiming.sln"},
                    {"ContentMd5Hash":"3f9b7c50015ca8be5ec84127bb37e2cb",
                    "RelativePath":"sourceCode/BSTTiming/App.config"},
                    {"ContentMd5Hash":"cc81f4ba0aa5873f817ca800373a2f8f",
                    "RelativePath":"sourceCode/BSTTiming/BSTTiming.csproj"},
                    {"ContentMd5Hash":"848c0c1d3051906f50bef8c134bd4ba7",
                    "RelativePath":"sourceCode/BSTTiming/.vscode/launch.json"}
                ],
                "References":[{"IncludedInArtifact":true,
                "RelativePath":"references/Reference Assemblies/Microsoft/Framework/.NETFramework/v4.5/Microsoft.CSharp.dll"},
                {"IncludedInArtifact":true,
                "RelativePath":"references/Reference Assemblies/Microsoft/Framework/.NETFramework/v4.5/mscorlib.dll"},
                {"IncludedInArtifact":true,
                "RelativePath":"references/Reference Assemblies/Microsoft/Framework/.NETFramework/v4.5/System.Core.dll"},
                {"IncludedInArtifact":true,
                "RelativePath":"references/Reference Assemblies/Microsoft/Framework/.NETFramework/v4.5/System.Data.DataSetExtensions.dll"},
                {"IncludedInArtifact":true,
                "RelativePath":"references/Reference Assemblies/Microsoft/Framework/.NETFramework/v4.5/System.Data.dll"},
                {"IncludedInArtifact":true,
                "RelativePath":"references/Reference Assemblies/Microsoft/Framework/.NETFramework/v4.5/System.dll"},
                {"IncludedInArtifact":true,
                "RelativePath":"references/Reference Assemblies/Microsoft/Framework/.NETFramework/v4.5/System.Xml.dll"},
                {"IncludedInArtifact":true,
                "RelativePath":"references/Reference Assemblies/Microsoft/Framework/.NETFramework/v4.5/System.Xml.Linq.dll"}]
            }
        ],
        "ArtifactPath":"/Volumes/workplace/qnet_output/MidTransformCode"
    }
    """
    # pylint: enable=line-too-long

    if not (isinstance(s3_dir, str) and s3_dir.startswith(S3_PREFIX)):
        return s3_dir

    if local_dir.endswith(".zip"):
        return _maybe_copy_repo_f2c_v2d1_20240619(s3_dir, local_dir=local_dir, **kwargs)

    # 1. Download
    if not local_dir or not os.path.exists(local_dir):
        work_dir = kwargs.pop("work_dir", "/tmp/ported/{bucket}--{key}")
        local_dir = copy_repo(s3_dir, work_dir, **kwargs)
    if not local_dir:
        return local_dir

    # 2. Run metrics's json data
    run_metrics_json_file = os.path.join(local_dir, "run_metrics.json")
    if not os.path.exists(run_metrics_json_file):
        logging.warning(
            "json file doesn't exist (%s): `%s`.", run_metrics_json_file, s3_dir
        )
        return None

    ported = utils.load_json(run_metrics_json_file).get("isPortingSucceeded", False)

    # 2. Unzip
    zip_dir = unzip(local_dir, s3_dir)
    if not zip_dir:
        return zip_dir

    requirement_json_file = os.path.join(zip_dir, "post-porting-requirement.json")
    project = utils.load_json(requirement_json_file).get("EntryPath")
    if project is None:
        return None
    project = os.path.join("{root_dir}", project)

    # 3. Git
    repo = git_repo.GitRepo(zip_dir)
    repo.initialize()
    utils.export_file(
        os.path.join(zip_dir, ".gitignore"),
        """
bin/
obj/
.DS_Store
.vs/

# NuGet
NuGet.Config

# HappyDotNet
.dotnet/
.local/
.nuget/
build/
build
        """,
    )
    commit_message = "PORTING: Initial commit"
    for file in ("run_metrics.json", "summary.json"):
        filename = os.path.join(local_dir, file)
        if os.path.exists(filename):
            content = utils.load_file(filename)
        else:
            content = f"// FILE {file} does NOT exist ..."
        commit_message += "\n".join(["", "", f"./{file}:", content])
    repo.commit_all(commit_message + "\n\n")
    repo.new_branch("ported")

    # (zip_dir, project, ported)
    return zip_dir, utils.parse_proto(
        f"""
            dataset {{
              dataset_repo {{
                root_dir: "{zip_dir}"
                project: "{project}"
                ported: {ported}

                s3_repo {{
                  s3_dir: "{s3_dir}"
                }}
              }}
            }}
        """,
        config_pb2.Config,
    )


def _maybe_copy_repo_f2c_v2d1_20240619(
    s3_dir: Union[str, Any],
    local_dir: str,
    **kwargs,
) -> Union[str, Tuple[str, Tuple[str]]]:
    # pylint: disable=line-too-long
    """Copy repo as is.

    sliuxl@ 17:46 /tmp/ported/self-dbg-plus--2024-06-14-16-14 $ ll /tmp/qnet-f2c-v2.1/
    total 12K
    drwxr-xr-x 3 sliuxl amazon 4.0K Jul  1 19:54 references
    -rw-r--r-- 1 sliuxl amazon 2.1K Jun 14 07:19 requirement.json
    drwxr-xr-x 3 sliuxl amazon 4.0K Jul  1 19:54 sourceCode

    ***
    requirement.json

    {
        "EntryPath":"sourceCode\\BSTTiming\\BSTTiming.csproj",
        "Projects":[
            {"projectFilePath":"sourceCode\\BSTTiming\\BSTTiming.csproj",
            "codeFiles":[{"contentMd5Hash":"2437e7f706ed2c158ddec6610041d071",
            "relativePath":"sourceCode\\BSTTiming\\Program.cs"},
            {"contentMd5Hash":"a9a732fa043955ea93b58faf0567c196",
            "relativePath":"sourceCode\\BSTTiming\\Properties\\AssemblyInfo.cs"},
            {"contentMd5Hash":"53bc39ad0865a244bb7c08259bb71699",
            "relativePath":"sourceCode\\BSTTiming\\obj\\Debug\\.NETFramework,
            Version=v4.5.AssemblyAttributes.cs"},
            {"contentMd5Hash":"14a7e188fb7e896bbaf79b596532be98",
            "relativePath":"sourceCode\\BSTTiming.sln"},
            {"contentMd5Hash":"3f9b7c50015ca8be5ec84127bb37e2cb",
            "relativePath":"sourceCode\\BSTTiming\\App.config"},
            {"contentMd5Hash":"cc81f4ba0aa5873f817ca800373a2f8f",
            "relativePath":"sourceCode\\BSTTiming\\BSTTiming.csproj"},
            {"contentMd5Hash":"848c0c1d3051906f50bef8c134bd4ba7",
            "relativePath":"sourceCode\\BSTTiming\\.vscode\\launch.json"}],
            "references":[{"includedInArtifact":true,
            "relativePath":"references\\Reference Assemblies\\Microsoft\\Framework\\.NETFramework\\v4.5\\Microsoft.CSharp.dll"},
            {"includedInArtifact":true,
            "relativePath":"references\\Reference Assemblies\\Microsoft\\Framework\\.NETFramework\\v4.5\\mscorlib.dll"},
            {"includedInArtifact":true,
            "relativePath":"references\\Reference Assemblies\\Microsoft\\Framework\\.NETFramework\\v4.5\\System.Core.dll"},
            {"includedInArtifact":true,
            "relativePath":"references\\Reference Assemblies\\Microsoft\\Framework\\.NETFramework\\v4.5\\System.Data.DataSetExtensions.dll"},
            {"includedInArtifact":true,
            "relativePath":"references\\Reference Assemblies\\Microsoft\\Framework\\.NETFramework\\v4.5\\System.Data.dll"},
            {"includedInArtifact":true,
            "relativePath":"references\\Reference Assemblies\\Microsoft\\Framework\\.NETFramework\\v4.5\\System.dll"},
            {"includedInArtifact":true,
            "relativePath":"references\\Reference Assemblies\\Microsoft\\Framework\\.NETFramework\\v4.5\\System.Xml.dll"},
            {"includedInArtifact":true,
            "relativePath":"references\\Reference Assemblies\\Microsoft\\Framework\\.NETFramework\\v4.5\\System.Xml.Linq.dll"}]}
        ],
        "ArtifactPath":null
    }
    """
    # pylint: enable=line-too-long

    if not (isinstance(s3_dir, str) and s3_dir.startswith(S3_PREFIX)):
        return s3_dir

    # 1. Download
    if not local_dir or not os.path.exists(local_dir):
        work_dir = kwargs.pop("work_dir", "/tmp/ported/{bucket}--{key}")
        local_dir = copy_repo(s3_dir, work_dir, **kwargs)
    if not local_dir:
        return local_dir

    # 2. Unzip
    zip_dir = unzip(local_dir, s3_dir)
    if not zip_dir:
        return zip_dir

    requirement_json_file = os.path.join(zip_dir, "requirement.json")
    project = utils.load_json(requirement_json_file).get("EntryPath")
    if project is None:
        return None
    project = project.replace("\\", os.path.sep)
    project = os.path.join("{root_dir}", project)

    # 3. Git
    repo = git_repo.GitRepo(zip_dir)
    repo.initialize()
    utils.export_file(
        os.path.join(zip_dir, ".gitignore"),
        """
bin/
obj/
.DS_Store
.vs/

# NuGet
NuGet.Config

# HappyDotNet
.dotnet/
.local/
.nuget/
build/
build
        """,
    )
    commit_message = "PORTING (TODO): Initial commit"
    for file in ("requirement.json",):
        filename = os.path.join(local_dir, file)
        if os.path.exists(filename):
            content = utils.load_file(filename)
        else:
            content = f"// FILE {file} does NOT exist ..."
        commit_message += "\n".join(["", "", f"./{file}:", content])
    repo.commit_all(commit_message + "\n\n")
    repo.new_branch("ported")

    # (zip_dir, project, ported)
    return zip_dir, utils.parse_proto(
        f"""
            dataset {{
              dataset_repo {{
                root_dir: "{zip_dir}"
                project: "{project}"
                ported: true

                s3_repo {{
                  s3_dir: "{s3_dir}"
                }}
              }}
            }}
        """,
        config_pb2.Config,
    )


def maybe_copy_repo(
    s3_dir: Union[str, Any], **kwargs
) -> Union[str, Tuple[str, Tuple[str]]]:
    """Copy repo as is.

    csproj_path	repos/007008aabb_WeiXinMPSDK/.../Senparc.Weixin.Open.vs2017.csproj
    commit_hash	c082aec53
    github_url	https://github.com/007008aabb/WeiXinMPSDK
    porting_result	false
    error	null
    """
    if not (isinstance(s3_dir, str) and s3_dir.startswith(S3_PREFIX)):
        return s3_dir

    # 1. Download
    work_dir = kwargs.pop("work_dir", "/tmp/ported/{bucket}--{key}")
    local_dir = copy_repo(s3_dir, work_dir, **kwargs)
    if not local_dir:
        return local_dir

    # 2. Unzip
    json_files = utils.find_files(local_dir, "*.json")
    if len(json_files) != 1:
        return _maybe_copy_repo_f2c_v1_20240614(s3_dir, local_dir=local_dir, **kwargs)

    zip_dir = unzip(local_dir, s3_dir)
    if not zip_dir:
        return zip_dir

    # (zip_dir, json files): ==> (work_dir, project, ported)
    json_data = utils.load_json(json_files[0])

    read_project = json_data.get(JSON_KEY_CSPROJ, "")
    read_files = utils.find_files(zip_dir, f"*{os.path.basename(read_project)}")
    if len(read_files) <= 1:
        files = read_files
    else:
        project, files = read_project, None
        while project and not files:
            files = [f for f in read_files if f.endswith(project)]
            logging.info("Project `%s`: len = %d.", project, len(files))
            if len(files) >= 1:
                if len(files) > 1:
                    # fs7744_Norns.UrdsrcNorns.UrdNorns.Urd $ find . -name Norns.Urd.csproj
                    # ./MidTransformCode/src/Norns.Urd/Norns.Urd.csproj         (***)
                    # ./MidTransformCode/old/src/Norns.Urd/Norns.Urd.csproj
                    #
                    # fs7744_Norns.UrdsrcNorns.UrdNorns.Urd $ cat *.json
                    # {csproj_path: repos/fs7744_Norns.Urd/src/Norns.Urd/Norns.Urd.csproj, ...
                    shortest_project = os.path.join(zip_dir, project)
                    if shortest_project in files:
                        logging.warning(
                            "Multiple csproj files (#=%d matching `%s` in json file => `%s`), "
                            "but keeping one of them `%s` (%s).",
                            len(files),
                            read_project,
                            project,
                            shortest_project,
                            files,
                        )
                        files = [shortest_project]
                    else:
                        logging.warning(
                            "Multiple csproj files (%s, %s): len = %d, `%s`",
                            read_project,
                            project,
                            len(files),
                            files,
                        )
                break

            # Remove one sub dir name in the prefix: e.g. a/b/c/d.csproj ==> b/c/d.csproj.
            project = os.path.sep.join(project.split(os.path.sep)[1:])

    if files:
        files = [os.path.abspath(f).replace(zip_dir, "{root_dir}") for f in files]
    else:
        logging.warning("NO csproj files: `%s`.", read_project)
    project = ",".join(files)

    ported = json_data.get(JSON_KEY_PORTED, False)
    return zip_dir, utils.parse_proto(
        f"""
            dataset {{
              dataset_repo {{
                root_dir: "{zip_dir}"
                project: "{project}"
                ported: {ported}

                s3_repo {{
                  s3_dir: "{s3_dir}"
                }}
              }}
            }}
        """,
        config_pb2.Config,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format=utils.LOGGING_FORMAT)
    result = maybe_copy_repo(
        s3_dir=S3_REPO,
        work_dir="/tmp/ported/{bucket}--{key}" if len(sys.argv) < 2 else sys.argv[1],
    )
    logging.info("Repo is at: `%s`.", result)

    if isinstance(result, tuple):
        dirname = os.path.dirname(result[0])
        logging.info(
            "[LOG] Upload to s3: `%s`.",
            upload_to_s3(
                dirname,
                S3_UPLOAD_DIR,
                random_len=8,
                dry_run=1 if len(sys.argv) < 3 else int(sys.argv[2]),
            ),
        )

        short_name = os.path.basename(dirname)
        logging.info(
            "[LOG] Upload to s3: `%s`.",
            zip_and_upload_to_s3(
                dirname,
                S3_UPLOAD_DIR.format(root_dir=short_name)
                + f"--zipped/{short_name}.zip",
                dry_run=1 if len(sys.argv) < 3 else int(sys.argv[2]),
            ),
        )
