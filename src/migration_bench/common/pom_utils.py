import logging
from xml.etree import ElementTree

LOG = logging.getLogger(__file__)
LOG.setLevel(logging.INFO)
namespaces = {"xmlns": "http://maven.apache.org/POM/4.0.0"}
from typing import Dict
import re
from typing import Optional

from packaging import version


def get_property(root, properties, ref):
    """
    Obtain the actual version number refered by ${var}
    by searching the properties sections of the POM

    Parameters
    ----------
    root :
        root of the POM XML tree
    properties : dict
        the entire properties section of the POM
        ontained by calling pom_read.extract_pom_property
    ref :
        the property name to be searched
    Returns
    -------
    TYPE str
        actual version number referred by ref

    """
    # this is for ${ case the following line
    # removes ${ }
    name = ref[2:-1]
    if name in properties:
        property_version = properties[name]
        if property_version is not None:
            value = property_version
            if value.startswith("${"):
                # recursive call (rarely happens)
                return get_property(root, properties, value)
            else:
                return property_version
    return None


def should_upgrade(old_version: Optional[str], new_version: str):
    """
    Compare old and new version

    Parameters
    ----------
    old_version : str
        version number e.g, 2.0.1
    new_version : str
        version number

    Returns
    -------
    TYPE Boolean
        True: if old_version<new_version
        False: if old_version>=new_version

    """
    if not old_version:
        return False
    # remove letters from old_version
    old_version = re.sub("[a-zA-Z\\-]", "", old_version)
    if old_version[-1] == ".":
        old_version = old_version[:-1]
    # remove letters from new_version
    new_version = re.sub("[a-zA-Z\\-]", "", new_version)
    # special handlig for cases e.g., 4.3.16.RELEASE
    # remove the last . after re remove RELEASE
    if new_version[-1] == ".":
        new_version = new_version[:-1]
    # using the packaging version utiles to perform actual comparison
    try:
        return version.parse(old_version) < version.parse(new_version)
    except:
        return False


def update_pom_parent(root, new_groupid, new_artifactid, new_version):
    """
    Update parent block

    Parameters
    ----------
    root:
        root of the POM XML tree
    new_groupid : str
        groupid of the dependency block
    new_artifactid: str
        aritifactid of the dependency block
    new_veresion: str
        version of the dependency block

    """
    deps = root.findall(".//xmlns:parent", namespaces=namespaces)
    # no insertion only update
    if deps:
        groupid = None
        artifactid = None
        current_version = None
        for e in list(deps[0]):
            tag = e.tag.replace("{http://maven.apache.org/POM/4.0.0}", "")
            if tag == "groupId":
                groupid = e.text
            elif tag == "artifactId":
                artifactid = e.text
            elif tag == "version":
                current_version = e.text
                break
        if groupid == new_groupid and artifactid == new_artifactid:
            # find a matching item
            if current_version:
                if should_upgrade(current_version, new_version):
                    # if the version field exist
                    e.text = new_version
            else:
                # if the version field does not exist
                request = ElementTree.XML("<version>" + new_version + "</version>")
                e.append(request)
            LOG.info("****** Found a match parent for updating!!! ******")
            LOG.info(f"Updating {new_groupid, new_artifactid, new_version}")


def update_jdk_property(root, property_name, property_version, forced):
    """
    Update or add JDK-related properties to the POM file.
    """
    # Find the <properties> block in the POM
    properties_block = root.find(".//xmlns:properties", namespaces=namespaces)

    # If <properties> block doesn't exist, create it if forced
    if properties_block is None:
        if forced:
            # Create a new <properties> element with the correct namespace
            properties_block = ElementTree.Element(
                "{http://maven.apache.org/POM/4.0.0}properties"
            )
            root.append(properties_block)
            LOG.info("****** No <properties> block found. Creating a new one. ******")

    # If <properties> block exists or was created, update or add the property
    if properties_block is not None:
        found_property = False
        for e in list(properties_block):
            tag = e.tag.replace("{http://maven.apache.org/POM/4.0.0}", "")
            if tag == property_name:
                found_property = True
                e.text = property_version
                LOG.info(
                    f"****** Found existing property: {property_name}. Updating its value to {property_version}. ******"
                )
                break

        if not found_property:
            if forced:
                new_property = ElementTree.Element(
                    f"{{http://maven.apache.org/POM/4.0.0}}{property_name}"
                )
                new_property.text = property_version
                properties_block.append(new_property)
                LOG.info(
                    f"****** Property not found. Adding new property: {property_name} with value {property_version}. ******"
                )


