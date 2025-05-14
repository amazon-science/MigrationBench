# Sample command to build an image:
# (A better way is to use ../image.sh instead to build the image and push to ECR)
#
# ```
# cd .../docker
# cp -r ~/.aws .  # AWS credentials
# docker build -t test .  # --no-cache
# rm -rf .aws     # AWS credentials clean up
# ```
#
# *************************
# Packages to install
#
# - Python: pip install ...
# - Non Python
#   * aws-cli
#   * wget
# - [java]
# - maven (s3)
# - Self debugging (./SelfDebug)
# *************************
#
#
# Inputs:
#   - It copies ./SelfDebug, which can include your local changes
#
# Outputs:
#   - Self debugging lib at: $SELF_DEBUGGING_PATH=/self-dbg
#
# Env var changes:
#   - A few libraries added to $PATH:
#     * $MAVEN_ROOT:  mvn --version


# Base image is from EMR serverless, references:
#
# https://docs.aws.amazon.com/emr/latest/EMR-Serverless-UserGuide/application-custom-image.html
# https://github.com/aws-samples/emr-serverless-samples/tree/main/examples/pyspark/custom-images
# https://gallery.ecr.aws/emr-serverless: Available base images

FROM --platform=linux/amd64 public.ecr.aws/emr-serverless/spark/emr-7.0.0:latest


USER root

#
# Customized container: BEGIN
#

# Python packages
RUN python3 -m pip install \
    "boto3==1.34.4" \
    "gitpython==3.1.43" \
    "numpy==1.26.4" \
    "parameterized==0.8.1" \
    "protobuf==3.20.3" \
    "pydantic==2.6.4" \
    "pylint==2.14.5" \
    "python-dateutil==2.8.2" \
    "pytz==2024.1"

# Install wget and other tools: To run `git ...` command
RUN yum update -y \
    && yum install -y git gzip jq libicu tar tree vim wget \
    && yum clean all \
    && git config --system --add safe.directory '*'  \
    && git config --system user.email "no-reply@amazon.com" \
    && git config --system user.name "NoReply Amazon"

# Install aws-cli
### RUN yum remove -y aws-cli && \
###     yum install -y aws-cli && \
###     python -m awscli --version  # Works
###     # aws --version             # Not work

WORKDIR /tmp
RUN curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" && \
    unzip awscliv2.zip && \
    ./aws/install && \
    rm -rf ./aws && \
    rm -rf ./awscliv2.zip && \
    aws --version


# 1. Install java: N.A. as Java 17 is already present in the base image.
RUN yum -y install java-17-amazon-corretto-devel
#********************************
# IMPORTANT: Add AWS credentials.
#********************************
COPY .aws /root/.aws

# 2. Install maven
ENV MAVEN_ROOT=/usr/local/bin
COPY apache-maven-3.9.6-bin.zip $MAVEN_ROOT

WORKDIR $MAVEN_ROOT
RUN unzip apache-maven-3.9.6-bin.zip && \
    rm -f apache-maven-3.9.6-bin.zip

ENV MAVEN_ROOT=$MAVEN_ROOT/apache-maven-3.9.6/bin
ENV PATH=$PATH:$MAVEN_ROOT
RUN mvn --version

# 3. Add the self debugging+ lib: Python AND C# versions.
# 4. Add benchmark datasets
ARG SELF_DEBUGGING_PATH=/self-dbg

# /self-dbg
# Remove .git to decrease container size.

RUN mkdir /SDK && \
    chown -R hadoop /SDK && \
    chmod 777 /SDK

WORKDIR /
COPY SelfDebug self-dbg
### COPY SDKAssemblies.zip /SDK
### COPY QnetTransformCLI.zip .

RUN cd $SELF_DEBUGGING_PATH && \
    rm -rf src/*.egg-info && \
    # git log -2 && \
    # du -sh .git && \
    # rm -rf .git && \
    pip install -r requirements.txt -e .

#*******************************
# IMPORTANT: Remove credentials.
#*******************************
RUN rm -rf /root/.aws



#
# Customized container: END
#

USER hadoop:hadoop

WORKDIR $SELF_DEBUGGING_PATH
