# Dockerfile for MigrationBench evaluation environment
# Provides a consistent environment with Java 17 and Maven 3.9.6

FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /workspace

# Create directory for mounting user data (predictions, diffs, migrated repos)
RUN mkdir -p /data

# Python and UV environment variables
ENV UV_SYSTEM_PYTHON=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_NO_PROGRESS=1 \
    PYTHONUNBUFFERED=1 \
    DOCKER_CONTAINER=1

# ---------- Java code migration specific requirements ----------

# 1. Install Java 17
RUN apt-get update && \
    apt-get install -y openjdk-17-jdk && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set JAVA_HOME dynamically based on where java is actually installed
# This works for both amd64 and arm64 architectures
RUN JAVA_BIN=$(readlink -f /usr/bin/java) && \
    DETECTED_JAVA_HOME=$(dirname $(dirname $JAVA_BIN)) && \
    echo "export JAVA_HOME=$DETECTED_JAVA_HOME" > /etc/profile.d/java_env.sh && \
    echo "export PATH=\$JAVA_HOME/bin:\$PATH" >> /etc/profile.d/java_env.sh && \
    echo "=== Java Installation Verification ===" && \
    echo "JAVA_HOME=$DETECTED_JAVA_HOME" && \
    $DETECTED_JAVA_HOME/bin/java --version

# Set ENV based on detected location
# For arm64: /usr/lib/jvm/java-17-openjdk-arm64
# For amd64: /usr/lib/jvm/java-17-openjdk-amd64
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-arm64
ENV PATH=$JAVA_HOME/bin:$PATH

# 2. Install Maven 3.9.6
# Install tools needed for Maven first
RUN apt-get update && \
    apt-get install -y curl unzip && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN curl -O https://archive.apache.org/dist/maven/maven-3/3.9.6/binaries/apache-maven-3.9.6-bin.zip && \
    unzip apache-maven-3.9.6-bin.zip -d /opt/ && \
    rm apache-maven-3.9.6-bin.zip && \
    ln -s /opt/apache-maven-3.9.6 /opt/maven

# Set Maven environment variables
ENV MAVEN_HOME=/opt/maven
ENV PATH=$MAVEN_HOME/bin:$JAVA_HOME/bin:$PATH

RUN echo "=== Maven Installation Verification ===" && \
    echo "JAVA_HOME=$JAVA_HOME" && \
    echo "MAVEN_HOME=$MAVEN_HOME" && \
    mvn --version

# 3. Install Node.js (prevents some frontend plugins from downloading it
# at runtime, which incurs latency & introduces spammy logs)
RUN apt-get update && \
    apt-get install -y --no-install-recommends nodejs && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 4. Install git
RUN apt-get update && \
    apt-get install -y git && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    git config --system --add safe.directory '*' && \
    git config --system user.email "no-reply@example.com" && \
    git config --system user.name "MigrationBench"

# ----------

# Install build dependencies for Python packages (protobuf, datasets dependencies need gcc)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    && apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt /workspace/
RUN uv pip install -r requirements.txt

# Copy source code
COPY setup.py /workspace/
COPY src /workspace/src/

# Install MigrationBench
RUN uv pip install -e .

# Create non-root user
RUN useradd -m -u 1000 migrationbench

USER migrationbench

# Default command
CMD ["python", "-m", "migration_bench.run_eval", "--help"]
