"""Builder factory."""

import logging
from typing import Any

from self_debug.common import utils
from self_debug.lang.base import builder

from self_debug.lang.java.maven import builder as maven_builder


BaseBuilder = builder.BaseBuilder
BuildData = builder.BuildData
CmdData = builder.CmdData


def create_builder(option: Any, *args, **kwargs) -> BaseBuilder:
    """Create builder based on its name: Option can be a string (infer class name) or a config."""
    logging.info("[factory] Create builder: `%s`.", option)

    classes = (maven_builder.MavenBuilder,)

    if isinstance(option, str):
        config_kwargs = kwargs
    else:
        args = ("builder",) + args

        config_kwargs = {
            builder.BASE_CONFIG: option,
        }
        config_kwargs.update(kwargs)

    return utils.create_instance(option, classes, *args, **config_kwargs)
