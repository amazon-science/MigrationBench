"""EMR Serverless applications.

Reference:
https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/emr-serverless.html

1. Sample command:
```
export CONFIG=/self-dbg/src/self_debug/common/testdata/batch.pbtxt
export CONFIG=../common/testdata/batch.pbtxt

export CONFIG=configs/batch_csharp_micro-benchmark.pbtxt
export CONFIG=configs/batch_csharp_core-to-core--v0-20240531--00-full.pbtxt
export CONFIG=configs/batch_csharp_core-to-core--v0-20240531--01-ported.pbtxt
export CONFIG=configs/batch_csharp_core-to-core--v0-20240531--02-llm.pbtxt
export CONFIG=configs/batch_csharp_core-to-core--v0-20240531--03-llm-calls.pbtxt
export CONFIG=configs/batch_csharp_core-to-core--v0-20240531--first03.pbtxt
export CONFIG=configs/batch_csharp_core-to-core--v0-20240531--fix-by-rules.pbtxt
export CONFIG=configs/batch_csharp_core-to-core--v0-20240531.pbtxt
export CONFIG=configs/batch_csharp_framework-to-core--v0-20240516--00-full.pbtxt
export CONFIG=configs/batch_csharp_framework-to-core--v0-20240516--01-ported.pbtxt
export CONFIG=configs/batch_csharp_framework-to-core--v0-20240516--02-llm.pbtxt
export CONFIG=configs/batch_csharp_framework-to-core--v0-20240516--03-llm-calls.pbtxt
export CONFIG=configs/batch_csharp_framework-to-core--v0-20240516--first03.pbtxt
export CONFIG=configs/batch_csharp_framework-to-core--v0-20240516--fix-by-rules.pbtxt
export CONFIG=configs/batch_csharp_framework-to-core--v0-20240516.pbtxt
# Java
CONFIG=configs/batch_java__v00_ozt_ngde_20240620__first10.pbtxt
CONFIG=configs/batch_java__v01_zhouqia_or_20241030__first10.pbtxt

export APPLICATION=
export APPLICATION=emrs-dbg-{user}--{date}--run00

export SCRIPT=
export SCRIPT=debugger
export SCRIPT=builder

echo "(<$CONFIG>, <$APPLICATION>, <$SCRIPT>)"

python emrs.py --config_file=$CONFIG --application=$APPLICATION --script=$SCRIPT \
    --user=sliuxl --dry_run=1

python emrs.py --config_file=$CONFIG --application=$APPLICATION --script=$SCRIPT \
    --dry_run=1 --user=sliuxl
```

2. Go to AWS console ==> `EMR Studio` to find out job statuses and logs.
"""

import argparse
import copy
import datetime
import logging
import os
import re
from typing import Any, Dict, Optional, Tuple
from pytz import timezone

import boto3
from self_debug.proto import batch_pb2

from self_debug.common import github, utils


RANDOM_LEN = 6
_FORMAT_DATE = "%Y%m%d"
_FORMAT_TIMESTAMP = "%Y%m%d-%H%M%S"


# EMR client's output.
EMR_OUTPUT_APPLICATION_ARN = "arn"
EMR_OUTPUT_APPLICATION_ID = "applicationId"
EMR_OUTPUT_APPLICATION_NAME = "name"
EMR_OUTPUT_JOB_ID = "jobRunId"

JAVA_HOME_08 = "/usr/lib/jvm/java-1.8.0-amazon-corretto.x86_64/jre"
JAVA_HOME_17 = "/usr/lib/jvm/java-17-amazon-corretto.x86_64"

