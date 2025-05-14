# FILENAME=/home/sliuxl/xmpp-light/src/main/java/ua/tumakha/yuriy/xmpp/light/web/IndexController.java
# FILENAME=src/main/java/qct/XmlBeautifier.java

set -ex

# mvn clean install

FILENAME=src/main/java/qct/AstParser.java


CMD="java -jar target/qct-ast-parser-1.0-jar-with-dependencies.jar -input_files $FILENAME -export_path /tmp/test.xml "
$CMD \
   -add_import true \
   -add_line true \
   -add_var true \

cp /tmp/test.xml ../testdata/ast_parser.xml

$CMD
