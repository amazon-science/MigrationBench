"""File util functions."""

from collections import defaultdict
import datetime
import logging
import os
import tempfile
import time
from typing import Dict, Optional, Tuple
import xml.etree.ElementTree as ET

from packaging.version import Version

from self_debug.common import hash_utils, maven_utils, utils

# pylint: disable=broad-exception-caught,too-many-branches,too-many-locals,too-many-nested-blocks,too-many-return-statements

MVN_CLEAN_COMPILE = maven_utils.MVN_CLEAN_COMPILE
MVN_CLEAN_VERIFY = maven_utils.MVN_CLEAN_VERIFY

MVN_TIMEOUT_SECONDS = 300  # 5 min

CSHARP_ITEM_GROUP = "ItemGroup"
CSHARP_PROPERTY_GROUP = "PropertyGroup"

CSHARP_KEY_TARGET_FRAMEWORK = "TargetFramework"
CSHARP_KEY_GENERATE_ASSEMBLY_INFO = "GenerateAssemblyInfo"
CSHARP_KEY_GENERATE_TARGET_FRAMEWORK_ATTRIBUTE = "GenerateTargetFrameworkAttribute"

CSHARP_KEY_PACKAGE_TARGET_FALLBACK = "PackageTargetFallback"
CSHARP_KEY_RUNTIME_FRAMEWORK_VERSION = "RuntimeFrameworkVersion"

POM = "pom.xml"

MS_ASP_NET_CORE_APP_PACKAGES = (
    "Microsoft.AspNetCore.ApplicationInsights.HostingStartup",
    "Microsoft.AspNetCore.AzureAppServices.HostingStartup",
    "Microsoft.AspNetCore.AzureAppServicesIntegration",
    "Microsoft.AspNetCore.DataProtection.AzureKeyVault",
    "Microsoft.AspNetCore.DataProtection.AzureStorage",
    "Microsoft.AspNetCore.Server.Kestrel.Transport.Libuv",
    "Microsoft.AspNetCore.SignalR.Redis",
    "Microsoft.Data.Sqlite",
    "Microsoft.Data.Sqlite.Core",
    "Microsoft.EntityFrameworkCore.Sqlite",
    "Microsoft.EntityFrameworkCore.Sqlite.Core",
    "Microsoft.Extensions.Caching.Redis",
    "Microsoft.Extensions.Configuration.AzureKeyVault",
    "Microsoft.Extensions.Logging.AzureAppServices",
    "Microsoft.VisualStudio.Web.BrowserLink",
)


# Examples:
#   <ItemGroup>
#     <DotNetCliToolReference Include="Microsoft.EntityFrameworkCore.Tools.DotNet" Version="8.0.2"/>
#     <DotNetCliToolReference Include="Microsoft.Extensions.SecretManager.Tools" Version="2.0.1" />
#     <DotNetCliToolReference Include="Microsoft.VisualStudio.Web.CodeGeneration.Tools" />
#   </ItemGroup>
MS_ASP_NET_CORE_APP_PACKAGES_CLI_TOOL_REFERENCE = {
    "Microsoft.EntityFrameworkCore.Tools.DotNet": "Microsoft.EntityFrameworkCore.Design",
    "Microsoft.Extensions.SecretManager.Tools": "Microsoft.Extensions.Configuration.UserSecrets",
    "Microsoft.VisualStudio.Web.CodeGeneration.Tools": (
        "Microsoft.VisualStudio.Web.CodeGeneration.Design"
    ),
    # "BundlerMinifier.Core": ??? Microsoft.DotNet.Watcher.Tools
    "Microsoft.DotNet.Watcher.Tools": "Microsoft.DotNet.Watcher.Tools",
}


def load_xml(filename: str):
    """Load xml."""
    try:
        return ET.fromstring(utils.load_file(filename).strip())
    except Exception as error:
        logging.exception("Unable to parse filename (%s): <<<%s>>>", filename, error)
        return None


def _get_ns(root) -> str:
    namespace = ""
    # Check if the root element has a namespace
    if "}" in root.tag:
        namespace = root.tag.split("}")[0] + "}"

    return namespace


def _get_from_pom(filename: str, fmt: str, root=None, findall: bool = False):
    if root is None:
        root = load_xml(filename)

    if root is None:
        return None

    namespace = _get_ns(root)
    return (
        root,
        namespace,
        (root.findall if findall else root.find)(fmt.format(namespace=namespace)),
    )


def _get_pom_projects(filename: str, field="project", **kwargs):
    del kwargs

    root = load_xml(filename)
    if root is None:
        return None

    projs = []
    for child in root.iter():
        if child.tag.endswith(f"}}{field}") or child.tag == field:
            projs.append(child)

    return projs


def _get_pom_properties(filename: str, fmt="{namespace}properties", root=None):
    return _get_from_pom(filename, fmt=fmt, root=root)