# pylint: disable=line-too-long
# https://docs.aws.amazon.com/emr/latest/EMR-Serverless-UserGuide/jobs-spark.html
EMR_SPARK_CONFIG = " ".join(
    f"--conf {config}"
    for config in [
        "spark.blacklist.enabled=true",
        # Driver
        "spark.driver.cores={cores}",
        "spark.driver.memory={memory}",
        # Executor
        "spark.executor.cores={e_cores}",
        "spark.executor.memory={e_memory}",
        "spark.executor.instances={instances}",
        ### Long running jobs: BEGIN
        "spark.executor.heartbeatInterval=120s",  # 10s
        "spark.executor.heartbeat.maxFailures=360",
        "spark.network.timeout=72000s",  # 120s
        ### Long running jobs: END
        # Executor: Again
        "spark.dynamicAllocation.initialExecutors={min_instances}",
        "spark.dynamicAllocation.minExecutors={min_instances}",
        "spark.dynamicAllocation.maxExecutors={instances}",
        "spark.task.cpus={e_cores}",
        ### "spark.task.cpus={e_cores_minus1}",
        # Disk: Driver & executor
        "spark.emr-serverless.driver.disk={disk}",
        "spark.emr-serverless.executor.disk={e_disk}",
        # Misc: To plug in `JAVA_HOME_VALUE`
        "spark.emr-serverless.driverEnv.JAVA_HOME=JAVA_HOME_VALUE",
        "spark.executorEnv.JAVA_HOME=JAVA_HOME_VALUE",
        # IMPORTANT: AWS credentials time out
        "spark.hadoop.fs.s3a.aws.credentials.provider=org.apache.hadoop.fs.s3a.TemporaryAWSCredentialsProvider",
        "spark.hadoop.fs.s3a.aws.credentials.duration={time_out_seconds}",
    ]
)
# pylint: enable=line-too-long


APPLICATION_NAME = "application_name"


