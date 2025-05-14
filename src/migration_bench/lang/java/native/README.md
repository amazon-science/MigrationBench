## How to run `Java 17` binaries


```
cd .../java/native

# Make sure maven is installed
# mvn --verison  # Should give you a valid version


mvn clean install


FILENAME=src/main/java/qct/AstParser.java
FILENAME=src/main/java/qct/XmlBeautifier.java
FILENAME=/home/sliuxl/xmpp-light/src/main/java/ua/tumakha/yuriy/xmpp/light/web/IndexController.java
java -jar target/qct-ast-parser-1.0-jar-with-dependencies.jar -input_files $FILENAME -export_path /tmp/test.xml
# cat /tmp/test.xml

### To update ../tesdata/ast_parser.xml
### ./cmd.sh
```


### Sample Output

- Refer to https://code.amazon.com/packages/ElasticGumbySelfDebugging/blobs/mainline/--/src/lang/java/testdata/ast_parser.xml

```
[2024-04] ec2-user@ip-172-31-67-47.ec2.internal 21:26 /home/sliuxl/self-dbg/src/self_debug/lang/java/native $ FILENAME=src/main/java/qct/AstParser.java
[2024-04] ec2-user@ip-172-31-67-47.ec2.internal 00:07 /home/sliuxl/self-dbg/src/self_debug/lang/java/native $ java -jar target/qct-ast-parser-1.0-jar-with-dependencies.jar -input_files $FILENAME -export_path /tmp/test.xml
[QCT] Reading from `src/main/java/qct/AstParser.java`.
[QCT] Writing to `/tmp/test.xml`.
[QCT] Done.
```