def get_java_version(filename: str, root_dir: str, result=None):
    """Parse a Maven pom.xml file to find hardcoded Java versions 8, 11, 17, etc."""
    if result is None:
        result = _get_pom_properties(filename)
    if result is None:
        # Invalid pom.xml
        return None

    filename = os.path.abspath(filename)
    root_dir = os.path.abspath(root_dir)
    if root_dir.endswith("/") and root_dir != "/":
        root_dir = root_dir[:-1]

    root, namespace, properties = result

    # Version as strings.
    versions = set()
    version_dict = {}
    if properties is not None:
        for key in (
            "maven.compiler.source",
            "maven.compiler.target",
            "maven.compiler.release",
        ):
            value = properties.find(f"{namespace}{key}")
            if value is not None and value.text is not None:
                version = value.text.strip()
                if version:
                    version_dict[key] = version
                    versions.add(version)

    # Locate configuration in plugins
    all_plugins = (
        root.find(f".//{namespace}build/{namespace}plugins"),
        root.find(
            f".//{namespace}build/{namespace}pluginManagement/{namespace}plugins"
        ),
    )

    for plugins in all_plugins:
        if plugins is None:
            logging.info("./build/.../plugins is None.")
            continue

        for plugin in plugins.findall(f"{namespace}plugin"):
            artifact_id = plugin.find(f"{namespace}artifactId")
            if artifact_id is not None and artifact_id.text == "maven-compiler-plugin":
                logging.debug("  >> maven-compiler-plugin ...")
                config = plugin.find(f"{namespace}configuration")
                if config is not None:
                    for key in ("source", "target", "release"):
                        value = config.find(f"{namespace}{key}")
                        logging.debug("  >> value text `%s` ...", value)
                        if value is None or value.text is None:
                            continue

                        version = value.text.strip()
                        logging.info("  >> version text `%s` ...", version)

                        # It needs to do a look up here for the actual version through name.
                        if (
                            version.startswith("${")
                            or version.startswith("{$")
                            or version.startswith("1.${")
                            or version.startswith("@")
                            or " " in version.strip()
                        ):
                            # To find `properties` definition in the same file or parent module.
                            dirname = os.path.dirname(filename)

                            ref_properties = properties
                            ref_ns = namespace
                            while True:
                                version_prefix = ""
                                if ref_properties is None:
                                    try_value = None
                                else:
                                    var = version
                                    if version.startswith("1.${"):
                                        var = var[2:]
                                        version_prefix = "1."
                                    var = var.strip("${}@")
                                    try_value = ref_properties.find(f"{ref_ns}{var}")

                                if try_value is not None and try_value.text is not None:
                                    version = try_value.text.strip()
                                    version = f"{version_prefix}{version}"
                                    break

                                # Use its direct parent dir as a backup.
                                dirname = os.path.dirname(dirname)
                                # Already at the root dir.
                                if len(dirname) < len(
                                    root_dir
                                ) or not dirname.startswith(root_dir):
                                    break

                                parent_pom = os.path.join(dirname, POM)
                                result = _get_pom_properties(parent_pom)
                                if result is None:
                                    ref_ns, ref_properties = None, None
                                else:
                                    _, ref_ns, ref_properties = result

                        if version:
                            # Different versions with the same key in the SAME file is not allowed.
                            if key in version_dict and version_dict[key] != version:
                                logging.warning(
                                    "Java version {`%s`: `%s`} is already present: <<<%s>>>",
                                    key,
                                    value,
                                    version_dict,
                                )
                            version_dict[key] = version
                            versions.add(version)

    if versions:
        return versions, version_dict

    # Still valid pom.xml
    return None, None


def get_effective_java_version(filename: str, root_dir: str):
    """Parse an efffective Maven pom.xml file to find hardcoded Java versions 8, 11, 17, etc."""
    # Find out `project`
    projects = _get_pom_projects(filename)
    if projects is None:
        logging.debug("There are no projects.")
        return None

    logging.debug("Projects len = %d.", len(projects))

    summary_versions = set()
    summary_version_dict = {}

    count_prop = 0
    for proj in projects:
        # Find out `properties`
        result = _get_pom_properties(filename, root=proj)
        if result is None:
            continue
        prop = (proj, _get_ns(proj), result[-1])
        count_prop += 1

        # Find out version from `project`
        versions = get_java_version(filename, root_dir, prop)
        if versions is None or versions[0] is None:
            continue

        versions, version_dict = versions
        summary_versions |= versions
        summary_version_dict.update(version_dict)

    logging.debug("Properties len = %d.", count_prop)

    if summary_versions:
        return summary_versions, summary_version_dict

    # Still valid pom.xml
    return None, None