def _parse_args():
    """Parse args."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config_file", type=str, default=None, help="Config file for batch job."
    )

    # Options to overwrite in config file.
    parser.add_argument(
        "--qnet_bin",
        type=str,
        default="/QnetTransform.CLI",
        help="Use qnet repo: dir containing `./bin/`.",
    )
    parser.add_argument(
        "--qnet_runs", type=int, default=2, help="How many QNetCLI runs."
    )
    parser.add_argument(
        "--application", type=str, default="", help="Application id or name."
    )
    parser.add_argument("--max_iterations", type=int, default=80, help="Max LLM calls.")
    parser.add_argument("--script", type=str, default="", help="Scripts to run.")
    parser.add_argument(
        "--show_jobs", type=int, default=3, help="How many jobs to show."
    )

    # The user running this job, and to send summary email to.
    parser.add_argument(
        "--user",
        type=str,
        default=None,
        help="User running the job, without @amazon.com.",
    )
    parser.add_argument(
        "--timezone", type=str, default="America/Los_Angeles", help="Time zone."
    )
    parser.add_argument("--dry_run", type=int, default=None, help="Dry run.")
    parser.add_argument(
        "--java_n", type=int, default=17, help="Which Java version to use."
    )

    return parser.parse_known_args()


class Emrs:
    """EMR Serverless."""

    def __init__(
        self,
        role: str,
        config: batch_pb2.BatchJob,
        application_id: str = "",
        client: str = "emr-serverless",
        **kwargs,
    ):
        """EMR Serverless."""
        self.role = role
        self.config = config

        self._application_id = application_id
        self._client = client

        self.kwargs = kwargs

        logging.debug(
            "[ctor] EMR Serverless with (account, role, boto3, client, id) = (%s, %s, %s, %s, %s).",
            self.account(role),
            self.role,
            boto3.__version__,
            client,
            application_id,
        )

    def account(self, role: Optional[str] = None) -> str:
        """Account from role: `arn:aws:iam::552793110740:role/EMRServerlessS3RuntimeRoleSelfDbg`."""
        role = role or self.role

        if isinstance(role, str):
            match = re.match(r"\D*(\d{12})\D*", role)
            if match:
                return match.group(1)
            msg = "Not matched"
        else:
            msg = "Type mismatch"

        raise ValueError(f"Unable to get account info from `{role}`: {msg}.")

    @property
    def client(self):
        """Get boto3 client."""
        if isinstance(self._client, str):
            self._client = boto3.client(
                self._client, region_name=self.kwargs.get("region")
            )

        return self._client

    @property
    def application_id(self):
        """Get application id: str."""
        if not self._application_id:
            self._application_id, arn = self.maybe_create_application()

            account = self.account()
            if account not in arn:
                raise ValueError(
                    f"Please make sure using the same account (account): `{arn}`."
                )

        logging.debug("Application id: `%s`.", self._application_id)
        return self._application_id

    def maybe_create_application(self, **kwargs) -> Tuple[str, str]:
        """Maybe create an application and get the application id: Try to reuse the same name."""
        application_name = self.kwargs.get(APPLICATION_NAME)

        all_apps = self.list_applications()
        apps = [
            app
            for app in all_apps
            if app.get(EMR_OUTPUT_APPLICATION_NAME) == application_name
        ]
        logging.info(
            "Retrieved %d out of %d application with name = `%s`.",
            len(apps),
            len(all_apps),
            application_name,
        )

        if apps:
            app = apps[0]
            application_id = app.get("id")
            arn = app.get(EMR_OUTPUT_APPLICATION_ARN)
            logging.info(
                "Skip creating a new one, reusing the first one: `%s` (%s).",
                application_id,
                arn,
            )

            return application_id, arn

        return self.create_application(**kwargs)

    def create_application(self, **kwargs) -> Tuple[str, str]:
        """Create an application and get the (application id, arn).

        Reference:
        https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/emr-serverless/client/create_application.html
        """
        del kwargs

        if self._application_id:
            return self._application_id

        config = self.config.emr_serverless
        app_kwargs = {}
        image = config.application.image_uri.format(**self.kwargs)
        if image:
            app_kwargs.update(
                {
                    "imageConfiguration": {
                        "imageUri": image,
                    },
                }
            )
        subnet_ids = list(config.application.subnet_ids)
        sg_ids = list(config.application.security_group_ids)
        if subnet_ids or sg_ids:
            app_kwargs.update(
                {
                    "networkConfiguration": {
                        "subnetIds": subnet_ids,
                        "securityGroupIds": sg_ids,
                    },
                }
            )
        if config.application.logging.enable_cloud_watch:
            # Logs are at: AWS Console > CloudWatch > Log groups > /aws/emr-serverless
            log_types = {
                key: getattr(config.application.logging, field)
                .replace(" ", "")
                .split(",")
                for key, field in (
                    ("SPARK_DRIVER", "driver"),
                    ("SPARK_EXECUTOR", "executor"),
                )
            }
            app_kwargs.update(
                {
                    "monitoringConfiguration": {
                        "cloudWatchLoggingConfiguration": {
                            "enabled": True,
                            "logTypes": log_types,
                        },
                    },
                }
            )
        logging.info("Application kwargs: <<<%s>>>", app_kwargs)

        application_name = self.kwargs.get(APPLICATION_NAME)
        response = self.client.create_application(
            name=application_name,
            releaseLabel=config.application.emr_version,
            type=config.application.emr_application_type,
            **app_kwargs,
        )

        if response.get(EMR_OUTPUT_APPLICATION_NAME) != application_name:
            logging.warning(
                "Getting a different application name: `%s` != `%s`.",
                response.get(EMR_OUTPUT_APPLICATION_NAME),
                application_name,
            )

        self._application_id = response.get(EMR_OUTPUT_APPLICATION_ID)
        arn = response.get(EMR_OUTPUT_APPLICATION_ARN)
        logging.info(
            "EMR Serverless application id = `%s` (%s): name = `%s`.",
            self._application_id,
            arn,
            application_name,
        )
        return self._application_id, arn

    def list_applications(self, **kwargs) -> Tuple[Dict[str, Any]]:
        """List applications.

        Reference:
        https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/emr-serverless/client/list_applications.html
        """
        apps = self.client.list_applications(**kwargs)["applications"]
        logging.info("EMRS applications: # = %d.", len(apps))
        for index, app in enumerate(apps):
            logging.debug("EMRS app [%02d/%02d]:", index, len(apps))
            for key, value in sorted(app.items()):
                logging.debug("    `%-12s`: `%s`.", key, value)

        return tuple(apps)

    def delete_application(self) -> None:
        """Delete an application.

        Reference:
        https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/emr-serverless/client/delete_application.html
        """
        if not self._application_id:
            return

        self.client.delete_application(applicationId=self._application_id)
        logging.info(
            "EMR Serverless application id = `%s`: delete ...", self._application_id
        )

        self._application_id = None

    def list_job_runs(self, show_jobs: int, **kwargs) -> Tuple[Dict[str, Any]]:
        """List job runs.

        Reference:
        https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/emr-serverless/client/list_applications.html
        """
        jobs = self.client.list_job_runs(applicationId=self.application_id, **kwargs)[
            "jobRuns"
        ]
        logging.info("EMRS jobs: # = %d.", len(jobs))
        for index, job in enumerate(jobs):
            if index > show_jobs:
                break
            logging.info("EMRS job [%02d/%02d]:", index, len(jobs))
            for key, value in sorted(job.items()):
                logging.info("    `%-12s`: `%s`.", key, value)

        return tuple(jobs)

    def start_jobs(
        self, script_name: str = "", dry_run: bool = False, java_n: int = 17
    ):
        """Start all jobs."""
        config = self.config.emr_serverless
        for script in config.scripts:
            if script.disable or (script_name and script.name != script_name):
                logging.info(
                    "Skip script `%s`: `%s` (%s, %s).",
                    script.name,
                    script.binary,
                    script.disable,
                    script_name,
                )
                continue

            kwargs = copy.deepcopy(self.kwargs)  # Base kwargs.
            kwargs.update(
                {
                    "script_name": script.name,  # Needs to be used in `job_name`.
                }
            )
            ec2 = script.ec2
            for field in ("instances", "min_instances"):
                if ec2.HasField(field):
                    kwargs.update(
                        {
                            field: f"{getattr(ec2, field):03d}",
                        }
                    )

            job_name = config.job.name.format(**kwargs)
            timeout = "executionTimeoutMinutes"
            kwargs.update(
                {
                    "job_name": job_name,
                    "nodes": kwargs["min_instances"],
                    timeout: (
                        config.job.time_out_minutes
                        if config.job.HasField("time_out_minutes")
                        else 120
                    ),
                }
            )
            kwargs[timeout] = min(kwargs[timeout], 720)  # Up to 12h

            kwargs.update(
                {
                    # Time out minutes => seconds.
                    "time_out_seconds": kwargs[timeout] * 60,
                }
            )
            if kwargs.get("qnet_bin") and kwargs[timeout] <= 120:
                kwargs[timeout] *= 2
                logging.info(
                    "Timeout increase by 2x to `%s` mins with `qnet_bin=%s`.",
                    kwargs[timeout],
                    kwargs["qnet_bin"],
                )
            self.start_job_run(script, job_name, dry_run, java_n=java_n, **kwargs)

    def start_job_run(
        self,
        script: batch_pb2.Script,
        name: str,
        dry_run: bool = False,
        java_n=17,
        **kwargs,
    ) -> Tuple[Dict[str, Any]]:
        """Start to run a job.

        Reference:
        https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/emr-serverless/client/start_job_run.html
        """

        java_home = JAVA_HOME_17
        if java_n not in (8, 17):
            raise ValueError(
                f"Unsupported Java version other than {8, 17}: `{java_n}`."
            )
        logging.info("Using Java %d: `%s`.", java_n, java_home)

        job_kwargs = {
            "jobDriver": {
                "sparkSubmit": {
                    "entryPoint": script.binary.format(**kwargs),
                    "entryPointArguments": [
                        a
                        if (
                            a.startswith("--upload_to_s3")
                            or a.startswith("--upload_project_to_s3=")
                            or a.startswith("--upload_raw_metrics_to_s3=")
                        )
                        else a.format(**kwargs)
                        for a in list(script.args)
                    ],
                    "sparkSubmitParameters": EMR_SPARK_CONFIG.format(**kwargs).replace(
                        "JAVA_HOME_VALUE", java_home
                    ),
                },
            },
            "name": name,
            "executionTimeoutMinutes": kwargs["executionTimeoutMinutes"],
        }
        logging.info("Start job `%s` ...", name)

        if dry_run:
            logging.info("Skip job with dry_run mode: `%s`.", name)
            return ()

        response = self.client.start_job_run(
            applicationId=self.application_id,
            executionRoleArn=self.role,
            **job_kwargs,
        )

        if response.get(EMR_OUTPUT_APPLICATION_ID) != self._application_id:
            logging.warning(
                "Getting a different application id: `%s` != `%s`.",
                response.get(EMR_OUTPUT_APPLICATION_ID),
                self._application_id,
            )

        job_id = response.get(EMR_OUTPUT_JOB_ID)
        logging.info(
            "EMR Serverless (app, job) id = (%s, %s): name = `%s`.",
            self._application_id,
            job_id,
            response.get(EMR_OUTPUT_APPLICATION_ARN),
        )
        return job_id


def main():
    """Main."""
    args, _ = _parse_args()

    config = utils.load_proto(args.config_file, batch_pb2.BatchJob)

    emrs = config.emr_serverless
    now = datetime.datetime.now(timezone(args.timezone))
    name_kwargs = {
        "max_iterations": args.max_iterations,
        "qnet_bin": args.qnet_bin if args.qnet_bin.startswith("/") else "",
        "qnet_runs": args.qnet_runs,
        "user": args.user or config.user.split(",")[0] or "job",
        "region": config.region,
        "users": config.user,
        "batch_config": os.path.join(
            "/self-dbg/src/self_debug",
            re.sub(r"^.*/src/", "", os.path.abspath(args.config_file)),
        ),
        # Resources
        # - From driver.
        "cores": f"{emrs.job.driver.cores:02d}",
        "disk": emrs.job.driver.disk.lower(),
        "memory": emrs.job.driver.memory.lower(),
        # - From worker: Could be job/ SCript specific, will overwrite for each job.
        "instances": f"{emrs.job.worker.instances:03d}",
        "min_instances": f"{emrs.job.worker.min_instances:03d}",
        # Tags
        "date": now.strftime(_FORMAT_DATE),
        "timestamp": now.strftime(_FORMAT_TIMESTAMP),
        "random": github.get_random_string(RANDOM_LEN),
        "tag": f"--r-{github.get_random_string(RANDOM_LEN)}",
    }
    name_kwargs.update(
        {
            "qnet": "-q" if name_kwargs["qnet_bin"] else "",
            APPLICATION_NAME: (args.application or emrs.application.name).format(
                **name_kwargs
            ),
        }
    )
    for field, value in (
        ("cores", f"{emrs.job.worker.cores:02d}"),
        ("disk", emrs.job.worker.disk.lower()),
        ("memory", emrs.job.worker.memory.lower()),
    ):
        # - From workers.
        worker_value = value if emrs.job.worker.HasField(field) else name_kwargs[field]
        name_kwargs.update({f"e_{field}": worker_value})

        if field == "cores" and int(worker_value) > 2:
            worker_value = max(int(worker_value) - 1, 1)
        name_kwargs.update({f"e_{field}_minus1": worker_value})

    emrs = Emrs(config.emr_serverless.job.role, config, **name_kwargs)
    if args.dry_run:
        all_apps = emrs.list_applications()
        apps = [
            app
            for app in all_apps
            if app.get(EMR_OUTPUT_APPLICATION_NAME) == name_kwargs[APPLICATION_NAME]
        ]
        if apps:
            # Avoid creating new applications in the dry run mode.
            emrs.list_job_runs(args.show_jobs)

    emrs.start_jobs(dry_run=args.dry_run, script_name=args.script, java_n=args.java_n)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format=utils.LOGGING_FORMAT)
    main()
