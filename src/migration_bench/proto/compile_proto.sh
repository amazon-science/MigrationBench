#!/bin/bash

# Compile proto files.

# Sample cmd:
#   cd .../proto/../..
#   ./self_debug/proto/compile_proto.sh self_debug ./

set -ex

INPUT_DIR=${1:-"./"}
OUTPUT_DIR=${2:-"./"}

proto_files=("ast_parser.proto" "batch.proto" "builder.proto" "dataset.proto" "llm_parser.proto" "metrics.proto" "model.proto" "trajectory.proto")
proto_files+=("llm_agent.proto")
proto_files+=("config.proto")
proto_files+=("cloudwatch.proto")

for proto_file in "${proto_files[@]}"; do
    $HOME/.local/bin/protoc $INPUT_DIR/proto/$proto_file --python_out=$OUTPUT_DIR
done