def get_java_versions(
    filenames,
    root_dir: str,
    mvn_command: str = MVN_CLEAN_VERIFY,
    run_effective: bool = True,
    return_int_on_failing_effective: bool = False,
):
    """Parse repos' Maven pom.xml file to find hardcoded Java versions 8, 11, 17, etc."""
    summary_versions = set()
    summary_version_dict = {}

    for filename in filenames:
        versions = get_java_version(filename, root_dir=root_dir)
        if versions is None:
            # Invalid pom.xml
            return None

        if versions[0] is None:
            # Still valid pom.xml
            continue

        versions, version_dict = versions
        summary_versions |= versions
        summary_version_dict.update(version_dict)

    if not summary_versions and not summary_version_dict and run_effective:
        with tempfile.TemporaryDirectory() as temp_dir:
            # Generate
            temp_pom = os.path.join(temp_dir, "effective-pom.xml")
            cmd = maven_utils.replace_maven_command(
                mvn_command,
                new_partial_command=maven_utils.MVN_EFFECTIVE_POM_TO_FILE.format(
                    POM=temp_pom
                ),
            )[0].format(root_dir=root_dir)

            # Parse
            for index in range(maven_utils.MVN_EFFECTIVE_POM_MAX_ATTEMPTS):
                result = utils.do_run_command(cmd, check=False)
                if result.return_code == 0:
                    break

                logging.warning(
                    "[%d/%d] Unable to generate effective pom.xml: <<<%s>>>",
                    index,
                    maven_utils.MVN_EFFECTIVE_POM_MAX_ATTEMPTS,
                    result,
                )

                std = str(result)
                early_stop = False
                # pylint: disable=line-too-long
                # [ERROR]     ========================: Type org.eclipse.tycho.core.p2.P2ArtifactRepositoryLayout not present: org/eclipse/tycho/core/p2/P2ArtifactRepositoryLayout has been compiled by a more recent version of the Java Runtime (class file version 55.0), this version of the Java Runtime only recognizes class file versions up to 52.0\n
                for regex in (
                    " Goal requires a project to execute but there is no POM in this directory ",
                    # " http://cwiki.apache.org/confluence/display/MAVEN/InternalErrorException",  # InternalError could be fixed
                    # " The following artifacts could not be resolved: ",
                    ", this version of the Java Runtime only recognizes class file versions up to 52.0",
                    " Unknown packaging: ",
                ):
                    if regex in std:
                        early_stop = True
                        break

                # [ERROR] Child module /tmp/ported/HubSpot__httpQL/httpql/httpql-core of /tmp/ported/HubSpot__httpQL/pom.xml does not exist @ \n
                # [ERROR] 'dependencies.dependency.version' for io.vertx:vertx-docgen:jar is missing. @ line 25, column 17
                # [ERROR] 'dependencies.dependency.version' for net.javacrumbs.shedlock:shedlock-provider-jdbc-template:jar must be a valid version but is '${shedlock.version}'. @ line 186, column 13
                # [ERROR] Malformed POM /tmp/ported/admin-ch__CovidCertificate-Management-Service/pom.xml: expected START_TAG or END_TAG not TEXT (position: TEXT seen ...<version>4.1.2</version>q\n\t<n... @14:4)  @ /tmp/ported/admin-ch__CovidCertificate-Management-Service/pom.xml, line 14, column 4
                # [FATAL] Non-parseable POM /home/hadoop/.m2/repository/org/apache/isis/app/isis-app-starter-parent/2.0.0-M6/isis-app-starter-parent-2.0.0-M6.pom: unexpected markup <!d (position: START_DOCUMENT seen <!d... @1:4)  @ /home/hadoop/.m2/repository/org/apache/isis/app/isis-app-starter-parent/2.0.0-M6/isis-app-starter-parent-2.0.0-M6.pom, line 1, column 4\n @
                ### Throttling?
                ### [FATAL] Non-resolvable parent POM for org.codelibs.fess:fess:14.9.0-SNAPSHOT: The following artifacts could not be resolved: org.codelibs.fess:fess-parent:pom:14.9.0-SNAPSHOT (absent): Could not find artifact org.codelibs.fess:fess-parent:pom:14.9.0-SNAPSHOT and 'parent.relativePath' points at no local POM @ line 30, column 10
                # [ERROR] Non-resolvable import POM: The following artifacts could not be resolved: org.springframework.data:spring-data-releasetrain:pom:Moore-M1 (absent): Could not transfer artifact org.springframework.data:spring-data-releasetrain:pom:Moore-M1 from/to spring-libs-milestone (https://repo.spring.io/libs-milestone): status code: 401, reason phrase:  (401) @ org.springframework.boot:spring-boot-dependencies:2.1.1.RELEASE, /home/hadoop/.m2/repository/org/springframework/boot/spring-boot-dependencies/2.1.1.RELEASE/spring-boot-dependencies-2.1.1.RELEASE.pom, line 2748, column 25\n
                # [FATAL] 'modelVersion' of '4.0.1' is newer than the versions supported by this version of Maven: [4.0.0]. Building this project requires a newer version of Maven. @ line 17, column 19
                # "Unrecognized option: --add-exports\nError: Could not create the Java Virtual Machine.\nError: A fatal exception has occurred. Program will exit.",
                # pylint: enable=line-too-long
                if not early_stop:
                    for regex_list in (
                        (
                            "[ERROR] Child module ",
                            "pom.xml does not exist @",
                        ),
                        (
                            "'dependencies.dependency.version' for ",
                            ":jar is missing. @ line ",
                            ", column ",
                        ),
                        (
                            "'dependencies.dependency.version' for ",
                            ":jar must be a valid version but is '",
                            "'. @ line ",
                            ", column ",
                        ),
                        (
                            "[ERROR] Malformed POM ",
                            "/pom.xml, line ",
                            ", column ",
                        ),
                        (
                            "[FATAL] Non-parseable POM ",
                            ".pom, line ",
                            ", column ",
                        ),
                        # Unauthorized
                        (
                            ": status code: 401, reason phrase: ",
                            "[ERROR] Non-resolvable import POM: The following artifacts could not be resolved: ",
                            ": Could not transfer artifact ",
                            # ": status code: 401, reason phrase: ",
                            ".pom, line ",
                            ", column ",
                        ),
                        (
                            "is newer than the versions supported by this version of Maven: ",
                            "Building this project requires a newer version of Maven. @ line ",
                            ", column ",
                        ),
                        (
                            "Unrecognized option: --add-exports",
                            "Error: Could not create the Java Virtual Machine.",
                            "Error: A fatal exception has occurred. Program will exit.",
                        ),
                    ):
                        match_all = True
                        for regex in regex_list:
                            if regex not in std:
                                match_all = False
                                break

                        if match_all:
                            early_stop = True
                            break

                if early_stop:
                    break

                if index + 1 < maven_utils.MVN_EFFECTIVE_POM_MAX_ATTEMPTS:
                    time.sleep(maven_utils.MVN_EFFECTIVE_POM_SLEEP_SECONDS)

            if result.return_code == 0:
                # Parse directly
                # TODO(sliuxl): Not sure whether need to find out whether it's multi-module.
                result = get_java_version(temp_pom, root_dir)
                if result is not None and result[0] is not None:
                    summary_versions, summary_version_dict = result

                logging.warning(
                    "Parse effective pom.xml directly for `%s`: Java version `%s`. [%s]",
                    root_dir,
                    result,
                    cmd,
                )

                # Parse indirectly
                result = get_effective_java_version(temp_pom, root_dir)
                logging.warning(
                    "Parse effective pom.xml as multi module for `%s`: Java version `%s`. [%s]",
                    root_dir,
                    result,
                    cmd,
                )
                if result is not None and result[0] is not None:
                    versions, version_dict = result
                    summary_versions |= versions
                    summary_version_dict.update(version_dict)
            elif return_int_on_failing_effective:
                return -1

    if not summary_versions and not summary_version_dict:
        return None, None

    return summary_versions, summary_version_dict


