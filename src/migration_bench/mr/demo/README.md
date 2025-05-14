# Apache Examples

Using open source frameworks to run batch jobs.
- Map reduce.


## Setup

The current dir has been copied to `s3`:

```
(self-dbg) [2024-04] ec2-user@ip-172-31-67-47.ec2.internal 01:26 /home/sliuxl/self-dbg/src/self_debug/mr $ aws s3 sync demo/ s3://self-dbg-plus/apache-demo-scripts
```

## Apache Spark

Reference:
- https://github.com/spark-examples/pyspark-examples/tree/master
  has plenty examples of using Spark, on dataframes and other types.


```
(self-dbg) [2024-04] ec2-user@ip-172-31-67-47.ec2.internal 01:22 /home/sliuxl/self-dbg/src/self_debug/mr/demo $ conda activate py37

(self-dbg) [2024-04] ec2-user@ip-172-31-67-47.ec2.internal 01:22 /home/sliuxl/self-dbg/src/self_debug/mr/demo $ python spark_metrics.py
Setting default log level to "WARN".
To adjust logging level use sc.setLogLevel(newLevel). For SparkR, use setLogLevel(newLevel).
24/04/26 18:17:44 WARN NativeCodeLoader: Unable to load native-hadoop library for your platform... using builtin-java classes where applicable
/home/ec2-user/miniconda3/envs/py37/lib/python3.7/site-packages/pyspark/context.py:317: FutureWarning: Python 3.7 support is deprecated in Spark 3.4.
  warnings.warn("Python 3.7 support is deprecated in Spark 3.4.", FutureWarning)
  2024-04-26 18:17:46,126 [spark_metrics.py:58] INFO - {'metric_00': 5, 'metric_01': 4}``

```


### Build Errors: Stats

Sample run:

1. To make sure driver and workers are using the same python (locally):

```
export PY_PATH=/home/ec2-user/miniconda3/envs/self-dbg/bin/python
export PYSPARK_PYTHON=$PY_PATH
export PYSPARK_DRIVER_PYTHON=$PY_PATH
```


2. Kick off the job:

