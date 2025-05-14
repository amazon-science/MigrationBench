# pylint: disable=line-too-long
"""EMR Serverless applications.

Reference:
https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/emr-serverless.html

Supported APIs in this module:

```
- Applications
    * maybe_create_application
      - Try to retrieve application with the same name, and reusing the same `id`.
      - Other functions just delegate to boto3.
    * create_application
    * list_applications
    * delete_application
- Jobs
    * list_job_runs
    * start_job_run

```


### AWS EMR

1. Run the demo job:

```
python ./emrs.py $USER $APPLICAITON_NAME

python ./emrs.py sliuxl emrs-{user}--{date}--run00
```

2. Go to AWS console --> EMR Studio to find out job statuses.
   - Alternatively, you can use AWS CLI command for EMR Serverless to find job information.

### AWS CLI command:

# 1. To start an application: Output contains the `application_id`

```
aws emr-serverless create-application --release-label emr-6.9.0 --type SPARK --name my-application \
  --image-configuration '{ \"imageUri\": \"$IMAGE\" }'"
```

# 2. To start a job under the given $application_id:

```
CMD="aws emr-serverless start-job-run \
    --application-id $application_id \
    --execution-role-arn $role  \
    --name $job \
    --job-driver '{
        \"sparkSubmit\": {
          \"entryPoint\": \"s3://$bucket/wordcount_beam.py\",
          \"entryPointArguments\": [\"s3://$bucket/emr-serverless-spark/output\"],
          \"sparkSubmitParameters\": \"--conf spark.executor.cores=1 --conf spark.executor.memory=4g --conf spark.driver.cores=1 --conf spark.driver.memory=4g --conf spark.executor.instances=1\"
        }
    }'"
```

"""
# pylint: enable=line-too-long

import datetime
import logging
import re
import sys
from typing import Any, Dict, Optional, Sequence, Tuple

import boto3

from self_debug.common import github, utils

_FORMAT_DATE = "%Y%m%d"
_FORMAT_TIMESTAMP = "%Y%m%d-%H%M%S"

EMR_IAM = "arn:aws:iam::552793110740:role/EMRServerlessS3RuntimeRoleSelfDbg"

# EMR client's output.
EMR_OUTPUT_APPLICATION_ARN = "arn"
EMR_OUTPUT_APPLICATION_ID = "applicationId"
EMR_OUTPUT_APPLICATION_NAME = "name"
EMR_OUTPUT_JOB_ID = "jobRunId"

# EMR client's input.
EMR_APPLICATION_TYPE = "SPARK"
EMR_IMAGE_URI = "image_uri"
EMR_VPC_SUBNET_IDS = "vpc_subnet_ids"
EMR_SECURITY_GROUP_IDS = "security_group_ids"
# pylint: disable=line-too-long
# https://docs.aws.amazon.com/emr/latest/EMR-Serverless-UserGuide/jobs-spark.html
EMR_SPARK_CONFIG = " ".join(
    f"--conf {config}"
    for config in [
        # Driver
        "spark.driver.cores={cores}",
        "spark.driver.memory={memory}",
        # Executor
        "spark.executor.cores={e_cores}",
        "spark.executor.memory={e_memory}",
        "spark.executor.instances{instances}",
        # Executor: Again
        "spark.dynamicAllocation.initialExecutors={min_instances}",
        "spark.dynamicAllocation.minExecutors={min_instances}",
        "spark.dynamicAllocation.maxExecutors={instances}",
        # Disk: Driver & executor
        "spark.emr-serverless.driver.disk={disk}",
        "spark.emr-serverless.executor.disk={e_disk}",
        # Misc
        "spark.emr-serverless.driverEnv.JAVA_HOME=/usr/lib/jvm/java-17-amazon-corretto.x86_64/",
        "spark.executorEnv.JAVA_HOME=/usr/lib/jvm/java-17-amazon-corretto.x86_64/",
    ]
)
# pylint: enable=line-too-long

EMR_VERSION = "emr-7.0.0"


# For DEMO only.
EMR_DEMO_APPLICATION = "emrs-{user}-{timestamp}"
# EMR_DEMO_BINARY = "s3://self-dbg-plus/batch/spark_build.py"
EMR_DEMO_BINARY = "/self-dbg/src/self_debug/mr/demo/spark_build.py"
EMR_DEMO_BINARY = "/self-dbg/src/self_debug/batch/spark_build.py"