def _cmp_versions(version, spec) -> int:
    if version == spec:
        return 0
    if version < spec:
        return -1
    if version > spec:
        return +1

    raise ValueError(f"Should not happen to cmp `{version}` vs `{spec}`.")


def _is_unknown_java_version(version: str) -> bool:
    """Whether a java version is unknown."""
    if (
        "${" in version
        or "{$" in version
        or "@" in version
        or version.endswith(".")
        or " " in version.strip()
        or not version.strip()
    ):
        return True

    try:
        Version(version)
        return False
    except Exception as error:
        logging.exception("Unable to parse version (%s): <<<%s>>>", version, error)

    return True


def _cmp_java_version(version, spec: int = 8) -> Optional[int]:
    """To compare java versions."""
    if _is_unknown_java_version(version):
        return None

    if "." not in version:
        return _cmp_versions(int(version), spec)

    # "." is present and we have to use version comparison.
    return _cmp_versions(Version(version), Version(f"1.{spec}"))


def reject_older_java_version(version, spec_ge: int = 8):
    """Whether to reject java version, as it's older than spec_ge."""
    cmp = _cmp_java_version(version, spec_ge)

    return None if cmp is None else cmp < 0


def reject_older_java_versions(versions, spec_ge: int = 8):
    """Whether to reject java versions, as it's older than spec_ge."""
    for version in versions:
        if reject_older_java_version(version, spec_ge):
            return True

    return False


def reject_newer_java_version(version, spec_ge: int = 8):
    """Whether to reject java version, as it's newer than spec_ge."""
    cmp = _cmp_java_version(version, spec_ge)

    return None if cmp is None else cmp > 0


def reject_newer_java_versions(versions, spec_ge: int = 8):
    """Whether to reject java versions, as it's newer than spec_ge."""
    for version in versions:
        if reject_newer_java_version(version, spec_ge):
            return True

    return False


def reject_conflicting_java_versions(versions):
    """Whether to reject conflicting java versions."""
    # TODO(sliuxl): There are some issues as both versions are str, no int.
    versions = [v for v in versions if not _is_unknown_java_version(v)]

    length = len(versions)
    for lhs in range(length):
        for rhs in range(lhs + 1, length):
            if _cmp_java_version(versions[lhs], versions[rhs]) != 0:
                return True

    return False