```
(self-dbg) [2024-04] ec2-user@ip-172-31-67-47.ec2.internal 20:39 /home/sliuxl/self-dbg/src/self_debug/mr/demo $ python spark_build.py  > log.spark.11 2>&1 &

(self-dbg) [2024-04] ec2-user@ip-172-31-67-47.ec2.internal 20:39 /home/sliuxl/self-dbg/src/self_debug/mr/demo $ cat log.spark.11

Setting default log level to "WARN".
To adjust logging level use sc.setLogLevel(newLevel). For SparkR, use setLogLevel(newLevel).
24/04/27 07:34:34 WARN NativeCodeLoader: Unable to load native-hadoop library for your platform... using builtin-java classes where applicable
2024-04-27 07:34:35,178 [spark_build.py:106] INFO - Total number of datasets: # = 8.
[Stage 0:>                                                          (0 + 1) / 1]                                                                                [Stage 1:>                                                          (0 + 1) / 1]                                                                                2024-04-27 07:34:51,465 [utils.py:50] INFO - Metrics: # = 23.
2024-04-27 07:34:51,465 [utils.py:53] INFO -   # = 0008: `#datasets`.
2024-04-27 07:34:51,465 [utils.py:53] INFO -   # = 0004: `BuilderMetrics::00-start`.
2024-04-27 07:34:51,465 [utils.py:53] INFO -   # = 0004: `BuilderMetrics::01-filter--dir-exists`.
2024-04-27 07:34:51,465 [utils.py:53] INFO -   # = 0004: `BuilderMetrics::02-build-errors--len=001`.
2024-04-27 07:34:51,465 [utils.py:53] INFO -   # = 0004: `BuilderMetrics::03-build-error--code=<None>`.
2024-04-27 07:34:51,465 [utils.py:53] INFO -   # = 0002: `BuilderMetrics::03-build-error--lines=001`.
2024-04-27 07:34:51,465 [utils.py:53] INFO -   # = 0001: `BuilderMetrics::03-build-error--lines=003`.
2024-04-27 07:34:51,465 [utils.py:53] INFO -   # = 0001: `BuilderMetrics::03-build-error--lines=005`.
2024-04-27 07:34:51,465 [utils.py:53] INFO -   # = 0001: `BuilderMetrics::04-build-error--line00=<<<cannot find symbol>>>`.
2024-04-27 07:34:51,465 [utils.py:53] INFO -   # = 0001: `BuilderMetrics::04-build-error--line00=<<<incompatible types: java.lang.Long cannot be converted to ua.tumakha.yuriy.xmpp.light.domain.User>>>`.
2024-04-27 07:34:51,465 [utils.py:53] INFO -   # = 0001: `BuilderMetrics::04-build-error--line00=<<<method does not override or implement a method from a supertype>>>`.
2024-04-27 07:34:51,465 [utils.py:53] INFO -   # = 0001: `BuilderMetrics::04-build-error--line00=<<<method findOne in interface org.springframework.data.repository.query.QueryByExampleExecutor<T> cannot be applied to given types;>>>`.
2024-04-27 07:34:51,465 [utils.py:53] INFO -   # = 0001: `BuilderMetrics::04-build-error--line01=<<<required: org.springframework.data.domain.Example<S>>>>`.
2024-04-27 07:34:51,465 [utils.py:53] INFO -   # = 0001: `BuilderMetrics::04-build-error--line01=<<<symbol:   method formLogin((login)->l[...]All())>>>`.
2024-04-27 07:34:51,465 [utils.py:53] INFO -   # = 0001: `BuilderMetrics::04-build-error--line02=<<<found:    java.lang.Long>>>`.
2024-04-27 07:34:51,465 [utils.py:53] INFO -   # = 0001: `BuilderMetrics::04-build-error--line02=<<<location: variable requests of type org.springframework.security.config.annotation.web.configurers.ExpressionUrlAuthorizationConfigurer<org.springframework.security.config.annotation.web.builders.HttpSecurity>.ExpressionInterceptUrlRegistry>>>`.
2024-04-27 07:34:51,465 [utils.py:53] INFO -   # = 0001: `BuilderMetrics::04-build-error--line03=<<<reason: cannot infer type-variable(s) S>>>`.
2024-04-27 07:34:51,465 [utils.py:53] INFO -   # = 0001: `BuilderMetrics::04-build-error--line04=<<<(argument mismatch; java.lang.Long cannot be converted to org.springframework.data.domain.Example<S>)>>>`.
2024-04-27 07:34:51,465 [utils.py:53] INFO -   # = 0004: `BuilderMetrics::05-build-error--file-suffix=<java>`.
2024-04-27 07:34:51,465 [utils.py:53] INFO -   # = 0001: `BuilderMetrics::05-build-error--file=<src/main/java/ua/tumakha/yuriy/xmpp/light/WebSecurityConfig.java>`.
2024-04-27 07:34:51,465 [utils.py:53] INFO -   # = 0002: `BuilderMetrics::05-build-error--file=<src/main/java/ua/tumakha/yuriy/xmpp/light/service/impl/UserServiceImpl.java>`.
2024-04-27 07:34:51,465 [utils.py:53] INFO -   # = 0001: `BuilderMetrics::05-build-error--file=<src/main/java/ua/tumakha/yuriy/xmpp/light/web/IndexController.java>`.
2024-04-27 07:34:51,465 [utils.py:53] INFO -   # = 0004: `BuilderMetrics::06-finish`.
[Stage 2:>                                                          (0 + 1) / 1]                                                                                [Stage 3:>                                                          (0 + 1) / 1]                                                                                2024-04-27 07:35:07,033 [utils.py:50] INFO - Metrics: # = 73.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0008: `#datasets`.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0004: `JavaAstParser::00-start`.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0004: `JavaAstParser::01-filter--project-exists`.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0004: `JavaAstParser::02-packages--len=019`.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0004: `JavaAstParser::03-00-package--name=<com.mysql>`.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0004: `JavaAstParser::03-00-package--name=<de.svenkubiak>`.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0004: `JavaAstParser::03-00-package--name=<io.github.jpenren>`.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0004: `JavaAstParser::03-00-package--name=<jakarta.persistence>`.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0004: `JavaAstParser::03-00-package--name=<org.apache.vysper.extensions>`.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0004: `JavaAstParser::03-00-package--name=<org.apache.vysper>`.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0004: `JavaAstParser::03-00-package--name=<org.springframework.boot>`.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0004: `JavaAstParser::03-00-package--name=<org.webjars>`.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0004: `JavaAstParser::03-01-package--name-artifact==<com.mysql~mysql-connector-j>`.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0004: `JavaAstParser::03-01-package--name-artifact==<de.svenkubiak~jBCrypt>`.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0004: `JavaAstParser::03-01-package--name-artifact==<io.github.jpenren~thymeleaf-spring-data-dialect>`.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0004: `JavaAstParser::03-01-package--name-artifact==<jakarta.persistence~jakarta.persistence-api>`.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0004: `JavaAstParser::03-01-package--name-artifact==<org.apache.vysper.extensions~xep0045-muc>`.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0004: `JavaAstParser::03-01-package--name-artifact==<org.apache.vysper.extensions~xep0060-pubsub>`.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0004: `JavaAstParser::03-01-package--name-artifact==<org.apache.vysper~vysper-core>`.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0004: `JavaAstParser::03-01-package--name-artifact==<org.springframework.boot~spring-boot-starter-cache>`.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0004: `JavaAstParser::03-01-package--name-artifact==<org.springframework.boot~spring-boot-starter-data-jpa>`.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0004: `JavaAstParser::03-01-package--name-artifact==<org.springframework.boot~spring-boot-starter-security>`.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0004: `JavaAstParser::03-01-package--name-artifact==<org.springframework.boot~spring-boot-starter-test>`.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0004: `JavaAstParser::03-01-package--name-artifact==<org.springframework.boot~spring-boot-starter-thymeleaf>`.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0004: `JavaAstParser::03-01-package--name-artifact==<org.springframework.boot~spring-boot-starter-tomcat>`.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0004: `JavaAstParser::03-01-package--name-artifact==<org.springframework.boot~spring-boot-starter-validation>`.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0004: `JavaAstParser::03-01-package--name-artifact==<org.springframework.boot~spring-boot-starter-web>`.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0004: `JavaAstParser::03-01-package--name-artifact==<org.webjars~bootstrap>`.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0004: `JavaAstParser::03-01-package--name-artifact==<org.webjars~jquery>`.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0004: `JavaAstParser::03-01-package--name-artifact==<org.webjars~momentjs>`.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0004: `JavaAstParser::03-01-package--name-artifact==<org.webjars~webjars-locator-core>`.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0004: `JavaAstParser::03-02-package--name-artifact-version==<com.mysql~mysql-connector-j==None>`.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0004: `JavaAstParser::03-02-package--name-artifact-version==<de.svenkubiak~jBCrypt==0.4.1>`.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0004: `JavaAstParser::03-02-package--name-artifact-version==<io.github.jpenren~thymeleaf-spring-data-dialect==3.2.0>`.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0004: `JavaAstParser::03-02-package--name-artifact-version==<jakarta.persistence~jakarta.persistence-api==None>`.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0004: `JavaAstParser::03-02-package--name-artifact-version==<org.apache.vysper.extensions~xep0045-muc==0.7>`.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0004: `JavaAstParser::03-02-package--name-artifact-version==<org.apache.vysper.extensions~xep0060-pubsub==0.7>`.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0004: `JavaAstParser::03-02-package--name-artifact-version==<org.apache.vysper~vysper-core==0.7>`.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0004: `JavaAstParser::03-02-package--name-artifact-version==<org.springframework.boot~spring-boot-starter-cache==None>`.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0004: `JavaAstParser::03-02-package--name-artifact-version==<org.springframework.boot~spring-boot-starter-data-jpa==None>`.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0004: `JavaAstParser::03-02-package--name-artifact-version==<org.springframework.boot~spring-boot-starter-security==None>`.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0004: `JavaAstParser::03-02-package--name-artifact-version==<org.springframework.boot~spring-boot-starter-test==None>`.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0004: `JavaAstParser::03-02-package--name-artifact-version==<org.springframework.boot~spring-boot-starter-thymeleaf==None>`.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0004: `JavaAstParser::03-02-package--name-artifact-version==<org.springframework.boot~spring-boot-starter-tomcat==None>`.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0004: `JavaAstParser::03-02-package--name-artifact-version==<org.springframework.boot~spring-boot-starter-validation==None>`.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0004: `JavaAstParser::03-02-package--name-artifact-version==<org.springframework.boot~spring-boot-starter-web==None>`.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0004: `JavaAstParser::03-02-package--name-artifact-version==<org.webjars~bootstrap==3.3.7-1>`.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0004: `JavaAstParser::03-02-package--name-artifact-version==<org.webjars~jquery==3.1.1>`.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0004: `JavaAstParser::03-02-package--name-artifact-version==<org.webjars~momentjs==2.15.0>`.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0004: `JavaAstParser::03-02-package--name-artifact-version==<org.webjars~webjars-locator-core==None>`.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0004: `JavaAstParser::04-finish`.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0004: `MavenBuilder::00-start`.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0004: `MavenBuilder::01-filter--dir-exists`.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0004: `MavenBuilder::02-build-errors--len=001`.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0004: `MavenBuilder::03-build-error--code=<None>`.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0002: `MavenBuilder::03-build-error--lines=001`.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0001: `MavenBuilder::03-build-error--lines=003`.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0001: `MavenBuilder::03-build-error--lines=005`.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0001: `MavenBuilder::04-build-error--line00=<<<cannot find symbol>>>`.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0001: `MavenBuilder::04-build-error--line00=<<<incompatible types: java.lang.Long cannot be converted to ua.tumakha.yuriy.xmpp.light.domain.User>>>`.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0001: `MavenBuilder::04-build-error--line00=<<<method does not override or implement a method from a supertype>>>`.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0001: `MavenBuilder::04-build-error--line00=<<<method findOne in interface org.springframework.data.repository.query.QueryByExampleExecutor<T> cannot be applied to given types;>>>`.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0001: `MavenBuilder::04-build-error--line01=<<<required: org.springframework.data.domain.Example<S>>>>`.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0001: `MavenBuilder::04-build-error--line01=<<<symbol:   method formLogin((login)->l[...]All())>>>`.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0001: `MavenBuilder::04-build-error--line02=<<<found:    java.lang.Long>>>`.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0001: `MavenBuilder::04-build-error--line02=<<<location: variable requests of type org.springframework.security.config.annotation.web.configurers.ExpressionUrlAuthorizationConfigurer<org.springframework.security.config.annotation.web.builders.HttpSecurity>.ExpressionInterceptUrlRegistry>>>`.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0001: `MavenBuilder::04-build-error--line03=<<<reason: cannot infer type-variable(s) S>>>`.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0001: `MavenBuilder::04-build-error--line04=<<<(argument mismatch; java.lang.Long cannot be converted to org.springframework.data.domain.Example<S>)>>>`.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0004: `MavenBuilder::05-build-error--file-suffix=<java>`.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0001: `MavenBuilder::05-build-error--file=<src/main/java/ua/tumakha/yuriy/xmpp/light/WebSecurityConfig.java>`.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0002: `MavenBuilder::05-build-error--file=<src/main/java/ua/tumakha/yuriy/xmpp/light/service/impl/UserServiceImpl.java>`.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0001: `MavenBuilder::05-build-error--file=<src/main/java/ua/tumakha/yuriy/xmpp/light/web/IndexController.java>`.
2024-04-27 07:35:07,034 [utils.py:53] INFO -   # = 0004: `MavenBuilder::06-finish`.
2024-04-27 07:35:08,030 [clientserver.py:543] INFO - Closing down clientserver connection
```
