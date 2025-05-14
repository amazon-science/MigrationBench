#!/usr/bin/env bash

set -ex

#
#             1               2                3
# ./launch.sh $CONTAINER_NAME $CONTAINER_IMAGE $CONTAINER_ACCOUNT
#

export CONTAINER_NAME=${1:-"sliuxl__self-dbg"}
export CONTAINER_IMAGE=${2:-"552793110740.dkr.ecr.us-east-1.amazonaws.com/sliuxl:dotnet-self-dbg-emrs"}
export ACCOUNT=${3:-""}
export REGION=${4:-""}

if [[ $ACCOUNT == "" ]]; then
    ACCOUNT=`echo $CONTAINER_IMAGE | cut -c-12`
fi
if [[ $REGION == "" ]]; then
    REGION=`echo $CONTAINER_IMAGE | cut -c22-30`
fi


# 1. Set the docker ECR path
# 552793110740.dkr.ecr.us-east-1.amazonaws.com/sliuxl:self-dbg
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ACCOUNT.dkr.ecr.$REGION.amazonaws.com

FSX_MOUNT=""  # "-v /fsx/:/fsx"
NFS_MOUNT=""  # "-v /nfs/:/nfs"


# 2. Clean up
docker stop $CONTAINER_NAME || true

# docker ps -aq | xargs docker stop | xargs docker rm || true
docker stop $(docker ps -aq) || true
docker rm -f $(docker ps -aq) || true
# docker rmi -f $(docker images -q -a) || true


# 3. Start new image
docker pull ${CONTAINER_IMAGE}
docker run -it --privileged \
    --name $CONTAINER_NAME \
    ${CONTAINER_IMAGE}

    # --entrypoint /bin/sh \
    # ${CONTAINER_IMAGE}


# 4. Show images
docker ps