def reject_java_repo_or_snapshot(
    root_dir: str,
    version: int = 8,
    compiled_version: int = 52,
    mvn_command: str = MVN_CLEAN_VERIFY,
    timeout_seconds: int = None,
    java_home: str = None,
    max_maven_attempts: int = maven_utils.MVN_DEPENDENCY_RESOLVE_MAX_ATTEMPTS,
) -> Tuple[bool, bool, Dict[str, int]]:
    """Whether to reject java (repo, snapshot, metrics)."""
    metrics = defaultdict(int)

    metrics["reject-snapshot-00-start"] += 1

    root_pom_xml = os.path.join(root_dir, POM)
    # 1. pom.xml: No such files
    poms = []
    if os.path.exists(root_pom_xml):
        poms = utils.find_files(root_dir, POM)
    if not poms:
        metrics["reject-snapshot-01-no-pom-xml"] += 1
        return None, True, metrics

    # 2. pom.xml hard coded Java versions
    versions = get_java_versions(poms, root_dir, mvn_command=mvn_command)
    logging.warning("Java versions `%s`: Repo `%s`.", versions, root_dir)

    if versions is None:
        # Invalid pom.xml
        metrics["reject-snapshot-02-00-invalid-pom-xml"] += 1
        return False, True, metrics

    if versions[0] is not None and version is not None:
        versions = versions[0]
        # - Java version is older than version: REJECT REPO.
        if reject_older_java_versions(versions, version):
            metrics["reject-snapshot-02-00-REPO-java_versions-too-old"] += 1
            return True, True, metrics

        # - Java version is newer than version.
        if reject_newer_java_versions(versions, version):
            metrics["reject-snapshot-02-01-java_versions-too-new"] += 1
            return False, True, metrics

        # - Java versions are conflicting: Should not happen?
        #   * Disabled as both are string values, and it's harder to figure out.
        # if reject_conflicting_java_versions(versions):
        #     metrics["reject-snapshot-02-02-java_versions-conflicting"] += 1
        #     return False, True, metrics

    # 3. mvn clean verify
    if timeout_seconds:
        kwargs = {"timeout": timeout_seconds}
    else:
        kwargs = {}
    result = maven_utils.do_run_maven_command(
        (mvn_command or MVN_CLEAN_VERIFY).format(root_dir=root_dir),
        check=False,
        **kwargs,
        MVN_DEPENDENCY_RESOLVE_MAX_ATTEMPTS=max_maven_attempts,
    )

    if result.return_code != 0:
        logging.warning("Mvn cmd result: <<<%s>>>", result)
        metrics["reject-snapshot-03-mvn-clean-verify-failure"] += 1
        return False, True, metrics

    # 4. Validate compiled class
    if compiled_version:
        base_commit = False
        c_versions = utils.get_compiled_java_major_versions(
            root_dir, java_home=java_home
        )
        logging.warning("Compiled versions: `%s`.", c_versions)

        if c_versions is not None:
            metrics[
                f"reject-snapshot-04-complied-java-version-len__EQ__{len(c_versions):02d}"
            ] += 1

            s_versions = sorted(list(str(v) for v in c_versions))
            metrics[
                f"reject-snapshot-04-complied-java-version-values__EQ__{'|'.join(s_versions)}"
            ] += 1

        if c_versions is None:
            metrics["reject-snapshot-05-00-complied-java-version-none"] += 1
        elif not c_versions:
            # TODO(sliuxl): Not sure whether it's possible.
            metrics["reject-snapshot-05-01-complied-java-version-empty"] += 1
        elif len(c_versions) == 1 and list(c_versions)[0] == compiled_version:
            base_commit = True
            metrics["reject-snapshot-05-02-complied-java-version-exact-match"] += 1
        elif min(c_versions) < compiled_version:
            # - Compiled Java version is older than version: REJECT REPO.
            metrics["reject-snapshot-05-03-REPO-compiled-java_versions-too-old"] += 1
            return True, True, metrics

        elif max(c_versions) > compiled_version:
            # - Compiled Java version is newer than version.
            metrics["reject-snapshot-05-04-compiled-java_versions-too-new"] += 1

        # Unable to get the right compiled versions.
        if not base_commit:
            return False, True, metrics

    # This is the right base commit id: ACCEPT SNAPSHOT.
    metrics["reject-snapshot-10-base-commit-id-found"] += 1
    return False, False, metrics


def _checkout_commit(
    repo_obj, commit_ids, attempt: int, index: int, prefix: str = "base"
) -> None:
    commit_id = commit_ids[index]
    repo_obj.checkout(commit_id)

    # Check out on a clean branch.
    repo_obj.restore()
    repo_obj.clean()
    repo_obj.new_branch(f"{prefix}-try{attempt:03d}-idx{index:04d}--{commit_id}")