# pylint: disable=line-too-long
CSHARP_BENCHMARK_00 = (
    "/self-dbg/src/self_debug/datasets/configs/dataset_csharp_core-to-core.pbtxt"
)
CSHARP_BENCHMARK_01 = "/self-dbg/src/self_debug/datasets/configs/dataset_csharp_framework-to-core--v0-20240516.pbtxt"
# pylint: enable=line-too-long
EMR_DEMO_ARGS = [
    "--base_config_file=/self-dbg/src/self_debug/configs/csharp_config.pbtxt",
    f"--config_file={CSHARP_BENCHMARK_01}",
    "--dry_run_ast=0",
    "--dry_run_builder=0",
]

# EMR_DEMO_LLM_BINARY = "s3://self-dbg-plus/apache-demo-scripts/claude.py"
EMR_DEMO_LLM_BINARY = "/self-dbg/src/self_debug/mr/demo/claude.py"
EMR_DEMO_LLM_ARGS = []

APPLICATION_NAME = "application_name"


CORES = 16
DISK = "200G"
MEMORY = "64G"

INSTANCES = 1


class Emrs:
    """EMR Serverless."""

    def __init__(
        self,
        role: str,
        application_id: str = "",
        client: str = "emr-serverless",
        **kwargs,
    ):
        """EMR Serverless.

        kwargs:
          application_name: str
          image: str: The docker image to use.

          cores (e_cores):
          memory (e_memory):
          instances
        """
        self.role = role

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
            self._client = boto3.client(self._client)

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
        application_name = kwargs.get(
            APPLICATION_NAME, self.kwargs.get(APPLICATION_NAME)
        )

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
        if self._application_id:
            return self._application_id

        app_kwargs = {}
        image = kwargs.pop(EMR_IMAGE_URI, self.kwargs.get(EMR_IMAGE_URI))
        if image:
            app_kwargs.update(
                {
                    "imageConfiguration": {
                        "imageUri": image,
                    },
                }
            )
        subnet_ids = kwargs.pop(
            EMR_VPC_SUBNET_IDS, self.kwargs.get(EMR_VPC_SUBNET_IDS, [])
        )
        sg_ids = kwargs.pop(
            EMR_SECURITY_GROUP_IDS, self.kwargs.get(EMR_SECURITY_GROUP_IDS, [])
        )

        if subnet_ids or sg_ids:
            app_kwargs.update(
                {
                    "networkConfiguration": {
                        "subnetIds": list(subnet_ids),
                        "securityGroupIds": list(sg_ids),
                    },
                }
            )
        logging.info("Application kwargs: <<<%s>>>", app_kwargs)

        application_name = kwargs.get(
            APPLICATION_NAME, self.kwargs.get(APPLICATION_NAME)
        )
        response = self.client.create_application(
            name=application_name,
            releaseLabel=EMR_VERSION,
            type=EMR_APPLICATION_TYPE,
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

    def list_job_runs(self, **kwargs) -> Tuple[Dict[str, Any]]:
        """List job runs.

        Reference:
        https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/emr-serverless/client/list_applications.html
        """
        jobs = self.client.list_job_runs(applicationId=self.application_id, **kwargs)[
            "jobRuns"
        ]
        logging.info("EMRS jobs: # = %d.", len(jobs))
        for index, job in enumerate(jobs):
            logging.info("EMRS job [%02d/%02d]:", index, len(jobs))
            for key, value in sorted(job.items()):
                logging.debug("    `%-12s`: `%s`.", key, value)

        return tuple(jobs)

    def start_job_run(
        self,
        binary: str,
        binary_args: Sequence[str],
        name: str = "",
        role: Optional[str] = None,
        **kwargs,
    ) -> Tuple[Dict[str, Any]]:
        """Start to run a job.

        Reference:
        https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/emr-serverless/client/start_job_run.html

        kwargs:
        - cores: int: Number of cores for both the driver and executors.
        - memory: str e.g. `4g`: Memory for both the driver and executors.
        - instances: int, Number of executors.
        """

        cores = kwargs.pop("cores", self.kwargs.get("cores"))
        memory = kwargs.pop("memory", self.kwargs.get("memory"))
        disk = kwargs.pop("disk", self.kwargs.get("disk"))
        instances = kwargs.pop("instances", self.kwargs.get("instances"))
        min_instances = kwargs.pop("min_instances", self.kwargs.get("min_instances"))
        job_kwargs = {
            "jobDriver": {
                "sparkSubmit": {
                    "entryPoint": binary,
                    "entryPointArguments": list(binary_args),
                    "sparkSubmitParameters": EMR_SPARK_CONFIG.format(
                        cores=cores,
                        disk=disk,
                        memory=memory,
                        e_cores=kwargs.pop("e_cores", cores),
                        e_disk=kwargs.pop("e_disk", disk),
                        e_memory=kwargs.pop("e_memory", memory),
                        instances=instances,
                        min_instances=min_instances,
                    ),
                },
            },
        }
        if name:
            job_kwargs.update({"name": name})

        response = self.client.start_job_run(
            applicationId=self._application_id,
            executionRoleArn=role or self.role,
            **job_kwargs,
            **kwargs,
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


def _demo(
    application_name: str,
    binary: str,
    binary_args: Sequence[str],
    job_name: str,
    **kwargs,
):
    """A quick demo."""
    emrs = Emrs(EMR_IAM, application_name=application_name, **kwargs)
    emrs.list_applications()
    emrs.list_job_runs()

    emrs.start_job_run(binary, binary_args, name=job_name)
    emrs.list_job_runs()

    # emrs.delete_application()


def _demo_without_llm(application_name: str = EMR_DEMO_APPLICATION, **kwargs):
    instances = kwargs.get("instances", 1)
    min_instances = kwargs.get("min_instances", 1)
    cores = kwargs.get("cores", 1)

    user = kwargs.pop("user", "")

    now = datetime.datetime.now()
    name_kwargs = {
        "cores": f"{cores:02d}",
        "disk": kwargs.get("disk", "disk").lower(),
        "instances": f"{instances:03d}",
        "min_instances": f"{min_instances:03d}",
        # Tags.
        "date": now.strftime(_FORMAT_DATE),
        "timestamp": now.strftime(_FORMAT_TIMESTAMP),
        "tag": f"--r-{github.get_random_string(6)}",
        "user": user or "job",
    }
    job_name = "{user}-{timestamp}--nodes{instances}m{min_instances}x{cores}-{disk}{tag}".format(
        **name_kwargs
    )

    return _demo(
        application_name.format(**name_kwargs),
        EMR_DEMO_BINARY,
        EMR_DEMO_ARGS
        + [
            f"--user={user}",
            f"--application={application_name.format(**name_kwargs)}",
            f"--job_name={job_name.format(**name_kwargs)}",
        ],
        job_name,
        **kwargs,
    )


def _demo_with_llm(application_name: str = EMR_DEMO_APPLICATION, **kwargs):
    return _demo(
        application_name,
        EMR_DEMO_LLM_BINARY,
        EMR_DEMO_LLM_ARGS,
        "job-01-with-llm",
        **kwargs,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format=utils.LOGGING_FORMAT)

    ctor_kwargs = {
        EMR_IMAGE_URI: "552793110740.dkr.ecr.us-east-1.amazonaws.com/sliuxl:self-dbg",
        EMR_VPC_SUBNET_IDS: (
            "subnet-07d1820b0be284714",
            "subnet-081c9be74d5307d23",
        ),
        EMR_SECURITY_GROUP_IDS: ("sg-0a63b0a4e43236a87",),
        "cores": CORES,
        "disk": DISK,
        "instances": INSTANCES * 10,
        "memory": MEMORY,
        # Where to send the email.
        "user": sys.argv[1] if len(sys.argv) >= 2 else "",
        APPLICATION_NAME: sys.argv[2] if len(sys.argv) >= 3 else EMR_DEMO_APPLICATION,
    }
    ctor_kwargs.update(
        {
            "min_instances": max(1, ctor_kwargs["instances"] // 2),
        }
    )
    _demo_without_llm(**ctor_kwargs)
    # _demo_with_llm(**ctor_kwargs)
