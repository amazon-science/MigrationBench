# Build docker image locally, sample command (By default cache is on):
#
#            1    2     3      4           5
# ./image.sh $TAG $USER $CACHE $DOCKERFILE $ECR
# 
# Final image: $ECR/$USER:$TAG


set -ex

TAG=${1:-"java-emrs"}
USER=${2:-"`whoami`"}
CACHE=${3:-"1"}
DOCKERFILE=${4:-"docker/Dockerfile"}
ECR=${5:-"552793110740.dkr.ecr.us-east-1.amazonaws.com"}

REGION=`echo $ECR | cut -c22-30`
IMAGE="$ECR/$USER:$TAG"


### AWS credentials
rm -rf .aws
rm -f  apache-maven-3.9.6-bin.zip

mkdir ~/.aws || true
cp -r ~/.aws .

curl -O https://archive.apache.org/dist/maven/maven-3/3.9.6/binaries/apache-maven-3.9.6-bin.zip

rm -rf SelfDebug
git clone --depth 1 https://github.com/amazon-science/migration_bench.git
mv migration_bench SelfDebug

sed -i "s/^transformers$/### transformers   ### To reduce container size/g" SelfDebug/requirements.txt
sed -i "s/^torch$/### torch   ### To reduce container size/g" SelfDebug/requirements.txt

# sed -i "s/^  timeout_minutes: 90$/  timeout_minutes: 5/g" SelfDebug/src/configs/java_compile_config.pbtxt SelfDebug/src/configs/java_compile_config_08.pbtxt

# sed -i "s/^  run_java_base_commit_search: true$/  run_java_base_commit_search: true\n  run_java_hash: true/g" SelfDebug/src/configs/java_compile_config.pbtxt SelfDebug/src/configs/java_compile_config_08.pbtxt
# sed -i "s/^  run_java_base_commit_search: true$/  run_java_base_commit_search: false\n  run_java_base_commit_search_no_maven: true/g" SelfDebug/src/configs/java_compile_config.pbtxt SelfDebug/src/configs/java_compile_config_08.pbtxt

cd SelfDebug
git diff
cd ..
rm -rf SelfDebug/dotnet
rm -rf SelfDebug/scripts
cd -
# Used in final eval: base commit id & #test-cases
git checkout scripts/benchmark/java/raw-metrics-generated/raw_metrics__20250322-125330__repo__len-9978.json.normalized.full-len-05119
git checkout scripts/benchmark/java/raw-metrics/emrs-dbg-sliuxl--20250321--run02-hash/sliuxl-builder-java-v05d6-20250322-101827--nodes023x04--r-q7ls09/java__v05--6_20250321--pbtxt/raw_metrics__20250322-125330__repo__len-9978.json
cd -


# Build
echo "0. Building ..."

CMD="docker build -f $DOCKERFILE -t $IMAGE"
if test $CACHE -lt 1; then
    CMD="$CMD --no-cache"
fi
CMD="$CMD ."
sleep 3

`$CMD` || true


# Push
echo "1. Pushing ..."
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ECR
CMD="docker push $IMAGE"

`$CMD` || true


### AWS credentials
rm -rf ./.aws


echo "Done."