def _find_out_base_commit_index(
    repo_obj,
    global_commit_ids,
    version,
    java_home: str = None,
    compiled_version: int = 52,
    mvn_command: str = MVN_CLEAN_COMPILE,
    max_maven_attempts=maven_utils.MVN_DEPENDENCY_RESOLVE_MAX_ATTEMPTS,
    timeout_seconds: int = 30 * 60,
    do_search: bool = True,
) -> Tuple[int, int]:
    """Find out commit_ids based on pom.xml file changes only."""
    start_time = time.time()

    attempt_index = 0
    # pom.xml
    #     CxxxxxxCxxxxCxxxxDxxxx
    #     +      +    +    Version
    #                  ^

    # Cached index for the previous checked commit's next (Older) commit.
    cached_index = 0
    commit_index = 0

    if version is None:
        return attempt_index, cached_index

    root_pom_xml = os.path.join(repo_obj.root_dir, POM)

    total_len = len(global_commit_ids)
    reject_repo = False
    while commit_index < total_len:
        runtime_seconds = time.time() - start_time
        if runtime_seconds > timeout_seconds:
            logging.warning(
                " >>> [%04d] timeout @`%.1f`s.", commit_index, runtime_seconds
            )
            break

        _checkout_commit(
            repo_obj, global_commit_ids, attempt_index, commit_index, "s0-pom"
        )
        attempt_index += 1

        poms = []
        if os.path.exists(root_pom_xml):
            poms = utils.find_files(repo_obj.root_dir, POM)
        if not poms:
            logging.warning(
                " >>> [%04d/04d] No (root) pom.xml available.", commit_index, total_len
            )
            reject_repo = True
            break

        versions = get_java_versions(
            poms,
            repo_obj.root_dir,
            mvn_command=mvn_command,
            return_int_on_failing_effective=True,
        )
        logging.warning(
            " >>> [%04d/%04d] versions = <<<%s>>>", commit_index, total_len, versions
        )

        # Invalid effective pom.xml when it's an `int`.
        valid_versions = not isinstance(versions, int)

        if valid_versions and (versions is None or versions[0] is None):
            # Case 0: Invalid pom or missing versions
            # TODO(sliuxl): Revisit
            break

            if (
                maven_utils.do_run_maven_command(
                    maven_utils.replace_maven_command(
                        mvn_command,
                        new_partial_command=MVN_CLEAN_COMPILE.rsplit(";", maxsplit=1)[
                            -1
                        ].strip(),
                    )[0].format(root_dir=repo_obj.root_dir),
                    check=False,
                    MVN_DEPENDENCY_RESOLVE_MAX_ATTEMPTS=max_maven_attempts,
                    timeout=max(MVN_TIMEOUT_SECONDS, timeout_seconds - runtime_seconds),
                ).return_code
                != 0
            ):
                # Throttling issues or other issues
                cached_index = commit_index
                break

            c_versions = utils.get_compiled_java_major_versions(
                repo_obj.root_dir, java_home=java_home
            )

            missing_versions = c_versions is None or not c_versions
            if (
                (not missing_versions)
                and len(c_versions) == 1
                and list(c_versions)[0] == compiled_version
            ):
                # - Exact version
                cached_index = commit_index
                break

            if (not missing_versions) and min(c_versions) < compiled_version:
                # - Older versions
                reject_repo = True
                break

            if missing_versions or max(c_versions) > compiled_version:
                # - Newer versions
                commit_index += 1
                cached_index = commit_index
                continue

            raise ValueError(f"Unable to process compiled versions: <<<{c_versions}>>>")

        if valid_versions and reject_older_java_versions(versions[0], version):
            # Case 1: Older versions
            reject_repo = True
            break

        if valid_versions and not reject_newer_java_versions(versions[0], version):
            # Case 2: No newer versions
            break

        head_commit_id = global_commit_ids[commit_index]

        # Find out next commit id, based on existing pom.xml files **only**.
        pom_2_commit_ids = hash_utils.get_git_commit_ids(repo_obj, num=2, poms=poms)
        effective_commit_index = commit_index
        if pom_2_commit_ids:
            if pom_2_commit_ids[0] != head_commit_id:
                msg = ""

                used_id = pom_2_commit_ids[0]
                used_index = global_commit_ids.index(used_id)
                if used_index != commit_index:
                    effective_commit_index = used_index
                    msg = f" **{used_index:03d} <== {commit_index:03d}**"

                # Head doesn't change `pom.xml`, so it's effectively using pom commits' head.
                logging.warning(
                    "[%s] Checking Java version effectively with commit `%s` instead.%s",
                    head_commit_id,
                    pom_2_commit_ids[0],
                    msg,
                )

            # Use pom.xml commit different from the head.
            pom_2_commit_ids = pom_2_commit_ids[1:]
        else:
            raise ValueError(
                f"pom.xml is present in commit `{head_commit_id}` without any history."
            )

        if not pom_2_commit_ids:
            # Should reject REPO in this case.
            cached_index = total_len
            break

        next_commit_id = pom_2_commit_ids[0]
        if next_commit_id not in global_commit_ids:
            raise ValueError(
                f"Unable to find next commit id `{next_commit_id}` in global ones: # = %d.",
                next_commit_id,
                len(global_commit_ids),
            )

        # `commit_index` is newer java version, therefore we need to go for the next/ older one.
        cached_index = effective_commit_index + 1

        commit_index = global_commit_ids.index(next_commit_id)

        if not do_search:
            break

    if not do_search:
        cached_index = 0

    return attempt_index, cached_index, reject_repo


