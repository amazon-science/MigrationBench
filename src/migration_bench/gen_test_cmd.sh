FILENAME=run_test_cmd.sh


# Clean up: Begin
cd lang/java/native
mvn clean verify
cd -

find . -name __pycache__ | xargs rm -rf
find . -name .ruff_cache | xargs rm -rf

rm -rf ./container/SelfDebug

rm -rf ../SelfDebug.egg-info
rm -rf ./SelfDebug.egg-info
# Clean up: End


echo "set -x" > $FILENAME
echo ""      >> $FILENAME

find . -name test_\*.py | sort | sed -e "s/^/python /g" >> $FILENAME

chmod +x $FILENAME