def update_jdk_plugin_configuration(root, groupid, artifactid):
    """
    Update JDK plugin configuration block

    Parameters
    ----------
    root:
        root of the POM XML tree
    new_groupid : str
        groupid of the dependency block, e.g., org.apache.maven.plugins
    new_artifactid: str
        aritifactid of the dependency block, e.g., maven-compiler-plugin
    """
    # hard code config block for jdk, later will be moved to central file maintain all constants
    config_block = "<configuration>\n <source>17</source> <target>17</target>  <release>17</release>\n</configuration>\n"

    deps = root.findall(".//xmlns:plugins", namespaces=namespaces)
    if not deps:
        tmp = root.findall(".//xmlns:build", namespaces=namespaces)
        if not tmp:
            request = ElementTree.XML(
                "\n<build>\n<plugins>\n<plugin>\n<groupId>"
                + groupid
                + "</groupId>\n<artifactId>"
                + artifactid
                + "</artifactId>\n"
                + config_block
                + "\n</plugin>\n</plugins>\n</build>\n"
            )
            root.append(request)
        else:
            request = ElementTree.XML(
                "\n<plugins>\n<plugin>\n<groupId>"
                + groupid
                + "</groupId>\n<artifactId>"
                + artifactid
                + "</artifactId>\n"
                + config_block
                + "\n</plugin>\n</plugins>\n"
            )
            LOG.info("****** No match JDK plugin configuration found!!! ******")
            LOG.info(f"Adding (with mega block): {groupid, artifactid}")
            tmp[0].append(request)
    else:
        flag = False
        deps = root.findall(".//xmlns:plugin", namespaces=namespaces)
        for d in deps:
            artifactid_text = None
            configuration = None
            for e in list(d):
                tag = e.tag.replace("{http://maven.apache.org/POM/4.0.0}", "")
                if tag == "artifactId":
                    artifactid_text = e.text
                elif tag == "configuration":
                    configuration = e
            # Some POM file for maven compiler plugin misses groupId
            # therefore only artifactid is compared
            if artifactid_text == artifactid:
                # adding the config block
                flag = True
                if not configuration:
                    request = ElementTree.XML(config_block)
                    d.append(request)
                else:
                    source = None
                    target = None
                    release = None
                    for t in list(configuration):
                        tag = t.tag.replace("{http://maven.apache.org/POM/4.0.0}", "")
                        if tag == "source":
                            source = t.text
                            t.text = "17"
                        if tag == "target":
                            target = t.text
                            t.text = "17"
                        if tag == "release":
                            release = t.text
                            t.text = "17"
                    if not source:
                        configuration.append(ElementTree.XML("<source>17</source>"))
                    if not target:
                        configuration.append(ElementTree.XML("<target>17</target>"))
                    if not release:
                        configuration.append(ElementTree.XML("<release>17</release>"))
                    LOG.info("****** Match JDK plugin found!!! ******")
                    LOG.info("Update/insert JDK configurations if necessary")
        if not flag:
            # missing the entire plugin
            sub_tree = root.findall(".//xmlns:plugins", namespaces=namespaces)
            request = ElementTree.XML(
                "<plugin>\n<groupId>"
                + groupid
                + "</groupId>\n<artifactId>"
                + artifactid
                + "</artifactId>\n"
                + config_block
                + "</plugin>\n"
            )
            LOG.info("****** No match JDK plugin configuration found!!! ******")
            LOG.info(f"Adding: {groupid, artifactid}")
            sub_tree[0].append(request)


def update_jdk_related(pom_file, new_pom_file):
    """
    Update JDK related properties and plugin configurations
    Called by mandatory recipe by the control flow

    Parameters
    ----------
    pom_file:
        filename of the input pom file
    new_pom_file
        filename of the output pom file (could be the same as pom_file)
    """
    logging.warning("Rewrite pom file: `%s` <== `%s` ...", new_pom_file, pom_file)

    forced_properties = [
        "maven.compiler.source",
        "maven.compiler.target",
        "maven.compiler.release",
    ]
    optional_properties = [
        "java.version",
        "jdk.version",
        "javaVersion",
        "jdkversion",
        "java.testversion",
    ]

    parser = ElementTree.XMLParser(encoding="utf-8")
    tree = ElementTree.parse(pom_file, parser=parser)
    root = tree.getroot()

    for property_name in forced_properties:
        update_jdk_property(root, property_name, "17", True)
    for property_name in optional_properties:
        update_jdk_property(root, property_name, "17", False)

    update_jdk_plugin_configuration(
        root, "org.apache.maven.plugins", "maven-compiler-plugin"
    )
    ElementTree.register_namespace("", "http://maven.apache.org/POM/4.0.0")
    tree.write(new_pom_file, default_namespace=None)


def apply_selected_notes(pom_file, candidate: Dict) -> None:
    for group_artifact_str in candidate:
        group_id, artifact_id = group_artifact_str.split(":")
        version = candidate[group_artifact_str]
        update_pom_content(
            pom_file=pom_file,
            d_type="dependency",
            new_groupid=group_id,
            new_artifactid=artifact_id,
            new_version=version,
            new_pom_file=pom_file,
        )


def extract_pom_property(root):
    """
    Extract the properties section of the POM file
    Parameters
    ----------
    root : root
        root of ElementTree

    Returns
    -------
    dict[str]
        return a dictionary with key property and value string

    """
    res_pro = {}
    results = root.findall(".//xmlns:properties", namespaces=namespaces)
    if results:
        for e in list(results[0]):
            tag = e.tag.replace("{http://maven.apache.org/POM/4.0.0}", "")
            res_pro[tag] = e.text
    return res_pro