def keep_java_repo_with_history(
    root_dir: str,
    repo_obj,
    no_maven: bool = False,
    version: int = 8,
    compiled_version: int = 52,
    max_attempts: int = 100,
    do_search: bool = True,
    **kwargs,
) -> Tuple[bool, str, Dict[str, int]]:
    """Whether to reject java (repo, snapshot, metrics), with its commit history."""
    start_time = time.time()

    metrics = defaultdict(int)

    logging.warning("Processing Java repo with history: `%s` ...", root_dir)

    global_commit_ids = hash_utils.get_git_commit_ids(repo_obj)
    total_len = len(global_commit_ids)

    metrics["00-start"] += 1
    metrics[f"00-start-num-commits__EQ__{total_len:04d}"] += 1

    keep = False
    base_commit = None

    # Explicit Java versions only.
    mvn_command = kwargs.get("mvn_command", MVN_CLEAN_VERIFY)
    max_maven_attempts = kwargs.get(
        "MVN_DEPENDENCY_RESOLVE_MAX_ATTEMPTS",
        maven_utils.MVN_DEPENDENCY_RESOLVE_MAX_ATTEMPTS,
    )
    timeout_seconds = kwargs.get("timeout_minutes", 90) * 60
    attempt_index, commit_index, reject_repo = _find_out_base_commit_index(
        repo_obj,
        global_commit_ids,
        version,
        java_home=kwargs.get("java_home"),
        compiled_version=compiled_version,
        mvn_command=mvn_command,
        max_maven_attempts=max_maven_attempts,
        timeout_seconds=timeout_seconds,
        do_search=do_search,
    )
    metrics[f"00-start-at-commit-index__EQ__{commit_index:04d}"] += 1
    metrics[f"00-start-at-commit-index__EQ__{commit_index:04d}-{total_len:04d}"] += 1

    if reject_repo:
        metrics["09-02-reject-repo-java-version-too-old"] += 1
    if commit_index == total_len:
        metrics["09-00-reject-repo-initial-index-eq-total-len"] += 1

    base_commit_index = commit_index
    if reject_repo:
        keep = False
    elif no_maven:
        if commit_index < total_len:
            keep = True
            base_commit = global_commit_ids[commit_index]
    else:
        logging.warning("Using mvn command: `%s`.", mvn_command)

        for index in range(commit_index, total_len):
            base_commit_index = index

            commit_id = global_commit_ids[index]
            attempt_index += 1

            runtime_seconds = time.time() - start_time
            if runtime_seconds > timeout_seconds:
                timeout = f"timeout-{(int(runtime_seconds) // 60):03d}-minutes"
                metrics["05-00-REJECT-REPO-timeout"] += 1
                metrics[f"05-01-{timeout}"] += 1
                metrics[f"05-02-{timeout}-{index:03d}-{total_len:04d}-commits"] += 1
                break

            if max_attempts is not None and attempt_index >= max_attempts:
                metrics["04-00-REJECT-REPO-skip-gt-{max_attempts:03d}-commits"] += 1
                metrics[
                    "04-01-reject-repo-skip-gt-{max_attempts:03d}-{total_len:04d}-commits"
                ] += 1
                break

            # Check out on a clean branch.
            _checkout_commit(
                repo_obj, global_commit_ids, attempt_index, index, prefix="s1"
            )

            # Run as a base commit candidate.
            reject_repo, reject_commit, c_metrics = reject_java_repo_or_snapshot(
                root_dir,
                version=version,
                compiled_version=compiled_version,
                mvn_command=mvn_command,
                timeout_seconds=max(
                    MVN_TIMEOUT_SECONDS, timeout_seconds - runtime_seconds
                ),
                java_home=kwargs.get("java_home"),
                max_maven_attempts=max_maven_attempts,
            )

            if index == 0:
                metrics.update(c_metrics)

            if reject_repo:
                metrics["01-REJECT-REPO-at-commit"] += 1
                metrics[f"01-reject-repo-at-index-{index:04d}"] += 1
                break

            if reject_commit:
                metrics["02-reject-commit"] += 1
                continue

            keep = True
            base_commit = commit_id

            runtime_mins = int(time.time() - start_time) // 60
            metrics["03-accept-repo-commit"] += 1
            metrics[f"03-accept-repo-commit-at-index-{index:04d}"] += 1
            metrics[f"03-accept-repo-commit-at-minutes-{runtime_mins:04d}"] += 1
            break
        else:
            base_commit_index = total_len
            metrics["09-01-REJECT-REPO-final-index-eq-total-len"] += 1

    logging.warning("Keep repo: `%s` @ `%s`.", keep, datetime.datetime.now())
    metrics[f"10-keep-repo__EQ__{keep}"] += 1
    metrics[f"11-keep-repo-base-commit-id__EQ__{base_commit}"] += 1

    ground_truth = kwargs.get("ground_truth") or ""
    if not isinstance(ground_truth, str):
        ground_truth = "____".join(ground_truth)

    metrics[f"11-keep-repo-url__EQ__{ground_truth}"] += 1
    metrics[f"11-keep-repo-index__EQ__{base_commit_index:04d}"] += 1
    metrics[f"11-keep-repo-total-len__EQ__{total_len:04d}"] += 1

    return (
        keep,
        base_commit,
        {f"BaseCommit::{key}": value for key, value in metrics.items()},
    )