def update_pom_dependency(root, d_type, new_groupid, new_artifactid, new_version):
    """
    Update dependency/plugin block

    Parameters
    ----------
    root:
        root of the POM XML tree
    d_type: str
        dependency or plugin
    new_groupid : str
        groupid of the dependency block
    new_artifactid: str
        aritifactid of the dependency block
    new_veresion: str
        version of the dependency block

    """

    deps = root.findall(".//xmlns:" + d_type, namespaces=namespaces)

    if not deps:
        # there is no mega dependencies/plugins block
        # add entire mega block
        if d_type == "dependency":
            request = ElementTree.XML(
                "\n<dependencies>\n<dependency>\n<groupId>"
                + new_groupid
                + "</groupId>\n<artifactId>"
                + new_artifactid
                + "</artifactId>\n<version>"
                + new_version
                + "</version>\n</dependency>\n</dependencies>\n"
            )
        else:
            request = ElementTree.XML(
                "\n<build>\n<plugins>\n<plugin>\n<groupId>"
                + new_groupid
                + "</groupId>\n<artifactId>"
                + new_artifactid
                + "</artifactId>\n<version>"
                + new_version
                + "</version>\n</plugin>\n</plugins>\n</build>\n"
            )
        LOG.info("****** No match dependency/plugin found!!! ******")
        LOG.info(
            f"Adding (with mega block): {new_groupid, new_artifactid, new_version}"
        )
        root.append(request)
    else:
        # mega block exist
        flag = False
        for d in deps:
            groupid = None
            artifactid = None
            current_version = None
            for e in list(d):
                tag = e.tag.replace("{http://maven.apache.org/POM/4.0.0}", "")
                if tag == "groupId":
                    groupid = e.text
                elif tag == "artifactId":
                    artifactid = e.text
                elif tag == "version":
                    current_version = e.text
                    break

            if groupid == new_groupid and artifactid == new_artifactid:
                # find the existing matching dependency
                properties = extract_pom_property(root)
                flag = True
                if current_version:
                    # if version exist than try to upgrade
                    # otherwise leave it untouched
                    if current_version.startswith("${"):
                        # if the version is a variable then need to
                        # extract the actual version from the property section
                        current_version = get_property(
                            root, properties, current_version
                        )

                    if should_upgrade(current_version, new_version):
                        # check whether the proposed new version is newer
                        e.text = new_version
                        LOG.info(
                            "****** Found a match dependency/plugin for updating!!! ******"
                        )
                        LOG.info(
                            f"Updating: {new_groupid, new_artifactid, new_version}"
                        )

        # if not flag:
        #     # no match block is found append the entire block
        #     if d_type == "dependency":
        #         request = ElementTree.XML(
        #             "\n<dependency>\n<groupId>"
        #             + new_groupid
        #             + "</groupId>\n<artifactId>"
        #             + new_artifactid
        #             + "</artifactId>\n<version>"
        #             + new_version
        #             + "</version>\n</dependency>\n"
        #         )
        #         sub_tree = root.findall(".//xmlns:dependencies", namespaces=namespaces)
        #         # without dependency management block the length of tt is always 0
        #         # with it there will be two such blocks use for loop to add
        #         # to both blocks
        #         if len(sub_tree) == 1:
        #             sub_tree[0].append(request)
        #         else:
        #             for e in sub_tree:
        #                 e.append(request)
        #     else:
        #         request = ElementTree.XML(
        #             "\n<plugin>\n<groupId>"
        #             + new_groupid
        #             + "</groupId>\n<artifactId>"
        #             + new_artifactid
        #             + "</artifactId>\n<version>"
        #             + new_version
        #             + "</version>\n</plugin>\n"
        #         )
        #         sub_tree = root.findall(".//xmlns:plugins", namespaces=namespaces)
        #         sub_tree[0].append(request)
        #     LOG.info("****** No match dependency/plugin found!!! ******")
        #     LOG.info(f"Adding: {new_groupid,new_artifactid, new_version}")


def update_pom_content(
    pom_file, d_type, new_groupid, new_artifactid, new_version, new_pom_file
):
    # TODO: add capability to add other artifact, e.g. scope, test, etc.
    """
    Update POM content

    Parameters
    ----------
    pom_file:
        filename of the input pom file
    d_type: str
        dependency or plugin
    new_groupid : str
        groupid of the dependency block
    new_artifactid: str
        aritifactid of the dependency block
    new_version: str
        version of the dependency block
    new_pom_file:
        filename of the output pom file (could be the same as the pom_file)
    """

    parser = ElementTree.XMLParser(encoding="utf-8")
    tree = ElementTree.parse(pom_file, parser=parser)
    root = tree.getroot()

    update_pom_dependency(root, d_type, new_groupid, new_artifactid, new_version)
    update_pom_parent(root, new_groupid, new_artifactid, new_version)

    ElementTree.register_namespace("", "http://maven.apache.org/POM/4.0.0")
    tree.write(new_pom_file, default_namespace=None)