def _add_or_update_field(xml_obj, name: str, value: str, tail: str = "\n    "):
    existing_field = xml_obj.find(name)

    if existing_field is None:
        new_field = ET.SubElement(xml_obj, name)
        new_field.text = value
        new_field.tail = tail
    else:
        if existing_field.text == value:
            return xml_obj, False

        existing_field.text = value

    return xml_obj, True


def dedup_csharp_target_framework_attribute(filename: str, output_filename: str = None):
    """Dedup C# target framework attribute."""
    try:
        tree = ET.parse(filename)
    except Exception as error:
        logging.exception("Unable to parse filename (%s): <<<%s>>>", filename, error)
        return None, None

    root = tree.getroot()
    prop_groups = root.findall(CSHARP_PROPERTY_GROUP)
    if not prop_groups:
        logging.warning("No %s: %s.", CSHARP_PROPERTY_GROUP, filename)
        return None, None

    group = None
    for prop_group in prop_groups:
        if prop_group.findall(CSHARP_KEY_TARGET_FRAMEWORK):
            group = prop_group
            break

    if group is None:
        return None, None

    updated = set()
    for field in (
        CSHARP_KEY_GENERATE_ASSEMBLY_INFO,
        CSHARP_KEY_GENERATE_TARGET_FRAMEWORK_ATTRIBUTE,
    ):
        group, status = _add_or_update_field(group, field, "false", group[-1].tail)
        updated.add(status)

    updated = any(updated)
    if updated and output_filename:
        logging.info("Exporting to: `%s`.", output_filename)
        tree.write(output_filename, encoding="utf-8")  # , xml_declaration=True)

    return tree, updated


def clean_up_csharp_csproj(
    filename: str, output_filename: str = None, remove_item_group_fields=None
):
    """Clean up C# csproj files: Core -> Core."""
    try:
        tree = ET.parse(filename)
    except Exception as error:
        logging.exception("Unable to parse filename (%s): <<<%s>>>", filename, error)
        return None, None

    root = tree.getroot()
    updated = False
    # - ItemGroup
    item_groups = root.findall(CSHARP_ITEM_GROUP)
    if item_groups:
        updated_ast_net_core_app = False
        for item_group in item_groups:
            for field in remove_item_group_fields or ():
                for group in item_group.findall(field):
                    updated = True
                    item_group.remove(group)

            package_ref = item_group.find(
                ".//PackageReference[@Include='Microsoft.AspNetCore.All']"
            )
            if package_ref is not None:
                updated = True
                updated_ast_net_core_app = True
                # Replace `PackageReference with `FrameworkReference`.
                package_ref.tag = "FrameworkReference"
                package_ref.attrib["Include"] = "Microsoft.AspNetCore.App"
                del package_ref.attrib["Version"]
                continue

            for source_cli_tool_name, dest_pkg in sorted(
                MS_ASP_NET_CORE_APP_PACKAGES_CLI_TOOL_REFERENCE.items()
            ):
                cli_tool_ref = item_group.find(
                    f".//DotNetCliToolReference[@Include='{source_cli_tool_name}']"
                )
                if cli_tool_ref is None:
                    continue

                updated = True
                # Replace `DotNetCliToolReference` with `PackageReference`.
                cli_tool_ref.tag = "PackageReference"
                cli_tool_ref.attrib["Include"] = dest_pkg
                del cli_tool_ref.attrib["Version"]
    else:
        logging.info("No %s: %s.", CSHARP_ITEM_GROUP, filename)

    # - PropertyGroup
    prop_groups = root.findall(CSHARP_PROPERTY_GROUP)
    if prop_groups:
        for prop_group in prop_groups:
            for field in (
                CSHARP_KEY_PACKAGE_TARGET_FALLBACK,
                CSHARP_KEY_RUNTIME_FRAMEWORK_VERSION,
                "AssemblyOriginatorKeyFile",
                "PublicSign",
                "SignAssembly",
            ):
                for group in prop_group.findall(field):
                    updated = True
                    prop_group.remove(group)
    else:
        logging.info("No %s: %s.", CSHARP_PROPERTY_GROUP, filename)

    if updated and output_filename:
        logging.info("Exporting to: `%s`.", output_filename)
        tree.write(output_filename, encoding="utf-8")  # , xml_declaration=True)

        if updated_ast_net_core_app:
            # Seems unable to add packages in batches.
            for pkg in MS_ASP_NET_CORE_APP_PACKAGES:
                cmd = f"dotnet add package {pkg}"
                utils.run_command(cmd, cwd=os.path.dirname(output_filename))

    return tree, updated
